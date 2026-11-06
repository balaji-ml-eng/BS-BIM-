"""Headless structural workflow test inside Blender + Bonsai + BS BIM.

    blender.exe -b --python tools/blender_structure_test.py -- <work_dir>

Builds a 20' x 30' steel bay the Revit way and checks levels, types, containment and geometry.
Prints STRUCTURE PASS / STRUCTURE FAIL.
"""

import sys
import tempfile
import traceback
from importlib import import_module
from pathlib import Path

import bpy

work = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else Path(tempfile.mkdtemp())
work.mkdir(parents=True, exist_ok=True)
results = []
FT = 0.3048  # metres per foot


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


def near(a, b, tol=1e-3):
    return abs(a - b) <= tol


def z_range(obj):
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
    return min(zs), max(zs)


def xy_length(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    return max(max(xs) - min(xs), max(ys) - min(ys))


try:
    key = next(k for k in bpy.context.preferences.addons.keys() if k.endswith(".bsbim"))
    structure = import_module(key + ".structure")
    import bonsai.tool as tool
    import ifcopenshell.util.element as E

    ifc_path = work / "bay.ifc"
    res = bpy.ops.bsbim.new_project(filepath=str(ifc_path), project_name="Bay Test", template="us_structural")
    check("new US project", res == {"FINISHED"})
    f = tool.Ifc.get()
    types = {(t.ElementType, t.Name): t for t in f.by_type("IfcElementType")}
    col_type = types[("W Shapes-Column", "W10x33")]
    beam_type = types[("W Shapes", "W12x26")]

    l1, l2 = structure.level_named("Level 1"), structure.level_named("Level 2")
    check("level heights", near(structure.level_z(l1), 0.0) and near(structure.level_z(l2), 10 * FT),
          (structure.level_z(l1), structure.level_z(l2)))

    # Revit: placing columns in the Level 2 plan with Depth -> they run from Level 1 up to Level 2
    corners = [(0, 0), (20 * FT, 0), (20 * FT, 30 * FT), (0, 30 * FT)]
    cols = [structure.place_column(col_type, x, y, l2) for x, y in corners]
    check("4 columns created", len(f.by_type("IfcColumn")) == 4)
    zmin, zmax = z_range(cols[0])
    check("column runs Level 1 -> Level 2", near(zmin, 0.0) and near(zmax, 10 * FT), (round(zmin, 4), round(zmax, 4)))
    c0 = tool.Ifc.get_entity(cols[0])
    check("column type W10x33", E.get_type(c0) == col_type)
    check("column hosted on base level", E.get_container(c0) == l1, E.get_container(c0).Name)

    # Revit: beams drawn in Level 2 plan, z-Justification Top -> top of steel at Level 2
    beams = [structure.place_beam(beam_type, corners[i], corners[(i + 1) % 4], l2) for i in range(4)]
    check("4 beams created", len(f.by_type("IfcBeam")) == 4)
    bzmin, bzmax = z_range(beams[0])
    depth = 12.2 * 0.0254
    check("beam top at Level 2", near(bzmax, 10 * FT, 2e-3), round(bzmax, 4))
    check("beam depth = W12x26 depth", near(bzmax - bzmin, depth, 2e-3), round(bzmax - bzmin, 4))
    check("beam 1 length 20'", near(xy_length(beams[0]), 20 * FT, 0.01), round(xy_length(beams[0]) / FT, 3))
    check("beam 2 length 30'", near(xy_length(beams[1]), 30 * FT, 0.01), round(xy_length(beams[1]) / FT, 3))
    b0 = tool.Ifc.get_entity(beams[0])
    check("beam type W12x26", E.get_type(b0) == beam_type)
    check("beam on Level 2", E.get_container(b0) == l2)

    # Errors a Revit user could hit
    try:
        structure.place_column(col_type, 0, 0, l1, mode="DEPTH")
        check("Depth on lowest level refused", False)
    except ValueError as e:
        check("Depth on lowest level refused", "no level below" in str(e), str(e))
    try:
        structure.place_beam(beam_type, (1, 1), (1, 1), l2)
        check("zero-length beam refused", False)
    except ValueError:
        check("zero-length beam refused", True)

    # Level (LL) and Grid (GR) commands
    tools = import_module(key + ".tools")
    l3 = tools.add_level("Level 3", 20 * FT)
    check("Level 3 added", near(structure.level_z(l3), 20 * FT) and near(l3.Elevation, 20.0),
          (round(structure.level_z(l3), 4), l3.Elevation))
    check("Level 3 in the building", E.get_aggregate(l3) == f.by_type("IfcBuilding")[0])
    try:
        tools.add_level("Level 3", 30 * FT)
        check("duplicate level refused", False)
    except ValueError:
        check("duplicate level refused", True)
    upper = structure.place_column(col_type, 0, 0, l3)
    uz = z_range(upper)
    check("column on Level 3 runs Level 2 -> Level 3", near(uz[0], 10 * FT) and near(uz[1], 20 * FT),
          (round(uz[0] / FT, 3), round(uz[1] / FT, 3)))

    grid = tools.add_grid(4, 20 * FT, 3, 30 * FT)
    tags_v = [a.AxisTag for a in grid.VAxes]
    tags_u = [a.AxisTag for a in grid.UAxes]
    check("grid numbered 1-4", tags_v == ["1", "2", "3", "4"], tags_v)
    check("grid lettered A-C", tags_u == ["A", "B", "C"], tags_u)
    snaps = tools.snap_points()
    inter = [p for p in snaps if any(near(p.x, i * 20 * FT, 1e-3) and near(p.y, j * 30 * FT, 1e-3)
                                     for i in range(4) for j in range(3))]
    check("snap points at all 12 grid intersections", len({(round(p.x, 3), round(p.y, 3)) for p in inter}) == 12,
          len(snaps))
    check("Revit length format", tools.fmt_m(10.5 * FT) == "10' - 6\"", tools.fmt_m(10.5 * FT))
    check("Revit length input", near(tools.parse_to_m("20' 6\""), 20.5 * FT))

    # Saved IFC must carry the same data (what other software sees)
    bpy.ops.bim.save_project(filepath=str(ifc_path))
    import ifcopenshell
    g = ifcopenshell.open(str(ifc_path))
    gcol = g.by_type("IfcColumn")[0]
    solid = next(i for r in gcol.Representation.Representations for i in r.Items if i.is_a("IfcExtrudedAreaSolid"))
    check("saved column depth 10 ft (project units)", near(solid.Depth, 10.0, 1e-4), solid.Depth)
    check("saved beam types", {E.get_type(b).Name for b in g.by_type("IfcBeam")} == {"W12x26"})
    check("saved columns are W10x33", {E.get_type(c).Name for c in g.by_type("IfcColumn")} == {"W10x33"})
except Exception:
    traceback.print_exc()
    results.append(False)

ok = bool(results) and all(results)
print("STRUCTURE PASS" if ok else "STRUCTURE FAIL")
sys.stdout.flush()
sys.exit(0 if ok else 1)
