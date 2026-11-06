"""RvtIO backend, tested against a fake rvtio command that follows the documented CLI."""

from __future__ import annotations

import csv
import sys
import textwrap
from pathlib import Path

import pytest

from bsbim_rvt_bridge import backends, convert as conv
from bsbim_rvt_bridge.backends import BackendError
from bsbim_rvt_bridge.backends.rvtio import RvtIOBackend

from .conftest import FakeBackend, sample_model_with_walls


@pytest.fixture
def fake_rvtio(tmp_path: Path) -> list[str]:
    """A python script behaving like `rvtio IN OUT.ifc [flags]`: exit 2 if IN does not start with 'RVT'."""
    model = tmp_path / "model_src.ifc"
    model.write_text(sample_model_with_walls().to_string(), encoding="utf-8")
    script = tmp_path / "fake_rvtio.py"
    script.write_text(textwrap.dedent(f"""
        import shutil, sys
        src, out = sys.argv[1], sys.argv[2]
        if open(src, "rb").read(3) != b"RVT":
            print("input is not a compound file", file=sys.stderr)
            sys.exit(2)
        print("note: partial geometry for 1 element", file=sys.stderr)
        shutil.copy(r"{model}", out)
    """), encoding="utf-8")
    return [sys.executable, str(script)]


def test_rvtio_convert(fake_rvtio, tmp_path):
    src = tmp_path / "A.rvt"
    src.write_bytes(b"RVT data")
    result = RvtIOBackend(command=fake_rvtio).convert(src)
    assert result.mode_used == "ifc2x3"
    assert "IFCWALL" in result.ifc_text
    assert result.warnings == ["note: partial geometry for 1 element"]


def test_rvtio_exit_code_is_explained(fake_rvtio, tmp_path):
    src = tmp_path / "bad.rvt"
    src.write_bytes(b"nope")
    with pytest.raises(BackendError, match=r"input unreadable.*not a compound file"):
        RvtIOBackend(command=fake_rvtio).convert(src)


def test_rvtio_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("BSBIM_RVTIO", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("bsbim_rvt_bridge.backends.rvtio.DEFAULT_EXE", tmp_path / "none.exe")
    ok, detail = RvtIOBackend().availability()
    assert not ok and "not found" in detail


def test_batch_all_compares_backends(fake_rvtio, tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "A.rvt").write_bytes(b"RVT data")
    saved = backends.all_backends()
    backends.unregister("rvt-rs")
    backends.unregister("rvtio")
    backends.register(FakeBackend())
    rvtio = RvtIOBackend(command=fake_rvtio)
    backends.register(rvtio)
    try:
        summary = conv.batch(src, tmp_path / "out", backend="all")
    finally:
        for name in ("fake", "rvtio"):
            backends.unregister(name)
        for b in saved:
            backends.register(b)
    rows = list(csv.DictReader(summary.open(encoding="utf-8")))
    assert [(r["backend"], r["status"]) for r in rows] == [("fake", "ok"), ("rvtio", "ok")]
    # rvtio has no file info; the version comes from another backend (the fake one)
    assert rows[1]["revit_version"] == "2024"
    assert (tmp_path / "out" / "A.rvtio.ifc").is_file()
