"""Revit-style Properties palette and Project Browser, drawn in a dock on the left.

Colours and layout measured from a Revit 2027 screenshot:

    Properties                              <- title bar  #D9D9D9
    ┌────┐ W Shapes                    ▾    <- Type Selector box #F5F5F5
    │ ▣  │ W12x26
    └────┘
    Structural Framing (1)  ▾  [Edit Type]  <- filter row
    Constraints                         ^   <- group bar #E6E6E6
    Reference Level   │ Level 2             <- rows on white, grid #ECECEC
    ...
    Project Browser - Project Name          <- title bar
    [ Search                          ]
    ⊟ Views (all)
       ⊟ Structural Plans
           ▢ Level 1
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import bpy
import gpu

from . import revit_ui, structure
from .ribbon_draw import _draw, _hex, arrow_down, outline, rect, scale, text, text_width

TITLE = _hex("D9D9D9")
PANEL = _hex("F5F5F5")
EDGE = _hex("BBBBBB")
GROUP = _hex("E6E6E6")
GRID = _hex("ECECEC")
WHITE = _hex("FFFFFF")
TEXT = _hex("3C3C3C")
TEXT_DIM = _hex("A0A0A0")
BUTTON = _hex("E1E1E1")
BUTTON_EDGE = _hex("ADADAD")
FIELD_EDGE = _hex("ABABAB")
HOVER = _hex("E5F1FB")
SELECT = _hex("CCE8FF")
PLAN_BLUE = _hex("5B9BD5")

ROW = 18
PROPERTIES_SHARE = 0.52   # Properties take the top half of the dock, Project Browser the rest

_hit: list[tuple[float, float, float, float, str, dict]] = []
_hover = {"x": -1, "y": -1}
_scroll = {"props": 0.0, "browser": 0.0}
_split = {"y": 0.0}


def is_palette_area(area) -> bool:
    """The left dock: a tall Text Editor area in the BS BIM workspace."""
    if area is None or area.type != "TEXT_EDITOR":
        return False
    ws = bpy.context.workspace
    return ws is not None and ws.name == revit_ui.WORKSPACE and area.height >= 200 * scale()


# ------------------------------------------------------------------ data
@dataclass
class Row:
    label: str
    value: str = ""
    op: str = ""
    kwargs: dict = field(default_factory=dict)
    style: str = "text"      # text | field | button
    enabled: bool = True


def _tool():
    import bonsai.tool as tool
    return tool


def _running_tool(context) -> str | None:
    for op in context.window.modal_operators:
        if op.bl_idname in ("BSBIM_OT_place_column", "BSBIM_OT_place_beam"):
            return op.bl_idname
    return None


def properties_model(context):
    """(header, filter_row, groups) for whatever Revit would show now."""
    from . import palette, state
    from .tools import _pick_type, unit_system
    tool = _tool()
    f = tool.Ifc.get()
    if f is None:
        return ({"family": "", "type": "No project open", "op": "", "kwargs": {}},
                {"text": "", "edit_op": "", "edit_kwargs": {}}, [])
    wm = context.window_manager
    obj = context.active_object if context.selected_objects else None
    entity = tool.Ifc.get_entity(obj) if obj else None

    running = _running_tool(context)
    if running and entity is None:
        is_col = running == "BSBIM_OT_place_column"
        cls, target, prop = (("IfcColumnType", "COLUMN", "bsbim_new_column_type") if is_col
                             else ("IfcBeamType", "BEAM", "bsbim_new_beam_type"))
        t = _pick_type(cls, getattr(wm, prop))
        level = state.active_level()
        header = {"family": t.ElementType if t else "", "type": t.Name if t else "",
                  "op": "bsbim.choose_type", "kwargs": {"ifc_class": cls, "target": target}}
        filt = {"text": "New Structural Columns" if is_col else "New Structural Framing",
                "edit_op": "bsbim.edit_type" if t else "", "edit_kwargs": {"type_id": t.id()} if t else {}}
        rows = [Row("Level" if is_col else "Reference Level", level.Name)]
        if is_col:
            rows.append(Row("Placement", "Depth" if structure.level_below(level) else "Height"))
        else:
            rows.append(Row("z-Justification", "Top"))
        return header, filt, [("Constraints", rows)]

    if entity is not None and not entity.is_a("IfcTypeObject"):
        import ifcopenshell.util.element as E
        etype = E.get_type(entity)
        selected = [o for o in context.selected_objects if tool.Ifc.get_entity(o)]
        category = revit_ui.CATEGORY.get(entity.is_a(), entity.is_a()[3:])
        header = {"family": etype.ElementType if etype else "", "type": etype.Name if etype else "(no type)",
                  "op": "bsbim.choose_type", "kwargs": {"ifc_class": palette._type_class(entity) or "",
                                                        "target": "SELECTION"}}
        filt = {"text": f"{category} ({len(selected)})", "edit_op": "bsbim.edit_type" if etype else "",
                "edit_kwargs": {"type_id": etype.id()} if etype else {}}
        container = E.get_container(entity)
        cons: list[Row] = []
        if entity.is_a("IfcColumn"):
            zmin, zmax = palette._vertical_extent(obj)
            base, top = palette._level_at(zmin), palette._level_at(zmax)
            cons += [Row("Base Level", container.Name if container else "-"),
                     Row("Base Offset", palette._fmt(zmin - structure.level_z(base)) if base else palette._fmt(0)),
                     Row("Top Level", top.Name if top else "Unconnected"),
                     Row("Top Offset", palette._fmt(0.0) if top else "-"),
                     Row("Column Style", "Vertical")]
        elif entity.is_a("IfcBeam") or entity.is_a("IfcMember"):
            usage = E.get_material(entity, should_skip_usage=False)
            cp = str(getattr(usage, "CardinalPoint", "") or "")
            zmax = palette._vertical_extent(obj)[1]
            offset = palette._fmt(zmax - structure.level_z(container)) if container else "-"
            cons += [Row("Reference Level", container.Name if container else "-"),
                     Row("Start Level Offset", offset), Row("End Level Offset", offset),
                     Row("z-Justification", palette.Z_JUSTIFICATION.get(cp, "Top"))]
        else:
            cons.append(Row("Level", container.Name if container else "-"))
        groups = [("Constraints", cons)]
        if entity.is_a("IfcBeam") or entity.is_a("IfcMember"):
            length = palette._extrusion_length_m(entity)
            groups.append(("Dimensions", [Row("Length", palette._fmt(length) if length is not None else "-")]))
        groups.append(("Identity Data", [
            Row("Comments", entity.Description or "", "bsbim.edit_identity", {"field": "Description"}, "field"),
            Row("Mark", entity.Tag or "", "bsbim.edit_identity", {"field": "Tag"}, "field"),
        ]))
        groups.append(("Phasing", [Row("Phase Created", "New Construction"), Row("Phase Demolished", "None")]))
        return header, filt, groups

    # Nothing selected: the active view's properties, as in Revit
    view = wm.bsbim_active_view
    is_plan = view.startswith("PLAN:")
    kind = "Structural Plan" if is_plan else "3D View"
    imperial = unit_system() == "imperial"
    header = {"family": kind, "type": kind, "op": "", "kwargs": {}}
    filt = {"text": f"{kind}: {view[5:] if is_plan else '{3D}'}", "edit_op": "", "edit_kwargs": {}}
    graphics = [Row("View Scale", '1/8" = 1\'-0"' if imperial else "1 : 100", style="field"),
                Row("Detail Level", "Coarse" if is_plan else "Medium"),
                Row("Visibility/Graphics Overrides", "Edit...", style="button", enabled=False),
                Row("Discipline", "Structural")]
    groups = [("Graphics", graphics)]
    if is_plan:
        from .browser import PLAN_BELOW_M, PLAN_CUT_M
        system = unit_system()
        groups.append(("Extents", [Row("View Range", "Edit...", style="button", enabled=False),
                                   Row("Cut Plane", palette._fmt(PLAN_CUT_M[system])),
                                   Row("Bottom", palette._fmt(-PLAN_BELOW_M[system]))]))
    groups.append(("Identity Data", [Row("View Name", view[5:] if is_plan else "{3D}")]))
    return header, filt, groups


@dataclass
class Node:
    depth: int
    label: str
    toggle: str = ""          # group key for expand/collapse
    expanded: bool = False
    op: str = ""
    kwargs: dict = field(default_factory=dict)
    icon: str = ""            # plan | 3d | cloud | ""
    active: bool = False
    enabled: bool = True


def browser_model(context) -> list[Node]:
    from .browser import _collapsed
    tool = _tool()
    f = tool.Ifc.get()
    if f is None:
        return [Node(0, "No project open", enabled=False)]
    nodes: list[Node] = []
    active = context.window_manager.bsbim_active_view

    def group(depth, key, label):
        open_ = key not in _collapsed
        nodes.append(Node(depth, label, toggle=key, expanded=open_))
        return open_

    if group(0, "Views", "Views (all)"):
        if group(1, "Plans", "Structural Plans"):
            for level in structure.levels():
                nodes.append(Node(2, level.Name, op="bsbim.open_view", kwargs={"kind": "PLAN", "level": level.Name},
                                  icon="plan", active=active == f"PLAN:{level.Name}"))
        if group(1, "3D", "3D Views"):
            nodes.append(Node(2, "{3D}", op="bsbim.open_view", kwargs={"kind": "3D"}, icon="3d", active=active == "3D"))
        for label in ("Elevations (Building Elevation)", "Sections (Building Section)"):
            nodes.append(Node(1, label, enabled=False))
    for label in ("Legends", "Schedules/Quantities (all)", "Sheets (all)"):
        nodes.append(Node(0, label, enabled=False))
    if group(0, "Families", "Families"):
        by_cat = defaultdict(lambda: defaultdict(list))
        for t in f.by_type("IfcElementType"):
            cat = revit_ui.CATEGORY.get(t.is_a()[:-4], t.is_a()[3:-4])
            by_cat[cat][t.ElementType or "(no family)"].append(t.Name or "")
        for cat in sorted(by_cat):
            if group(1, f"cat:{cat}", cat):
                for fam in sorted(by_cat[cat]):
                    if group(2, f"fam:{cat}:{fam}", fam):
                        for name in sorted(by_cat[cat][fam]):
                            nodes.append(Node(3, name))
    from .pointcloud import _clouds
    if _clouds and group(0, "PointClouds", "Point Clouds"):
        for name, cloud in _clouds.items():
            nodes.append(Node(1, f"{name}  ({cloud['count']:,} pts)" + ("" if cloud["visible"] else "  (hidden)"),
                              op="bsbim.point_cloud_visibility", kwargs={"name": name}, icon="cloud"))
    return nodes


# ------------------------------------------------------------------ drawing helpers
def fit(s: str, size: float, max_w: float) -> str:
    """Shorten text with '...' to fit max_w, like Revit's palette."""
    if text_width(s, size) <= max_w:
        return s
    while s and text_width(s + "...", size) > max_w:
        s = s[:-1]
    return s + "..."


def _hovered(x0, y0, x1, y1) -> bool:
    return x0 <= _hover["x"] <= x1 and y0 <= _hover["y"] <= y1


def _title_bar(y_top, w, s, label, size):
    h = ROW * s
    rect(0, y_top - h, w, y_top, TITLE)
    _draw("LINES", [(0, y_top - h), (w, y_top - h)], EDGE)
    text(5 * s, y_top - h + 4 * s, fit(label, size, w - 10 * s), size, TEXT)
    return y_top - h


def _icon(kind, x, y, size):
    if kind == "plan":
        outline(x, y, x + size, y + size, PLAN_BLUE)
        rect(x + 2, y + 2, x + size - 2, y + size - 2, _hex("BDD7EE"))
    elif kind == "3d":
        _draw("LINE_LOOP", [(x, y + size * 0.3), (x + size / 2, y), (x + size, y + size * 0.3),
                            (x + size, y + size * 0.75), (x + size / 2, y + size), (x, y + size * 0.75)], TEXT)
    elif kind == "cloud":
        for dx, dy in ((0.2, 0.3), (0.5, 0.6), (0.7, 0.25), (0.35, 0.75), (0.8, 0.7)):
            rect(x + dx * size, y + dy * size, x + dx * size + 2, y + dy * size + 2, PLAN_BLUE)


# ------------------------------------------------------------------ drawing
def _draw_properties(context, w, y_top, y_bottom, s, size):
    header, filt, groups = properties_model(context)
    y = _title_bar(y_top, w, s, "Properties", size)
    # Type Selector box
    box_h = 62 * s
    rect(0, y - box_h, w, y, PANEL)
    _draw("LINES", [(0, y - box_h), (w, y - box_h)], EDGE)
    pic = 46 * s
    px0, py0 = 6 * s, y - box_h + (box_h - pic) / 2
    rect(px0, py0, px0 + pic, py0 + pic, WHITE)
    outline(px0, py0, px0 + pic, py0 + pic, EDGE)
    from .ribbon_draw import draw_icon
    draw_icon("Beam" if "Shapes" in header["family"] or "Beam" in header["family"] else
              "Column" if "Column" in header["family"] else "3D View" if "View" in header["family"] else
              "Level" if "Plan" in header["family"] else "Floor", px0 + 7 * s, py0 + 7 * s, pic - 14 * s, True)
    tx = px0 + pic + 8 * s
    text(tx, y - 22 * s, fit(header["family"], size, w - tx - 20 * s), size, TEXT)
    text(tx, y - 40 * s, fit(header["type"], size, w - tx - 20 * s), size, TEXT)
    if header["op"]:
        arrow_down(w - 10 * s, y - box_h / 2, 3 * s, TEXT)
        if _hovered(0, y - box_h, w, y):
            outline(1, y - box_h + 1, w - 1, y - 1, _hex("9CCBEE"))
        _hit.append((0, y - box_h, w, y, header["op"], header["kwargs"]))
    y -= box_h
    # filter row
    fh = 24 * s
    rect(0, y - fh, w, y, PANEL)
    _draw("LINES", [(0, y - fh), (w, y - fh)], _hex("CCCCCC"))
    if filt["text"]:
        bw = text_width("Edit Type", size) + 14 * s
        text(5 * s, y - fh + 7 * s, fit(filt["text"], size, w - bw - 30 * s), size, TEXT)
        arrow_down(w - bw - 16 * s, y - fh / 2, 3 * s, TEXT)
        bx0, bx1 = w - bw - 4 * s, w - 4 * s
        by0, by1 = y - fh + 3 * s, y - 3 * s
        enabled = bool(filt["edit_op"])
        rect(bx0, by0, bx1, by1, HOVER if enabled and _hovered(bx0, by0, bx1, by1) else BUTTON)
        outline(bx0, by0, bx1, by1, BUTTON_EDGE)
        text((bx0 + bx1) / 2, by0 + 4 * s, "Edit Type", size, TEXT if enabled else TEXT_DIM, center=True)
        if enabled:
            _hit.append((bx0, by0, bx1, by1, filt["edit_op"], filt["edit_kwargs"]))
    y -= fh
    # parameter groups (scrollable)
    area_top = y
    gpu.state.scissor_test_set(True)
    gpu.state.scissor_set(0, int(y_bottom), int(w), int(max(1, area_top - y_bottom)))
    rect(0, y_bottom, w, area_top, WHITE)
    y = area_top + _scroll["props"]
    split_x = w * 0.48
    row_h = ROW * s
    for title, rows in groups:
        rect(0, y - row_h, w, y, GROUP)
        text(4 * s, y - row_h + 4 * s, title, size, TEXT)
        _draw("LINE_STRIP", [(w - 16 * s, y - row_h + 7 * s), (w - 12 * s, y - row_h + 11 * s),
                             (w - 8 * s, y - row_h + 7 * s)], TEXT)  # Revit's collapse chevron
        y -= row_h
        for r in rows:
            y0, y1 = y - row_h, y
            if y1 > y_bottom and y0 < area_top:
                text(10 * s, y0 + 4 * s, fit(r.label, size, split_x - 14 * s), size, TEXT if r.enabled else TEXT_DIM)
                vx0, vx1 = split_x + 2 * s, w - 3 * s
                if r.style == "button":
                    rect(vx0, y0 + 2 * s, vx1, y1 - 2 * s, BUTTON)
                    outline(vx0, y0 + 2 * s, vx1, y1 - 2 * s, BUTTON_EDGE)
                    text((vx0 + vx1) / 2, y0 + 4 * s, r.value, size, TEXT if r.enabled else TEXT_DIM, center=True)
                elif r.style == "field":
                    if r.op and _hovered(vx0, y0, vx1, y1):
                        rect(vx0, y0 + 1 * s, vx1, y1 - 1 * s, HOVER)
                    outline(vx0, y0 + 1 * s, vx1, y1 - 1 * s, FIELD_EDGE)
                    text(vx0 + 4 * s, y0 + 4 * s, fit(r.value, size, vx1 - vx0 - 8 * s), size, TEXT)
                else:
                    text(vx0 + 4 * s, y0 + 4 * s, fit(r.value, size, vx1 - vx0 - 8 * s), size,
                         TEXT if r.enabled else TEXT_DIM)
                _draw("LINES", [(0, y0), (w, y0), (split_x, y0), (split_x, y1)], GRID)
                if r.op and r.enabled:
                    _hit.append((vx0, max(y0, y_bottom), vx1, min(y1, area_top), r.op, r.kwargs))
            y -= row_h
    gpu.state.scissor_test_set(False)
    _scroll["props_content"] = area_top + _scroll["props"] - y


def _draw_browser(context, w, y_top, s, size):
    tool = _tool()
    f = tool.Ifc.get()
    project = f.by_type("IfcProject")[0].Name if f else ""
    y = _title_bar(y_top, w, s, f"Project Browser - {project}" if project else "Project Browser", size)
    # search box (looks like Revit's; filtering comes later)
    sh = 26 * s
    rect(0, y - sh, w, y, WHITE)
    outline(6 * s, y - sh + 4 * s, w - 6 * s, y - 4 * s, FIELD_EDGE)
    text(12 * s, y - sh + 8 * s, "Search", size, TEXT_DIM)
    y -= sh
    area_top = y
    gpu.state.scissor_test_set(True)
    gpu.state.scissor_set(0, 0, int(w), int(max(1, area_top)))
    rect(0, 0, w, area_top, WHITE)
    y = area_top + _scroll["browser"]
    row_h = ROW * s
    indent = 16 * s
    for n in browser_model(context):
        y0, y1 = y - row_h, y
        if y1 > 0 and y0 < area_top:
            x = 6 * s + n.depth * indent
            if n.toggle:
                bx0, by0 = x, y0 + 4 * s
                b = 9 * s
                rect(bx0, by0, bx0 + b, by0 + b, WHITE)
                outline(bx0, by0, bx0 + b, by0 + b, _hex("919191"))
                _draw("LINES", [(bx0 + 2 * s, by0 + b / 2), (bx0 + b - 2 * s, by0 + b / 2)], TEXT)
                if not n.expanded:
                    _draw("LINES", [(bx0 + b / 2, by0 + 2 * s), (bx0 + b / 2, by0 + b - 2 * s)], TEXT)
                _hit.append((bx0 - 2 * s, y0, bx0 + b + 2 * s, y1, "bsbim.toggle_browser_group", {"group": n.toggle}))
                x += b + 5 * s
            elif n.icon:
                _icon(n.icon, x + 12 * s, y0 + 3 * s, 12 * s)
                x += 30 * s
            else:
                x += 14 * s
            label_w = text_width(n.label, size)
            if n.active:
                rect(x - 2 * s, y0 + 1 * s, x + label_w + 3 * s, y1 - 1 * s, SELECT)
            elif n.op and _hovered(x - 2 * s, y0, x + label_w + 3 * s, y1):
                rect(x - 2 * s, y0 + 1 * s, x + label_w + 3 * s, y1 - 1 * s, HOVER)
            text(x, y0 + 4 * s, fit(n.label, size, w - x - 6 * s), size, TEXT if n.enabled else TEXT_DIM)
            if n.op:
                _hit.append((x - 2 * s, y0, w, y1, n.op, n.kwargs))
            elif n.toggle:
                _hit.append((x - 2 * s, y0, w, y1, "bsbim.toggle_browser_group", {"group": n.toggle}))
        y -= row_h
    gpu.state.scissor_test_set(False)
    _scroll["browser_content"] = area_top + _scroll["browser"] - y


def draw_palette():
    context = bpy.context
    if not is_palette_area(context.area):
        return
    region = context.region
    s = scale()
    w, h = region.width, region.height
    size = 12 * s
    gpu.state.blend_set("ALPHA")
    _hit.clear()
    rect(0, 0, w, h, WHITE)
    split = h * (1 - PROPERTIES_SHARE)
    _split["y"] = split
    _draw_properties(context, w, h, split + 4 * s, s, size)
    rect(0, split, w, split + 4 * s, TITLE)  # splitter between the two palettes
    _draw_browser(context, w, split, s, size)
    _draw("LINES", [(w - 1, 0), (w - 1, h)], EDGE)
    gpu.state.blend_set("NONE")


# ------------------------------------------------------------------ interaction (called by ribbon_draw's operators)
def click(context, x: float, y: float) -> bool:
    for x0, y0, x1, y1, op, kwargs in reversed(_hit):
        if x0 <= x <= x1 and y0 <= y <= y1:
            from .keymap import run_command
            run_command(context, op, kwargs, op)
            redraw()
            return True
    return False


def hover(x: float, y: float):
    _hover["x"], _hover["y"] = x, y


def scroll(y: float, steps: int):
    key = "props" if y > _split["y"] else "browser"
    content = _scroll.get(f"{key}_content", 0.0)
    _scroll[key] = max(0.0, min(max(0.0, content - 100), _scroll[key] + steps * ROW * scale() * 2))


def redraw(*_args):
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "TEXT_EDITOR":
                area.tag_redraw()


_handle = None


def register():
    global _handle
    _handle = bpy.types.SpaceTextEditor.draw_handler_add(draw_palette, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceTextEditor.draw_handler_remove(_handle, "WINDOW")
        _handle = None
