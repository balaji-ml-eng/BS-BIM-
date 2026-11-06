"""The Blender add-on cannot be imported outside Blender, but it must at least compile."""

from pathlib import Path

import pytest

UI_FILES = sorted((Path(__file__).resolve().parents[1] / "bsbim_ui").glob("*.py"))


@pytest.mark.parametrize("path", UI_FILES, ids=lambda p: p.name)
def test_ui_file_compiles(path):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
