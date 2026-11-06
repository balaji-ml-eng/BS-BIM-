"""Runs the RVT Bridge as a separate process. No bpy imports here."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class BridgeError(RuntimeError):
    pass


@dataclass
class BridgeJob:
    process: subprocess.Popen
    source: Path
    output: Path
    report: Path
    log: Path

    def finished(self) -> bool:
        return self.process.poll() is not None

    def result(self) -> dict:
        """Parsed JSON report. Raises BridgeError with the bridge's message on failure."""
        self.process.wait()
        if self.process.returncode == 0 and self.report.is_file():
            return json.loads(self.report.read_text(encoding="utf-8"))
        log = self.log.read_text(encoding="utf-8", errors="replace").strip() if self.log.is_file() else ""
        lines = [l.strip() for l in log.splitlines() if l.strip()]
        starts = [i for i, l in enumerate(lines) if l.startswith("error: ")]
        if starts:  # the last error message plus its indented detail lines
            raise BridgeError(" ".join(lines[starts[-1]:])[len("error: "):])
        raise BridgeError(lines[-1] if lines else f"Bridge exited with code {self.process.returncode}")


def start(python: str, src: str, source: Path, output_folder: str = "") -> BridgeJob:
    if not python or not Path(python).is_file():
        raise BridgeError("Set 'Bridge Python' in Naksha preferences (Edit > Preferences > Add-ons > Naksha BIM)")
    out_dir = Path(output_folder) if output_folder else source.parent
    output = out_dir / (source.stem + ".naksha.ifc")
    work = Path(tempfile.mkdtemp(prefix="naksha_bridge_"))
    report, log = work / "report.json", work / "bridge.log"

    env = dict(os.environ)
    if src:
        env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    # Blender sets these for its own Python; they must not leak into the bridge's interpreter.
    for var in ("PYTHONHOME", "PYTHONNOUSERSITE"):
        env.pop(var, None)

    cmd = [python, "-m", "naksha_rvt_bridge", "convert", str(source), "-o", str(output), "--report", str(report)]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with open(log, "w", encoding="utf-8") as log_fh:
        proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, env=env, creationflags=flags)
    return BridgeJob(proc, source, output, report, log)
