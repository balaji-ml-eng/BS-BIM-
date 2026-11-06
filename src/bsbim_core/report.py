"""Model quality report: how complete is the BIM data in an IFC file?

Used to measure RVT -> IFC conversion quality and to check models before delivery.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

import ifcopenshell
import ifcopenshell.util.element


@dataclass
class ModelReport:
    schema: str
    project_name: str | None
    storeys: list[str] = field(default_factory=list)
    spaces: int = 0
    total_elements: int = 0
    with_geometry: int = 0
    with_type: int = 0
    with_material: int = 0
    with_properties: int = 0
    with_storey: int = 0
    by_class: dict[str, int] = field(default_factory=dict)
    # Elements whose geometry is only a placeholder box. An IFC file cannot tell us this,
    # so importers that know it (e.g. the RVT Bridge) set it.
    box_only: int = 0

    def ratio(self, count: int) -> float:
        return count / self.total_elements if self.total_elements else 0.0

    @property
    def with_real_geometry(self) -> int:
        return max(0, self.with_geometry - self.box_only)

    @property
    def score(self) -> float:
        """0-100: average share of elements with real geometry, type, material, properties and a storey."""
        if not self.total_elements:
            return 0.0
        parts = (self.with_real_geometry, self.with_type, self.with_material, self.with_properties, self.with_storey)
        return round(100.0 * sum(self.ratio(p) for p in parts) / len(parts), 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["with_real_geometry"] = self.with_real_geometry
        d["score"] = self.score
        return d


def build_report(f: ifcopenshell.file) -> ModelReport:
    projects = f.by_type("IfcProject")
    report = ModelReport(
        schema=f.schema,
        project_name=projects[0].Name if projects else None,
        storeys=[s.Name or "(unnamed)" for s in sorted(
            f.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation if s.Elevation is not None else 0.0
        )],
        spaces=len(f.by_type("IfcSpace")),
    )
    counts: Counter[str] = Counter()
    for element in f.by_type("IfcElement"):
        if element.is_a("IfcFeatureElementSubtraction"):  # openings are not model objects users count
            continue
        counts[element.is_a()] += 1
        report.total_elements += 1
        if element.Representation is not None:
            report.with_geometry += 1
        if ifcopenshell.util.element.get_type(element) is not None:
            report.with_type += 1
        if ifcopenshell.util.element.get_material(element) is not None:
            report.with_material += 1
        if ifcopenshell.util.element.get_psets(element):
            report.with_properties += 1
        if ifcopenshell.util.element.get_container(element) is not None:
            report.with_storey += 1
    report.by_class = dict(counts.most_common())
    return report


def format_report(r: ModelReport) -> str:
    def line(label: str, count: int) -> str:
        return f"  {label:<16}{count:>8}  ({100 * r.ratio(count):5.1f}%)"

    out = [
        f"Project:   {r.project_name or '(none)'}   [{r.schema}]",
        f"Storeys:   {len(r.storeys)}  {', '.join(r.storeys)}",
        f"Rooms:     {r.spaces}",
        f"Elements:  {r.total_elements}",
        line("with geometry", r.with_geometry),
        *([line("  real shape", r.with_real_geometry), line("  box only", r.box_only)] if r.box_only else []),
        line("with type", r.with_type),
        line("with material", r.with_material),
        line("with properties", r.with_properties),
        line("on a storey", r.with_storey),
        f"Quality score: {r.score} / 100",
    ]
    if r.by_class:
        out.append("By class:")
        out += [f"  {cls:<28}{n:>8}" for cls, n in r.by_class.items()]
    return "\n".join(out)
