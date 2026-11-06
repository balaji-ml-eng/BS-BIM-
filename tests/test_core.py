from __future__ import annotations

import ifcopenshell
import ifcopenshell.util.element as E
import ifcopenshell.util.unit
import pytest

from bsbim_core import project, report, steel, template
from bsbim_core.__main__ import main as core_main
from bsbim_core.units import format_feet_inches, parse_length

from .conftest import sample_model_with_walls


def _types(f):
    return {(t.ElementType, t.Name): t for t in f.by_type("IfcElementType")}


def test_us_project_units_levels():
    f = project.create_project(project.ProjectSettings(name="Demo", template="us_structural"))
    assert f.by_type("IfcProject")[0].Name == "Demo"
    assert ifcopenshell.util.unit.calculate_unit_scale(f) == pytest.approx(0.3048)  # feet
    assert project.unit_system(f) == "imperial"
    storeys = f.by_type("IfcBuildingStorey")
    assert [(s.Name, s.Elevation) for s in storeys] == [("Level 1", 0.0), ("Level 2", 10.0)]
    building = f.by_type("IfcBuilding")[0]
    assert E.get_aggregate(building) == f.by_type("IfcSite")[0]
    for s in storeys:
        assert E.get_aggregate(s) == building
        assert s.ObjectPlacement.RelativePlacement.Location.Coordinates[2] == pytest.approx(s.Elevation)


def test_us_steel_types_match_aisc():
    f = project.create_project(project.ProjectSettings(template="us_structural"))
    types = _types(f)
    beam = types[("W Shapes", "W12x26")]
    assert beam.is_a("IfcBeamType") and beam.PredefinedType == "BEAM"
    mp = E.get_material(beam)
    assert mp.is_a("IfcMaterialProfileSet")
    prof = mp.MaterialProfiles[0]
    assert prof.Material.Name == "Steel ASTM A992"
    # AISC W12x26: d = 12.2 in, bf = 6.49 in, tw = 0.230 in, tf = 0.380 in (project unit = feet)
    p = prof.Profile
    assert p.is_a("IfcIShapeProfileDef") and p.ProfileName == "W12x26"
    assert p.OverallDepth * 12 == pytest.approx(12.2, abs=0.01)
    assert p.OverallWidth * 12 == pytest.approx(6.49, abs=0.01)
    assert p.WebThickness * 12 == pytest.approx(0.23, abs=0.001)
    assert p.FlangeThickness * 12 == pytest.approx(0.38, abs=0.001)
    col = types[("W Shapes-Column", "W10x33")]
    assert col.is_a("IfcColumnType")
    hss = types[("HSS-Hollow Structural Section-Column", "HSS6x6x3/8")]
    assert E.get_material(hss).MaterialProfiles[0].Profile.is_a("IfcRectangleHollowProfileDef")
    assert types[("HSS-Hollow Structural Section", "HSS6x6x3/8")].PredefinedType == "BRACE"
    conc = types[("Concrete-Rectangular Beam", "12 x 24")]
    rp = E.get_material(conc).MaterialProfiles[0].Profile
    assert (rp.XDim, rp.YDim) == (pytest.approx(1.0), pytest.approx(2.0))  # feet


def test_us_layered_types():
    f = project.create_project(project.ProjectSettings(template="us_structural"))
    floor = _types(f)[("Floor", '6" Concrete')]
    layers = E.get_material(floor).MaterialLayers
    assert [(l.Material.Name, l.LayerThickness) for l in layers] == [("Concrete, Normal Weight - 4 ksi", pytest.approx(0.5))]
    assert set(f.by_type("IfcRelDeclares")[0].RelatedDefinitions) == set(f.by_type("IfcElementType"))


def test_uk_project_metric_concrete():
    f = project.create_project(project.ProjectSettings(template="uk_structural"))
    assert ifcopenshell.util.unit.calculate_unit_scale(f) == pytest.approx(0.001)
    assert project.unit_system(f) == "metric"
    assert [(s.Name, s.Elevation) for s in f.by_type("IfcBuildingStorey")] == [("Level 1", 0.0), ("Level 2", 4000.0)]
    col = _types(f)[("M_Concrete-Rectangular-Column", "400 x 400mm")]
    assert E.get_material(col).MaterialProfiles[0].Material.Name == "Concrete, Cast-in-Place - C40"
    wall = _types(f)[("Basic Wall", "Concrete 200mm")]
    assert E.get_material(wall).MaterialLayers[0].LayerThickness == 200.0


def test_every_template_type_has_a_material_set():
    for key in template.TEMPLATES:
        f = project.create_project(project.ProjectSettings(template=key))
        tpl = template.TEMPLATES[key]
        assert len(f.by_type("IfcElementType")) == len(tpl.profile_types) + len(tpl.layered_types)
        for t in f.by_type("IfcElementType"):
            assert E.get_material(t) is not None, t.Name
            assert t.ElementType, t.Name


def test_add_level_and_errors():
    f = project.create_project(project.ProjectSettings(template="us_structural", include_types=False))
    roof = project.add_level(f, "Roof", 24.0)
    assert roof.Elevation == 24.0 and E.get_aggregate(roof) == f.by_type("IfcBuilding")[0]
    with pytest.raises(ValueError, match="already exists"):
        project.add_level(f, "Roof", 30.0)
    with pytest.raises(ValueError, match="Unknown template"):
        project.create_project(project.ProjectSettings(template="nope"))
    with pytest.raises(ValueError):
        project.create_project(project.ProjectSettings(levels=[]))
    with pytest.raises(ValueError):
        project.create_project(project.ProjectSettings(levels=[("A", 0), ("A", 10)]))


@pytest.mark.parametrize("lib,name,family_beam,family_col", [
    ("W12X26", "W12x26", "W Shapes", "W Shapes-Column"),
    ("HSS6X6X.375", "HSS6x6x3/8", "HSS-Hollow Structural Section", "HSS-Hollow Structural Section-Column"),
    ("C10X15.3", "C10X15.3", "C Shapes", "C Shapes"),
    ("L4X4X1_2", "L4x4x1/2", "L-Angle", "L-Angle"),
])
def test_revit_steel_names(lib, name, family_beam, family_col):
    assert steel.revit_type_name(lib) == name
    assert steel.revit_family(lib, "beam") == family_beam
    assert steel.revit_family(lib, "column") == family_col


def test_steel_library_size():
    s = steel.shapes()
    assert len(s) > 1000 and "W44X335" in s and "HSS20X.500" in s


@pytest.mark.parametrize("feet,text", [
    (10.0, "10' - 0\""), (10.5, "10' - 6\""), (0.0, "0' - 0\""), (1 / 12 * 3.5, "0' - 3 1/2\""),
    (-2.0, "-2' - 0\""), (12.2 / 12, "1' - 0 51/256\""), (1 / 24, "0' - 0 1/2\""),
])
def test_format_feet_inches(feet, text):
    assert format_feet_inches(feet) == text


@pytest.mark.parametrize("text,system,value", [
    ("10'", "imperial", 10.0), ("10' 6\"", "imperial", 10.5), ("10'-6\"", "imperial", 10.5),
    ("10' - 6 1/2\"", "imperial", 10 + 6.5 / 12), ("6\"", "imperial", 0.5), ("3 1/2\"", "imperial", 3.5 / 12),
    ("10.5", "imperial", 10.5), ("1/2\"", "imperial", 1 / 24), ("-2'", "imperial", -2.0),
    ("4000", "metric", 4000.0), ("4000 mm", "metric", 4000.0), ("4.2m", "metric", 4200.0), ("40 cm", "metric", 400.0),
])
def test_parse_length(text, system, value):
    assert parse_length(text, system) == pytest.approx(value)


@pytest.mark.parametrize("bad,system", [("", "imperial"), ("abc", "imperial"), ("10 ft", "metric"), ("'", "imperial")])
def test_parse_length_rejects(bad, system):
    with pytest.raises(ValueError):
        parse_length(bad, system)


def test_save_roundtrip(tmp_path):
    path = project.save(project.create_project(), tmp_path / "sub" / "p.ifc")
    g = ifcopenshell.open(str(path))
    assert len(g.by_type("IfcBuildingStorey")) == 2
    assert _types(g)[("W Shapes", "W12x26")].is_a("IfcBeamType")


def test_report_counts_and_score():
    r = report.build_report(sample_model_with_walls(n_walls=4, typed=2))
    assert r.total_elements == 4
    assert r.by_class == {"IfcWall": 4}
    assert (r.with_geometry, r.with_type, r.with_storey) == (4, 2, 4)
    assert r.with_material == 2  # inherited from the type
    assert r.with_properties == 0
    # geometry 1 + type .5 + material .5 + props 0 + storey 1 = 3 / 5
    assert r.score == 60.0
    text = report.format_report(r)
    assert "Quality score: 60.0" in text and "IfcWall" in text


def test_report_empty_model():
    r = report.build_report(project.create_project())
    assert r.total_elements == 0 and r.score == 0.0
    assert r.storeys == ["Level 1", "Level 2"]


def test_core_cli(tmp_path, capsys):
    out = tmp_path / "cli.ifc"
    assert core_main(["new-project", str(out), "--name", "CLI", "--template", "uk_structural"]) == 0
    assert core_main(["report", str(out), "--json"]) == 0
    assert '"project_name": "CLI"' in capsys.readouterr().out


def test_report_box_only_shown():
    r = report.build_report(sample_model_with_walls(n_walls=2, typed=2))
    r.box_only = 1
    text = report.format_report(r)
    assert "real shape" in text and "box only" in text
    assert r.to_dict()["with_real_geometry"] == 1
