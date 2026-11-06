"""Revit-style ribbon drawn in its own strip at the top of the BS BIM screen.

Blender's header rows are one line high, so the ribbon is drawn by hand (gpu + blf) inside a small
Text Editor area that has all its own regions hidden:

    ┌───────┬──────────────────────────────────────────┬──────────────────┬──────────────┐
    │  ↖    │  ═╪═    ▭     ┃      ▱     /\/\   ╱    │   ▃    ▭    ▬    │  ─▽─    ⊙─   │
    │Modify │  Beam  Wall  Column Floor  Truss Brace  │ Isolated Wall Slab│ Level  Grid  │
    ├───────┼──────────────────────────────────────────┼──────────────────┼──────────────┤
    │Select │               Structure                  │    Foundation    │    Datum     │
    └───────┴──────────────────────────────────────────┴──────────────────┴──────────────┘

Icons are simple line drawings made for BS BIM (not Autodesk artwork).
Clicks run the command in the main 3D view, exactly like the ribbon buttons in Revit.
"""

from __future__ import annotations

import math

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from . import ribbon

RIBBON_HEIGHT = 92  # pixels at 100% UI scale

# Revit 2027 light ribbon colours
BG = (0.965, 0.965, 0.965, 1.0)
TITLE_BG = (0.91, 0.91, 0.91, 1.0)
SEPARATOR = (0.78, 0.78, 0.78, 1.0)
TEXT = (0.13, 0.13, 0.13, 1.0)
TEXT_DISABLED = (0.62, 0.62, 0.62, 1.0)
HOVER = (0.80, 0.89, 0.98, 1.0)
HOVER_EDGE = (0.45, 0.66, 0.90, 1.0)
DARK = (0.28, 0.30, 0.33, 1.0)
BLUE = (0.16, 0.45, 0.78, 1.0)
STEEL = (0.45, 0.52, 0.60, 1.0)
CONCRETE = (0.74, 0.74, 0.72, 1.0)
GREEN = (0.20, 0.60, 0.30, 1.0)
RED = (0.80, 0.25, 0.20, 1.0)

# Button rectangles from the last draw: (x0, y0, x1, y1, Cmd)
_hit: list[tuple[float, float, float, float, ribbon.Cmd]] = []
_hover: dict = {"x": -1, "y": -1}


def scale() -> float:
    return bpy.context.preferences.system.ui_scale


def is_ribbon_area(area) -> bool:
    """The ribbon strip: a short Text Editor area in the BS BIM workspace."""
    if area is None or area.type != "TEXT_EDITOR":
        return False
    ws = bpy.context.workspace
    from .revit_ui import WORKSPACE
    return ws is not None and ws.name == WORKSPACE and area.height < 200 * scale()


# ------------------------------------------------------------------ primitive drawing
_shader = None


def _sh():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    return _shader


def _draw(kind, coords, color, indices=None):
    sh = _sh()
    batch = batch_for_shader(sh, kind, {"pos": coords}, indices=indices)
    sh.uniform_float("color", color)
    batch.draw(sh)


def rect(x0, y0, x1, y1, color):
    _draw("TRIS", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color, indices=[(0, 1, 2), (0, 2, 3)])


def outline(x0, y0, x1, y1, color):
    _draw("LINE_LOOP", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color)


def text(x, y, s, size, color, center=False):
    blf.size(0, size)
    if center:
        x -= blf.dimensions(0, s)[0] / 2
    blf.color(0, *color)
    blf.position(0, x, y, 0)
    blf.draw(0, s)


def text_width(s, size) -> float:
    blf.size(0, size)
    return blf.dimensions(0, s)[0]


# ------------------------------------------------------------------ icons (unit square 0..1)
def _icon_shapes(name: str):
    """Line-art icon as a list of (primitive, points, colour). Points in a 0..1 square, y up."""
    L, R, F = "LINE_STRIP", "LINE_LOOP", "TRIS"

    def box(x0, y0, x1, y1, c, fill=None):
        out = []
        if fill:
            out.append((F, [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)], fill))
        out.append((R, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], c))
        return out

    def circle(cx, cy, r, c, n=20):
        return [(R, [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)], c)]

    icons = {
        "Modify": [(F, [(0.30, 0.90), (0.30, 0.20), (0.48, 0.38), (0.30, 0.90), (0.48, 0.38), (0.72, 0.42)], DARK),
                   (L, [(0.45, 0.36), (0.62, 0.08)], DARK)],
        "Beam": [*box(0.05, 0.62, 0.95, 0.70, BLUE, STEEL), *box(0.05, 0.30, 0.95, 0.38, BLUE, STEEL),
                 (L, [(0.05, 0.50), (0.95, 0.50)], BLUE)],
        "Wall": [*box(0.10, 0.10, 0.90, 0.85, DARK, CONCRETE), (L, [(0.10, 0.47), (0.90, 0.47)], DARK),
                 (L, [(0.50, 0.47), (0.50, 0.85)], DARK), (L, [(0.30, 0.10), (0.30, 0.47)], DARK),
                 (L, [(0.70, 0.10), (0.70, 0.47)], DARK)],
        "Column": [*box(0.25, 0.85, 0.75, 0.92, BLUE, STEEL), *box(0.45, 0.13, 0.55, 0.85, BLUE, STEEL),
                   *box(0.25, 0.06, 0.75, 0.13, BLUE, STEEL)],
        "Floor": [(F, [(0.05, 0.35), (0.65, 0.35), (0.95, 0.65), (0.05, 0.35), (0.95, 0.65), (0.35, 0.65)], CONCRETE),
                  (R, [(0.05, 0.35), (0.65, 0.35), (0.95, 0.65), (0.35, 0.65)], DARK),
                  (L, [(0.05, 0.35), (0.05, 0.25), (0.65, 0.25), (0.95, 0.55), (0.95, 0.65)], DARK)],
        "Truss": [(L, [(0.05, 0.25), (0.95, 0.25)], BLUE), (L, [(0.05, 0.75), (0.95, 0.75)], BLUE),
                  (L, [(0.05, 0.25), (0.25, 0.75), (0.45, 0.25), (0.65, 0.75), (0.85, 0.25), (0.95, 0.5)], BLUE)],
        "Brace": [*box(0.08, 0.08, 0.16, 0.92, DARK, STEEL), *box(0.84, 0.08, 0.92, 0.92, DARK, STEEL),
                  (L, [(0.16, 0.12), (0.84, 0.88)], BLUE), (L, [(0.16, 0.16), (0.84, 0.92)], BLUE)],
        "Beam System": [(R, [(0.08, 0.15), (0.92, 0.15), (0.92, 0.85), (0.08, 0.85)], DARK),
                        *[(L, [(0.08 + i * 0.14, 0.15), (0.08 + i * 0.14, 0.85)], BLUE) for i in range(1, 6)]],
        "Connection": [*box(0.10, 0.10, 0.20, 0.90, DARK, STEEL), *box(0.20, 0.45, 0.90, 0.55, DARK, STEEL),
                       *box(0.20, 0.30, 0.32, 0.70, BLUE, None)],
        "Isolated": [*box(0.15, 0.10, 0.85, 0.40, DARK, CONCRETE), *box(0.40, 0.40, 0.60, 0.90, BLUE, STEEL)],
        "Slab": [*box(0.05, 0.30, 0.95, 0.55, DARK, CONCRETE)],
        "Level": [(L, [(0.05, 0.40), (0.95, 0.40)], BLUE),
                  (F, [(0.10, 0.40), (0.30, 0.40), (0.20, 0.60)], BLUE), (L, [(0.40, 0.62), (0.90, 0.62)], DARK)],
        "Grid": [*circle(0.22, 0.75, 0.16, BLUE), (L, [(0.22, 0.59), (0.22, 0.05)], BLUE),
                 (L, [(0.38, 0.75), (0.95, 0.75)], DARK)],
        "Ref Plane": [(L, [(0.05, 0.50), (0.20, 0.50)], GREEN), (L, [(0.30, 0.50), (0.45, 0.50)], GREEN),
                      (L, [(0.55, 0.50), (0.70, 0.50)], GREEN), (L, [(0.80, 0.50), (0.95, 0.50)], GREEN)],
        "Door": [*box(0.25, 0.05, 0.75, 0.90, DARK, CONCRETE), *circle(0.66, 0.48, 0.03, DARK)],
        "Window": [*box(0.15, 0.20, 0.85, 0.85, DARK, (0.80, 0.90, 0.98, 1)), (L, [(0.50, 0.20), (0.50, 0.85)], DARK)],
        "Roof": [(R, [(0.05, 0.40), (0.50, 0.85), (0.95, 0.40)], DARK), (L, [(0.20, 0.40), (0.20, 0.10), (0.80, 0.10), (0.80, 0.40)], DARK)],
        "Ceiling": [*box(0.05, 0.75, 0.95, 0.85, DARK, CONCRETE), (L, [(0.20, 0.75), (0.20, 0.55)], DARK), (L, [(0.80, 0.75), (0.80, 0.55)], DARK)],
        "Railing": [(L, [(0.05, 0.75), (0.95, 0.75)], DARK), *[(L, [(x, 0.15), (x, 0.75)], DARK) for x in (0.1, 0.3, 0.5, 0.7, 0.9)]],
        "Stair": [(L, [(0.05, 0.10), (0.25, 0.10), (0.25, 0.30), (0.45, 0.30), (0.45, 0.50), (0.65, 0.50), (0.65, 0.70), (0.85, 0.70), (0.85, 0.90)], DARK)],
        "Duct": [*box(0.05, 0.35, 0.95, 0.65, BLUE, (0.85, 0.92, 0.98, 1)), (L, [(0.30, 0.50), (0.70, 0.50)], BLUE),
                 (L, [(0.60, 0.58), (0.70, 0.50), (0.60, 0.42)], BLUE)],
        "Duct Fitting": [(L, [(0.05, 0.30), (0.55, 0.30), (0.70, 0.95)], BLUE), (L, [(0.05, 0.60), (0.35, 0.60), (0.42, 0.95)], BLUE)],
        "Air Terminal": [*box(0.15, 0.15, 0.85, 0.85, DARK, (0.92, 0.92, 0.92, 1)), *box(0.30, 0.30, 0.70, 0.70, DARK)],
        "Mechanical Equipment": [*box(0.10, 0.15, 0.90, 0.80, DARK, CONCRETE), *circle(0.50, 0.48, 0.20, BLUE)],
        "Pipe": [*box(0.05, 0.40, 0.95, 0.60, GREEN, (0.85, 0.95, 0.88, 1))],
        "Plumbing Fixture": [(R, [(0.15, 0.55), (0.85, 0.55), (0.75, 0.15), (0.25, 0.15)], DARK), (L, [(0.50, 0.55), (0.50, 0.85), (0.65, 0.85)], DARK)],
        "Sprinkler": [*circle(0.50, 0.55, 0.12, RED), (L, [(0.50, 0.67), (0.50, 0.95)], RED),
                      (L, [(0.25, 0.25), (0.40, 0.45)], RED), (L, [(0.75, 0.25), (0.60, 0.45)], RED)],
        "Cable Tray": [(L, [(0.05, 0.65), (0.05, 0.35), (0.95, 0.35), (0.95, 0.65)], DARK),
                       *[(L, [(x, 0.35), (x, 0.50)], DARK) for x in (0.25, 0.5, 0.75)]],
        "Conduit": [(L, [(0.05, 0.45), (0.95, 0.45)], DARK), (L, [(0.05, 0.55), (0.95, 0.55)], DARK)],
        "Electrical Equipment": [*box(0.20, 0.10, 0.80, 0.90, DARK, CONCRETE), (L, [(0.55, 0.75), (0.42, 0.50), (0.58, 0.50), (0.45, 0.25)], (0.9, 0.6, 0.0, 1))],
        "Lighting Fixture": [*circle(0.50, 0.55, 0.22, (0.9, 0.6, 0.0, 1)), (L, [(0.40, 0.30), (0.60, 0.30)], DARK), (L, [(0.42, 0.20), (0.58, 0.20)], DARK)],
        "Open Revit File": [*box(0.20, 0.05, 0.80, 0.90, DARK, (1, 1, 1, 1)), (L, [(0.32, 0.65), (0.68, 0.65)], BLUE), (L, [(0.32, 0.45), (0.68, 0.45)], BLUE), (L, [(0.32, 0.25), (0.55, 0.25)], BLUE)],
        "Open IFC": [*box(0.20, 0.05, 0.80, 0.90, DARK, (1, 1, 1, 1)), *circle(0.50, 0.45, 0.18, GREEN)],
        "Load Family": [*box(0.10, 0.10, 0.90, 0.70, DARK, CONCRETE), (L, [(0.50, 0.95), (0.50, 0.40)], BLUE), (L, [(0.35, 0.55), (0.50, 0.40), (0.65, 0.55)], BLUE)],
        "Aligned": [(L, [(0.10, 0.20), (0.10, 0.70)], DARK), (L, [(0.90, 0.20), (0.90, 0.70)], DARK), (L, [(0.10, 0.55), (0.90, 0.55)], BLUE)],
        "Text": [(L, [(0.20, 0.85), (0.80, 0.85)], DARK), (L, [(0.50, 0.85), (0.50, 0.10)], DARK)],
        "Tag by Category": [(R, [(0.15, 0.30), (0.65, 0.30), (0.90, 0.55), (0.65, 0.80), (0.15, 0.80)], BLUE)],
        "Model Quality": [*box(0.15, 0.10, 0.85, 0.90, DARK, (1, 1, 1, 1)), (L, [(0.28, 0.50), (0.42, 0.32), (0.72, 0.72)], GREEN)],
        "Interference Check": [*box(0.10, 0.30, 0.60, 0.80, BLUE), *box(0.40, 0.10, 0.90, 0.60, RED)],
        "3D View": [(R, [(0.15, 0.30), (0.50, 0.12), (0.85, 0.30), (0.85, 0.70), (0.50, 0.88), (0.15, 0.70)], DARK),
                    (L, [(0.15, 0.70), (0.50, 0.52), (0.85, 0.70)], DARK), (L, [(0.50, 0.52), (0.50, 0.12)], DARK)],
        "Section": [(L, [(0.10, 0.50), (0.90, 0.50)], BLUE), *circle(0.12, 0.50, 0.08, BLUE), (F, [(0.85, 0.50), (0.95, 0.50), (0.90, 0.65)], BLUE)],
        "Sheet": [*box(0.10, 0.15, 0.90, 0.85, DARK, (1, 1, 1, 1)), *box(0.65, 0.15, 0.90, 0.40, DARK)],
        "Visibility/Graphics": [*circle(0.50, 0.50, 0.15, DARK), (R, [(0.05, 0.50), (0.30, 0.72), (0.70, 0.72), (0.95, 0.50), (0.70, 0.28), (0.30, 0.28)], DARK)],
        "Project Units": [(L, [(0.05, 0.40), (0.95, 0.40)], DARK), *[(L, [(x, 0.40), (x, 0.55 if i % 2 else 0.65)], DARK) for i, x in enumerate((0.1, 0.3, 0.5, 0.7, 0.9))]],
        "Move": [(L, [(0.10, 0.50), (0.90, 0.50)], DARK), (L, [(0.50, 0.10), (0.50, 0.90)], DARK),
                 (F, [(0.90, 0.50), (0.78, 0.58), (0.78, 0.42)], DARK), (F, [(0.50, 0.90), (0.42, 0.78), (0.58, 0.78)], DARK)],
        "Copy": [*box(0.10, 0.30, 0.60, 0.80, DARK, CONCRETE), *box(0.40, 0.10, 0.90, 0.60, BLUE, (1, 1, 1, 1))],
        "Rotate": [(L, [(0.5 + 0.35 * math.cos(a / 10), 0.5 + 0.35 * math.sin(a / 10)) for a in range(0, 50)], DARK)],
        "Mirror": [(L, [(0.50, 0.05), (0.50, 0.95)], GREEN), (R, [(0.10, 0.25), (0.40, 0.25), (0.40, 0.75)], DARK), (R, [(0.90, 0.25), (0.60, 0.25), (0.60, 0.75)], DARK)],
        "Array": [*box(0.05, 0.35, 0.30, 0.65, DARK), *box(0.375, 0.35, 0.625, 0.65, DARK), *box(0.70, 0.35, 0.95, 0.65, DARK)],
        "Align": [(L, [(0.15, 0.05), (0.15, 0.95)], BLUE), *box(0.15, 0.60, 0.80, 0.80, DARK), *box(0.15, 0.20, 0.60, 0.40, DARK)],
        "Delete": [(L, [(0.20, 0.20), (0.80, 0.80)], RED), (L, [(0.20, 0.80), (0.80, 0.20)], RED)],
        "Point Cloud": [(F, [(x, y), (x + 0.05, y), (x + 0.05, y + 0.05), (x, y), (x + 0.05, y + 0.05), (x, y + 0.05)], c)
                        for x, y, c in ((0.15, 0.20, BLUE), (0.30, 0.45, GREEN), (0.45, 0.30, RED), (0.60, 0.60, BLUE),
                                        (0.75, 0.35, GREEN), (0.25, 0.70, RED), (0.50, 0.80, DARK), (0.80, 0.75, BLUE),
                                        (0.40, 0.15, DARK), (0.65, 0.15, BLUE), (0.85, 0.55, RED), (0.10, 0.50, DARK))],
        "Blender Mode": [*circle(0.50, 0.50, 0.30, (0.92, 0.47, 0.16, 1)), *circle(0.50, 0.50, 0.12, BLUE)],
    }
    icons["Wall Foundation"] = icons["Slab"]
    return icons.get(name) or [*box(0.20, 0.20, 0.80, 0.80, DARK, CONCRETE)]


def draw_icon(name: str, x: float, y: float, size: float, enabled: bool):
    for kind, pts, color in _icon_shapes(name):
        c = color if enabled else (color[0], color[1], color[2], 0.30)
        _draw(kind, [(x + px * size, y + py * size) for px, py in pts], c)


# ------------------------------------------------------------------ layout
def _wrap(label: str, size: float, max_w: float) -> list[str]:
    if text_width(label, size) <= max_w or " " not in label:
        return [label]
    words = label.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        w = max(text_width(a, size), text_width(b, size))
        if best is None or w < best[0]:
            best = (w, [a, b])
    return best[1]


def current_panels(context):
    """Revit always starts each tab with the Select panel; selection shows the contextual Modify tab."""
    select = ("Select", [ribbon.Cmd("Modify", "", "bsbim.ribbon_modify")])
    from .revit_ui import _selection_category
    if _selection_category(context):
        return [select, *ribbon.MODIFY]
    return [select, *ribbon.TABS[context.window_manager.bsbim_ribbon_tab]]


def draw_ribbon():
    context = bpy.context
    area = context.area
    if not is_ribbon_area(area):
        return
    region = context.region
    s = scale()
    w, h = region.width, region.height
    gpu.state.blend_set("ALPHA")
    rect(0, 0, w, h, BG)
    title_h = 18 * s
    rect(0, 0, w, title_h, TITLE_BG)
    _draw("LINES", [(0, h - 1), (w, h - 1), (0, title_h), (w, title_h)], SEPARATOR)

    font = 11 * s
    icon = 30 * s
    pad = 6 * s
    _hit.clear()
    x = 4 * s
    for title, cmds in current_panels(context):
        panel_x0 = x
        for c in cmds:
            lines = _wrap(c.label, font, 64 * s)
            bw = max(max(text_width(l, font) for l in lines) + 2 * pad, icon + 2 * pad)
            x0, x1, y0, y1 = x, x + bw, title_h + 2 * s, h - 3 * s
            enabled = bool(c.op)
            if enabled and x0 <= _hover["x"] <= x1 and y0 <= _hover["y"] <= y1:
                rect(x0, y0, x1, y1, HOVER)
                outline(x0, y0, x1, y1, HOVER_EDGE)
            draw_icon(c.label, x + (bw - icon) / 2, h - icon - 6 * s, icon, enabled)
            ty = h - icon - 6 * s - font - 3 * s
            for line in lines:
                text(x + bw / 2, ty, line, font, TEXT if enabled else TEXT_DISABLED, center=True)
                ty -= font + 2 * s
            _hit.append((x0, y0, x1, y1, c))
            x += bw + 2 * s
        x += 6 * s
        text((panel_x0 + x) / 2 - 3 * s, 5 * s, title, 10.5 * s, TEXT, center=True)
        _draw("LINES", [(x - 3 * s, 4 * s), (x - 3 * s, h - 6 * s)], SEPARATOR)
    gpu.state.blend_set("NONE")


def hit(x: float, y: float):
    for x0, y0, x1, y1, c in _hit:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return c
    return None


# ------------------------------------------------------------------ operators
def main_view3d(context):
    """(area, region) of the largest 3D view on the screen: where ribbon commands act."""
    areas = [a for a in context.screen.areas if a.type == "VIEW_3D"]
    if not areas:
        return None, None
    area = max(areas, key=lambda a: a.width * a.height)
    return area, next(r for r in area.regions if r.type == "WINDOW")


class BSBIM_OT_ribbon_click(bpy.types.Operator):
    bl_idname = "bsbim.ribbon_click"
    bl_label = "Ribbon"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        if not is_ribbon_area(context.area):
            return {"PASS_THROUGH"}
        c = hit(event.mouse_region_x, event.mouse_region_y)
        if c is None:
            return {"FINISHED"}
        if not c.op:
            self.report({"INFO"}, f"{c.label}: coming in a later BS BIM version")
            return {"FINISHED"}
        from .keymap import run_command
        if not run_command(context, c.op, c.kwargs, c.label):
            self.report({"WARNING"}, f"{c.label} could not start here")
        return {"FINISHED"}


class BSBIM_OT_ribbon_hover(bpy.types.Operator):
    bl_idname = "bsbim.ribbon_hover"
    bl_label = "Ribbon hover"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        if is_ribbon_area(context.area):
            _hover["x"], _hover["y"] = event.mouse_region_x, event.mouse_region_y
            context.area.tag_redraw()
        return {"PASS_THROUGH"}


class BSBIM_OT_ribbon_modify(bpy.types.Operator):
    """Modify: finish the current tool and clear the selection, like Revit's Modify button"""

    bl_idname = "bsbim.ribbon_modify"
    bl_label = "Modify"

    def execute(self, context):
        if context.mode == "OBJECT":
            bpy.ops.object.select_all(action="DESELECT")
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.select_box")
        except RuntimeError:
            pass
        return {"FINISHED"}


@bpy.app.handlers.persistent
def redraw_ribbon(*_args):
    """Selection changes switch the ribbon to the Modify tab, so redraw it."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "TEXT_EDITOR":
                area.tag_redraw()


classes = (BSBIM_OT_ribbon_click, BSBIM_OT_ribbon_hover, BSBIM_OT_ribbon_modify)

_handle = None
_keymaps: list = []


def register():
    global _handle
    _handle = bpy.types.SpaceTextEditor.draw_handler_add(draw_ribbon, (), "WINDOW", "POST_PIXEL")
    bpy.app.handlers.depsgraph_update_post.append(redraw_ribbon)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is not None:
        km = kc.keymaps.new(name="Text", space_type="TEXT_EDITOR")
        _keymaps.append((km, km.keymap_items.new("bsbim.ribbon_click", "LEFTMOUSE", "PRESS")))
        _keymaps.append((km, km.keymap_items.new("bsbim.ribbon_hover", "MOUSEMOVE", "ANY")))


def unregister():
    global _handle
    if redraw_ribbon in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(redraw_ribbon)
    if _handle is not None:
        bpy.types.SpaceTextEditor.draw_handler_remove(_handle, "WINDOW")
        _handle = None
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
