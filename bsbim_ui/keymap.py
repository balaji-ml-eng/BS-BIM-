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
    "DE": ("bim.override_object_delete", {}, "Delete"),
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
            op_id, kwargs, _ = SHORTCUTS[exact]
            module, name = op_id.split(".")
            op = getattr(getattr(bpy.ops, module), name)
            try:
                op("INVOKE_DEFAULT", **kwargs)
            except RuntimeError as e:
                self.report({"WARNING"}, f"{exact}: {e}")
            return {"FINISHED"}
        if not cands:
            self._end(context)
            self.report({"INFO"}, f"No shortcut {self.typed}")
            return {"CANCELLED"}
        self._show(context)
        return {"RUNNING_MODAL"}


class BSBIM_OT_nav(bpy.types.Operator):
    """Revit mouse: middle-drag pans, Shift + middle-drag orbits"""

    bl_idname = "bsbim.nav"
    bl_label = "Navigate"
    action: bpy.props.EnumProperty(items=[("PAN", "Pan", ""), ("ORBIT", "Orbit", "")])

    def invoke(self, context, event):
        if not revit_ui.revit_mode(context):
            return {"PASS_THROUGH"}
        if self.action == "PAN":
            bpy.ops.view3d.move("INVOKE_DEFAULT")
        else:
            bpy.ops.view3d.rotate("INVOKE_DEFAULT")
        return {"FINISHED"}


class BSBIM_OT_select(bpy.types.Operator):
    """Revit selection: Ctrl + click adds, Shift + click removes"""

    bl_idname = "bsbim.select"
    bl_label = "Select"
    mode: bpy.props.EnumProperty(items=[("ADD", "Add", ""), ("REMOVE", "Remove", "")])

    def invoke(self, context, event):
        if not revit_ui.revit_mode(context):
            return {"PASS_THROUGH"}
        if self.mode == "ADD":
            bpy.ops.view3d.select("INVOKE_DEFAULT", extend=True)
        else:
            bpy.ops.view3d.select("INVOKE_DEFAULT", deselect=True)
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


classes = (BSBIM_OT_shortcut, BSBIM_OT_nav, BSBIM_OT_select, BSBIM_OT_temp_hide)


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
    ]
    items[0].properties.action = "PAN"
    items[1].properties.action = "ORBIT"
    items[2].properties.mode = "ADD"
    items[3].properties.mode = "REMOVE"
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
