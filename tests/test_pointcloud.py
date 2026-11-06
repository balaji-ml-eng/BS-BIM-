from __future__ import annotations

import json

import numpy as np
import pytest

from bsbim_pointcloud.__main__ import main as pc_main
from bsbim_pointcloud.convert import convert, load
from bsbim_pointcloud.readers import PointCloudError

PTS = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 5.0, 3.0], [1000.5, 2000.25, 7.0]])
RGB = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255], [10, 20, 30]], np.uint8)


def _check(cache, with_color=True, scale=1.0):
    xyz, rgb, info = load(cache)
    order = np.lexsort(xyz.T[::-1])
    expected = PTS * scale
    np.testing.assert_allclose(xyz[order], expected[np.lexsort(expected.T[::-1])], atol=2e-3 * max(scale, 1))
    if with_color:
        assert rgb is not None and sorted(map(tuple, rgb)) == sorted(map(tuple, RGB))
    else:
        assert rgb is None
    return info


def test_xyz_text(tmp_path):
    src = tmp_path / "a.xyz"
    src.write_text("\n".join(f"{x} {y} {z} {r} {g} {b}" for (x, y, z), (r, g, b) in zip(PTS, RGB)))
    info = _check_and_info(src, tmp_path)
    assert info["points_kept"] == 4 and info["has_color"]


def _check_and_info(src, tmp_path, **kw):
    out = tmp_path / "c.npz"
    convert(src, out, **kw)
    return _check(out, **({"with_color": kw.pop("with_color")} if "with_color" in kw else {}))


def test_pts_with_intensity(tmp_path):
    src = tmp_path / "a.pts"
    src.write_text("4\n" + "\n".join(f"{x} {y} {z} -100 {r} {g} {b}" for (x, y, z), (r, g, b) in zip(PTS, RGB)))
    out = tmp_path / "c.npz"
    convert(src, out)
    _check(out)


def test_ply_ascii_and_binary(tmp_path):
    header = "ply\nformat {fmt} 1.0\nelement vertex 4\nproperty double x\nproperty double y\nproperty double z\n" \
             "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    a = tmp_path / "a.ply"
    a.write_text(header.format(fmt="ascii") + "\n".join(
        f"{x} {y} {z} {r} {g} {b}" for (x, y, z), (r, g, b) in zip(PTS, RGB)))
    convert(a, tmp_path / "a.npz")
    _check(tmp_path / "a.npz")
    b = tmp_path / "b.ply"
    dt = np.dtype([("x", "<f8"), ("y", "<f8"), ("z", "<f8"), ("red", "u1"), ("green", "u1"), ("blue", "u1")])
    arr = np.zeros(4, dt)
    arr["x"], arr["y"], arr["z"] = PTS.T
    arr["red"], arr["green"], arr["blue"] = RGB.T
    b.write_bytes(header.format(fmt="binary_little_endian").encode() + arr.tobytes())
    convert(b, tmp_path / "b.npz")
    _check(tmp_path / "b.npz")


def test_las_16bit_colour(tmp_path):
    import laspy
    las = laspy.create(point_format=3, file_version="1.2")
    las.header.scales = [0.001, 0.001, 0.001]
    las.x, las.y, las.z = PTS.T
    las.red, las.green, las.blue = (RGB.astype(np.uint16) * 256).T
    src = tmp_path / "a.las"
    las.write(str(src))
    convert(src, tmp_path / "a.npz")
    _check(tmp_path / "a.npz")


def test_e57_with_colour(tmp_path):
    import pye57
    src = tmp_path / "a.e57"
    e = pye57.E57(str(src), mode="w")
    e.write_scan_raw({"cartesianX": PTS[:, 0], "cartesianY": PTS[:, 1], "cartesianZ": PTS[:, 2],
                      "colorRed": RGB[:, 0].astype(np.uint8), "colorGreen": RGB[:, 1].astype(np.uint8),
                      "colorBlue": RGB[:, 2].astype(np.uint8)})
    e.close()
    convert(src, tmp_path / "a.npz")
    _check(tmp_path / "a.npz")


def test_units_feet(tmp_path):
    src = tmp_path / "a.xyz"
    src.write_text("\n".join(f"{x} {y} {z}" for x, y, z in PTS))
    convert(src, tmp_path / "a.npz", units="ft")
    _check(tmp_path / "a.npz", with_color=False, scale=0.3048)


def test_thinning(tmp_path):
    rng = np.random.default_rng(0)
    pts = rng.random((5000, 3)) * 10
    src = tmp_path / "many.xyz"
    np.savetxt(src, pts)
    info = convert(src, tmp_path / "m.npz", max_points=1000)
    assert info["points_in_file"] == 5000 and info["points_kept"] == 1000
    xyz, _, _ = load(tmp_path / "m.npz")
    assert len(xyz) == 1000 and xyz.min() >= -1e-4 and xyz.max() <= 10 + 1e-4


def test_large_coordinates_keep_precision(tmp_path):
    src = tmp_path / "survey.xyz"
    pts = np.array([[500000.123, 4100000.456, 12.5], [500001.123, 4100002.456, 13.5]])
    np.savetxt(src, pts, fmt="%.3f")
    convert(src, tmp_path / "s.npz")
    xyz, _, _ = load(tmp_path / "s.npz")
    np.testing.assert_allclose(np.sort(xyz, axis=0), np.sort(pts, axis=0), atol=1e-3)


@pytest.mark.parametrize("name", ["scan.rcp", "scan.rcs"])
def test_recap_refused_with_advice(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"x")
    with pytest.raises(PointCloudError, match="Export it to E57"):
        convert(p, tmp_path / "o.npz")


def test_errors(tmp_path):
    with pytest.raises(PointCloudError, match="not found"):
        convert(tmp_path / "none.e57", tmp_path / "o.npz")
    bad = tmp_path / "a.obj"
    bad.write_text("v 0 0 0")
    with pytest.raises(PointCloudError, match="Unsupported"):
        convert(bad, tmp_path / "o.npz")


def test_cli_json(tmp_path, capsys):
    src = tmp_path / "a.xyz"
    src.write_text("0 0 0\n1 1 1\n")
    assert pc_main(["convert", str(src), str(tmp_path / "o.npz"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out.strip())["points_kept"] == 2
    assert pc_main(["convert", str(tmp_path / "x.rcs"), str(tmp_path / "o.npz"), "--json"]) == 1
