"""Real UI test: drive BS BIM with simulated mouse clicks and key presses, like a user would.

    blender.exe --enable-event-simulate --python tools/ui_interaction_test.py -- project.ifc out_dir

While this runs Blender ignores the real mouse and keyboard. Every step injects input events
into the window, waits for Blender to process them, then checks the IFC model / screen state.
Prints [PASS]/[FAIL] per check and INTERACTION PASS / INTERACTION FAIL at the end.
"""

import sys
import traceback
from importlib import import_module
from pathlib import Path

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
PROJECT, OUT = Path(args[0]), Path(args[1])
OUT.mkdir(parents=True, exist_ok=True)
FT = 0.3048
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)


def win():
    return bpy.context.window_manager.windows[0]


def bsbim(module):
    key = next(k for k in bpy.context.preferences.addons.keys() if k.endswith(".bsbim"))
    return import_module(f"{key}.{module}")


def ifc():
    import bonsai.tool as tool
    return tool.Ifc.get()


def count(cls):
    f = ifc()
    return len(f.by_type(cls)) if f else 0


def shot(name):
    w = win()
    area = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    with bpy.context.temp_override(window=w, screen=w.screen, area=area):
        bpy.ops.screen.screenshot(filepath=str(OUT / name), check_existing=False)


def ribbon_area():
    return next((a for a in win().screen.areas if a.type == "TEXT_EDITOR"), None)


def view_area():
    return max((a for a in win().screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)


def view_region():
    return next(r for r in view_area().regions if r.type == "WINDOW")


# ---------------------------------------------------------------- input simulation
_mouse = {"x": 0, "y": 0}


def move(x, y):
    _mouse["x"], _mouse["y"] = int(x), int(y)
    win().event_simulate(type="MOUSEMOVE", value="NOTHING", x=int(x), y=int(y))


def click(x, y, button="LEFTMOUSE"):
    move(x, y)
    win().event_simulate(type=button, value="PRESS", x=int(x), y=int(y))
    win().event_simulate(type=button, value="RELEASE", x=int(x), y=int(y))


def key(k):
    """Key press at the current mouse position (real key events always carry it)."""
    w = win()
    w.event_simulate(type=k, value="PRESS", x=_mouse["x"], y=_mouse["y"])
    w.event_simulate(type=k, value="RELEASE", x=_mouse["x"], y=_mouse["y"])


def ribbon_button(label):
    """Window coordinates of a ribbon button's centre, from the last ribbon draw."""
    rd = bsbim("ribbon_draw")
    area = ribbon_area()
    region = next(r for r in area.regions if r.type == "WINDOW")
    for x0, y0, x1, y1, c in rd._hit:
        if c.label == label:
            return region.x + (x0 + x1) / 2, region.y + (y0 + y1) / 2
    return None


def world_to_window(x, y, z):
    region = view_region()
    rv3d = view_area().spaces.active.region_3d
    p = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector((x, y, z)))
    return (region.x + p.x, region.y + p.y) if p is not None else None


def modal_running(idname):
    return any(op.bl_idname == idname for op in win().modal_operators)


# ---------------------------------------------------------------- steps
state = {}


def s_wait_ribbon():
    if ribbon_area() is None or not bsbim("ribbon_draw")._hit:
        return "again"
    check("ribbon strip present at start", True)


def s_load():
    w = win()
    with bpy.context.temp_override(window=w, screen=w.screen, area=view_area(), region=view_region()):
        bpy.ops.bim.load_project(filepath=str(PROJECT))


def s_wait_after_load():
    if ifc() is None or ribbon_area() is None or not bsbim("ribbon_draw")._hit or view_area().spaces.active.show_region_toolbar:
        return "again"
    check("project loaded, BS BIM screen rebuilt", ifc() is not None)
    labels = [c.label for *_, c in bsbim("ribbon_draw")._hit]
    check("Structure ribbon shows Revit buttons", labels[:9] == ["Modify", "Beam", "Wall", "Column", "Floor", "Truss",
                                                                  "Brace", "Beam System", "Connection"], labels[:9])


def s_plan():
    w = win()
    with bpy.context.temp_override(window=w, screen=w.screen, area=view_area(), region=view_region()):
        bpy.ops.bsbim.open_view(kind="PLAN", level="Level 2")
        # frame a 40' x 40' area so clicks land at known places
        rv3d = view_area().spaces.active.region_3d
        rv3d.view_location = Vector((15 * FT, 15 * FT, 10 * FT))
        rv3d.view_distance = 60 * FT
    check("Level 2 plan opened", bpy.context.window_manager.bsbim_active_view == "PLAN:Level 2")


def s_click_column_button():
    pos = ribbon_button("Column")
    check("Column button found on ribbon", pos is not None, pos)
    click(*pos)


def s_column_tool_running():
    check("clicking ribbon Column starts the Column tool", modal_running("BSBIM_OT_place_column"),
          [op.bl_idname for op in win().modal_operators])
    state["cols"] = count("IfcColumn")
    for x, y in ((0, 0), (20 * FT, 0)):
        p = world_to_window(x, y, 10 * FT)
        click(*p)


def s_columns_placed():
    n = count("IfcColumn") - state["cols"]
    check("two clicks in the plan placed 2 columns", n == 2, n)
    key("ESC")


def s_beam_button():
    check("Esc ends the Column tool", not modal_running("BSBIM_OT_place_column"))
    state["beams"] = count("IfcBeam")
    click(*ribbon_button("Beam"))


def s_beam_clicks():
    check("clicking ribbon Beam starts the Beam tool", modal_running("BSBIM_OT_place_beam"))
    click(*world_to_window(0, 0, 10 * FT))
    click(*world_to_window(20 * FT, 0, 10 * FT))


def s_beam_placed():
    n = count("IfcBeam") - state["beams"]
    check("start + end click placed 1 beam", n == 1, n)
    if n:
        import bonsai.tool as tool
        beam = ifc().by_type("IfcBeam")[-1]
        obj = tool.Ifc.get_object(beam)
        xs = [(obj.matrix_world @ v.co).x for v in obj.data.vertices]
        check("beam snapped to the two columns: length 20'", abs((max(xs) - min(xs)) / FT - 20) < 0.05,
              round((max(xs) - min(xs)) / FT, 3))
    key("ESC")
    key("ESC")


def s_shortcut_cl():
    check("Esc Esc ends the Beam tool", not modal_running("BSBIM_OT_place_beam"))
    state["cols"] = count("IfcColumn")
    bpy.context.window_manager["bsbim_trace"] = True
    move(*world_to_window(25 * FT, 25 * FT, 10 * FT))
    key("C")


def s_shortcut_second_key():
    print("after C, modal operators:", [op.bl_idname for op in win().modal_operators], flush=True)
    key("L")


def s_shortcut_click():
    check("typing C L starts the Column tool", modal_running("BSBIM_OT_place_column"),
          [op.bl_idname for op in win().modal_operators])
    click(*world_to_window(0, 30 * FT, 10 * FT))


def s_shortcut_done():
    n = count("IfcColumn") - state["cols"]
    check("CL + click placed a column", n == 1, n)
    key("ESC")
    rv3d = view_area().spaces.active.region_3d
    state["loc"] = Vector(rv3d.view_location)
    state["rot"] = rv3d.view_rotation.copy()
    cx = view_region().x + view_region().width / 2
    cy = view_region().y + view_region().height / 2
    move(cx, cy)
    win().event_simulate(type="MIDDLEMOUSE", value="PRESS", x=int(cx), y=int(cy))
    for i in range(1, 6):
        move(cx + 30 * i, cy)
    win().event_simulate(type="MIDDLEMOUSE", value="RELEASE", x=int(cx + 150), y=int(cy))


def s_pan_checked():
    rv3d = view_area().spaces.active.region_3d
    moved = (Vector(rv3d.view_location) - state["loc"]).length
    rotated = rv3d.view_rotation.rotation_difference(state["rot"]).angle
    check("middle-drag pans (Revit), it does not orbit", moved > 0.01 and rotated < 1e-3,
          f"moved {moved:.3f} m, rotated {rotated:.4f} rad")



def s_click_column():
    """Click the last column where it really is on screen now (after the pan)."""
    import bonsai.tool as tool
    col = ifc().by_type("IfcColumn")[-1]
    state["col_obj"] = tool.Ifc.get_object(col)
    p = state["col_obj"].matrix_world.translation
    click(*world_to_window(p.x, p.y, 10 * FT))


def s_selected():
    print("modal operators before select:", [op.bl_idname for op in win().modal_operators], flush=True)
    sel = bpy.context.selected_objects
    check("clicking a column selects it", state["col_obj"] in sel, [o.name for o in sel])
    labels = [c.label for *_, c in bsbim("ribbon_draw")._hit]
    check("ribbon switches to Modify tab", "Delete" in labels and "Move" in labels, labels)
    shot("ix_column_selected.png")
    state["cols"] = count("IfcColumn")
    pos = ribbon_button("Delete")
    if pos:
        click(*pos)


def s_deleted():
    n = state["cols"] - count("IfcColumn")
    check("ribbon Delete removes the column", n == 1, n)
    shot("ix_final.png")


def s_quit():
    ok = bool(results) and all(results)
    print("INTERACTION PASS" if ok else "INTERACTION FAIL", flush=True)
    bpy.ops.wm.quit_blender()


plan = [s_wait_ribbon, s_load, s_wait_after_load, s_plan, s_click_column_button, s_column_tool_running,
        s_columns_placed, s_beam_button, s_beam_clicks, s_beam_placed, s_shortcut_cl, s_shortcut_second_key, s_shortcut_click,
        s_shortcut_done, s_pan_checked, s_click_column, s_selected, s_deleted, s_quit]
tries = {"n": 0}


def run():
    if not plan:
        return None
    step = plan[0]
    try:
        again = step() == "again"
    except Exception:
        traceback.print_exc()
        check(f"step {step.__name__} ran without error", False)
        again = False
    if again and tries["n"] < 40:
        tries["n"] += 1
        return 0.5
    tries["n"] = 0
    plan.pop(0)
    return 0.6 if plan else None


bpy.app.timers.register(run, first_interval=3.0, persistent=True)
