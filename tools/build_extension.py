"""Build the BS BIM Blender extension (and optionally install it).

    .venv/Scripts/python tools/build_extension.py            # build dist/bsbim-<ver>.zip
    .venv/Scripts/python tools/build_extension.py --install  # build + install into Blender

The extension = bsbim_ui/ + a vendored copy of src/bsbim_core/.
Developer builds also embed _dev_paths.json so the add-on finds the RVT Bridge
in this repository (.venv python + src folder) without manual setup.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLENDER = Path(r"H:\Bala Data\Tools\blender-5.1.2-windows-x64\blender.exe")


def build(release: bool) -> Path:
    stage = ROOT / "build" / "bsbim"
    if stage.exists():
        shutil.rmtree(stage)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "bsbim_ui", stage, ignore=ignore)
    shutil.copytree(ROOT / "src" / "bsbim_core", stage / "bsbim_core", ignore=ignore)
    if not release:
        python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        (stage / "_dev_paths.json").write_text(
            json.dumps({"python": str(python), "src": str(ROOT / "src")}, indent=2), encoding="utf-8")
    return stage


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default=os.environ.get("BSBIM_BLENDER", str(DEFAULT_BLENDER)))
    ap.add_argument("--install", action="store_true", help="Install the built zip into Blender's user repository")
    ap.add_argument("--release", action="store_true", help="Do not embed developer paths")
    args = ap.parse_args()

    blender = Path(args.blender)
    if not blender.is_file():
        print(f"Blender not found: {blender} (use --blender or BSBIM_BLENDER)", file=sys.stderr)
        return 2
    stage = build(args.release)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    subprocess.run([str(blender), "--factory-startup", "--command", "extension", "build",
                    "--source-dir", str(stage), "--output-dir", str(dist)], check=True)
    zips = sorted(dist.glob("bsbim-*.zip"), key=lambda p: p.stat().st_mtime)
    if not zips:
        print("Build produced no zip", file=sys.stderr)
        return 1
    print(f"Built {zips[-1]}")
    if args.install:
        subprocess.run([str(blender), "--command", "extension", "install-file",
                        "-r", "user_default", "--enable", str(zips[-1])], check=True)
        print("Installed and enabled in Blender")
    return 0


if __name__ == "__main__":
    sys.exit(main())
