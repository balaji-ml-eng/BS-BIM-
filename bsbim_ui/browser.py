"""Project Browser, laid out like Revit's: Views (all) > Structural Plans / 3D Views, Families.

Opening a structural plan shows the model from the top, limited to a Revit-like view range around
the level: from 2'-0" below the level (so beams under the level show) up to the 4'-0" cut plane.
"""

from __future__ import annotations

from collections import defaultdict
from math import radians

import bpy
from mathutils import Euler

from . import revit_ui, structure

# Groups the user has collapsed (Revit remembers this per session)
_collapsed: set[str] = {"Families"}

PLAN_BELOW_M = {"imperial": 2 * 0.3048, "metric": 0.6}
PLAN_CUT_M = {"imperial": 4 * 0.3048, "metric": 1.2}


def _tool():
    import bonsai.tool as tool
    return tool


def _element_objects():
    """Blender objects that show physical IFC elements (not levels, grids or types)."""
    tool = _tool()
    for obj in bpy.context.view_layer.objects:
        e = tool.Ifc.get_entity(obj)
        if e is not None and e.is_a("IfcElement") and obj.type == "MESH":
            yield obj


def _z_range(obj):
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices] or [obj.matrix_world.translation.z]
    return min(zs), max(zs)


def _view3d_areas(context):
    screen = context.screen or (context.window.screen if context.window else None)
    if screen is None:
        screen = bpy.context.window_manager.windows[0].screen
    for area in screen.areas:
        if area.type == "VIEW_3D":
            yield area


def _frame_all(context, area, region):
    window = context.window or bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region):
        bpy.ops.view3d.view_all(center=False)


def open_plan(context, level) -> int:
    """Show the structural plan of ``level``. Returns how many elements are visible."""
    from .tools import unit_system
    system = unit_system()
    z = structure.level_z(level)
    low, high = z - PLAN_BELOW_M[system], z + PLAN_CUT_M[system]
    shown = 0
    for obj in _element_objects():
        zmin, zmax = _z_range(obj)
        visible = zmax >= low - 1e-6 and zmin <= high + 1e-6
        obj.hide_set(not visible)
        shown += visible
    wm = context.window_manager
    wm.bsbim_active_level = level.Name
    wm.bsbim_active_view = f"PLAN:{level.Name}"
    for area in _view3d_areas(context):
        region = next(r for r in area.regions if r.type == "WINDOW")
        rv3d = area.spaces.active.region_3d
        rv3d.view_rotation = Euler((0, 0, 0)).to_quaternion()  # looking straight down
        rv3d.view_perspective = "ORTHO"
        _frame_all(context, area, region)
    return shown


def open_3d(context) -> int:
    shown = 0
    for obj in _element_objects():
        obj.hide_set(False)
        shown += 1
    context.window_manager.bsbim_active_view = "3D"
    for area in _view3d_areas(context):
        region = next(r for r in area.regions if r.type == "WINDOW")
        rv3d = area.spaces.active.region_3d
        # Revit's default {3D} view: isometric from the south-east, orthographic
        rv3d.view_rotation = Euler((radians(54.7356), 0, radians(45))).to_quaternion()
        rv3d.view_perspective = "ORTHO"
        _frame_all(context, area, region)
    return shown


class BSBIM_OT_open_view(bpy.types.Operator):
    """Open this view"""

    bl_idname = "bsbim.open_view"
    bl_label = "Open View"
    kind: bpy.props.EnumProperty(items=[("PLAN", "Plan", ""), ("3D", "3D", "")])
    level: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return _tool().Ifc.get() is not None

    def execute(self, context):
        try:
            if self.kind == "PLAN":
                open_plan(context, structure.level_named(self.level))
            else:
                open_3d(context)
        except (ValueError, RuntimeError) as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        return {"FINISHED"}


class BSBIM_OT_toggle_browser_group(bpy.types.Operator):
    bl_idname = "bsbim.toggle_browser_group"
    bl_label = "Expand / Collapse"
    group: bpy.props.StringProperty()

    def execute(self, context):
        _collapsed.symmetric_difference_update({self.group})
        return {"FINISHED"}


def _group(layout, key: str, label: str, depth: int):
    row = layout.row(align=True)
    for _ in range(depth):
        row.label(text="", icon="BLANK1")
    open_ = key not in _collapsed
    row.operator("bsbim.toggle_browser_group", text=label, emboss=False,
                 icon="DOWNARROW_HLT" if open_ else "RIGHTARROW").group = key
    return open_


def _item(layout, depth: int):
    row = layout.row(align=True)
    for _ in range(depth):
        row.label(text="", icon="BLANK1")
    return row


class BSBIM_PT_project_browser(bpy.types.Panel):
    bl_label = "Project Browser"
    bl_idname = "BSBIM_PT_project_browser"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BS BIM"
    bl_order = 2

    @classmethod
    def poll(cls, context):
        return revit_ui.revit_mode(context)

    def draw(self, context):
        layout = self.layout.column(align=True)
        f = _tool().Ifc.get()
        if f is None:
            layout.label(text="No project open")
            layout.operator("bsbim.new_project", icon="FILE_NEW")
            layout.operator("bim.load_project", text="Open...", icon="FILE_FOLDER")
            return
        active = context.window_manager.bsbim_active_view
        if _group(layout, "Views", "Views (all)", 0):
            if _group(layout, "Plans", "Structural Plans", 1):
                for level in structure.levels():
                    op = _item(layout, 2).operator("bsbim.open_view", text=level.Name, icon="VIEW_ORTHO",
                                                   depress=active == f"PLAN:{level.Name}")
                    op.kind, op.level = "PLAN", level.Name
            if _group(layout, "3D", "3D Views", 1):
                _item(layout, 2).operator("bsbim.open_view", text="{3D}", icon="VIEW3D",
                                          depress=active == "3D").kind = "3D"
            for label in ("Elevations (Building Elevation)", "Sections (Building Section)"):
                row = _item(layout, 1)
                row.enabled = False
                row.label(text=label, icon="RIGHTARROW")
        for label in ("Schedules/Quantities (all)", "Sheets (all)"):
            row = _item(layout, 0)
            row.enabled = False
            row.label(text=label, icon="RIGHTARROW")
        if _group(layout, "Families", "Families", 0):
            by_cat: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
            for t in f.by_type("IfcElementType"):
                cat = revit_ui.CATEGORY.get(t.is_a()[:-4], t.is_a()[3:-4])
                by_cat[cat][t.ElementType or "(no family)"].append(t.Name or "")
            for cat in sorted(by_cat):
                if _group(layout, f"cat:{cat}", cat, 1):
                    for fam in sorted(by_cat[cat]):
                        if _group(layout, f"fam:{cat}:{fam}", fam, 2):
                            for name in sorted(by_cat[cat][fam]):
                                _item(layout, 3).label(text=name)


classes = (BSBIM_OT_open_view, BSBIM_OT_toggle_browser_group, BSBIM_PT_project_browser)
