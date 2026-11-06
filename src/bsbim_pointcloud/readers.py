"""Point cloud readers. Each returns (xyz float64 N x 3, rgb uint8 N x 3 or None).

``keep`` is the fraction of points to keep (0 < keep <= 1), applied while reading so very large
scans never have to fit in memory whole.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import RECAP_SUFFIXES, SUFFIXES


class PointCloudError(RuntimeError):
    pass


def _subsample(n: int, keep: float, rng: np.random.Generator) -> np.ndarray | slice:
    if keep >= 1.0:
        return slice(None)
    return rng.random(n) < keep


# ------------------------------------------------------------------ E57
def count_e57(path: Path) -> int:
    import pye57
    e = pye57.E57(str(path))
    return sum(int(e.get_header(i).point_count) for i in range(e.scan_count))


def read_e57(path: Path, keep: float, rng) -> tuple[np.ndarray, np.ndarray | None]:
    import pye57
    e = pye57.E57(str(path))
    xyz_parts, rgb_parts, have_rgb = [], [], True
    for i in range(e.scan_count):
        header = e.get_header(i)
        fields = set(header.point_fields)
        colors = {"colorRed", "colorGreen", "colorBlue"} <= fields
        have_rgb &= colors
        data = e.read_scan(i, colors=colors, ignore_missing_fields=True, transform=True)
        x, y, z = data["cartesianX"], data["cartesianY"], data["cartesianZ"]
        sel = _subsample(len(x), keep, rng)
        xyz_parts.append(np.column_stack((x[sel], y[sel], z[sel])))
        if colors:
            rgb = np.column_stack((data["colorRed"][sel], data["colorGreen"][sel], data["colorBlue"][sel]))
            limit = header.colorLimits if hasattr(header, "colorLimits") else None
            hi = float(np.max(rgb)) if rgb.size else 255.0
            scale = 255.0 / (hi if hi > 255 else 255.0)
            rgb_parts.append(np.clip(rgb * scale, 0, 255).astype(np.uint8))
    if not xyz_parts:
        raise PointCloudError("The E57 file has no scans")
    xyz = np.concatenate(xyz_parts)
    rgb = np.concatenate(rgb_parts) if have_rgb and rgb_parts else None
    return xyz, rgb


# ------------------------------------------------------------------ LAS / LAZ
def count_las(path: Path) -> int:
    import laspy
    with laspy.open(str(path)) as f:
        return int(f.header.point_count)


def read_las(path: Path, keep: float, rng) -> tuple[np.ndarray, np.ndarray | None]:
    import laspy
    xyz_parts, rgb_parts = [], []
    with laspy.open(str(path)) as f:
        has_rgb = "red" in f.header.point_format.dimension_names
        for chunk in f.chunk_iterator(2_000_000):
            sel = _subsample(len(chunk), keep, rng)
            xyz_parts.append(np.column_stack((np.asarray(chunk.x)[sel], np.asarray(chunk.y)[sel],
                                              np.asarray(chunk.z)[sel])))
            if has_rgb:
                rgb = np.column_stack((np.asarray(chunk.red)[sel], np.asarray(chunk.green)[sel],
                                       np.asarray(chunk.blue)[sel])).astype(np.float64)
                rgb_parts.append(rgb)
    xyz = np.concatenate(xyz_parts) if xyz_parts else np.zeros((0, 3))
    rgb = None
    if rgb_parts:
        rgb = np.concatenate(rgb_parts)
        if rgb.size and rgb.max() > 255:  # LAS colours are 16-bit
            rgb = rgb / 256.0
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    return xyz, rgb


# ------------------------------------------------------------------ PLY
_PLY_TYPES = {"char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1", "short": "i2", "int16": "i2",
              "ushort": "u2", "uint16": "u2", "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4",
              "float": "f4", "float32": "f4", "double": "f8", "float64": "f8"}


def read_ply(path: Path, keep: float, rng) -> tuple[np.ndarray, np.ndarray | None]:
    with open(path, "rb") as fh:
        if fh.readline().strip() != b"ply":
            raise PointCloudError("Not a PLY file")
        fmt, count, props, in_vertex = None, 0, [], False
        while True:
            line = fh.readline()
            if not line:
                raise PointCloudError("PLY header has no end_header")
            words = line.decode("ascii", "replace").split()
            if not words:
                continue
            if words[0] == "format":
                fmt = words[1]
            elif words[0] == "element":
                in_vertex = words[1] == "vertex"
                if in_vertex:
                    count = int(words[2])
            elif words[0] == "property" and in_vertex:
                if words[1] == "list":
                    raise PointCloudError("PLY vertex lists are not supported")
                props.append((words[2], _PLY_TYPES[words[1]]))
            elif words[0] == "end_header":
                break
        names = [n for n, _ in props]
        if not {"x", "y", "z"} <= set(names):
            raise PointCloudError("PLY file has no x, y, z vertex properties")
        if fmt == "ascii":
            data = np.loadtxt(fh, max_rows=count, ndmin=2)
            col = {n: data[:, i] for i, n in enumerate(names)}
        elif fmt in ("binary_little_endian", "binary_big_endian"):
            order = "<" if fmt == "binary_little_endian" else ">"
            dtype = np.dtype([(n, order + t) for n, t in props])
            arr = np.fromfile(fh, dtype=dtype, count=count)
            col = {n: arr[n] for n in names}
        else:
            raise PointCloudError(f"Unknown PLY format {fmt!r}")
    sel = _subsample(len(col["x"]), keep, rng)
    xyz = np.column_stack((col["x"][sel], col["y"][sel], col["z"][sel])).astype(np.float64)
    rgb = None
    for r, g, b in (("red", "green", "blue"), ("r", "g", "b"), ("diffuse_red", "diffuse_green", "diffuse_blue")):
        if {r, g, b} <= set(names):
            rgb = np.column_stack((col[r][sel], col[g][sel], col[b][sel])).astype(np.float64)
            if rgb.size and rgb.max() <= 1.0:
                rgb = rgb * 255.0
            rgb = np.clip(rgb, 0, 255).astype(np.uint8)
            break
    return xyz, rgb


# ------------------------------------------------------------------ PTS / XYZ (text)
def read_text(path: Path, keep: float, rng) -> tuple[np.ndarray, np.ndarray | None]:
    """PTS: first line = point count, then "x y z [intensity] [r g b]". XYZ: "x y z [r g b]"."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        first = fh.readline().split()
        skip = 1 if len(first) == 1 else 0
    data = np.loadtxt(path, skiprows=skip, ndmin=2, comments=("#", "//"),
                      delimiter=None if "," not in " ".join(first) else ",")
    if data.shape[1] < 3:
        raise PointCloudError("Text point file needs at least x y z per line")
    sel = _subsample(len(data), keep, rng)
    data = data[sel]
    rgb = None
    if data.shape[1] >= 7:      # x y z intensity r g b (PTS)
        rgb = data[:, 4:7]
    elif data.shape[1] == 6:    # x y z r g b
        rgb = data[:, 3:6]
    if rgb is not None:
        rgb = np.clip(rgb * (255.0 if rgb.max() <= 1.0 else 1.0), 0, 255).astype(np.uint8)
    return data[:, :3].astype(np.float64), rgb


# ------------------------------------------------------------------ dispatch
def check_input(path: str | Path) -> Path:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in RECAP_SUFFIXES:
        raise PointCloudError(
            f"{p.name} is an Autodesk ReCap file. ReCap's format has no open-source reader. "
            "Export it to E57 from ReCap (or ask the scanning team for the original E57/LAS) and link that.")
    if not p.is_file():
        raise PointCloudError(f"File not found: {p}")
    if suffix not in SUFFIXES:
        raise PointCloudError(f"Unsupported point cloud format {suffix}; use {', '.join(SUFFIXES)}")
    return p


def count_points(path: Path) -> int | None:
    """Fast point count from the header, when the format has one."""
    suffix = path.suffix.lower()
    if suffix == ".e57":
        return count_e57(path)
    if suffix in (".las", ".laz"):
        return count_las(path)
    return None


def read(path: Path, keep: float = 1.0, seed: int = 0):
    rng = np.random.default_rng(seed)
    suffix = path.suffix.lower()
    if suffix == ".e57":
        return read_e57(path, keep, rng)
    if suffix in (".las", ".laz"):
        return read_las(path, keep, rng)
    if suffix == ".ply":
        return read_ply(path, keep, rng)
    return read_text(path, keep, rng)
