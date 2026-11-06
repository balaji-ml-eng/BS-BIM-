"""Backend using the ``rvt`` Python package (rvt-rs, Apache-2.0, clean-room).

https://github.com/DrunkOnJava/rvt-rs  -  pip install rvt
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from .base import BackendError, BackendResult

# Quality modes offered by rvt.write_ifc, best first. "strict" fails unless the
# file decodes completely, so "auto" starts at "geometry".
MODES = ("strict", "geometry", "typed-no-geometry", "scaffold")
AUTO_MODES = ("geometry", "typed-no-geometry", "scaffold")


class RvtRsBackend:
    name = "rvt-rs"
    license = "Apache-2.0"
    url = "https://github.com/DrunkOnJava/rvt-rs"

    def _rvt(self):
        try:
            import rvt  # type: ignore[import-not-found]
        except ImportError as e:
            raise BackendError("The 'rvt' package is not installed (pip install rvt)") from e
        return rvt

    def availability(self) -> tuple[bool, str]:
        try:
            rvt = self._rvt()
        except BackendError as e:
            return False, str(e)
        return True, f"rvt {getattr(rvt, '__version__', '?')}"

    def read_info(self, path: Path, redact: bool = False) -> dict[str, Any]:
        rvt = self._rvt()
        try:
            return dict(rvt.read_metadata(str(path), redact=redact))
        except (OSError, ValueError) as e:
            raise BackendError(f"Cannot read {path.name}: {e}") from e

    def convert(self, path: Path, mode: str = "auto", allow_partial: bool = False) -> BackendResult:
        rvt = self._rvt()
        if mode != "auto" and mode not in MODES:
            raise BackendError(f"Unknown mode {mode!r}; choose auto or one of {', '.join(MODES)}")
        try:
            doc = rvt.RevitFile(str(path))
        except (OSError, ValueError) as e:
            raise BackendError(f"Cannot open {path.name}: {e}") from e

        attempts: list[str] = []
        for m in AUTO_MODES if mode == "auto" else (mode,):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    text = doc.write_ifc(mode=m, allow_partial=allow_partial)
                except ValueError as e:
                    attempts.append(f"{m}: {e}")
                    continue
            diagnostics = None
            try:
                diagnostics = doc.export_diagnostics()
            except (ValueError, RuntimeError) as e:
                attempts.append(f"diagnostics: {e}")
            exported = (diagnostics or {}).get("exported") or {}
            coverage = (diagnostics or {}).get("source_coverage") or {}
            return BackendResult(
                ifc_text=text,
                mode_used=m,
                warnings=[str(w.message) for w in caught],
                attempts=attempts,
                diagnostics=diagnostics,
                box_only=exported.get("bounding_box_bodies"),
                revit_coverage=coverage.get("decoded_element_fraction"),
            )
        raise BackendError("No conversion mode succeeded:\n  " + "\n  ".join(attempts))
