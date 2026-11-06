from __future__ import annotations

import ifcopenshell
import ifcopenshell.util.element as E
import ifcopenshell.util.unit
import pytest

from bsbim_core import project, report, template
from bsbim_core.__main__ import main as core_main

from .conftest import sample_model_with_walls


def test_new_project_structure():
    f = project.create_project(project.ProjectSettings(name="Demo"))
    assert f.schema == "IFC4"
    assert f.by_type("IfcProject")[0].Name == "Demo"
    assert ifcopenshell.util.unit.calculate_unit_scale(f) == pytest.approx(0.001)  # millimetres
    site, building = f.by_type("IfcSite")[0], f.by_type("IfcBuilding")[0]
    assert E.get_aggregate(building) == site
    storeys = f.by_type("IfcBuildingStorey")
    assert [(s.Name, s.Elevation) for s in storeys] == template.DEFAULT_LEVELS
    for s in storeys:
        assert E.get_aggregate(s) == building
        assert s.ObjectPlacement.RelativePlacement.Location.Coordinates[2] == pytest.approx(s.Elevation)


def test_template_types_have_correct_layers():
    f = project.create_project()
    names = {t.Name for t in f.by_type("IfcElementType")}
    assert names == {t.name for t in (*template.WALL_TYPES, *template.SLAB_TYPES)}
    wall = next(t for t in f.by_type("IfcWallType") if t.Name == "Brick Wall 230")
    layers = E.get_material(wall).MaterialLayers
    assert [(l.Material.Name, l.LayerThickness) for l in layers] == [
        ("Cement Plaster", 12.0), ("Brick", 230.0), ("Cement Plaster", 12.0)]
    declared = f.by_type("IfcRelDeclares")[0].RelatedDefinitions
    assert set(declared) == set(f.by_type("IfcElementType"))


def test_project_without_types():
    f = project.create_project(project.ProjectSettings(include_types=False))
    assert not f.by_type("IfcElementType")


def test_with_floors():
    s = project.ProjectSettings.with_floors("X", floors=3, floor_height_mm=3200)
    assert s.levels == [("Ground Floor", 0), ("Floor 1", 3200), ("Floor 2", 6400), ("Terrace", 9600)]
    with pytest.raises(ValueError):
        project.ProjectSettings.with_floors("X", floors=0, floor_height_mm=3000)
    with pytest.raises(ValueError):
        project.ProjectSettings.with_floors("X", floors=2, floor_height_mm=0)


def test_invalid_levels_rejected():
    with pytest.raises(ValueError):
        project.create_project(project.ProjectSettings(levels=[]))
    with pytest.raises(ValueError):
        project.create_project(project.ProjectSettings(levels=[("A", 0), ("A", 3000)]))


def test_save_roundtrip(tmp_path):
    path = project.save(project.create_project(), tmp_path / "sub" / "p.ifc")
    assert len(ifcopenshell.open(str(path)).by_type("IfcBuildingStorey")) == 3


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
    assert r.storeys == ["Ground Floor", "First Floor", "Terrace"]


def test_core_cli(tmp_path, capsys):
    out = tmp_path / "cli.ifc"
    assert core_main(["new-project", str(out), "--name", "CLI", "--floors", "2"]) == 0
    assert core_main(["report", str(out), "--json"]) == 0
    assert '"project_name": "CLI"' in capsys.readouterr().out
    assert core_main(["new-project", str(out), "--floors", "0"]) == 1
