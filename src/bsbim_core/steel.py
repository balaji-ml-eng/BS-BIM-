"""US (AISC) steel shapes with Revit-style family and type names."""

from __future__ import annotations

import json
import re
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import ifcopenshell

_DATA = Path(__file__).with_name("data") / "us_steel.json"


@lru_cache(maxsize=1)
def shapes() -> dict[str, dict]:
    """Library name (e.g. 'W12X26', 'HSS6X6X.375') -> profile data in millimetres."""
    return json.loads(_DATA.read_text(encoding="utf-8"))["shapes"]


def _fraction(text: str) -> str:
    """'.375' -> '3/8', '1_2' -> '1/2', '1-3_8' -> '1-3/8', '.280' stays decimal when not a clean fraction."""
    if "_" in text:
        return text.replace("_", "/")
    if text.startswith("."):
        frac = Fraction(text).limit_denominator(64)
        if abs(float(frac) - float(text)) < 1e-9 and frac.denominator <= 16:
            return f"{frac.numerator}/{frac.denominator}"
        return "0" + text
    return text


def revit_type_name(lib_name: str) -> str:
    """Name as shown in Revit's Type Selector: W12X26 -> W12x26, HSS6X6X.375 -> HSS6x6x3/8, C10X15.3 stays."""
    if re.match(r"^(C|MC)\d", lib_name):  # Revit keeps the capital X for channels (e.g. C8X11.5)
        return lib_name
    parts = lib_name.split("X")
    return "x".join([parts[0]] + [_fraction(p) for p in parts[1:]])


_FAMILIES = (  # (prefix regex, beam family, column family)
    (r"^W\d", "W Shapes", "W Shapes-Column"),
    (r"^HP\d", "HP Shapes", "HP Shapes-Column"),
    (r"^S\d", "S Shapes", "S Shapes-Column"),
    (r"^M\d", "M Shapes", "M Shapes-Column"),
    (r"^MC\d", "MC Shapes", "MC Shapes"),
    (r"^C\d", "C Shapes", "C Shapes"),
    (r"^WT\d", "WT Shapes", "WT Shapes"),
    (r"^(ST|MT)\d", "ST Shapes", "ST Shapes"),
    (r"^2?L\d", "L-Angle", "L-Angle"),
)


def revit_family(lib_name: str, role: str = "beam") -> str:
    """Revit family name for a shape. ``role`` is 'beam', 'column' or 'brace'."""
    data = shapes()[lib_name]
    column = role == "column"
    if data["ifc"] == "IfcRectangleHollowProfileDef":
        return "HSS-Hollow Structural Section" + ("-Column" if column else "")
    if data["ifc"] == "IfcCircleHollowProfileDef":
        return "HSS-Round Structural Tubing" + ("-Column" if column else "")
    for pattern, beam_family, column_family in _FAMILIES:
        if re.match(pattern, lib_name):
            return column_family if column else beam_family
    return "Steel Shapes"


def add_profile(f: ifcopenshell.file, lib_name: str, unit_scale_mm: float) -> ifcopenshell.entity_instance:
    """Create the IFC profile for ``lib_name`` in ``f``. ``unit_scale_mm`` = millimetres per project unit."""
    data = dict(shapes()[lib_name])
    ifc_class = data.pop("ifc")
    attrs = {k: (v / unit_scale_mm if isinstance(v, float) and k != "FlangeSlope" else v) for k, v in data.items()}
    return f.create_entity(ifc_class, ProfileType="AREA", ProfileName=revit_type_name(lib_name), **attrs)
