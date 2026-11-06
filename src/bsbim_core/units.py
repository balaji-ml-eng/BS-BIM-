"""Revit-style length formatting and parsing for US (feet-inches) and UK (millimetres) projects.

Values are handled in the project's own length unit: feet for imperial projects,
millimetres for metric projects.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Literal

UnitSystem = Literal["imperial", "metric"]

MM_PER_FOOT = 304.8


def format_feet_inches(feet: float, denominator: int = 256) -> str:
    """Revit default display: 10' - 6", 0' - 3 1/2", -2' - 0"."""
    sign = "-" if feet < 0 else ""
    total = Fraction(round(abs(feet) * 12 * denominator), denominator)  # inches, rounded to 1/denominator
    whole_feet, inches = divmod(total, 12)
    whole_in = int(inches)
    frac = inches - whole_in
    inch_text = str(whole_in)
    if frac:  # Revit keeps the whole inches even when zero: 0' - 0 1/2"
        inch_text = f"{whole_in} {frac.numerator}/{frac.denominator}"
    return f"{sign}{int(whole_feet)}' - {inch_text}\""


def format_mm(mm: float) -> str:
    """Revit metric default display: whole millimetres, e.g. 4000."""
    return f"{round(mm):d}"


def format_length(value: float, system: UnitSystem) -> str:
    return format_feet_inches(value) if system == "imperial" else format_mm(value)


_NUM = r"(\d+(?:\.\d+)?(?:\s+\d+/\d+)?|\d+/\d+)"


def _number(text: str) -> float:
    total = 0.0
    for part in text.split():
        total += float(Fraction(part)) if "/" in part else float(part)
    return total


def parse_length(text: str, system: UnitSystem) -> float:
    """Parse what a Revit user would type into a length field.

    Imperial (result in feet): 10'  10' 6"  10'-6"  10' - 6 1/2"  6"  3 1/2"  10.5 (feet)  1/2"
    Metric (result in mm):     4000  4000 mm  4000mm  4 m  4.2m  40 cm
    """
    s = text.strip().lower()
    if not s:
        raise ValueError("Empty length")
    neg = s.startswith("-")
    s = s.lstrip("-").strip()
    if system == "imperial":
        m = re.fullmatch(rf"(?:{_NUM}\s*')?\s*-?\s*(?:{_NUM}\s*\"?)?", s)
        if not m or (m.group(1) is None and m.group(2) is None):
            raise ValueError(f"Not a feet-inches length: {text!r}")
        feet_part, inch_part = m.group(1), m.group(2)
        if feet_part is None and '"' not in s:
            value = _number(inch_part)  # bare number = feet, as in Revit
        else:
            value = (_number(feet_part) if feet_part else 0.0) + (_number(inch_part) / 12 if inch_part else 0.0)
    else:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(mm|cm|m)?", s)
        if not m:
            raise ValueError(f"Not a metric length: {text!r}")
        value = float(m.group(1)) * {"mm": 1, None: 1, "cm": 10, "m": 1000}[m.group(2)]
    return -value if neg else value
