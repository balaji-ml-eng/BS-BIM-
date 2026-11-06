"""BS BIM: Blender extension (UI layer).

The Revit-style screen (ribbon, Properties, Project Browser, Revit mouse and shortcuts) is on by
default. "Blender Mode" (File menu or top bar) switches back to Blender's normal screen.
Business logic lives in bsbim_core (vendored into the built extension by tools/build_extension.py).
"""

import bpy
from bpy.app.handlers import persistent

from . import browser, keymap, operators, palette, prefs, revit_ui, state, tools, ui

_classes = (
    prefs.BsbimPreferences,
    *operators.classes,
    *ui.classes,
    *revit_ui.classes,
    *tools.classes,
    *browser.classes,
    *palette.classes,
    *keymap.classes,
)


def _setup_screen():
    """Build the Revit-style workspace once the window exists (not in background mode)."""
    if bpy.app.background:
        return None
    wm = bpy.context.window_manager
    if not wm.windows:
        return 0.5  # try again shortly
    if wm.bsbim_revit_ui:
        try:
            print("BS BIM:", revit_ui.setup_layout(wm.windows[0]))
        except Exception as e:  # never block Blender from starting
            print("BS BIM: could not set up the Revit-style screen:", e)
    return None


_tab_selected: set[int] = set()


def _select_bsbim_tab(window):
    """Open the sidebar on the BS BIM tab (Properties + Project Browser) once per sidebar.

    The tab can only be selected after the sidebar has drawn it, so this runs from the watcher.
    After that the user is free to pick another tab.
    """
    if window.workspace.name != revit_ui.WORKSPACE:
        return
    for area in window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        for region in area.regions:
            if region.type != "UI" or region.as_pointer() in _tab_selected:
                continue
            try:
                region.active_panel_category = "BS BIM"
                _tab_selected.add(region.as_pointer())
            except (TypeError, ValueError):
                pass  # not drawn yet; try again on the next tick


def _keep_bsbim_screen():
    """Bonsai switches to its own "BIM" workspace when a project loads; in Revit mode, switch back."""
    try:
        wm = bpy.context.window_manager
        if wm.bsbim_revit_ui and revit_ui.WORKSPACE in bpy.data.workspaces:
            target = bpy.data.workspaces[revit_ui.WORKSPACE]
            for window in wm.windows:
                if window.workspace != target and window.workspace.name.startswith("BIM"):
                    window.workspace = target
                _select_bsbim_tab(window)
    except Exception as e:  # keep the watcher alive whatever happens
        print("BS BIM screen watcher:", e)
    return 0.5


@persistent
def _on_load_post(*_args):
    """Bonsai opens projects in a fresh Blender file, which drops the BS BIM screen: rebuild it."""
    if not bpy.app.background:
        bpy.app.timers.register(_setup_screen, first_interval=0.2, persistent=True)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    revit_ui.register_props()
    state.register_props()
    bpy.types.TOPBAR_MT_editor_menus.append(ui.draw_topbar)
    revit_ui.install_headers()
    keymap.register_keymaps()
    if not bpy.app.background:
        bpy.context.preferences.inputs.use_zoom_to_mouse = True  # Revit zooms at the cursor
        bpy.app.timers.register(_setup_screen, first_interval=0.5, persistent=True)
        bpy.app.timers.register(_keep_bsbim_screen, first_interval=2.0, persistent=True)
    bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    if bpy.app.timers.is_registered(_keep_bsbim_screen):
        bpy.app.timers.unregister(_keep_bsbim_screen)
    keymap.unregister_keymaps()
    tools.unregister_draw_handler()
    revit_ui.uninstall_headers()
    bpy.types.TOPBAR_MT_editor_menus.remove(ui.draw_topbar)
    state.unregister_props()
    revit_ui.unregister_props()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
