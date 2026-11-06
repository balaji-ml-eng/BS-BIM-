"""Headless check that the installed BS BIM extension works with Bonsai.

    blender.exe -b --python tools/blender_smoke_test.py -- <work_dir>

Prints SMOKE PASS / SMOKE FAIL and exits non-zero on failure.
"""

import sys
import tempfile
import traceback
from pathlib import Path

import bpy

work = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else Path(tempfile.mkdtemp())
work.mkdir(parents=True, exist_ok=True)
results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


try:
    addons = bpy.context.preferences.addons.keys()
    bsbim_key = next((k for k in addons if k.endswith(".bsbim")), None)
    check("bsbim enabled", bsbim_key, bsbim_key or list(addons))
    check("bonsai enabled", any(k.endswith("bonsai") for k in addons))

    import bonsai.tool as tool

    ifc_path = work / "smoke_project.ifc"
    res = bpy.ops.bsbim.new_project(filepath=str(ifc_path), project_name="Smoke", template="us_structural")
    check("new_project finished", res == {"FINISHED"}, res)
    check("ifc written", ifc_path.is_file())
    f = tool.Ifc.get()
    check("bonsai has the project open", f is not None and f.by_type("IfcProject")[0].Name == "Smoke")
    storeys = sorted((s.Name, s.Elevation) for s in f.by_type("IfcBuildingStorey"))
    check("storeys", [n for n, _ in storeys] == ["Level 1", "Level 2"], storeys)
    check("template types", len(f.by_type("IfcElementType")) > 20, len(f.by_type("IfcElementType")))
    check("blender objects created", len(bpy.data.objects) > 0, f"{len(bpy.data.objects)} objects")

    res = bpy.ops.bsbim.model_report()
    from importlib import import_module
    ops_mod = import_module(bsbim_key + ".operators")
    check("model_report", res == {"FINISHED"} and any("Quality score" in l for l in ops_mod.last_report))

    fake_rvt = work / "not_revit.rvt"
    fake_rvt.write_bytes(b"this is not a revit file")
    try:  # in background mode Blender raises operator ERROR reports as RuntimeError
        res = bpy.ops.bsbim.import_rvt(filepath=str(fake_rvt))
    except RuntimeError:
        res = {"CANCELLED"}
    msg = " | ".join(ops_mod.last_report)
    check("import_rvt fails cleanly on a bad file", res == {"CANCELLED"} and "failed" in msg, msg)
    check("objects untouched after failed import", tool.Ifc.get().by_type("IfcProject")[0].Name == "Smoke")
except Exception:
    traceback.print_exc()
    results.append(False)

ok = results and all(results)
print("SMOKE PASS" if ok else "SMOKE FAIL")
sys.stdout.flush()
sys.exit(0 if ok else 1)
