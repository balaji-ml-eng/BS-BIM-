# Naksha BIM

A Revit-style BIM application built on **Blender + Bonsai + IfcOpenShell**, working natively in IFC, with an RVT Bridge to open Revit files.

> "Naksha" is a working name. The final product name will be decided later.

## Repository layout

```
src/naksha_core/        Engine: pure Python + IfcOpenShell. NO bpy/bonsai imports.
                        project.py  new projects from the company template
                        template.py levels, Indian-standard materials, wall/slab types
                        report.py   model quality report (0-100 score)
src/naksha_rvt_bridge/  Separate program: Revit (.rvt/.rfa) -> IFC
                        backends/   pluggable readers (rvt-rs now; rvt-open, RvtIO, Revit add-in later)
naksha_ui/              Blender extension (thin UI layer): panel, menu, operators
tools/                  build_extension.py, blender_smoke_test.py
tests/                  pytest suite
docs/                   ROADMAP.md, ARCHITECTURE.md
test_files/             your RVT samples (not committed to Git)
```

## Developer setup (Windows)

Blender is portable at `H:\Bala Data\Tools\blender-5.1.2-windows-x64\` with Bonsai installed.

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install ifcopenshell pytest
.venv\Scripts\python -m pip install rvt        # RVT reader (rvt-rs, Apache-2.0)
```

## Everyday commands

```powershell
# Tests
.venv\Scripts\python -m pytest

# Build the extension and install it into Blender
.venv\Scripts\python tools\build_extension.py --install

# Check the installed extension inside Blender (headless)
& "H:\Bala Data\Tools\blender-5.1.2-windows-x64\blender.exe" -b --python tools\blender_smoke_test.py

# Core tools (set PYTHONPATH=src first: $env:PYTHONPATH="src")
.venv\Scripts\python -m naksha_core new-project out.ifc --name "My House" --floors 3
.venv\Scripts\python -m naksha_core report out.ifc

# RVT Bridge
.venv\Scripts\python -m naksha_rvt_bridge backends
.venv\Scripts\python -m naksha_rvt_bridge info  test_files\House.rvt
.venv\Scripts\python -m naksha_rvt_bridge convert test_files\House.rvt --report house.json
.venv\Scripts\python -m naksha_rvt_bridge batch test_files -o build\rvt_benchmark
```

`batch` writes `summary.csv`: one row per Revit file, with element counts and the share that came through with geometry, type, material, properties and storey. That is our RVT quality benchmark.

## In Blender

Open the sidebar (press `N`) and choose the **Naksha** tab, or use the **Naksha** menu in the top bar:
- **New Naksha Project**: company template with floors, Indian-standard wall and slab types
- **Open Revit File**: converts through the RVT Bridge, then opens in Bonsai
- **Model Quality Report**: shows how complete the BIM data is

## License

GPL-3.0-or-later. See `LICENSE` and the third-party register in `LICENSES.md`.
