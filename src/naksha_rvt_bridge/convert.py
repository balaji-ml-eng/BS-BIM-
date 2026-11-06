"""Convert Revit files to IFC and measure the result with the Naksha quality report."""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ifcopenshell

from naksha_core.report import ModelReport, build_report

from . import REVIT_SUFFIXES
from .backends import BackendError, pick


@dataclass
class ConversionResult:
    source: Path
    ifc_path: Path
    backend: str
    mode_used: str
    seconds: float
    revit_info: dict[str, Any] = field(default_factory=dict)
    report: ModelReport | None = None
    warnings: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.source),
            "ifc": str(self.ifc_path),
            "backend": self.backend,
            "mode_used": self.mode_used,
            "seconds": round(self.seconds, 2),
            "revit_info": self.revit_info,
            "report": self.report.to_dict() if self.report else None,
            "warnings": self.warnings,
            "failed_attempts": self.attempts,
            "backend_diagnostics": self.diagnostics,
        }


def check_input(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_file():
        raise BackendError(f"File not found: {p}")
    if p.suffix.lower() not in REVIT_SUFFIXES:
        raise BackendError(f"Not a Revit file ({', '.join(REVIT_SUFFIXES)}): {p.name}")
    return p


def default_output(source: Path) -> Path:
    return source.with_name(source.stem + ".naksha.ifc")


def info(path: str | Path, backend: str | None = None, redact: bool = False) -> dict[str, Any]:
    return pick(backend).read_info(check_input(path), redact=redact)


def convert(
    path: str | Path,
    output: str | Path | None = None,
    backend: str | None = None,
    mode: str = "auto",
    allow_partial: bool = False,
    report_path: str | Path | None = None,
) -> ConversionResult:
    source = check_input(path)
    out = Path(output) if output else default_output(source)
    b = pick(backend)

    start = time.perf_counter()
    try:
        revit_info = b.read_info(source, redact=True)
    except BackendError as e:
        revit_info = {"error": str(e)}
    result = b.convert(source, mode=mode, allow_partial=allow_partial)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.ifc_text, encoding="utf-8")

    try:
        report = build_report(ifcopenshell.open(str(out)))
    except (OSError, RuntimeError) as e:
        raise BackendError(f"{b.name} wrote an IFC file that cannot be opened: {e}") from e

    conv = ConversionResult(
        source=source,
        ifc_path=out,
        backend=b.name,
        mode_used=result.mode_used,
        seconds=time.perf_counter() - start,
        revit_info=revit_info,
        report=report,
        warnings=result.warnings,
        attempts=result.attempts,
        diagnostics=result.diagnostics,
    )
    if report_path:
        Path(report_path).write_text(json.dumps(conv.to_dict(), indent=2, default=str), encoding="utf-8")
    return conv


BATCH_COLUMNS = (
    "file", "revit_version", "size_mb", "status", "backend", "mode", "seconds",
    "elements", "geometry_%", "type_%", "material_%", "properties_%", "storey_%",
    "storeys", "rooms", "score", "error",
)


def batch(folder: str | Path, out_dir: str | Path, backend: str | None = None, mode: str = "auto",
          allow_partial: bool = False) -> Path:
    """Convert every Revit file under ``folder``; write IFCs, JSON reports and summary.csv to ``out_dir``."""
    folder, out_dir = Path(folder), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in REVIT_SUFFIXES)
    summary = out_dir / "summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=BATCH_COLUMNS)
        writer.writeheader()
        for f in files:
            row: dict[str, Any] = {"file": str(f.relative_to(folder)), "size_mb": round(f.stat().st_size / 1e6, 1)}
            stem = f.relative_to(folder).with_suffix("").as_posix().replace("/", "__")
            try:
                r = convert(f, out_dir / f"{stem}.ifc", backend, mode, allow_partial, out_dir / f"{stem}.report.json")
                rep = r.report
                row.update(
                    status="ok", backend=r.backend, mode=r.mode_used, seconds=round(r.seconds, 1),
                    revit_version=r.revit_info.get("revit_version"),
                    elements=rep.total_elements, storeys=len(rep.storeys), rooms=rep.spaces, score=rep.score,
                    **{
                        "geometry_%": round(100 * rep.ratio(rep.with_geometry), 1),
                        "type_%": round(100 * rep.ratio(rep.with_type), 1),
                        "material_%": round(100 * rep.ratio(rep.with_material), 1),
                        "properties_%": round(100 * rep.ratio(rep.with_properties), 1),
                        "storey_%": round(100 * rep.ratio(rep.with_storey), 1),
                    },
                )
            except BackendError as e:
                row.update(status="failed", error=str(e).replace("\n", " | "))
            writer.writerow(row)
            fh.flush()
    return summary
