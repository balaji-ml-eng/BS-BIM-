"""Create new BS BIM projects from a US or UK template."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.unit
import numpy as np

from . import steel
from .template import TEMPLATES, LayeredTypeDef, ProfileTypeDef, ProjectTemplate, CONTEXTS


@dataclass
class ProjectSettings:
    name: str = "Project Name"
    template: str = "us_structural"
    site_name: str = "Default Site"
    building_name: str = "Building"
    levels: list[tuple[str, float]] | None = None  # None = the template's levels
    include_types: bool = True

    def get_template(self) -> ProjectTemplate:
        try:
            return TEMPLATES[self.template]
        except KeyError:
            raise ValueError(f"Unknown template {self.template!r}; choose {', '.join(TEMPLATES)}") from None


def _run(f: ifcopenshell.file, usecase: str, **kwargs):
    return ifcopenshell.api.run(usecase, f, **kwargs)


def _add_units(f: ifcopenshell.file, system: str) -> None:
    if system == "imperial":
        units = [
            _run(f, "unit.add_conversion_based_unit", name="foot"),
            _run(f, "unit.add_conversion_based_unit", name="square foot"),
            _run(f, "unit.add_conversion_based_unit", name="cubic foot"),
        ]
    else:
        units = [
            _run(f, "unit.add_si_unit", unit_type="LENGTHUNIT", prefix="MILLI"),
            _run(f, "unit.add_si_unit", unit_type="AREAUNIT"),
            _run(f, "unit.add_si_unit", unit_type="VOLUMEUNIT"),
        ]
    units.append(_run(f, "unit.add_si_unit", unit_type="PLANEANGLEUNIT"))
    _run(f, "unit.assign_unit", units=units)


def _add_contexts(f: ifcopenshell.file) -> None:
    roots = {
        "Model": _run(f, "context.add_context", context_type="Model"),
        "Plan": _run(f, "context.add_context", context_type="Plan"),
    }
    for ctype, identifier, view in CONTEXTS:
        _run(f, "context.add_context", context_type=ctype, context_identifier=identifier,
             target_view=view, parent=roots[ctype])


def _place(f: ifcopenshell.file, product, z: float = 0.0) -> None:
    """Place ``product`` at height ``z`` (project units)."""
    matrix = np.eye(4)
    matrix[2, 3] = z
    _run(f, "geometry.edit_object_placement", product=product, matrix=matrix, is_si=False)


def _profile_for(f: ifcopenshell.file, t: ProfileTypeDef, mm_per_unit: float):
    if t.steel_shape:
        return steel.add_profile(f, t.steel_shape, mm_per_unit)
    width, depth = t.rectangle
    return f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", ProfileName=t.name, XDim=width, YDim=depth)


def _add_types(f: ifcopenshell.file, project, tpl: ProjectTemplate) -> list:
    mm_per_unit = ifcopenshell.util.unit.calculate_unit_scale(f) * 1000.0
    materials = {m.name: _run(f, "material.add_material", name=m.name, category=m.category) for m in tpl.materials}
    types = []
    for t in tpl.profile_types:
        et = _run(f, "root.create_entity", ifc_class=t.ifc_class, name=t.name, predefined_type=t.predefined_type)
        et.ElementType = t.family
        pset = _run(f, "material.add_material_set", name=f"{t.family} : {t.name}", set_type="IfcMaterialProfileSet")
        _run(f, "material.add_profile", profile_set=pset, material=materials[t.material],
             profile=_profile_for(f, t, mm_per_unit))
        _run(f, "material.assign_material", products=[et], type="IfcMaterialProfileSet", material=pset)
        types.append(et)
    for t in tpl.layered_types:
        et = _run(f, "root.create_entity", ifc_class=t.ifc_class, name=t.name, predefined_type=t.predefined_type)
        et.ElementType = t.family
        lset = _run(f, "material.add_material_set", name=f"{t.family} : {t.name}", set_type="IfcMaterialLayerSet")
        for material, thickness in t.layers:
            layer = _run(f, "material.add_layer", layer_set=lset, material=materials[material])
            _run(f, "material.edit_layer", layer=layer, attributes={"LayerThickness": thickness})
        _run(f, "material.assign_material", products=[et], type="IfcMaterialLayerSet", material=lset)
        types.append(et)
    if types:
        _run(f, "project.assign_declaration", definitions=types, relating_context=project)
    return types


def add_level(f: ifcopenshell.file, name: str, elevation: float, building=None):
    """Add a Revit-style level (IfcBuildingStorey) at ``elevation`` (project units)."""
    if any(s.Name == name for s in f.by_type("IfcBuildingStorey")):
        raise ValueError(f"A level named {name!r} already exists")
    building = building or f.by_type("IfcBuilding")[0]
    storey = _run(f, "root.create_entity", ifc_class="IfcBuildingStorey", name=name)
    storey.Elevation = float(elevation)
    _place(f, storey, float(elevation))
    _run(f, "aggregate.assign_object", products=[storey], relating_object=building)
    return storey


def create_project(settings: ProjectSettings | None = None) -> ifcopenshell.file:
    """New IFC4 project: units, contexts, site, building, levels and the template's types."""
    s = settings or ProjectSettings()
    tpl = s.get_template()
    levels = list(s.levels) if s.levels is not None else list(tpl.levels)
    if not levels:
        raise ValueError("A project needs at least one level")
    names = [n for n, _ in levels]
    if len(set(names)) != len(names):
        raise ValueError("Level names must be unique")

    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = _run(f, "root.create_entity", ifc_class="IfcProject", name=s.name)
    _add_units(f, tpl.units)
    _add_contexts(f)

    site = _run(f, "root.create_entity", ifc_class="IfcSite", name=s.site_name)
    building = _run(f, "root.create_entity", ifc_class="IfcBuilding", name=s.building_name)
    _run(f, "aggregate.assign_object", products=[site], relating_object=project)
    _run(f, "aggregate.assign_object", products=[building], relating_object=site)
    _place(f, site)
    _place(f, building)
    for name, elevation in sorted(levels, key=lambda lv: lv[1]):
        add_level(f, name, elevation, building)

    if s.include_types:
        _add_types(f, project, tpl)
    return f


def unit_system(f: ifcopenshell.file) -> str:
    """'imperial' if the project's length unit is feet or inches, else 'metric'."""
    scale = ifcopenshell.util.unit.calculate_unit_scale(f)
    return "imperial" if abs(scale - 0.3048) < 1e-9 or abs(scale - 0.0254) < 1e-9 else "metric"


def save(f: ifcopenshell.file, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(path))
    return path
