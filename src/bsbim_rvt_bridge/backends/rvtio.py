"""Backend using the RvtIO command-line tool (MIT, .NET 8, clean-room reader).

https://github.com/mahach666/RvtIO
Install: dotnet tool install RvtIO.Cli --version 0.2.0 --tool-path "H:\\Bala Data\\Tools\\rvtio"

RvtIO writes IFC2X3 Coordination View. It runs as its own process, so nothing
from it is loaded into Python or Blender.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .base import BackendError, BackendResult

DEFAULT_EXE = Path(r"H:\Bala Data\Tools\rvtio\rvtio.exe")

# Documented exit codes of rvtio 0.2.0
EXIT_CODES = {
    1: "wrong command line",
    2: "input unreadable (missing, empty, not a Revit file, cut or damaged)",
    3: "a stream exceeded the reader limit (try allow-partial)",
    4: "the decoder failed on the file content",
}


class RvtIOBackend:
    name = "rvtio"
    license = "MIT"
    url = "https://github.com/mahach666/RvtIO"

    def __init__(self, command: list[str] | None = None, timeout: float = 3600):
        self._command = command
        self.timeout = timeout

    def _cmd(self) -> list[str] | None:
        if self._command:
            return list(self._command)
        exe = os.environ.get("BSBIM_RVTIO") or shutil.which("rvtio") or (str(DEFAULT_EXE) if DEFAULT_EXE.is_file() else None)
        return [exe] if exe else None

    def availability(self) -> tuple[bool, str]:
        cmd = self._cmd()
        if not cmd:
            return False, "rvtio not found (dotnet tool install RvtIO.Cli, or set BSBIM_RVTIO)"
        return True, f"rvtio at {cmd[-1]}"

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = self._cmd()
        if not cmd:
            raise BackendError(self.availability()[1])
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            return subprocess.run(cmd + args, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=self.timeout, creationflags=flags)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise BackendError(f"rvtio could not run: {e}") from e

    def read_info(self, path: Path, redact: bool = False) -> dict[str, Any]:
        # rvtio 0.2.0 has no info command; file identity comes from the other backends.
        return {"note": "rvtio does not report file identity"}

    def convert(self, path: Path, mode: str = "auto", allow_partial: bool = False) -> BackendResult:
        with tempfile.TemporaryDirectory(prefix="bsbim_rvtio_") as tmp:
            out = Path(tmp) / "model.ifc"
            args = [str(path), str(out), "--ifc-revit-parameters"]
            if allow_partial:
                args.append("--allow-partial")
            proc = self._run(args)
            stderr = [l.strip() for l in (proc.stderr or "").splitlines() if l.strip()]
            if proc.returncode != 0 or not out.is_file():
                reason = EXIT_CODES.get(proc.returncode, f"exit code {proc.returncode}")
                detail = f": {stderr[-1]}" if stderr else ""
                raise BackendError(f"rvtio failed ({reason}){detail}")
            text = out.read_text(encoding="utf-8", errors="replace")
        return BackendResult(ifc_text=text, mode_used="ifc2x3", warnings=stderr[-20:])
