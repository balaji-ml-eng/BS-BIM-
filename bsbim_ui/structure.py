"""Revit-style structural placement on top of Bonsai's parametric profile engine.

Revit behaviour reproduced here:
- Structural Column: click a point. Default placement is **Depth**: the column runs from the
  level below up to the current level. On the lowest level it runs **Height**: up to the level above.
- Beam: click start and end. The beam sits on the current level with z-Justification **Top**,
  so the top of steel is at the level.

All coordinates are Blender scene coordinates in metres.
"""

from __future__ import annotations

from typing import Literal

import bpy

CARDINAL_TOP_CENTRE = "8"
CARDINAL_MID_CENTRE = "5"


def _tool():
    import bonsai.tool as tool  # only importable when Bonsai is enabled
    return tool


def _generator():
    from bonsai.bim.module.model.profile import DumbProfileGenerator
    return DumbProfileGenerator


def ifc_file():
    f = _tool().Ifc.get()
    if f is None:
        raise RuntimeError("No project is open")
    return f


def levels() -> list:
    """Building storeys sorted by height."""
    return sorted(ifc_file().by_type("IfcBuildingStorey"), key=level_z)


def level_z(storey) -> float:
    """Height of a level in the Blender scene (metres), including any Bonsai model offset."""
    obj = _tool().Ifc.get_object(storey)
    if obj is None:
        raise RuntimeError(f"Level {storey.Name!r} has no object in the scene")
    return obj.matrix_world.translation.z


def level_named(name: str):
    for s in ifc_file().by_type("IfcBuildingStorey"):
        if s.Name == name:
            return s
    raise ValueError(f"No level named {name!r}")


def _neighbour(storey, step: int):
    ordered = levels()
    i = ordered.index(storey) + step
    return ordered[i] if 0 <= i < len(ordered) else None


def level_above(storey):
    return _neighbour(storey, 1)


def level_below(storey):
    return _neighbour(storey, -1)


def _set_default_level(storey) -> None:
    _tool().Spatial.get_spatial_props().default_container = storey.id()


def _check_type(element_type, allowed: tuple[str, ...]):
    if element_type is None or not element_type.is_a() in allowed:
        raise ValueError(f"Choose a {' or '.join(a[3:-4] for a in allowed)} type")
    import ifcopenshell.util.element
    material = ifcopenshell.util.element.get_material(element_type)
    if not (material and material.is_a("IfcMaterialProfileSet")):
        raise ValueError(f"Type {element_type.Name!r} has no profile, so it cannot be placed")


def column_extent(level, mode: Literal["DEPTH", "HEIGHT", "AUTO"] = "AUTO"):
    """(base_level, top_level) for a column placed on ``level``, following Revit's Depth/Height option."""
    if mode == "AUTO":
        mode = "DEPTH" if level_below(level) is not None else "HEIGHT"
    if mode == "DEPTH":
        below = level_below(level)
        if below is None:
            raise ValueError(f"There is no level below {level.Name!r}. Use Height instead.")
        return below, level
    above = level_above(level)
    if above is None:
        raise ValueError(f"There is no level above {level.Name!r}. Add a level or use Depth.")
    return level, above


def place_column(element_type, x: float, y: float, level, mode: Literal["DEPTH", "HEIGHT", "AUTO"] = "AUTO"):
    """Place a structural column at (x, y) on ``level``. Returns the Blender object."""
    _check_type(element_type, ("IfcColumnType",))
    base, top = column_extent(level, mode)
    base_z, top_z = level_z(base), level_z(top)
    tool = _tool()
    props = tool.Model.get_model_props()
    props.extrusion_depth = top_z - base_z
    props.cardinal_point = CARDINAL_MID_CENTRE
    _set_default_level(base)
    bpy.context.scene.cursor.location = (x, y, base_z)
    return _generator()(element_type).generate("CURSOR")


def place_beam(element_type, start: tuple[float, float], end: tuple[float, float], level, offset: float = 0.0):
    """Place a beam from ``start`` to ``end`` (x, y) with its top at ``level`` (+ ``offset`` metres)."""
    _check_type(element_type, ("IfcBeamType", "IfcMemberType"))
    if abs(start[0] - end[0]) < 1e-6 and abs(start[1] - end[1]) < 1e-6:
        raise ValueError("Beam start and end are the same point")
    z = level_z(level) + offset
    tool = _tool()
    tool.Model.get_model_props().cardinal_point = CARDINAL_TOP_CENTRE
    _set_default_level(level)
    polyline_props = tool.Model.get_polyline_props()
    polyline_props.insertion_polyline.clear()
    polyline = polyline_props.insertion_polyline.add()
    for x, y in (start, end):
        point = polyline.polyline_points.add()
        point.x, point.y, point.z = x, y, z
    try:
        profiles, _closed = _generator()(element_type).generate("POLYLINE")
    finally:
        polyline_props.insertion_polyline.clear()
    if not profiles:
        raise RuntimeError("Bonsai did not create the beam")
    return profiles[0]["obj"]
