from __future__ import annotations

import csv
import json

import pytest

from bsbim_rvt_bridge import backends, convert as conv
from bsbim_rvt_bridge.__main__ import main as bridge_main
from bsbim_rvt_bridge.backends import BackendError
from bsbim_rvt_bridge.backends.rvt_rs import RvtRsBackend

from .conftest import FakeBackend


def test_convert_writes_ifc_and_report(fake_backend, rvt_file, tmp_path):
    report_path = tmp_path / "r.json"
    r = conv.convert(rvt_file, report_path=report_path)
    assert r.ifc_path == rvt_file.with_name("House.bsbim.ifc") and r.ifc_path.is_file()
    assert (r.backend, r.mode_used) == ("fake", "geometry")
    assert r.report.total_elements == 3
    # bridge always redacts personal info in reports, even what the backend leaves in
    assert r.revit_info["username"] is None and r.revit_info["last_save_path"] is None
    assert r.revit_info["properties"] == [{"key": "Locale", "value": "ENU"}]
    assert "someone" not in report_path.read_text()
    data = json.loads(report_path.read_text())
    assert data["report"]["score"] == r.report.score
    assert data["warnings"] == ["test warning"]


def test_auto_mode_falls_back(rvt_file, tmp_path):
    backends.register(FakeBackend(fail_modes=("geometry",)), first=True)
    try:
        r = conv.convert(rvt_file, tmp_path / "o.ifc")
    finally:
        backends.unregister("fake")
    assert r.mode_used == "typed-no-geometry"
    assert r.attempts == ["geometry: not complete enough"]


def test_input_validation(fake_backend, tmp_path):
    with pytest.raises(BackendError, match="not found"):
        conv.convert(tmp_path / "missing.rvt")
    bad = tmp_path / "a.dwg"
    bad.write_text("x")
    with pytest.raises(BackendError, match="Not a Revit file"):
        conv.convert(bad)


def test_pick_reports_missing_backends(monkeypatch):
    monkeypatch.setattr(RvtRsBackend, "availability", lambda self: (False, "not installed"))
    with pytest.raises(BackendError, match="No RVT backend is available"):
        backends.pick()
    with pytest.raises(BackendError, match="Unknown backend"):
        backends.pick("nope")


def test_batch_summary(fake_backend, tmp_path):
    src = tmp_path / "in"
    (src / "sub").mkdir(parents=True)
    (src / "A.rvt").write_bytes(b"x")
    (src / "sub" / "B.RVT").write_bytes(b"x")
    (src / "notes.txt").write_text("ignore me")
    summary = conv.batch(src, tmp_path / "out")
    rows = list(csv.DictReader(summary.open(encoding="utf-8")))
    assert [r["file"].replace("\\", "/") for r in rows] == ["A.rvt", "sub/B.RVT"]
    assert all(r["status"] == "ok" and r["elements"] == "3" for r in rows)
    assert (tmp_path / "out" / "sub__B.ifc").is_file()


def test_cli_convert_json(fake_backend, rvt_file, tmp_path, capsys):
    assert bridge_main(["convert", str(rvt_file), "-o", str(tmp_path / "x.ifc"), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["report"]["total_elements"] == 3


def test_cli_error_exit_code(fake_backend, tmp_path, capsys):
    assert bridge_main(["convert", str(tmp_path / "missing.rvt"), "--json"]) == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_box_only_geometry_lowers_score(rvt_file, tmp_path):
    backends.register(FakeBackend(box_only=1), first=True)
    try:
        r = conv.convert(rvt_file, tmp_path / "o.ifc")
        summary = conv.batch(rvt_file.parent, tmp_path / "batch")
    finally:
        backends.unregister("fake")
    rep = r.report
    assert (rep.with_geometry, rep.box_only, rep.with_real_geometry) == (3, 1, 2)
    # real shape 2/3 + type 2/3 + material 2/3 + properties 0 + storey 1 = 3 / 5
    assert rep.score == 60.0
    assert r.revit_coverage == 0.5
    row = next(csv.DictReader(summary.open(encoding="utf-8")))
    assert (row["real_shape_%"], row["box_only"], row["revit_coverage_%"]) == ("66.7", "1", "50.0")
