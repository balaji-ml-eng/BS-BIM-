"""GUI test: link a point cloud in BS BIM, save, reopen, and screenshot.

    blender.exe --python tools/ui_pointcloud_test.py -- project.ifc scan.e57 out_dir
"""

import sys
import traceback
from importlib import import_module
from pathlib import Path

import bpy
from mathutils import Euler, Vector
from math import radians

args = sys.argv[sys.argv.index("--") + 1:]
PROJECT, SCAN, OUT = Path(args[0]), Path(args[1]), Path(args[2])
OUT.mkdir(parents=True, exist_ok=True)
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)


def win():
    return bpy.context.window_manager.windows[0]


def pc():
    key = next(k for k in bpy.context.preferences.addons.keys() if k.endswith(".bsbim"))
    return import_module(f"{key}.pointcloud")


def view_area():
    return max((a for a in win().screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)


def ctx():
    a = view_area()
    return bpy.context.temp_override(window=win(), screen=win().screen, area=a,
                                     region=next(r for r in a.regions if r.type == "WINDOW"))


def shot(name):
    with bpy.context.temp_override(window=win(), screen=win().screen, area=view_area()):
        bpy.ops.screen.screenshot(filepath=str(OUT / name), check_existing=False)


def frame_cloud(name):
    info = pc()._clouds[name]["info"]
    lo, hi = Vector(info["bounds_min_m"]), Vector(info["bounds_max_m"])
    rv3d = view_area().spaces.active.region_3d
    rv3d.view_location = (lo + hi) / 2
    rv3d.view_distance = (hi - lo).length * 0.9
    rv3d.view_rotation = Euler((radians(60), 0, radians(30))).to_quaternion()
    rv3d.view_perspective = "PERSP"


def ifc():
    import bonsai.tool as tool
    return tool.Ifc.get()


def s_load():
    with ctx():
        bpy.ops.bim.load_project(filepath=str(PROJECT))


def s_wait():
    if ifc() is None or not any(a.type == "TEXT_EDITOR" for a in win().screen.areas):
        return "again"


def s_link():
    with ctx():
        res = bpy.ops.bsbim.link_point_cloud(filepath=str(SCAN), units="m", max_points=3_000_000)
    check("Point Cloud command finished", res == {"FINISHED"}, res)
    clouds = pc()._clouds
    check("point cloud shown", SCAN.stem in clouds and clouds[SCAN.stem]["count"] > 100_000,
          {k: v["count"] for k, v in clouds.items()})
    links = pc().stored_links()
    check("link stored in the IFC project", any(l["name"] == SCAN.stem for l in links), [l["name"] for l in links])
    frame_cloud(SCAN.stem)


def s_shot1():
    shot("pc_1_linked.png")
    with ctx():
        bpy.ops.bim.save_project(filepath=str(PROJECT))
    # Close the project and reopen it: the link must come back
    pc()._clouds.clear()
    with ctx():
        bpy.ops.bim.load_project(filepath=str(PROJECT))


def s_after_reopen():
    if ifc() is None or not any(a.type == "TEXT_EDITOR" for a in win().screen.areas):
        return "again"
    if SCAN.stem not in pc()._clouds:
        return "again"
    check("point cloud comes back after reopening the project", True, pc()._clouds[SCAN.stem]["count"])
    frame_cloud(SCAN.stem)


def s_shot2():
    shot("pc_2_reopened.png")
    with ctx():
        bpy.ops.bsbim.point_cloud_visibility(name=SCAN.stem)
    check("hide point cloud", not pc()._clouds[SCAN.stem]["visible"])
    with ctx():
        bpy.ops.bsbim.point_cloud_visibility(name=SCAN.stem)


def s_recap():
    fake = OUT / "scan.rcs"
    fake.write_bytes(b"x")
    try:
        with ctx():
            bpy.ops.bsbim.link_point_cloud(filepath=str(fake))
        check("ReCap file refused with advice", False)
    except RuntimeError as e:
        check("ReCap file refused with advice", "Export it to E57" in str(e), str(e)[:120])


def s_quit():
    print("POINTCLOUD PASS" if results and all(results) else "POINTCLOUD FAIL", flush=True)
    bpy.ops.wm.quit_blender()


plan = [s_load, s_wait, s_link, s_shot1, s_after_reopen, s_shot2, s_recap, s_quit]
tries = {"n": 0}


def run():
    step = plan[0]
    try:
        again = step() == "again"
    except Exception:
        traceback.print_exc()
        check(f"step {step.__name__} ran without error", False)
        again = False
    if again and tries["n"] < 60:
        tries["n"] += 1
        return 0.5
    tries["n"] = 0
    plan.pop(0)
    return 1.0 if plan else None


bpy.app.timers.register(run, first_interval=3.0, persistent=True)
