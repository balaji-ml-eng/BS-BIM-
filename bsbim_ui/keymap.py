"""Revit keyboard shortcuts and mouse navigation (active only in the Revit-style screen).

Mouse, as in Revit:
    middle-drag = pan · Shift + middle-drag = orbit · wheel = zoom at cursor
    Ctrl + click = add to selection · Shift + click = remove from selection
Keyboard: Revit's two-letter shortcuts. Type the first letter, then the second within 1.5 s.
In Blender mode every key passes through to Blender unchanged.
"""

from __future__ import annotations

import time

import bpy

from . import revit_ui

# Revit default shortcut -> (operator id, kwargs, description)
SHORTCUTS: dict[str, tuple[str, dict, str]] = {
    "CL": ("bsbim.place_column", {}, "Structural Column"),
    "BM": ("bsbim.place_beam", {}, "Beam"),
    "BR": ("bsbim.place_beam", {"brace": True}, "Brace"),
    "GR": ("bsbim.add_grid", {}, "Grid"),
    "LL": ("bsbim.add_level", {}, "Level"),
    "WA": ("wm.tool_set_by_id", {"name": "bim.wall_tool"}, "Wall"),
    "SB": ("wm.tool_set_by_id", {"name": "bim.slab_tool"}, "Floor: Structural"),
    "MV": ("transform.translate", {}, "Move"),
    "RO": ("transform.rotate", {}, "Rotate"),
    "CO": ("bim.override_object_duplicate_move_macro", {}, "Copy"),
    "CC": ("bim.override_object_duplicate_move_macro", {}, "Copy"),
    "DE": ("bsbim.delete_elements", {}, "Delete"),
    "HH": ("bsbim.temp_hide", {"mode": "HIDE"}, "Hide Element (temporary)"),
    "HI": ("bsbim.temp_hide", {"mode": "ISOLATE"}, "Isolate Element (temporary)"),
    "HR": ("bsbim.temp_hide", {"mode": "RESET"}, "Reset Temporary Hide/Isolate"),
    "ZF": ("view3d.view_all", {}, "Zoom to Fit"),
    "ZE": ("view3d.view_all", {}, "Zoom to Fit"),
    "ZA": ("view3d.view_all", {}, "Zoom All to Fit"),
}
FIRST_LETTERS = sorted({k[0] for k in SHORTCUTS})
TIMEOUT_S = 1.5

_keymaps: list = []


def resolve(typed: str) -> tuple[str | None, list[str]]:
    """(complete shortcut or None, shortcuts still possible). Pure logic, unit-tested."""
    typed = typed.upper()
    exact = typed if typed in SHORTCUTS else None
    candidates = sorted(k for k in SHORTCUTS if k.startswith(typed))
    return exact, candidates


class BSBIM_OT_shortcut(bpy.types.Operator):
    """Revit two-letter shortcut"""

    bl_idname = "bsbim.shortcut"
    bl_label = "Revit Shortcut"
    first: bpy.props.StringProperty()

    def invoke(self, context, event):
        if not revit_ui.revit_mode(context):
            return {"PASS_THROUGH"}
        if context.window_manager.get("bsbim_trace"):
            print("BS BIM trace: shortcut started with", self.first)
        self.typed = self.first
        self.started = time.monotonic()
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        self._show(context)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _show(self, context):
        _, cands = resolve(self.typed)
        hints = ", ".join(f"{k} {SHORTCUTS[k][2]}" for k in cands)
        context.workspace.status_text_set(f"Shortcut {self.typed}_  ({hints})")

    def _end(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        if event.type == "TIMER":
            if time.monotonic() - self.started > TIMEOUT_S:
                self._end(context)
                return {"CANCELLED"}
            return {"RUNNING_MODAL"}
        if event.type == "ESC":
            self._end(context)
            return {"CANCELLED"}
        if event.value != "PRESS" or len(event.type) != 1 or not event.type.isalpha():
            return {"RUNNING_MODAL"} if event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"} else {"PASS_THROUGH"}
        self.typed += event.type
        exact, cands = resolve(self.typed)
        if exact and len(cands) == 1:
            self._end(context)
            run_command(context, SHORTCUTS[exact][0], SHORTCUTS[exact][1], exact)
            return {"FINISHED"}
        if not cands:
            self._end(context)
            self.report({"INFO"}, f"No shortcut {self.typed}")
            return {"CANCELLED"}
        self._show(context)
        return {"RUNNING_MODAL"}


def run_command(context, op_id: str, kwargs: dict, label: str) -> bool:
    """Run a command in the main 3D view (shortcuts and ribbon clicks have no 3D-view context)."""
    from .ribbon_draw import main_view3d
    area, region = main_view3d(context)
    module, name = op_id.split(".")
    op = getattr(getattr(bpy.ops, module), name)
    try:
        with context.temp_override(area=area, region=region):
            op("INVOKE_DEFAULT", **kwargs)
        return True
    except RuntimeError as e:
        print(f"BS BIM: {label} could not start: {e}")
        return False


class BSBIM_OT_nav(bpy.types.Operator):
    """Revit mouse: middle-drag pans, Shift + middle-drag orbits"""

    bl_idname = "bsbim.nav"
    bl_label = "Navigate"
    action: bpy.props.EnumProperty(items=[("PAN", "Pan", ""), ("ORBIT", "Orbit", "")])

    def invoke(self, context, event):
        if not revit_ui.revit_mode(context) or context.region_data is None:
            return {"PASS_THROUGH"}
        self.prev = (event.mouse_region_x, event.mouse_region_y)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "MIDDLEMOUSE" and event.value == "RELEASE":
            return {"FINISHED"}
        if event.type in {"ESC", "LEFTMOUSE", "RIGHTMOUSE"}:
            return {"FINISHED", "PASS_THROUGH"}
        if event.type not in {"MOUSEMOVE", "INBETWEEN_MOUSEMOVE"}:
            return {"PASS_THROUGH"}
        now = (event.mouse_region_x, event.mouse_region_y)
        rv3d, region = context.region_data, context.region
        if self.action == "PAN":
            from bpy_extras import view3d_utils
            a = view3d_utils.region_2d_to_location_3d(region, rv3d, self.prev, rv3d.view_location)
            b = view3d_utils.region_2d_to_location_3d(region, rv3d, now, rv3d.view_location)
            rv3d.view_location = rv3d.view_location + (a - b)
        else:
            from math import radians
            from mathutils import Quaternion, Vector
            dx, dy = now[0] - self.prev[0], now[1] - self.prev[1]
            turn = Quaternion(Vector((0, 0, 1)), radians(-dx * 0.4))
            tilt = Quaternion(rv3d.view_rotation @ Vector((1, 0, 0)), radians(dy * 0.4))
            rv3d.view_rotation = turn @ tilt @ rv3d.view_rotation
        self.prev = now
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}


PICK_PIXELS = 6


def pick(context, x: float, y: float):
    """Revit-style pick: the element whose on-screen outline is under (x, y), with a small tolerance.

    Overlapping elements: the smallest on screen wins (a column under a beam, like Revit's
    preference for the most specific element).
    """
    from bpy_extras import view3d_utils
    import bonsai.tool as tool
    region, rv3d = context.region, context.region_data
    best, best_area = None, None
    trace = bpy.context.window_manager.get("bsbim_trace")
    if trace:
        print("BS BIM trace: pick region", region.type, region.width, region.height,
              "visible", len(context.visible_objects))
    for obj in context.visible_objects:
        if obj.type != "MESH":
            continue
        e = tool.Ifc.get_entity(obj)
        if e is None or not e.is_a("IfcElement"):
            continue
        pts = [view3d_utils.location_3d_to_region_2d(region, rv3d, obj.matrix_world @ v.co)
               for v in obj.data.vertices]
        pts = [p for p in pts if p is not None]
        if not pts:
            continue
        x0, x1 = min(p.x for p in pts) - PICK_PIXELS, max(p.x for p in pts) + PICK_PIXELS
        y0, y1 = min(p.y for p in pts) - PICK_PIXELS, max(p.y for p in pts) + PICK_PIXELS
        if trace and e.is_a("IfcColumn"):
            print("BS BIM trace:  ", obj.name, "screen box", round(x0), round(y0), round(x1), round(y1))
        if x0 <= x <= x1 and y0 <= y <= y1:
            area = (x1 - x0) * (y1 - y0)
            if best_area is None or area < best_area:
                best, best_area = obj, area
    return best


class BSBIM_OT_select(bpy.types.Operator):
    """Revit selection: click selects, Ctrl + click adds, Shift + click removes, empty space clears"""

    bl_idname = "bsbim.select"
    bl_label = "Select"
    bl_options = {"REGISTER", "UNDO"}
    mode: bpy.props.EnumProperty(items=[("SET", "Set", ""), ("ADD", "Add", ""), ("REMOVE", "Remove", "")])

    def invoke(self, context, event):
        if not revit_ui.revit_mode(context) or context.region_data is None or context.mode != "OBJECT":
            return {"PASS_THROUGH"}
        obj = pick(context, event.mouse_region_x, event.mouse_region_y)
        if context.window_manager.get("bsbim_trace"):
            print("BS BIM trace: select", self.mode, "at", event.mouse_region_x, event.mouse_region_y, "->", obj and obj.name)
        if self.mode == "SET":
            for o in context.selected_objects:
                o.select_set(False)
        if obj is not None:
            obj.select_set(self.mode != "REMOVE")
            if self.mode != "REMOVE":
                context.view_layer.objects.active = obj
        elif self.mode == "SET":
            context.view_layer.objects.active = None
        return {"FINISHED"}


class BSBIM_OT_delete_elements(bpy.types.Operator):
    """Delete: remove the selected elements at once, like Revit (no confirmation pop-up)"""

    bl_idname = "bsbim.delete_elements"
    bl_label = "Delete"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects) and context.mode == "OBJECT"

    def invoke(self, context, event):
        if not revit_ui.revit_mode(context):
            return {"PASS_THROUGH"}
        return self.execute(context)

    def execute(self, context):
        n = len(context.selected_objects)
        bpy.ops.bim.override_object_delete("EXEC_DEFAULT")  # Bonsai also removes them from the IFC
        self.report({"INFO"}, f"Deleted {n} element{'s' if n != 1 else ''}")
        return {"FINISHED"}


class BSBIM_OT_temp_hide(bpy.types.Operator):
    """Temporary Hide/Isolate (HH, HI, HR)"""

    bl_idname = "bsbim.temp_hide"
    bl_label = "Temporary Hide/Isolate"
    mode: bpy.props.EnumProperty(items=[("HIDE", "Hide", ""), ("ISOLATE", "Isolate", ""), ("RESET", "Reset", "")])

    def execute(self, context):
        if self.mode == "RESET":
            for obj in context.view_layer.objects:
                if obj.get("bsbim_temp_hidden"):
                    obj.hide_set(False)
                    del obj["bsbim_temp_hidden"]
            return {"FINISHED"}
        selected = set(context.selected_objects)
        if not selected:
            self.report({"INFO"}, "Select elements first")
            return {"CANCELLED"}
        targets = selected if self.mode == "HIDE" else [o for o in context.visible_objects if o not in selected]
        for obj in targets:
            if obj.type == "MESH":
                obj["bsbim_temp_hidden"] = True
                obj.hide_set(True)
        return {"FINISHED"}


classes = (BSBIM_OT_shortcut, BSBIM_OT_nav, BSBIM_OT_select, BSBIM_OT_delete_elements, BSBIM_OT_temp_hide)


def register_keymaps():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:  # background mode
        return
    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
    items = [
        km.keymap_items.new("bsbim.nav", "MIDDLEMOUSE", "PRESS"),
        km.keymap_items.new("bsbim.nav", "MIDDLEMOUSE", "PRESS", shift=True),
        km.keymap_items.new("bsbim.select", "LEFTMOUSE", "CLICK", ctrl=True),
        km.keymap_items.new("bsbim.select", "LEFTMOUSE", "CLICK", shift=True),
        km.keymap_items.new("bsbim.select", "LEFTMOUSE", "CLICK"),
    ]
    items[0].properties.action = "PAN"
    items[1].properties.action = "ORBIT"
    items[2].properties.mode = "ADD"
    items[3].properties.mode = "REMOVE"
    items[4].properties.mode = "SET"
    items.append(km.keymap_items.new("bsbim.delete_elements", "DEL", "PRESS"))
    for letter in FIRST_LETTERS:
        kmi = km.keymap_items.new("bsbim.shortcut", letter, "PRESS")
        kmi.properties.first = letter
        items.append(kmi)
    _keymaps.extend((km, kmi) for kmi in items)


def unregister_keymaps():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
