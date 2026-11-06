from __future__ import annotations

import time
from pathlib import Path

import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import bridge_client, prefs
from .naksha_core import project as core_project
from .naksha_core import report as core_report

# Lines of the last model report, drawn by the panel.
last_report: list[str] = []


def bonsai_ready() -> bool:
    return any(name.endswith("bonsai") for name in bpy.context.preferences.addons.keys())


def _need_bonsai(op: bpy.types.Operator) -> bool:
    if bonsai_ready():
        return True
    op.report({"ERROR"}, "Bonsai is not enabled. Install it from Edit > Preferences > Get Extensions")
    return False


def _load_ifc(path: Path) -> None:
    bpy.ops.bim.load_project(filepath=str(path))


def _set_report(lines: list[str]) -> None:
    last_report[:] = lines
    for area in getattr(bpy.context.screen, "areas", []):
        area.tag_redraw()


class NAKSHA_OT_new_project(bpy.types.Operator, ExportHelper):
    """Create a new project from the Naksha company template and open it"""

    bl_idname = "naksha.new_project"
    bl_label = "New Naksha Project"
    bl_options = {"REGISTER"}

    filename_ext = ".ifc"
    filter_glob: bpy.props.StringProperty(default="*.ifc", options={"HIDDEN"})
    project_name: bpy.props.StringProperty(name="Project name", default="New Project")
    floors: bpy.props.IntProperty(name="Floors", description="Floors including ground", default=2, min=1, max=200)
    floor_height: bpy.props.FloatProperty(name="Floor height (mm)", default=3000.0, min=1000.0, max=20000.0)
    include_types: bpy.props.BoolProperty(name="Add template wall/slab types", default=True)

    def execute(self, context):
        if not _need_bonsai(self):
            return {"CANCELLED"}
        try:
            settings = core_project.ProjectSettings.with_floors(self.project_name, self.floors, self.floor_height)
            settings.include_types = self.include_types
            path = core_project.save(core_project.create_project(settings), self.filepath)
        except (ValueError, OSError) as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        _load_ifc(path)
        self.report({"INFO"}, f"Created {path.name}")
        return {"FINISHED"}


class NAKSHA_OT_import_rvt(bpy.types.Operator, ImportHelper):
    """Convert a Revit file to IFC with the Naksha RVT Bridge and open it"""

    bl_idname = "naksha.import_rvt"
    bl_label = "Open Revit File"
    bl_options = {"REGISTER"}

    filter_glob: bpy.props.StringProperty(default="*.rvt;*.rfa;*.rte;*.rft", options={"HIDDEN"})

    _job: bridge_client.BridgeJob | None = None
    _timer = None
    _started = 0.0

    def execute(self, context):
        if not _need_bonsai(self):
            return {"CANCELLED"}
        p = prefs.get(context)
        try:
            self._job = bridge_client.start(p.bridge_python, p.bridge_src, Path(self.filepath), p.output_folder)
        except (bridge_client.BridgeError, OSError) as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        self._started = time.monotonic()
        if bpy.app.background:  # no event loop: wait here
            return self._finish(context)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        if not self._job.finished():
            context.workspace.status_text_set(
                f"Naksha: converting {self._job.source.name}... {time.monotonic() - self._started:.0f}s")
            return {"PASS_THROUGH"}
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        return self._finish(context)

    def _finish(self, context):
        try:
            data = self._job.result()
        except (bridge_client.BridgeError, ValueError) as e:
            self.report({"ERROR"}, f"RVT conversion failed: {e}")
            _set_report([f"RVT conversion failed: {e}"])
            return {"CANCELLED"}
        r = data.get("report") or {}
        version = (data.get("revit_info") or {}).get("revit_version", "?")
        _set_report([
            f"From: {self._job.source.name} (Revit {version})",
            f"Reader: {data['backend']}, mode {data['mode_used']}, {data['seconds']}s",
            f"Elements: {r.get('total_elements', 0)}   Score: {r.get('score', 0)} / 100",
            *[f"Warning: {w}" for w in data.get("warnings", [])[:5]],
        ])
        _load_ifc(Path(data["ifc"]))
        self.report({"INFO"}, f"Opened {Path(data['ifc']).name}  (quality {r.get('score', 0)}/100)")
        return {"FINISHED"}


class NAKSHA_OT_model_report(bpy.types.Operator):
    """Check how complete the BIM data in the open project is"""

    bl_idname = "naksha.model_report"
    bl_label = "Model Quality Report"

    def execute(self, context):
        if not _need_bonsai(self):
            return {"CANCELLED"}
        import bonsai.tool as tool  # imported late: only available when Bonsai is enabled

        f = tool.Ifc.get()
        if f is None:
            self.report({"ERROR"}, "No IFC project is open")
            return {"CANCELLED"}
        r = core_report.build_report(f)
        text = core_report.format_report(r)
        _set_report(text.splitlines())
        print(text)
        self.report({"INFO"}, f"{r.total_elements} elements, quality score {r.score} / 100")
        return {"FINISHED"}


class NAKSHA_OT_clear_report(bpy.types.Operator):
    bl_idname = "naksha.clear_report"
    bl_label = "Clear Report"

    def execute(self, context):
        _set_report([])
        return {"FINISHED"}


classes = (NAKSHA_OT_new_project, NAKSHA_OT_import_rvt, NAKSHA_OT_model_report, NAKSHA_OT_clear_report)
