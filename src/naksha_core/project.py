"""Create new Naksha projects from the company template."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import numpy as np

from . import template


@dataclass
class ProjectSettings:
    name: str = "Naksha Project"
    site_name: str = "Site"
    building_name: str = "Building"
    levels: list[tuple[str, float]] = field(default_factory=lambda: list(template.DEFAULT_LEVELS))
    include_types: bool = True

    @classmethod
    def with_floors(cls, name: str, floors: int, floor_height_mm: float) -> "ProjectSettings":
        """Settings with ``floors`` storeys named Ground Floor, Floor 1, ... plus a Terrace."""
        if floors < 1:
            raise ValueError("A project needs at least one floor")
        if floor_height_mm <= 0:
            raise ValueError("Floor height must be positive")
        names = ["Ground Floor"] + [f"Floor {i}" for i in range(1, floors)] + ["Terrace"]
        levels = [(n, i * floor_height_mm) for i, n in enumerate(names)]
        return cls(name=name, levels=levels)


def _run(f: ifcopenshell.file, usecase: str, **kwargs):
    return ifcopenshell.api.run(usecase, f, **kwargs)


def _add_units(f: ifcopenshell.file) -> None:
    units = [
        _run(f, "unit.add_si_unit", unit_type="LENGTHUNIT", prefix="MILLI"),
        _run(f, "unit.add_si_unit", unit_type="AREAUNIT"),
        _run(f, "unit.add_si_unit", unit_type="VOLUMEUNIT"),
        _run(f, "unit.add_si_unit", unit_type="PLANEANGLEUNIT"),
    ]
    _run(f, "unit.assign_unit", units=units)


def _add_contexts(f: ifcopenshell.file) -> None:
    roots = {
        "Model": _run(f, "context.add_context", context_type="Model"),
        "Plan": _run(f, "context.add_context", context_type="Plan"),
    }
    for ctype, identifier, view in template.CONTEXTS:
        _run(
            f, "context.add_context",
            context_type=ctype, context_identifier=identifier, target_view=view, parent=roots[ctype],
        )


def _place(f: ifcopenshell.file, product, z_mm: float = 0.0) -> None:
    matrix = np.eye(4)
    matrix[2, 3] = z_mm / 1000.0  # edit_object_placement takes SI metres
    _run(f, "geometry.edit_object_placement", product=product, matrix=matrix, is_si=True)


def _add_types(f: ifcopenshell.file, project) -> list:
    materials = {}
    for m in template.MATERIALS:
        materials[m.name] = _run(f, "material.add_material", name=m.name, category=m.category, description=m.description)

    types = []
    for t in (*template.WALL_TYPES, *template.SLAB_TYPES):
        element_type = _run(f, "root.create_entity", ifc_class=t.ifc_class, name=t.name, predefined_type=t.predefined_type)
        element_type.Description = t.description
        layer_set = _run(f, "material.add_material_set", name=t.name, set_type="IfcMaterialLayerSet")
        for material_name, thickness in t.layers:
            layer = _run(f, "material.add_layer", layer_set=layer_set, material=materials[material_name])
            _run(f, "material.edit_layer", layer=layer, attributes={"LayerThickness": thickness})
        _run(f, "material.assign_material", products=[element_type], type="IfcMaterialLayerSet", material=layer_set)
        types.append(element_type)

    _run(f, "project.assign_declaration", definitions=types, relating_context=project)
    return types


def create_project(settings: ProjectSettings | None = None) -> ifcopenshell.file:
    """Build a new IFC4 project: units (mm), contexts, site, building, storeys, template types."""
    s = settings or ProjectSettings()
    if not s.levels:
        raise ValueError("A project needs at least one level")
    names = [n for n, _ in s.levels]
    if len(set(names)) != len(names):
        raise ValueError("Level names must be unique")

    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = _run(f, "root.create_entity", ifc_class="IfcProject", name=s.name)
    _add_units(f)
    _add_contexts(f)

    site = _run(f, "root.create_entity", ifc_class="IfcSite", name=s.site_name)
    building = _run(f, "root.create_entity", ifc_class="IfcBuilding", name=s.building_name)
    _run(f, "aggregate.assign_object", products=[site], relating_object=project)
    _run(f, "aggregate.assign_object", products=[building], relating_object=site)
    _place(f, site)
    _place(f, building)

    storeys = []
    for name, elevation in sorted(s.levels, key=lambda lv: lv[1]):
        storey = _run(f, "root.create_entity", ifc_class="IfcBuildingStorey", name=name)
        storey.Elevation = float(elevation)
        _place(f, storey, elevation)
        storeys.append(storey)
    _run(f, "aggregate.assign_object", products=storeys, relating_object=building)

    if s.include_types:
        _add_types(f, project)
    return f


def save(f: ifcopenshell.file, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(path))
    return path
