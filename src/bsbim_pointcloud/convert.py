"""Convert a scan into the BS BIM display cache (.npz)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from .readers import PointCloudError, check_input, count_points, read

DEFAULT_MAX_POINTS = 3_000_000
UNIT_TO_METRES = {"m": 1.0, "mm": 0.001, "cm": 0.01, "ft": 0.3048, "usft": 1200 / 3937, "in": 0.0254}


def convert(source: str | Path, output: str | Path, max_points: int = DEFAULT_MAX_POINTS,
            units: str = "m") -> dict:
    """Read ``source``, thin it to at most ``max_points`` and write ``output`` (.npz).

    The cache stores coordinates in metres as float32 relative to ``origin`` (float64), so large
    survey coordinates keep their precision.
    """
    src = check_input(source)
    if units not in UNIT_TO_METRES:
        raise PointCloudError(f"Unknown units {units!r}; use {', '.join(UNIT_TO_METRES)}")
    if max_points < 1:
        raise PointCloudError("max_points must be at least 1")
    start = time.perf_counter()
    total = count_points(src)
    keep = min(1.0, max_points / total) if total else 1.0
    xyz, rgb = read(src, keep)
    if total is None:
        total = len(xyz)
    if len(xyz) > max_points:  # formats without a header count are thinned after reading
        idx = np.random.default_rng(1).choice(len(xyz), max_points, replace=False)
        xyz, rgb = xyz[idx], (rgb[idx] if rgb is not None else None)
    if len(xyz) == 0:
        raise PointCloudError(f"{src.name} contains no points")
    xyz = xyz * UNIT_TO_METRES[units]
    finite = np.isfinite(xyz).all(axis=1)
    xyz, rgb = xyz[finite], (rgb[finite] if rgb is not None else None)
    origin = xyz.min(axis=0)
    rel = (xyz - origin).astype(np.float32)
    info = {
        "source": str(src),
        "format": src.suffix.lower().lstrip("."),
        "points_in_file": int(total),
        "points_kept": int(len(rel)),
        "has_color": rgb is not None,
        "units": units,
        "bounds_min_m": origin.tolist(),
        "bounds_max_m": (origin + rel.max(axis=0)).tolist(),
        "seconds": round(time.perf_counter() - start, 2),
    }
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, xyz=rel, origin=origin, rgb=rgb if rgb is not None else np.zeros((0, 3), np.uint8),
             info=json.dumps(info))
    return info


def load(cache: str | Path) -> tuple[np.ndarray, np.ndarray | None, dict]:
    """(xyz metres float64, rgb uint8 or None, info) from a cache written by ``convert``."""
    with np.load(cache, allow_pickle=False) as data:
        xyz = data["xyz"].astype(np.float64) + data["origin"]
        rgb = data["rgb"] if len(data["rgb"]) else None
        info = json.loads(str(data["info"]))
    return xyz, rgb, info
