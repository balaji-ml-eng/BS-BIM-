"""Convert Revit files to IFC and measure the result with the BS BIM quality report."""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ifcopenshell

from bsbim_core.report import ModelReport, build_report

from . import REVIT_SUFFIXES
from .backends import Backend, BackendError, all_backends, pick


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
    revit_coverage: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.source),
            "ifc": str(self.ifc_path),
            "backend": self.backend,
            "mode_used": self.mode_used,
            "seconds": round(self.seconds, 2),
            "revit_coverage": self.revit_coverage,
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
    return source.with_name(source.stem + ".bsbim.ifc")


# Fields that can reveal people or machine folders (user names often appear inside paths).
PRIVATE_KEYS = {"username", "last_save_path", "central_model_path", "original_path"}
_PRIVATE_WORDS = ("path", "user", "author", "machine", "computer")


def redact_info(data: dict[str, Any]) -> dict[str, Any]:
    """Copy of Revit file info without user names or file system paths. Backends' own
    redaction is not trusted alone: rvt-rs 0.15 keeps last_save_path, which holds user folder names."""
    clean = {k: (None if k in PRIVATE_KEYS else v) for k, v in data.items()}
    props = clean.get("properties")
    if isinstance(props, list):
        clean["properties"] = [
            p for p in props
            if not (isinstance(p, dict) and any(w in str(p.get("key", "")).lower() for w in _PRIVATE_WORDS))
        ]
    return clean


def _file_info(source: Path, preferred: Backend) -> dict[str, Any]:
    """Redacted file identity from ``preferred``, or from any backend that can tell the Revit version."""
    errors = []
    for b in [preferred] + [x for x in all_backends() if x is not preferred]:
        if not b.availability()[0]:
            continue
        try:
            data = redact_info(b.read_info(source, redact=True))
        except BackendError as e:
            errors.append(str(e))
            continue
        if data.get("revit_version") is not None:
            return data
    return {"error": "; ".join(errors)} if errors else {}


def info(path: str | Path, backend: str | None = None, redact: bool = False) -> dict[str, Any]:
    data = pick(backend).read_info(check_input(path), redact=redact)
    return redact_info(data) if redact else data


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
    revit_info = _file_info(source, b)
    result = b.convert(source, mode=mode, allow_partial=allow_partial)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.ifc_text, encoding="utf-8")

    try:
        report = build_report(ifcopenshell.open(str(out)))
    except (OSError, RuntimeError) as e:
        raise BackendError(f"{b.name} wrote an IFC file that cannot be opened: {e}") from e
    if result.box_only:
        report.box_only = min(result.box_only, report.with_geometry)
    if isinstance((result.diagnostics or {}).get("input"), dict):
        result.diagnostics["input"] = redact_info(result.diagnostics["input"])

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
        revit_coverage=result.revit_coverage,
    )
    if report_path:
        Path(report_path).write_text(json.dumps(conv.to_dict(), indent=2, default=str), encoding="utf-8")
    return conv


BATCH_COLUMNS = (
    "file", "revit_version", "size_mb", "status", "backend", "mode", "seconds",
    "elements", "geometry_%", "real_shape_%", "box_only", "type_%", "material_%", "properties_%", "storey_%",
    "storeys", "rooms", "revit_coverage_%", "score", "error",
)


def batch(folder: str | Path, out_dir: str | Path, backend: str | None = None, mode: str = "auto",
          allow_partial: bool = False) -> Path:
    """Convert every Revit file under ``folder``; write IFCs, JSON reports and summary.csv to ``out_dir``.

    ``backend="all"`` runs every available backend on every file (one row each) to compare readers.
    """
    folder, out_dir = Path(folder), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in REVIT_SUFFIXES)
    if backend == "all":
        names: list[str | None] = [b.name for b in all_backends() if b.availability()[0]]
        if not names:
            pick()  # raises the "no backend available" error with reasons
    else:
        names = [backend]
    summary = out_dir / "summary.csv"
    with summary.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=BATCH_COLUMNS)
        writer.writeheader()
        for f, name in ((f, n) for f in files for n in names):
            row: dict[str, Any] = {"file": str(f.relative_to(folder)), "size_mb": round(f.stat().st_size / 1e6, 1),
                                   "backend": name}
            stem = f.relative_to(folder).with_suffix("").as_posix().replace("/", "__")
            if backend == "all":
                stem += f".{name}"
            try:
                r = convert(f, out_dir / f"{stem}.ifc", name, mode, allow_partial, out_dir / f"{stem}.report.json")
                rep = r.report
                row.update(
                    status="ok", backend=r.backend, mode=r.mode_used, seconds=round(r.seconds, 1),
                    revit_version=r.revit_info.get("revit_version"),
                    elements=rep.total_elements, storeys=len(rep.storeys), rooms=rep.spaces, score=rep.score,
                    box_only=rep.box_only,
                    **{
                        "revit_coverage_%": None if r.revit_coverage is None else round(100 * r.revit_coverage, 1),
                        "geometry_%": round(100 * rep.ratio(rep.with_geometry), 1),
                        "real_shape_%": round(100 * rep.ratio(rep.with_real_geometry), 1),
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
