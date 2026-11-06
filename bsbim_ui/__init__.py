"""BS BIM: Blender extension (UI layer).

This package is the thin GPL user-interface layer. Business logic lives in
bsbim_core (vendored into the built extension by tools/build_extension.py).
"""

import bpy

from . import operators, prefs, ui

_classes = (prefs.BsbimPreferences, *operators.classes, *ui.classes)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_editor_menus.append(ui.draw_topbar)


def unregister():
    bpy.types.TOPBAR_MT_editor_menus.remove(ui.draw_topbar)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
