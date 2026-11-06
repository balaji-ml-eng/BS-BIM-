"""Point clouds in BS BIM, like Revit's Insert > Point Cloud.

- The scan is converted by the separate bsbim_pointcloud program into a cache next to the project.
- The cache is drawn straight on the GPU with its real colours (fast for millions of points).
- Positioning: Auto - Origin to Origin (Revit's default): scan coordinates = project coordinates.
- The link is stored in the IFC as a document reference on the project, so it comes back on reopen.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.io_utils import ImportHelper

from . import prefs

LINK_TAG = "BSBIM:PointCloud"

# name -> {"batch": GPUBatch, "visible": bool, "info": dict, "source": str, "cache": str}
_clouds: dict[str, dict] = {}
_draw_handle = None
_loaded_for: dict = {"file": None}


def _tool():
    import bonsai.tool as tool
    return tool


# ------------------------------------------------------------------ drawing
def _make_batch(xyz: np.ndarray, rgb: np.ndarray | None):
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader = gpu.shader.from_builtin("FLAT_COLOR")
    if rgb is None:
        colors = np.tile(np.array([[0.45, 0.45, 0.50, 1.0]], np.float32), (len(xyz), 1))
    else:
        colors = np.empty((len(xyz), 4), np.float32)
        colors[:, :3] = rgb.astype(np.float32) / 255.0
        colors[:, 3] = 1.0
    return batch_for_shader(shader, "POINTS", {"pos": xyz.astype(np.float32), "color": colors}), shader


def _draw():
    if not _clouds:
        return
    import gpu
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.point_size_set(2.0)
    for cloud in _clouds.values():
        if cloud["visible"]:
            cloud["batch"].draw(cloud["shader"])
    gpu.state.point_size_set(1.0)
    gpu.state.depth_test_set("NONE")


def _ensure_draw_handler():
    global _draw_handle
    if _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")


def _redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def show_cache(name: str, cache: Path, source: str) -> dict:
    """Load a converted cache into the viewport. Returns its info."""
    from .bsbim_pointcloud.convert import load  # vendored by tools/build_extension.py
    xyz, rgb, info = load(cache)
    batch, shader = _make_batch(xyz, rgb)
    _clouds[name] = {"batch": batch, "shader": shader, "visible": True, "info": info,
                     "source": source, "cache": str(cache), "count": len(xyz)}
    _ensure_draw_handler()
    _redraw()
    return info


# ------------------------------------------------------------------ converter process
def _cache_dir() -> Path:
    tool = _tool()
    ifc_path = tool.Ifc.get_path() or ""
    base = Path(ifc_path).parent if ifc_path else Path(bpy.app.tempdir or ".")
    stem = Path(ifc_path).stem if ifc_path else "unsaved"
    return base / f"{stem}_pointclouds"


def run_converter(source: Path, cache: Path, max_points: int, units: str) -> dict:
    p = prefs.get()
    python = p.bridge_python
    if not python or not Path(python).is_file():
        raise RuntimeError("Set 'Bridge Python' in BS BIM preferences (it also runs the point cloud converter)")
    env = dict(os.environ)
    if p.bridge_src:
        env["PYTHONPATH"] = p.bridge_src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    for var in ("PYTHONHOME", "PYTHONNOUSERSITE"):
        env.pop(var, None)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.run([python, "-m", "bsbim_pointcloud", "convert", str(source), str(cache),
                           "--max-points", str(max_points), "--units", units, "--json"],
                          capture_output=True, text=True, env=env, creationflags=flags, timeout=3600)
    last = (proc.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        data = json.loads(last)
    except ValueError:
        data = {"error": (proc.stderr.strip().splitlines() or ["converter failed"])[-1]}
    if proc.returncode != 0 or "error" in data:
        raise RuntimeError(data.get("error", "converter failed"))
    return data


# ------------------------------------------------------------------ IFC link
def _store_link(name: str, source: str, cache: str, units: str, max_points: int):
    import ifcopenshell.api
    f = _tool().Ifc.get()
    project = f.by_type("IfcProject")[0]
    info = ifcopenshell.api.run("document.add_information", f)
    info.Name = name
    info.Description = LINK_TAG
    info.Location = source
    ref = ifcopenshell.api.run("document.add_reference", f, information=info)
    ref.Location = source
    ref.Name = name
    ref.Description = json.dumps({"tag": LINK_TAG, "cache": cache, "units": units, "max_points": max_points})
    ifcopenshell.api.run("document.assign_document", f, products=[project], document=ref)


def stored_links() -> list[dict]:
    f = _tool().Ifc.get()
    if f is None:
        return []
    links = []
    for ref in f.by_type("IfcDocumentReference"):
        try:
            meta = json.loads(ref.Description or "")
        except ValueError:
            continue
        if isinstance(meta, dict) and meta.get("tag") == LINK_TAG:
            links.append({"name": ref.Name, "source": ref.Location, **meta, "ref": ref})
    return links


def reload_links():
    """Show the point clouds stored in the open project (after opening it)."""
    _clouds.clear()
    for link in stored_links():
        cache = Path(link["cache"])
        try:
            if not cache.is_file():
                run_converter(Path(link["source"]), cache, int(link.get("max_points", 3_000_000)), link.get("units", "m"))
            show_cache(link["name"], cache, link["source"])
        except Exception as e:  # a missing scan must not stop the project from opening
            print(f"BS BIM: point cloud {link['name']!r} not loaded: {e}")
    _redraw()


def watch_project_change():
    """Called by the add-on's watcher: reload links when another project is opened."""
    f = _tool().Ifc.get() if _tool_available() else None
    key = id(f) if f is not None else None
    if key != _loaded_for["file"]:
        _loaded_for["file"] = key
        if f is None:
            _clouds.clear()
            _redraw()
        else:
            reload_links()


def _tool_available() -> bool:
    try:
        import bonsai.tool  # noqa: F401
        return True
    except ImportError:
        return False


# ------------------------------------------------------------------ operators
class BSBIM_OT_link_point_cloud(bpy.types.Operator, ImportHelper):
    """Point Cloud: link a laser scan (E57, LAS, LAZ, PLY, PTS, XYZ), positioned origin to origin"""

    bl_idname = "bsbim.link_point_cloud"
    bl_label = "Point Cloud"
    bl_options = {"REGISTER"}

    filter_glob: bpy.props.StringProperty(default="*.e57;*.las;*.laz;*.ply;*.pts;*.xyz;*.txt;*.rcp;*.rcs",
                                          options={"HIDDEN"})
    positioning: bpy.props.EnumProperty(name="Positioning", items=[
        ("ORIGIN", "Auto - Origin to Origin", "Scan coordinates are project coordinates")])
    units: bpy.props.EnumProperty(name="Scan units", default="m", items=[
        ("m", "Metres", ""), ("ft", "Feet", ""), ("usft", "US survey feet", ""), ("mm", "Millimetres", "")])
    max_points: bpy.props.IntProperty(name="Max points shown", default=3_000_000, min=10_000, max=50_000_000)

    @classmethod
    def poll(cls, context):
        return _tool().Ifc.get() is not None

    def execute(self, context):
        source = Path(self.filepath)
        name = source.stem
        if name in _clouds:
            self.report({"ERROR"}, f"A point cloud named {name!r} is already linked")
            return {"CANCELLED"}
        cache = _cache_dir() / f"{name}.npz"
        context.window.cursor_set("WAIT")
        try:
            info = run_converter(source, cache, self.max_points, self.units)
            show_cache(name, cache, str(source))
            _store_link(name, str(source), str(cache), self.units, self.max_points)
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        finally:
            context.window.cursor_set("DEFAULT")
        self.report({"INFO"}, f"Linked {name}: {info['points_kept']:,} of {info['points_in_file']:,} points")
        return {"FINISHED"}


class BSBIM_OT_point_cloud_visibility(bpy.types.Operator):
    """Show or hide this point cloud"""

    bl_idname = "bsbim.point_cloud_visibility"
    bl_label = "Show / Hide Point Cloud"
    name: bpy.props.StringProperty()

    def execute(self, context):
        if self.name in _clouds:
            _clouds[self.name]["visible"] = not _clouds[self.name]["visible"]
            _redraw()
        return {"FINISHED"}


class BSBIM_OT_unlink_point_cloud(bpy.types.Operator):
    """Remove this point cloud link (the scan file itself is not touched)"""

    bl_idname = "bsbim.unlink_point_cloud"
    bl_label = "Remove Point Cloud Link"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        import ifcopenshell.api
        _clouds.pop(self.name, None)
        f = _tool().Ifc.get()
        for link in stored_links():
            if link["name"] == self.name:
                info = link["ref"].ReferencedDocument
                ifcopenshell.api.run("document.remove_reference", f, reference=link["ref"])
                if info is not None:
                    ifcopenshell.api.run("document.remove_information", f, information=info)
        _redraw()
        return {"FINISHED"}


def draw_browser_section(layout):
    """'Point Clouds' group for the Project Browser."""
    if not _clouds:
        return
    layout.label(text="Point Clouds", icon="OUTLINER_OB_POINTCLOUD")
    for name, cloud in _clouds.items():
        row = layout.row(align=True)
        row.label(text="", icon="BLANK1")
        row.operator("bsbim.point_cloud_visibility", text="", emboss=False,
                     icon="HIDE_OFF" if cloud["visible"] else "HIDE_ON").name = name
        row.label(text=f"{name}  ({cloud['count']:,} pts)")
        row.operator("bsbim.unlink_point_cloud", text="", emboss=False, icon="X").name = name


classes = (BSBIM_OT_link_point_cloud, BSBIM_OT_point_cloud_visibility, BSBIM_OT_unlink_point_cloud)


def unregister():
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None
    _clouds.clear()
