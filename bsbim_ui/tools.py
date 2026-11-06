"""Revit-style interactive structural tools: Column (CL), Beam (BM), Brace, Level, Grid.

Clicks are projected onto the active level. Points snap to grid intersections and to existing
column centres within a few pixels, like Revit's snapping. Esc or right-click ends the tool.
"""

from __future__ import annotations

import math

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

from . import state, structure
from .bsbim_core import project as core_project
from .bsbim_core import units as core_units

SNAP_PIXELS = 14


def _tool():
    import bonsai.tool as tool
    return tool


# ------------------------------------------------------------------ helpers
def project_units_per_metre() -> float:
    import ifcopenshell.util.unit
    return 1.0 / ifcopenshell.util.unit.calculate_unit_scale(structure.ifc_file())


def unit_system() -> str:
    return core_project.unit_system(structure.ifc_file())


def fmt_m(metres: float) -> str:
    """Format a Blender length (metres) the Revit way in project units."""
    return core_units.format_length(metres * project_units_per_metre(), unit_system())


def parse_to_m(text: str) -> float:
    return core_units.parse_length(text, unit_system()) / project_units_per_metre()


def snap_points() -> list[Vector]:
    """XY points to snap to: grid intersections and column centres."""
    tool = _tool()
    f = structure.ifc_file()
    pts: list[Vector] = []
    lines = []
    for axis in f.by_type("IfcGridAxis"):
        obj = tool.Ifc.get_object(axis)
        if obj and obj.type == "MESH" and len(obj.data.vertices) >= 2:
            a = obj.matrix_world @ obj.data.vertices[0].co
            b = obj.matrix_world @ obj.data.vertices[-1].co
            lines.append((a.to_2d(), b.to_2d()))
    for i, (a1, a2) in enumerate(lines):
        for b1, b2 in lines[i + 1:]:
            d1, d2 = a2 - a1, b2 - b1
            den = d1.x * d2.y - d1.y * d2.x
            if abs(den) < 1e-9:
                continue
            t = ((b1.x - a1.x) * d2.y - (b1.y - a1.y) * d2.x) / den
            pts.append((a1 + d1 * t).to_3d())
    for col in f.by_type("IfcColumn"):
        obj = tool.Ifc.get_object(col)
        if obj:
            pts.append(Vector((obj.matrix_world.translation.x, obj.matrix_world.translation.y, 0)))
    return pts


def mouse_on_level(context, event, z: float) -> tuple[Vector | None, bool]:
    """3D point under the mouse on the plane at height z, snapped if close to a snap point."""
    region, rv3d = context.region, context.region_data
    coord = (event.mouse_region_x, event.mouse_region_y)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    if abs(direction.z) < 1e-9:
        return None, False
    t = (z - origin.z) / direction.z
    point = origin + direction * t
    best, best_d = None, SNAP_PIXELS
    for p in snap_points():
        p3 = Vector((p.x, p.y, z))
        screen = view3d_utils.location_3d_to_region_2d(region, rv3d, p3)
        if screen is None:
            continue
        d = math.dist(screen, coord)
        if d < best_d:
            best, best_d = p3, d
    return (best, True) if best is not None else (point, False)


def _status(context, text: str | None):
    if context.workspace:
        context.workspace.status_text_set(text)
    if context.area:
        context.area.header_text_set(None)


def _pick_type(ifc_class: str, preferred_id: int):
    f = structure.ifc_file()
    if preferred_id:
        try:
            t = f.by_id(preferred_id)
            if t.is_a(ifc_class):
                return t
        except RuntimeError:
            pass
    types = sorted(f.by_type(ifc_class), key=lambda t: ((t.ElementType or ""), t.Name or ""))
    import ifcopenshell.util.element as E
    types = [t for t in types if (m := E.get_material(t)) and m.is_a("IfcMaterialProfileSet")]
    # Revit's US structural default is a wide-flange shape; prefer W shapes, then steel, then the rest
    def rank(t):
        family = t.ElementType or ""
        return (0 if family.startswith("W Shapes") else 1 if "HSS" in family else 2)
    types.sort(key=rank)
    return types[0] if types else None


# ------------------------------------------------------------------ Column
class BSBIM_OT_place_column(bpy.types.Operator):
    """Structural Column (CL): click to place. Depth from the level below, like Revit"""

    bl_idname = "bsbim.place_column"
    bl_label = "Structural Column"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _tool().Ifc.get() is not None and context.area and context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        wm = context.window_manager
        self.column_type = _pick_type("IfcColumnType", wm.bsbim_new_column_type)
        if self.column_type is None:
            self.report({"ERROR"}, "Load a structural column type first")
            return {"CANCELLED"}
        wm.bsbim_new_column_type = self.column_type.id()
        self.level = state.active_level()
        self.z = structure.level_z(self.level)
        self.placed = 0
        context.window.cursor_modal_set("CROSSHAIR")
        self._update_status(context)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _update_status(self, context):
        _status(context, f"Structural Column {self.column_type.ElementType} : {self.column_type.Name} on "
                         f"{self.level.Name} (Depth). Click to place. Esc to finish. Placed: {self.placed}")

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return self._finish(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            point, _snapped = mouse_on_level(context, event, self.z)
            if point is None:
                return {"RUNNING_MODAL"}
            try:
                structure.place_column(self.column_type, point.x, point.y, self.level)
                self.placed += 1
            except (ValueError, RuntimeError) as e:
                self.report({"ERROR"}, str(e))
                return self._finish(context)
            self._update_status(context)
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}  # let the user pan / zoom / orbit while placing

    def _finish(self, context):
        context.window.cursor_modal_restore()
        _status(context, None)
        return {"FINISHED"}


# ------------------------------------------------------------------ Beam / Brace
_draw_handle = None
_preview: dict = {}


def _draw_preview():
    if not _preview.get("start") or not _preview.get("end"):
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": [_preview["start"], _preview["end"]]})
    gpu.state.line_width_set(2.0)
    shader.uniform_float("color", (0.1, 0.55, 1.0, 1.0))
    batch.draw(shader)
    gpu.state.line_width_set(1.0)


class BSBIM_OT_place_beam(bpy.types.Operator):
    """Beam (BM): click the start point, then the end point. Top of beam at the level, like Revit"""

    bl_idname = "bsbim.place_beam"
    bl_label = "Beam"
    bl_options = {"REGISTER", "UNDO"}

    brace: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _tool().Ifc.get() is not None and context.area and context.area.type == "VIEW_3D"

    def invoke(self, context, event):
        global _draw_handle
        wm = context.window_manager
        ifc_class = "IfcMemberType" if self.brace else "IfcBeamType"
        preferred = wm.bsbim_new_brace_type if self.brace else wm.bsbim_new_beam_type
        self.beam_type = _pick_type(ifc_class, preferred)
        if self.beam_type is None:
            self.report({"ERROR"}, f"Load a {'brace' if self.brace else 'beam'} type first")
            return {"CANCELLED"}
        if self.brace:
            wm.bsbim_new_brace_type = self.beam_type.id()
        else:
            wm.bsbim_new_beam_type = self.beam_type.id()
        self.level = state.active_level()
        self.z = structure.level_z(self.level)
        self.start = None
        self.placed = 0
        _preview.clear()
        if _draw_handle is None:
            _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_preview, (), "WINDOW", "POST_VIEW")
        context.window.cursor_modal_set("CROSSHAIR")
        self._update_status(context)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _update_status(self, context):
        what = "Brace" if self.brace else "Beam"
        step = "Click end point" if self.start else "Click start point"
        _status(context, f"{what} {self.beam_type.ElementType} : {self.beam_type.Name} on {self.level.Name}. "
                         f"{step}. Esc to finish. Placed: {self.placed}")

    def modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            if self.start is not None:  # first Esc cancels the current beam, like Revit
                self.start = None
                _preview.clear()
                self._update_status(context)
                context.area.tag_redraw()
                return {"RUNNING_MODAL"}
            return self._finish(context)
        if event.type == "MOUSEMOVE" and self.start is not None:
            point, _ = mouse_on_level(context, event, self.z)
            if point is not None:
                _preview["end"] = point
                context.area.tag_redraw()
            return {"PASS_THROUGH"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            point, _ = mouse_on_level(context, event, self.z)
            if point is None:
                return {"RUNNING_MODAL"}
            if self.start is None:
                self.start = point
                _preview.update(start=point, end=point)
            else:
                try:
                    structure.place_beam(self.beam_type, self.start.to_2d(), point.to_2d(), self.level)
                    self.placed += 1
                except (ValueError, RuntimeError) as e:
                    self.report({"WARNING"}, str(e))
                self.start = None
                _preview.clear()
            self._update_status(context)
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def _finish(self, context):
        global _draw_handle
        if _draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
            _draw_handle = None
        _preview.clear()
        context.window.cursor_modal_restore()
        _status(context, None)
        context.area.tag_redraw()
        return {"FINISHED"}


# ------------------------------------------------------------------ Level
class BSBIM_OT_add_level(bpy.types.Operator):
    """Level (LL): add a level at an elevation"""

    bl_idname = "bsbim.add_level"
    bl_label = "Level"
    bl_options = {"REGISTER", "UNDO"}

    level_name: bpy.props.StringProperty(name="Name")
    elevation: bpy.props.StringProperty(name="Elevation", description="For example 20' or 20' 6\" or 8000")

    @classmethod
    def poll(cls, context):
        return _tool().Ifc.get() is not None

    def invoke(self, context, event):
        levels = structure.levels()
        top = levels[-1] if levels else None
        self.level_name = f"Level {len(levels) + 1}"
        step = 10.0 if unit_system() == "imperial" else 4000.0  # project units
        top_elev = (top.Elevation or 0.0) if top else 0.0
        self.elevation = core_units.format_length(top_elev + step, unit_system())
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            elevation_m = parse_to_m(self.elevation)
            add_level(self.level_name.strip(), elevation_m)
        except (ValueError, RuntimeError) as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Added {self.level_name} at {self.elevation}")
        return {"FINISHED"}


def add_level(name: str, elevation_m: float):
    """Create a level through Bonsai so it appears in the scene. Returns the IfcBuildingStorey."""
    import bonsai.core.aggregate
    import bonsai.core.geometry
    import bonsai.core.root
    tool = _tool()
    f = structure.ifc_file()
    if not name:
        raise ValueError("A level needs a name")
    if any(s.Name == name for s in f.by_type("IfcBuildingStorey")):
        raise ValueError(f"A level named {name!r} already exists")
    building = f.by_type("IfcBuilding")[0]
    obj = bpy.data.objects.new(name, None)
    bonsai.core.root.assign_class(tool.Ifc, tool.Collector, tool.Root, obj=obj,
                                  ifc_class="IfcBuildingStorey", should_add_representation=False)
    storey = tool.Ifc.get_entity(obj)
    storey.Name = name
    bonsai.core.aggregate.assign_object(tool.Ifc, tool.Aggregate, tool.Collector,
                                        relating_obj=tool.Ifc.get_object(building), related_obj=obj)
    base_z = structure.level_z(structure.levels()[0]) - (structure.levels()[0].Elevation or 0.0) / project_units_per_metre()
    obj.matrix_world.translation.z = base_z + elevation_m
    bpy.context.view_layer.update()
    bonsai.core.geometry.edit_object_placement(tool.Ifc, tool.Geometry, tool.Surveyor, obj=obj)
    storey.Elevation = elevation_m * project_units_per_metre()
    return storey


# ------------------------------------------------------------------ Grid
class BSBIM_OT_add_grid(bpy.types.Operator):
    """Grid (GR): add a rectangular grid, numbered 1, 2, 3... and lettered A, B, C... like Revit"""

    bl_idname = "bsbim.add_grid"
    bl_label = "Grid"
    bl_options = {"REGISTER", "UNDO"}

    numbered: bpy.props.IntProperty(name="Numbered lines (1, 2, 3...)", default=4, min=1, max=60)
    numbered_spacing: bpy.props.StringProperty(name="Spacing")
    lettered: bpy.props.IntProperty(name="Lettered lines (A, B, C...)", default=3, min=1, max=26)
    lettered_spacing: bpy.props.StringProperty(name="Spacing")

    @classmethod
    def poll(cls, context):
        return _tool().Ifc.get() is not None

    def invoke(self, context, event):
        default = "20'" if unit_system() == "imperial" else "6000"
        self.numbered_spacing = self.numbered_spacing or default
        self.lettered_spacing = self.lettered_spacing or default
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            add_grid(self.numbered, parse_to_m(self.numbered_spacing), self.lettered, parse_to_m(self.lettered_spacing))
        except (ValueError, RuntimeError) as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        return {"FINISHED"}


def add_grid(numbered: int, numbered_spacing_m: float, lettered: int, lettered_spacing_m: float):
    """Create the grid with Bonsai, then label it the Revit way: vertical lines 1, 2, 3; horizontal A, B, C."""
    tool = _tool()
    f = structure.ifc_file()
    before = set(f.by_type("IfcGridAxis"))
    # Bonsai: U axes run along X (horizontal lines, spaced in Y), V axes run along Y (vertical lines).
    res = bpy.ops.bim.add_grid(u_spacing=lettered_spacing_m, total_u=lettered,
                               v_spacing=numbered_spacing_m, total_v=numbered)
    if res != {"FINISHED"}:
        raise RuntimeError("Bonsai could not create the grid")
    new_axes = [a for a in f.by_type("IfcGridAxis") if a not in before]
    grid = next(g for g in f.by_type("IfcGrid") if set(g.UAxes or []) | set(g.VAxes or []) >= set(new_axes))
    # Bonsai lists U from A upward; Revit letters A at the bottom too. Number V axes 1, 2, 3 left to right.
    for i, axis in enumerate(grid.VAxes):
        axis.AxisTag = str(i + 1)
    for i, axis in enumerate(grid.UAxes):
        axis.AxisTag = chr(ord("A") + i)
    for axis in new_axes:
        obj = tool.Ifc.get_object(axis)
        if obj:
            obj.name = f"IfcGridAxis/{axis.AxisTag}"
    try:
        tool.Root.reload_grid_decorator()
    except Exception:
        pass
    return grid


classes = (BSBIM_OT_place_column, BSBIM_OT_place_beam, BSBIM_OT_add_level, BSBIM_OT_add_grid)


def unregister_draw_handler():
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None
