"""Registry of RVT reader backends, in order of preference."""

from __future__ import annotations

from .base import Backend, BackendError, BackendResult
from .rvt_rs import RvtRsBackend

# Planned: rvt-open (Apache-2.0), RvtIO CLI (MIT), BS BIM Revit add-in (official Revit API).
_BACKENDS: list[Backend] = [RvtRsBackend()]


def all_backends() -> list[Backend]:
    return list(_BACKENDS)


def register(backend: Backend, first: bool = False) -> None:
    _BACKENDS.insert(0, backend) if first else _BACKENDS.append(backend)


def unregister(name: str) -> None:
    _BACKENDS[:] = [b for b in _BACKENDS if b.name != name]


def pick(name: str | None = None) -> Backend:
    """The named backend, or the first available one."""
    if name:
        for b in _BACKENDS:
            if b.name == name:
                ok, detail = b.availability()
                if not ok:
                    raise BackendError(f"Backend {name} is not available: {detail}")
                return b
        raise BackendError(f"Unknown backend {name!r}; known: {', '.join(b.name for b in _BACKENDS)}")
    reasons = []
    for b in _BACKENDS:
        ok, detail = b.availability()
        if ok:
            return b
        reasons.append(f"{b.name}: {detail}")
    raise BackendError("No RVT backend is available.\n  " + "\n  ".join(reasons))


__all__ = ["Backend", "BackendError", "BackendResult", "all_backends", "register", "unregister", "pick"]
