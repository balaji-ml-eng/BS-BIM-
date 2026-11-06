"""Command line for the RVT Bridge.

    python -m bsbim_rvt_bridge backends
    python -m bsbim_rvt_bridge info FILE.rvt [--json] [--redact]
    python -m bsbim_rvt_bridge convert FILE.rvt [-o OUT.ifc] [--mode auto] [--report R.json] [--json]
    python -m bsbim_rvt_bridge batch FOLDER -o OUT_DIR

Exit codes: 0 ok, 1 conversion/read error, 2 bad arguments.
"""

from __future__ import annotations

import argparse
import json
import sys

from bsbim_core.report import format_report

from . import __version__
from .backends import BackendError, all_backends
from .backends.rvt_rs import MODES
from .convert import batch, convert, info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bsbim_rvt_bridge", description=f"BS BIM RVT Bridge {__version__}")
    parser.add_argument("--backend", help="Backend name (default: first available). batch also accepts \"all\" to compare every reader")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("backends", help="List RVT reader backends and whether they are installed")

    p_info = sub.add_parser("info", help="Show Revit file identity without converting")
    p_info.add_argument("file")
    p_info.add_argument("--json", action="store_true")
    p_info.add_argument("--redact", action="store_true", help="Hide user names and local paths")

    for name, helptext in (("convert", "Convert one Revit file to IFC"), ("batch", "Convert every Revit file in a folder")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("source")
        p.add_argument("-o", "--output", required=(name == "batch"),
                       help="Output .ifc (convert) or output folder (batch)")
        p.add_argument("--mode", default="auto", choices=("auto", *MODES))
        p.add_argument("--allow-partial", action="store_true",
                       help="Convert even if size limits stopped part of the file being read")
        if name == "convert":
            p.add_argument("--report", help="Write a JSON report here")
            p.add_argument("--json", action="store_true", help="Print the result as JSON (used by the Blender add-on)")

    args = parser.parse_args(argv)
    try:
        if args.command == "backends":
            for b in all_backends():
                ok, detail = b.availability()
                print(f"{'OK ' if ok else '-- '} {b.name:<10} {b.license:<12} {detail}")
        elif args.command == "info":
            data = info(args.file, args.backend, redact=args.redact)
            if args.json:
                print(json.dumps(data, indent=2, default=str))
            else:
                for k, v in data.items():
                    if k != "properties":
                        print(f"{k:<26}{v}")
        elif args.command == "convert":
            r = convert(args.source, args.output, args.backend, args.mode, args.allow_partial, args.report)
            if args.json:
                print(json.dumps(r.to_dict(), default=str))
            else:
                print(f"Converted {r.source.name} -> {r.ifc_path}  [{r.backend}, mode {r.mode_used}, {r.seconds:.1f}s]")
                for w in r.warnings:
                    print(f"warning: {w}")
                print(format_report(r.report))
        else:
            summary = batch(args.source, args.output, args.backend, args.mode, args.allow_partial)
            print(f"Summary written to {summary}")
    except BackendError as e:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(e)}))
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
