"""Project templates for US and UK structural work.

Names follow what Revit users see: family "W Shapes", type "W12x26"; materials
"Steel ASTM A992", "Concrete, Normal Weight - 4 ksi" (US) or "Concrete, Cast-in-Place - C30" (UK).

Lengths are in the template's project unit: feet (US) or millimetres (UK).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .units import UnitSystem

# Representation contexts expected by Bonsai tools:
# (context_type, identifier, target_view)
CONTEXTS: tuple[tuple[str, str, str], ...] = (
    ("Model", "Body", "MODEL_VIEW"),
    ("Model", "Axis", "GRAPH_VIEW"),
    ("Model", "Box", "MODEL_VIEW"),
    ("Model", "Annotation", "SECTION_VIEW"),
    ("Model", "Annotation", "ELEVATION_VIEW"),
    ("Model", "Annotation", "MODEL_VIEW"),
    ("Model", "Annotation", "PLAN_VIEW"),
    ("Model", "Profile", "ELEVATION_VIEW"),
    ("Plan", "Axis", "GRAPH_VIEW"),
    ("Plan", "Body", "PLAN_VIEW"),
    ("Plan", "Annotation", "PLAN_VIEW"),
    ("Plan", "Annotation", "REFLECTED_PLAN_VIEW"),
)


@dataclass(frozen=True)
class MaterialDef:
    name: str
    category: str  # steel, concrete, ... (used by Bonsai for styling)


@dataclass(frozen=True)
class ProfileTypeDef:
    """A Revit loadable-family type made of one profile: steel shape or concrete rectangle."""
    ifc_class: str            # IfcBeamType, IfcColumnType, IfcMemberType
    predefined_type: str      # BEAM, COLUMN, BRACE
    family: str               # Revit family name, stored in IfcElementType.ElementType
    name: str                 # Revit type name
    material: str
    steel_shape: str | None = None        # key in steel.shapes()
    rectangle: tuple[float, float] | None = None  # (width, depth) in project units


@dataclass(frozen=True)
class LayeredTypeDef:
    """A Revit system-family type made of layers: Basic Wall, Floor."""
    ifc_class: str            # IfcWallType, IfcSlabType
    predefined_type: str
    family: str               # "Basic Wall", "Floor"
    name: str
    layers: tuple[tuple[str, float], ...]  # (material, thickness in project units)

    @property
    def total_thickness(self) -> float:
        return sum(t for _, t in self.layers)


@dataclass(frozen=True)
class ProjectTemplate:
    key: str
    label: str
    units: UnitSystem
    levels: tuple[tuple[str, float], ...]
    materials: tuple[MaterialDef, ...]
    profile_types: tuple[ProfileTypeDef, ...] = field(default_factory=tuple)
    layered_types: tuple[LayeredTypeDef, ...] = field(default_factory=tuple)


def _w(ifc_class: str, predefined: str, role: str, shapes: tuple[str, ...], material: str) -> tuple[ProfileTypeDef, ...]:
    from .steel import revit_family, revit_type_name
    return tuple(
        ProfileTypeDef(ifc_class, predefined, revit_family(s, role), revit_type_name(s), material, steel_shape=s)
        for s in shapes
    )


IN = 1 / 12  # one inch in feet

US_A992 = "Steel ASTM A992"
US_A500_RECT = "Steel ASTM A500, Grade B, Rectangular and Square"
US_A36 = "Steel ASTM A36"
US_CONC = "Concrete, Normal Weight - 4 ksi"
US_LW = "Concrete, Lightweight - 4 ksi"

US_STRUCTURAL = ProjectTemplate(
    key="us_structural",
    label="US Structural (Imperial)",
    units="imperial",
    levels=(("Level 1", 0.0), ("Level 2", 10.0)),
    materials=(
        MaterialDef(US_A992, "steel"),
        MaterialDef(US_A500_RECT, "steel"),
        MaterialDef("Steel ASTM A500, Grade B, Round", "steel"),
        MaterialDef(US_A36, "steel"),
        MaterialDef(US_CONC, "concrete"),
        MaterialDef(US_LW, "concrete"),
        MaterialDef("Metal Deck", "steel"),
    ),
    profile_types=(
        *_w("IfcColumnType", "COLUMN", "column",
            ("W10X33", "W10X49", "W12X40", "W12X53", "W14X48", "W14X90"), US_A992),
        *_w("IfcColumnType", "COLUMN", "column", ("HSS6X6X.375", "HSS8X8X.500"), US_A500_RECT),
        *(ProfileTypeDef("IfcColumnType", "COLUMN", "Concrete-Rectangular-Column", f"{a} x {b}", US_CONC,
                         rectangle=(a * IN, b * IN)) for a, b in ((12, 12), (18, 18), (24, 24))),
        *_w("IfcBeamType", "BEAM", "beam",
            ("W8X10", "W10X12", "W12X26", "W14X22", "W16X26", "W18X35", "W21X44", "W24X55"), US_A992),
        *_w("IfcBeamType", "BEAM", "beam", ("C10X15.3",), US_A36),
        *(ProfileTypeDef("IfcBeamType", "BEAM", "Concrete-Rectangular Beam", f"{a} x {b}", US_CONC,
                         rectangle=(a * IN, b * IN)) for a, b in ((12, 24), (16, 32))),
        *_w("IfcMemberType", "BRACE", "brace", ("HSS6X6X.375",), US_A500_RECT),
        *_w("IfcMemberType", "BRACE", "brace", ("L4X4X1_2",), US_A36),
    ),
    layered_types=(
        LayeredTypeDef("IfcSlabType", "FLOOR", "Floor", '6" Concrete', ((US_CONC, 6 * IN),)),
        LayeredTypeDef("IfcSlabType", "FLOOR", "Floor", '8" Concrete', ((US_CONC, 8 * IN),)),
        LayeredTypeDef("IfcSlabType", "FLOOR", "Floor", '5 1/2" LW Concrete on 2" Metal Deck',
                       ((US_LW, 3.5 * IN), ("Metal Deck", 2 * IN))),
        LayeredTypeDef("IfcWallType", "STANDARD", "Basic Wall", 'Concrete - 8"', ((US_CONC, 8 * IN),)),
        LayeredTypeDef("IfcWallType", "STANDARD", "Basic Wall", 'Foundation - 12" Concrete', ((US_CONC, 12 * IN),)),
    ),
)

UK_C30 = "Concrete, Cast-in-Place - C30"
UK_C40 = "Concrete, Cast-in-Place - C40"
UK_S355 = "Steel, 50-355"

UK_STRUCTURAL = ProjectTemplate(
    key="uk_structural",
    label="UK Structural (Metric)",
    units="metric",
    levels=(("Level 1", 0.0), ("Level 2", 4000.0)),
    materials=(
        MaterialDef(UK_C30, "concrete"),
        MaterialDef(UK_C40, "concrete"),
        MaterialDef(UK_S355, "steel"),
        MaterialDef("Steel, 43-275", "steel"),
        MaterialDef("Steel Rebar - B500B", "steel"),
    ),
    # UK steel sections (UB, UC, PFC, SHS, CHS to BS EN 10365 / 10210) are added in the next step,
    # once their dimension tables are verified.
    profile_types=(
        *(ProfileTypeDef("IfcColumnType", "COLUMN", "M_Concrete-Rectangular-Column", f"{a} x {b}mm", UK_C40,
                         rectangle=(float(a), float(b))) for a, b in ((300, 300), (400, 400), (450, 450))),
        *(ProfileTypeDef("IfcBeamType", "BEAM", "M_Concrete-Rectangular Beam", f"{a} x {b}mm", UK_C30,
                         rectangle=(float(a), float(b))) for a, b in ((300, 450), (300, 600), (400, 750))),
    ),
    layered_types=(
        LayeredTypeDef("IfcSlabType", "FLOOR", "Floor", "Concrete 200mm", ((UK_C30, 200.0),)),
        LayeredTypeDef("IfcSlabType", "FLOOR", "Floor", "Concrete 250mm", ((UK_C30, 250.0),)),
        LayeredTypeDef("IfcWallType", "STANDARD", "Basic Wall", "Concrete 200mm", ((UK_C30, 200.0),)),
        LayeredTypeDef("IfcWallType", "STANDARD", "Basic Wall", "Concrete 300mm", ((UK_C30, 300.0),)),
    ),
)

TEMPLATES: dict[str, ProjectTemplate] = {t.key: t for t in (US_STRUCTURAL, UK_STRUCTURAL)}
