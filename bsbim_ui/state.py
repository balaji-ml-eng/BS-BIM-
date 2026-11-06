"""Session state shared by the BS BIM UI: active view and level, types chosen for new elements."""

from __future__ import annotations

import bpy

from . import structure


def active_level():
    """The level of the active plan view (Revit places new elements on the current view's level)."""
    levels = structure.levels()
    if not levels:
        raise RuntimeError("The project has no levels")
    name = bpy.context.window_manager.bsbim_active_level
    return next((l for l in levels if l.Name == name), levels[0])


def register_props():
    wm = bpy.types.WindowManager
    wm.bsbim_active_view = bpy.props.StringProperty(name="Active view", default="3D")
    wm.bsbim_active_level = bpy.props.StringProperty(name="Active level", default="")
    wm.bsbim_new_column_type = bpy.props.IntProperty(default=0)
    wm.bsbim_new_beam_type = bpy.props.IntProperty(default=0)
    wm.bsbim_new_brace_type = bpy.props.IntProperty(default=0)


def unregister_props():
    for name in ("bsbim_active_view", "bsbim_active_level", "bsbim_new_column_type",
                 "bsbim_new_beam_type", "bsbim_new_brace_type"):
        delattr(bpy.types.WindowManager, name)
