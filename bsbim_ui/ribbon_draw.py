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

TAB_ROW = 22      # pixels at 100% UI scale
PANEL_ROW = 96
RIBBON_HEIGHT = TAB_ROW + PANEL_ROW + 2


def _hex(h: str, a: float = 1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


# Colours measured from a Revit 2027 screenshot
TAB_BG = _hex("D9D9D9")
BG = _hex("F5F5F5")              # ribbon panels and the active tab
FILE_TAB = _hex("2B7BB3")
TAB_EDGE = _hex("BBBBBB")
BORDER = _hex("C1C1C1")
SEPARATOR = _hex("DADADA")
TEXT = _hex("3C3C3C")
TEXT_DISABLED = _hex("A6A6A6")
WHITE = _hex("FFFFFF")
ACTIVE_FILL = _hex("DDEEF6")     # pressed Modify button
ACTIVE_EDGE = _hex("77C3E6")
HOVER = _hex("E5F1FB")
HOVER_EDGE = _hex("9CCBEE")
CONTEXT_TAB = _hex("E3F1DE")     # contextual "Modify | ..." tab
CONTEXT_EDGE = _hex("6DB33F")
DARK = (0.28, 0.30, 0.33, 1.0)
BLUE = (0.16, 0.45, 0.78, 1.0)
STEEL = (0.45, 0.52, 0.60, 1.0)
CONCRETE = (0.74, 0.74, 0.72, 1.0)
GREEN = (0.20, 0.60, 0.30, 1.0)
RED = (0.80, 0.25, 0.20, 1.0)

def load_font():
    """Kept for registration. Segoe UI loaded through blf drew nothing in the real window
    (Blender 5.1), so the ribbon uses Blender's own UI font, which always draws."""


def font() -> int:
    return 0


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
    f = font()
    blf.size(f, size)
    if center:
        x -= blf.dimensions(f, s)[0] / 2
    blf.color(f, *color)
    blf.position(f, x, y, 0)
    blf.draw(f, s)


def text_width(s, size) -> float:
    f = font()
    blf.size(f, size)
    return blf.dimensions(f, s)[0]


def arrow_down(cx, cy, size, color):
    _draw("TRIS", [(cx - size, cy + size / 2), (cx + size, cy + size / 2), (cx, cy - size / 2)], color)


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


def _tool_running(context) -> bool:
    return any(op.bl_idname.startswith("BSBIM_OT_place") for op in context.window.modal_operators)


def _draw_tabs(context, w, h, s):
    """Row of tabs: blue File tab, then the Revit tabs; the active tab joins the panels below."""
    from .revit_ui import _selection_category
    y0, y1 = h - TAB_ROW * s, h
    rect(0, y0, w, y1, TAB_BG)
    size = 12 * s
    x = 2 * s
    fw = text_width("File", size) + 22 * s
    rect(x, y0 + 1 * s, x + fw, y1 - 2 * s, FILE_TAB)
    text(x + fw / 2, y0 + 6 * s, "File", size, WHITE, center=True)
    _hit.append((x, y0, x + fw, y1, ribbon.Cmd("File", "", "wm.call_menu", {"name": "BSBIM_MT_file"})))
    x += fw + 2 * s
    category = _selection_category(context)
    active_key = None if category else context.window_manager.bsbim_ribbon_tab
    tabs = list(ribbon.TAB_LABELS.items())
    if category:
        tabs.append(("__context__", f"Modify | {category}"))
    active_x = None
    for key, label in tabs:
        tw = text_width(label, size) + 18 * s
        is_active = key == active_key or key == "__context__"
        if is_active:
            fill = CONTEXT_TAB if key == "__context__" else BG
            rect(x, y0, x + tw, y1 - 1 * s, fill)
            _draw("LINE_STRIP", [(x, y0), (x, y1 - 1 * s), (x + tw, y1 - 1 * s), (x + tw, y0)],
                  CONTEXT_EDGE if key == "__context__" else TAB_EDGE)
            active_x = (x, x + tw)
        elif x <= _hover["x"] <= x + tw and y0 <= _hover["y"] <= y1:
            rect(x, y0 + 1 * s, x + tw, y1 - 2 * s, HOVER)
        text(x + tw / 2, y0 + 6 * s, label, size, TEXT, center=True)
        if key != "__context__":
            _hit.append((x, y0, x + tw, y1, ribbon.Cmd(label, "", "bsbim.set_ribbon_tab", {"tab": key})))
        x += tw
    if active_x:  # line under the tabs, open under the active one (Revit's folder-tab look)
        _draw("LINES", [(0, y0), (active_x[0], y0), (active_x[1], y0), (w, y0)], TAB_EDGE)
    else:
        _draw("LINES", [(0, y0), (w, y0)], TAB_EDGE)


def draw_ribbon():
    context = bpy.context
    area = context.area
    if not is_ribbon_area(area):
        return
    region = context.region
    s = scale()
    w, h = region.width, region.height
    gpu.state.blend_set("ALPHA")
    _hit.clear()
    panel_top = h - TAB_ROW * s
    rect(0, 0, w, panel_top, BG)
    _draw("LINES", [(0, 1), (w, 1)], BORDER)
    _draw_tabs(context, w, h, s)

    font_size = 12 * s
    icon = 32 * s
    pad = 5 * s
    title_y = 5 * s
    modify_active = not _tool_running(context)
    x = 3 * s
    for title, cmds in current_panels(context):
        panel_x0 = x
        for c in cmds:
            lines = _wrap(c.label, font_size, 60 * s)
            bw = max(max(text_width(l, font_size) for l in lines) + 2 * pad, icon + 2 * pad)
            x0, x1 = x, x + bw
            y0, y1 = 20 * s, panel_top - 3 * s
            enabled = bool(c.op)
            pressed = c.label == "Modify" and modify_active
            if pressed:
                rect(x0, y0, x1, y1, ACTIVE_FILL)
                outline(x0, y0, x1, y1, ACTIVE_EDGE)
            elif enabled and x0 <= _hover["x"] <= x1 and y0 <= _hover["y"] <= y1:
                rect(x0, y0, x1, y1, HOVER)
                outline(x0, y0, x1, y1, HOVER_EDGE)
            icon_y = panel_top - icon - 7 * s
            draw_icon(c.label, x + (bw - icon) / 2, icon_y, icon, enabled)
            ty = icon_y - font_size - 2 * s
            for line in lines:
                text(x + bw / 2, ty, line, font_size, TEXT if enabled else TEXT_DISABLED, center=True)
                ty -= font_size + 1 * s
            if c.dropdown:
                arrow_down(x + bw / 2, ty + font_size - 2 * s, 3 * s, TEXT if enabled else TEXT_DISABLED)
            _hit.append((x0, y0, x1, y1, c))
            x += bw + 1 * s
        x += 6 * s
        cx = (panel_x0 + x) / 2 - 3 * s
        text(cx, title_y, title, font_size, TEXT, center=True)
        if title in ribbon.PANEL_MENUS:
            arrow_down(cx + text_width(title, font_size) / 2 + 7 * s, title_y + 5 * s, 3 * s, TEXT)
        _draw("LINES", [(x - 3 * s, 5 * s), (x - 3 * s, panel_top - 5 * s)], SEPARATOR)
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
    load_font()
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
