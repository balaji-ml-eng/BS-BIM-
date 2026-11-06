"""Open BS BIM with a real window, take screenshots of the Revit-style screen, then quit.

    blender.exe --python tools/ui_screenshot.py -- model.ifc out_dir

Screenshots: 1_3d_view.png, 2_beam_selected.png, 3_level2_plan.png
"""

import sys
from pathlib import Path

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
MODEL, OUT = Path(args[0]), Path(args[1])
OUT.mkdir(parents=True, exist_ok=True)
steps = []


def window():
    return bpy.context.window_manager.windows[0]


def area3d():
    return next(a for a in window().screen.areas if a.type == "VIEW_3D")


def shot(name):
    win = window()
    with bpy.context.temp_override(window=win, screen=win.screen, area=area3d()):
        bpy.ops.screen.screenshot(filepath=str(OUT / name), check_existing=False)
    print("SHOT", OUT / name)


def ctx():
    win, area = window(), area3d()
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region)


def diag(tag):
    wm = bpy.context.window_manager
    for i, w in enumerate(wm.windows):
        print(f"DIAG {tag} window{i} ws={w.workspace.name} screen={w.screen.name} areas={[a.type for a in w.screen.areas]}")
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                sp = a.spaces.active
                print(f"DIAG {tag}   view3d ui={sp.show_region_ui} toolbar={sp.show_region_toolbar} persp={sp.region_3d.view_perspective}")


def step_start_shot():
    diag("start")
    shot("0_start.png")


def step_load():
    diag("before-load")
    print("WORKSPACE", window().workspace.name)
    with ctx():
        bpy.ops.bim.load_project(filepath=str(MODEL))


def step_open_3d():
    with ctx():
        bpy.ops.bsbim.open_view(kind="3D")


def step_3d():
    diag("after-load")
    shot("1_3d_view.png")


def step_select():
    import bonsai.tool as tool
    beam = next(o for o in bpy.context.view_layer.objects
                if (e := tool.Ifc.get_entity(o)) and e.is_a("IfcBeam"))
    with ctx():
        bpy.ops.object.select_all(action="DESELECT")
    beam.select_set(True)
    bpy.context.view_layer.objects.active = beam


def step_select_shot():
    shot("2_beam_selected.png")


def step_plan():
    with ctx():
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.bsbim.open_view(kind="PLAN", level="Level 2")


def step_plan_shot():
    shot("3_level2_plan.png")


def step_quit():
    print("UI SCREENSHOTS DONE")
    bpy.ops.wm.quit_blender()


plan = [step_start_shot, step_load, step_open_3d, step_3d, step_select, step_select_shot, step_plan, step_plan_shot, step_quit]


def run():
    try:
        step = plan.pop(0)
        print("STEP", step.__name__, flush=True)
        step()
        print("STEP OK", step.__name__, flush=True)
    except Exception:
        import traceback
        traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None
    return 2.0 if plan else None


bpy.app.timers.register(run, first_interval=4.0, persistent=True)  # survive project loads
