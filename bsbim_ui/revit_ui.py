"""Revit-style screen for BS BIM on top of Blender.

- Top bar: BS BIM "File" menu, then the Revit tabs (Architecture, Structure, Systems, ...).
- 3D view header: the active tab's command buttons (or "Modify | <Category>" while something is selected).
- Left sidebar: Properties and Project Browser (see palette.py / browser.py).
- "Blender Mode" switches all of this off and shows Blender's normal screen again.

Blender's own header draw functions are wrapped, not replaced: in Blender mode they run unchanged.
"""

from __future__ import annotations

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
    """Close Blender's side editors and put Properties + Project Browser on the left of the 3D view."""
    screen = window.screen
    closed = 0
    for kind in ("OUTLINER", "PROPERTIES", "DOPESHEET_EDITOR", "TIMELINE"):
        for area in _areas(screen, kind):
            with bpy.context.temp_override(window=window, screen=screen, area=area):
                if bpy.ops.screen.area_close() == {"FINISHED"}:
                    closed += 1
    for area in _areas(screen, "VIEW_3D"):
        space = area.spaces.active
        # Region visibility changes need a window context; without it Blender 5.1 crashes
        # (ED_area_init -> WM_window_get_active_workspace) when called from a timer.
        with bpy.context.temp_override(window=window, screen=screen, area=area):
            space.show_region_toolbar = False      # Revit has no tool strip on the left
            space.show_region_ui = True            # our sidebar = Properties + Project Browser
            space.show_region_tool_header = True   # Revit's Options Bar
            space.overlay.show_floor = True
            space.overlay.show_text = False        # no "User Orthographic" text; Revit shows none
        sidebar = next((r for r in area.regions if r.type == "UI"), None)
        if sidebar and sidebar.alignment == "RIGHT":
            with bpy.context.temp_override(window=window, screen=screen, area=area, region=sidebar):
                bpy.ops.screen.region_flip()
        for region in area.regions:
            if region.type == "UI":
                try:
                    region.active_panel_category = "BS BIM"
                except (AttributeError, TypeError, ValueError):
                    pass
    return f"BS BIM screen arranged ({closed} Blender panels closed)"


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
        if wm.bsbim_revit_ui:
            self.report({"INFO"}, setup_layout(context.window))
        elif "Layout" in bpy.data.workspaces:
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
