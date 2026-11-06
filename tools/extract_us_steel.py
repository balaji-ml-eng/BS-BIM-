"""Generate src/bsbim_core/data/us_steel.json from Bonsai's "IFC4 US Steel" library.

    .venv/Scripts/python tools/extract_us_steel.py [path/to/IFC4 US Steel.ifc]

Keeps the simple parametric AISC profiles (W, S, M, HP, HSS, L, C, MC, WT, ST...).
Dimensions are stored in millimetres, as in the source library.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.unit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIB = Path(r"H:\Bala Data\Tools\blender-5.1.2-windows-x64\portable\extensions\.local\lib"
                   r"\python3.13\site-packages\bonsai\bim\data\libraries\IFC4 US Steel.ifc")
KEEP = ("IfcIShapeProfileDef", "IfcRectangleHollowProfileDef", "IfcCircleHollowProfileDef",
        "IfcLShapeProfileDef", "IfcUShapeProfileDef", "IfcTShapeProfileDef")
SKIP_ATTRS = {"id", "type", "ProfileType", "ProfileName", "Position"}


def main() -> int:
    lib = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LIB
    f = ifcopenshell.open(str(lib))
    to_mm = ifcopenshell.util.unit.calculate_unit_scale(f) * 1000.0
    shapes = {}
    for cls in KEEP:
        for p in f.by_type(cls):
            if not p.ProfileName or p.ProfileName in shapes:
                continue
            dims = {k: (round(v * to_mm, 4) if isinstance(v, float) else v)
                    for k, v in p.get_info(recursive=False).items() if k not in SKIP_ATTRS and v is not None}
            shapes[p.ProfileName] = {"ifc": cls, **dims}
    out = ROOT / "src" / "bsbim_core" / "data" / "us_steel.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source": "Bonsai 'IFC4 US Steel' library (AISC shapes), extracted by tools/extract_us_steel.py",
        "units": "mm",
        "shapes": dict(sorted(shapes.items())),
    }, indent=0), encoding="utf-8")
    print(f"{len(shapes)} shapes -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
