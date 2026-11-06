"""Revit-style screen for BS BIM on top of Blender.

- Top bar: BS BIM "File" menu, then the Revit tabs (Architecture, Structure, Systems, ...).
- 3D view header: the active tab's command buttons (or "Modify | <Category>" while something is selected).
- Left sidebar: Properties and Project Browser (see palette.py / browser.py).
- "Blender Mode" switches all of this off and shows Blender's normal screen again.

Blender's own header draw functions are wrapped, not replaced: in Blender mode they run unchanged.
"""

from __future__ import annotations

from pathlib import Path

import bpy

from . import ribbon

WORKSPACE = "BS BIM"
_original_draws: dict[type, object] = {}


def revit_mode(context=None) -> bool:
    wm = (context or bpy.context).window_manager
    return bool(getattr(wm, "bsbim_revit_ui", False))


def _selection_category(context) -> str | None:
    """Revit category name of the selection, or None when nothing is selected."""
    objs = getattr(context, "selected_objects", None) or []
    if not objs:
        return None
    try:
        import bonsai.tool as tool
        names = set()
        for o in objs:
            e = tool.Ifc.get_entity(o)
            names.add(CATEGORY.get(e.is_a(), e.is_a()[3:]) if e else "Object")
    except Exception:
        return "Object"
    return names.pop() if len(names) == 1 else "Multi-Select"


# IFC class -> Revit category (as shown on the contextual Modify tab)
CATEGORY = {
    "IfcBeam": "Structural Framing", "IfcMember": "Structural Framing", "IfcColumn": "Structural Columns",
    "IfcWall": "Walls", "IfcSlab": "Floors", "IfcFooting": "Structural Foundations", "IfcPile": "Structural Foundations",
    "IfcDoor": "Doors", "IfcWindow": "Windows", "IfcRoof": "Roofs", "IfcStair": "Stairs", "IfcRailing": "Railings",
    "IfcBuildingStorey": "Levels", "IfcGridAxis": "Grids", "IfcGrid": "Grids",
    "IfcDuctSegment": "Ducts", "IfcPipeSegment": "Pipes", "IfcCableCarrierSegment": "Cable Trays",
}


# ---------------------------------------------------------------- top bar: File + tabs
def _draw_topbar(self, context):
    # Blender draws the top bar in two regions (left and right); draw each part once.
    if context.region and context.region.alignment == "RIGHT":
        _draw_topbar_right(self, context)
    else:
        _draw_topbar_left(self, context)


def _draw_topbar_left(self, context):
    layout = self.layout
    wm = context.window_manager
    row = layout.row(align=True)
    row.menu("BSBIM_MT_file", text="File")
    row.separator(factor=2)
    category = _selection_category(context)
    for key, label in ribbon.TAB_LABELS.items():
        active = wm.bsbim_ribbon_tab == key and not category
        op = row.operator("bsbim.set_ribbon_tab", text=label, depress=active, emboss=active)
        op.tab = key
    if category:
        row.separator()
        sub = row.row(align=True)
        sub.alert = True  # Revit shows the contextual tab in green; Blender's closest accent
        sub.operator("bsbim.set_ribbon_tab", text=f"Modify | {category}", depress=True).tab = wm.bsbim_ribbon_tab


def _draw_topbar_right(self, context):
    layout = self.layout
    row = layout.row(align=True)
    row.operator("bim.save_project", text="", icon=ribbon.icon("FILE_TICK"))
    row.operator("ed.undo", text="", icon=ribbon.icon("LOOP_BACK"))
    row.operator("ed.redo", text="", icon=ribbon.icon("LOOP_FORWARDS"))
    layout.operator("bsbim.toggle_revit_ui", text="Blender Mode", icon=ribbon.icon("BLENDER"))


# ---------------------------------------------------------------- 3D view header: commands
def _draw_view_header(self, context):
    layout = self.layout
    if _selection_category(context):
        ribbon.draw_commands(layout, ribbon.MODIFY)
    else:
        ribbon.draw_commands(layout, ribbon.TABS[context.window_manager.bsbim_ribbon_tab])


def _wrap(cls, revit_draw):
    original = cls.draw
    _original_draws[cls] = original

    def draw(self, context):
        if revit_mode(context):
            revit_draw(self, context)
        else:
            original(self, context)

    draw._bsbim_wrapper = True
    cls.draw = draw


def install_headers():
    _wrap(bpy.types.TOPBAR_HT_upper_bar, _draw_topbar)
    _wrap(bpy.types.VIEW3D_HT_header, _draw_view_header)


def uninstall_headers():
    for cls, original in _original_draws.items():
        cls.draw = original
    _original_draws.clear()


# ---------------------------------------------------------------- Bonsai's own workspace
def set_bonsai_workspace_switching(enabled: bool) -> None:
    """Bonsai switches to its "BIM" workspace whenever a project opens. In Revit mode BS BIM owns
    the screen, so that is turned off; Blender mode turns it back on."""
    for key, addon in bpy.context.preferences.addons.items():
        if key.endswith("bonsai") and addon.preferences is not None:
            prefs = addon.preferences
            for name in ("should_setup_workspace", "activate_workspace"):
                if hasattr(prefs, name):
                    setattr(prefs, name, enabled)


# ---------------------------------------------------------------- screen layout
def _areas(screen, kind):
    return [a for a in screen.areas if a.type == kind]


def setup_layout(window) -> str:
    """Make the BS BIM workspace: one big 3D view with Properties + Project Browser on the left.

    Works on a copy of the current workspace, so Blender's own "Layout" workspace stays untouched.
    Returns a short report.
    """
    if WORKSPACE in bpy.data.workspaces:
        window.workspace = bpy.data.workspaces[WORKSPACE]
        return "BS BIM workspace activated"
    before = set(bpy.data.workspaces)
    with bpy.context.temp_override(window=window, screen=window.screen):
        bpy.ops.workspace.duplicate()
    new = next(iter(set(bpy.data.workspaces) - before), None)
    if new is None:
        return "Could not create the BS BIM workspace"
    new.name = WORKSPACE
    window.workspace = new
    # Blender switches the window's screen on its next refresh: arrange the screen after that.
    tries = {"n": 0}

    def arrange():
        # window.workspace changes at once, but window.screen only after Blender's next refresh
        if not any(s == window.screen for s in new.screens) and tries["n"] < 30:
            tries["n"] += 1
            return 0.1
        print("BS BIM:", arrange_screen(window), "on screen", window.screen.name)
        return None

    bpy.app.timers.register(arrange, first_interval=0.1, persistent=True)
    return "BS BIM workspace created"


def arrange_screen(window) -> str:
    """Close Blender's side editors, then add the ribbon strip and set up the 3D view (in steps)."""
    screen = window.screen
    closed = 0
    for kind in ("OUTLINER", "PROPERTIES", "DOPESHEET_EDITOR", "TIMELINE"):
        for area in _areas(screen, kind):
            with bpy.context.temp_override(window=window, screen=screen, area=area):
                if bpy.ops.screen.area_close() == {"FINISHED"}:
                    closed += 1
    apply_revit_theme()
    remove_blender_default_objects()
    _RibbonSetup(window).start()
    return f"BS BIM screen: {closed} Blender panels closed, building ribbon"


def _configure_view3d(window):
    screen = window.screen
    for area in _areas(screen, "VIEW_3D"):
        space = area.spaces.active
        # Region visibility changes need a window context; without it Blender 5.1 crashes
        # (ED_area_init -> WM_window_get_active_workspace) when called from a timer.
        with bpy.context.temp_override(window=window, screen=screen, area=area):
            space.show_region_header = False       # Revit's drawing area has no header row
            space.show_region_toolbar = False      # Revit has no tool strip on the left
            space.show_region_ui = True            # our sidebar = Properties + Project Browser
            space.show_region_tool_header = True   # Revit's Options Bar
            space.overlay.show_floor = True
            space.overlay.show_text = False        # no "User Orthographic" text; Revit shows none
        sidebar = next((r for r in area.regions if r.type == "UI"), None)
        if sidebar and sidebar.alignment == "RIGHT":
            with bpy.context.temp_override(window=window, screen=screen, area=area, region=sidebar):
                bpy.ops.screen.region_flip()


def _save_as_startup(window):
    """Save the finished BS BIM screen as Blender's start-up file (portable/config/startup.blend).

    Bonsai reloads the start-up file whenever it opens a project; with the BS BIM screen saved in it,
    nothing has to be rearranged at run time any more. Only done on a clean scene.
    """
    try:
        import bonsai.tool as tool
        if tool.Ifc.get() is not None:
            return None
    except ImportError:
        pass
    if any(o for o in bpy.data.objects):
        return None
    try:
        with bpy.context.temp_override(window=window, screen=window.screen):
            bpy.ops.wm.save_homefile()
        print("BS BIM: Revit-style screen saved as the start-up layout")
    except RuntimeError as e:
        print("BS BIM: could not save the start-up layout:", e)
    return None


class _RibbonSetup:
    """Split a ribbon strip off the top of the 3D view, one step per Blender refresh.

    Area sizes and positions only update after Blender redraws, so each step re-reads them.
    """

    def __init__(self, window):
        self.window = window
        self.step = "split"
        self.tries = 0
        self.sign = 1

    def start(self):
        bpy.app.timers.register(self.tick, first_interval=0.1, persistent=True)

    def _pair(self):
        screen = self.window.screen
        areas = [a for a in screen.areas if a.type in ("VIEW_3D", "TEXT_EDITOR")]
        if len(areas) < 2:
            return None, None
        areas.sort(key=lambda a: a.y, reverse=True)  # window y grows upwards: first = top
        return areas[0], areas[1]

    def tick(self):
        from .ribbon_draw import RIBBON_HEIGHT, scale
        w, screen = self.window, self.window.screen
        target = RIBBON_HEIGHT * scale()
        try:
            if self.step == "split":
                if any(a.type == "TEXT_EDITOR" for a in screen.areas):
                    self.step = "size"
                    return 0.1
                view = max(_areas(screen, "VIEW_3D"), key=lambda a: a.width * a.height)
                with bpy.context.temp_override(window=w, screen=screen, area=view):
                    bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.5)
                self.step = "assign"
                return 0.1
            if self.step == "assign":
                top, bottom = self._pair()
                if top is None:
                    return 0.1
                top.type, bottom.type = "TEXT_EDITOR", "VIEW_3D"
                space = top.spaces.active
                with bpy.context.temp_override(window=w, screen=screen, area=top):
                    space.show_region_header = False
                    space.show_region_footer = False
                    space.show_region_ui = False
                    space.show_line_numbers = False
                self.step = "size"
                return 0.1
            if self.step == "size":
                top, _ = self._pair()
                diff = top.height - target
                if abs(diff) <= 3 or self.tries >= 6:
                    _configure_view3d(w)
                    print(f"BS BIM: ribbon strip {top.height}px (target {target:.0f})")
                    bpy.app.timers.register(lambda: _save_as_startup(w), first_interval=0.5, persistent=True)
                    return None
                if self.tries and abs(diff) >= abs(self.last_diff):
                    self.sign = -self.sign  # the edge moved the wrong way: reverse
                self.last_diff = diff
                self.tries += 1
                try:
                    with bpy.context.temp_override(window=w, screen=screen, area=top):
                        bpy.ops.screen.area_move(x=top.x + top.width // 2, y=top.y, delta=int(self.sign * diff))
                except RuntimeError:  # screen busy (e.g. a menu is open): try again on the next tick
                    pass
                return 0.2
        except Exception as e:  # never break Blender's start-up
            print("BS BIM: ribbon setup stopped:", e)
            _configure_view3d(w)
        return None


_THEMES = Path(bpy.utils.resource_path("LOCAL")) / "scripts" / "presets" / "interface_theme"


def apply_revit_theme():
    """Light grey interface and a white drawing area, like Revit."""
    light = _THEMES / "Blender_Light.xml"
    if light.is_file():
        bpy.ops.script.execute_preset(filepath=str(light), menu_idname="USERPREF_MT_interface_theme_presets")
    theme = bpy.context.preferences.themes[0]
    grad = theme.view_3d.space.gradients
    grad.background_type = "SINGLE_COLOR"
    grad.high_gradient = (1.0, 1.0, 1.0)
    theme.view_3d.grid = (0.85, 0.85, 0.85, 1.0)


def apply_blender_theme():
    dark = _THEMES / "Blender_Dark.xml"
    if dark.is_file():
        bpy.ops.script.execute_preset(filepath=str(dark), menu_idname="USERPREF_MT_interface_theme_presets")


def remove_blender_default_objects():
    """Revit starts empty: drop Blender's start-up cube, camera and light when no project is open."""
    try:
        import bonsai.tool as tool
        if tool.Ifc.get() is not None:
            return
    except ImportError:
        pass
    for name in ("Cube", "Camera", "Light"):
        obj = bpy.data.objects.get(name)
        if obj is not None and not obj.get("ifc_definition_id"):
            bpy.data.objects.remove(obj)


# ---------------------------------------------------------------- operators
class BSBIM_OT_set_ribbon_tab(bpy.types.Operator):
    bl_idname = "bsbim.set_ribbon_tab"
    bl_label = "Ribbon Tab"
    bl_description = "Show this ribbon tab"
    tab: bpy.props.StringProperty()

    def execute(self, context):
        if self.tab in ribbon.TABS:
            context.window_manager.bsbim_ribbon_tab = self.tab
        for area in context.screen.areas:
            area.tag_redraw()
        return {"FINISHED"}


class BSBIM_OT_toggle_revit_ui(bpy.types.Operator):
    bl_idname = "bsbim.toggle_revit_ui"
    bl_label = "Switch Revit / Blender screen"
    bl_description = "Switch between the Revit-style BS BIM screen and Blender's normal screen"

    def execute(self, context):
        wm = context.window_manager
        wm.bsbim_revit_ui = not wm.bsbim_revit_ui
        set_bonsai_workspace_switching(not wm.bsbim_revit_ui)
        if wm.bsbim_revit_ui:
            self.report({"INFO"}, setup_layout(context.window))
            apply_revit_theme()
        else:
            apply_blender_theme()
            if "Layout" in bpy.data.workspaces:
                context.window.workspace = bpy.data.workspaces["Layout"]
        return {"FINISHED"}


class BSBIM_OT_not_ready(bpy.types.Operator):
    bl_idname = "bsbim.not_ready"
    bl_label = "Coming soon"
    bl_description = "This Revit command is planned but not built yet"
    feature: bpy.props.StringProperty()

    def execute(self, context):
        self.report({"INFO"}, f"{self.feature}: coming in a later BS BIM version")
        return {"FINISHED"}


class BSBIM_MT_file(bpy.types.Menu):
    bl_idname = "BSBIM_MT_file"
    bl_label = "File"

    def draw(self, context):
        layout = self.layout
        layout.operator("bsbim.new_project", icon=ribbon.icon("FILE_NEW"))
        layout.operator("bim.load_project", text="Open...", icon=ribbon.icon("FILE_FOLDER"))
        layout.operator("bsbim.import_rvt", text="Open Revit File...", icon=ribbon.icon("FILE_3D"))
        layout.separator()
        layout.operator("bim.save_project", text="Save", icon=ribbon.icon("FILE_TICK"))
        layout.operator("bim.save_project", text="Save As...").should_save_as = True
        layout.separator()
        layout.operator("bsbim.toggle_revit_ui", text="Blender Mode", icon=ribbon.icon("BLENDER"))
        layout.operator("wm.quit_blender", text="Exit", icon=ribbon.icon("QUIT"))


classes = (BSBIM_OT_set_ribbon_tab, BSBIM_OT_toggle_revit_ui, BSBIM_OT_not_ready, BSBIM_MT_file)


def register_props():
    wm = bpy.types.WindowManager
    wm.bsbim_revit_ui = bpy.props.BoolProperty(name="Revit-style screen", default=True)
    wm.bsbim_ribbon_tab = bpy.props.EnumProperty(
        name="Ribbon tab", items=[(k, v, "") for k, v in ribbon.TAB_LABELS.items()], default="STRUCTURE")


def unregister_props():
    del bpy.types.WindowManager.bsbim_revit_ui
    del bpy.types.WindowManager.bsbim_ribbon_tab
