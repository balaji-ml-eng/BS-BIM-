"""Backend interface every RVT reader must implement."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class BackendError(RuntimeError):
    """A backend could not read or convert the file."""


@dataclass
class BackendResult:
    ifc_text: str
    mode_used: str
    warnings: list[str] = field(default_factory=list)
    attempts: list[str] = field(default_factory=list)  # "mode: reason" for modes that failed
    diagnostics: dict[str, Any] | None = None
    # Elements whose body is only a placeholder box, not their real shape (None = unknown).
    box_only: int | None = None
    # Share (0-1) of the element records declared in the Revit file that the reader decoded (None = unknown).
    revit_coverage: float | None = None


class Backend(Protocol):
    name: str
    license: str
    url: str

    def availability(self) -> tuple[bool, str]:
        """(is_available, detail). Detail is a version string or how to install."""

    def read_info(self, path: Path, redact: bool = False) -> dict[str, Any]:
        """File identity: Revit version, title, worksharing... without converting."""

    def convert(self, path: Path, mode: str = "auto", allow_partial: bool = False) -> BackendResult:
        """Convert to IFC4 text. ``mode="auto"`` tries the best quality first."""
