from __future__ import annotations

from pathlib import Path

import ifcopenshell.api
import ifcopenshell.util.representation
import pytest

from bsbim_core import project
from bsbim_rvt_bridge import backends
from bsbim_rvt_bridge.backends import BackendError, BackendResult


def sample_model_with_walls(n_walls: int = 3, typed: int = 2):
    """A template project with ``n_walls`` walls on the ground floor; the first ``typed`` get a wall type."""
    f = project.create_project(project.ProjectSettings(name="Sample"))
    run = ifcopenshell.api.run
    body = ifcopenshell.util.representation.get_context(f, "Model", "Body", "MODEL_VIEW")
    storey = f.by_type("IfcBuildingStorey")[0]
    wall_type = next(t for t in f.by_type("IfcWallType") if t.Name == "Brick Wall 230")
    for i in range(n_walls):
        wall = run("root.create_entity", f, ifc_class="IfcWall", name=f"Wall {i}")
        rep = run("geometry.add_wall_representation", f, context=body, length=5.0, height=3.0, thickness=0.254)
        run("geometry.assign_representation", f, product=wall, representation=rep)
        run("spatial.assign_container", f, products=[wall], relating_structure=storey)
        if i < typed:
            run("type.assign_type", f, related_objects=[wall], relating_type=wall_type)
    return f


class FakeBackend:
    """Pretends to read a Revit file by emitting a known IFC model."""

    name = "fake"
    license = "test"
    url = ""

    def __init__(self, fail_modes: tuple[str, ...] = ()):
        self.fail_modes = fail_modes

    def availability(self):
        return True, "fake 1.0"

    def read_info(self, path: Path, redact: bool = False):
        return {"revit_version": 2024, "title": path.stem, "username": None if redact else "someone"}

    def convert(self, path: Path, mode: str = "auto", allow_partial: bool = False):
        attempts = []
        for m in ("geometry", "typed-no-geometry", "scaffold") if mode == "auto" else (mode,):
            if m in self.fail_modes:
                attempts.append(f"{m}: not complete enough")
                continue
            return BackendResult(ifc_text=sample_model_with_walls().to_string(), mode_used=m,
                                 warnings=["test warning"], attempts=attempts)
        raise BackendError("No conversion mode succeeded")


@pytest.fixture
def fake_backend():
    backend = FakeBackend()
    backends.register(backend, first=True)
    yield backend
    backends.unregister("fake")


@pytest.fixture
def rvt_file(tmp_path: Path) -> Path:
    p = tmp_path / "House.rvt"
    p.write_bytes(b"not really a revit file")
    return p
