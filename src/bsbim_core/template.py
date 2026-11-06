"""Default company template data: levels, materials, wall and slab types.

All lengths are in millimetres. Values follow common Indian practice
(IS 1077 bricks, IS 456 concrete grades) and are meant as a starting point
the BIM team will refine.
"""

from __future__ import annotations

from dataclasses import dataclass

# (name, elevation in mm)
DEFAULT_LEVELS: list[tuple[str, float]] = [
    ("Ground Floor", 0.0),
    ("First Floor", 3000.0),
    ("Terrace", 6000.0),
]


@dataclass(frozen=True)
class MaterialDef:
    name: str
    category: str
    description: str


@dataclass(frozen=True)
class LayeredTypeDef:
    ifc_class: str
    name: str
    description: str
    predefined_type: str
    layers: tuple[tuple[str, float], ...]  # (material name, thickness mm)

    @property
    def total_thickness(self) -> float:
        return sum(t for _, t in self.layers)


MATERIALS: tuple[MaterialDef, ...] = (
    MaterialDef("Brick", "brick", "Burnt clay brick masonry (IS 1077)"),
    MaterialDef("Cement Plaster", "plaster", "Cement plaster 1:6"),
    MaterialDef("Concrete M25", "concrete", "Reinforced cement concrete, grade M25 (IS 456)"),
    MaterialDef("Concrete M20", "concrete", "Reinforced cement concrete, grade M20 (IS 456)"),
    MaterialDef("Cement Screed", "concrete", "Cement-sand screed 1:4"),
    MaterialDef("Vitrified Tile", "tile", "Vitrified floor tile"),
    MaterialDef("AAC Block", "block", "Autoclaved aerated concrete block (IS 2185-3)"),
)

WALL_TYPES: tuple[LayeredTypeDef, ...] = (
    LayeredTypeDef(
        "IfcWallType", "Brick Wall 230", "230 mm (9 inch) brick wall, 12 mm plaster both sides",
        "STANDARD", (("Cement Plaster", 12.0), ("Brick", 230.0), ("Cement Plaster", 12.0)),
    ),
    LayeredTypeDef(
        "IfcWallType", "Brick Wall 115", "115 mm (4.5 inch) brick partition, 12 mm plaster both sides",
        "PARTITIONING", (("Cement Plaster", 12.0), ("Brick", 115.0), ("Cement Plaster", 12.0)),
    ),
    LayeredTypeDef(
        "IfcWallType", "AAC Block Wall 200", "200 mm AAC block wall, 12 mm plaster both sides",
        "STANDARD", (("Cement Plaster", 12.0), ("AAC Block", 200.0), ("Cement Plaster", 12.0)),
    ),
    LayeredTypeDef(
        "IfcWallType", "RCC Wall 200", "200 mm reinforced concrete wall",
        "SHEAR", (("Concrete M25", 200.0),),
    ),
)

SLAB_TYPES: tuple[LayeredTypeDef, ...] = (
    LayeredTypeDef(
        "IfcSlabType", "RCC Slab 150", "150 mm RCC slab",
        "FLOOR", (("Concrete M25", 150.0),),
    ),
    LayeredTypeDef(
        "IfcSlabType", "RCC Slab 125", "125 mm RCC slab",
        "FLOOR", (("Concrete M25", 125.0),),
    ),
    LayeredTypeDef(
        "IfcSlabType", "Floor Finish Tile 50", "Vitrified tile on 40 mm screed",
        "FLOOR", (("Vitrified Tile", 10.0), ("Cement Screed", 40.0)),
    ),
)

# Representation contexts expected by Bonsai tools:
# (context_type, identifier, target_view); identifier "" means the root context.
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
