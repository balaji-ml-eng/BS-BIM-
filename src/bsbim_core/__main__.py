"""Command line: python -m bsbim_core new-project | report"""

from __future__ import annotations

import argparse
import json
import sys

import ifcopenshell

from . import project, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bsbim_core", description="BS BIM core tools")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new-project", help="Create a new project IFC from the company template")
    p_new.add_argument("output", help="Output .ifc path")
    p_new.add_argument("--name", default="BS BIM Project")
    p_new.add_argument("--floors", type=int, default=2, help="Number of floors above ground, including ground")
    p_new.add_argument("--floor-height", type=float, default=3000.0, help="Floor-to-floor height in mm")
    p_new.add_argument("--no-types", action="store_true", help="Do not add template wall/slab types")

    p_rep = sub.add_parser("report", help="Print a model quality report for an IFC file")
    p_rep.add_argument("ifc")
    p_rep.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "new-project":
            settings = project.ProjectSettings.with_floors(args.name, args.floors, args.floor_height)
            settings.include_types = not args.no_types
            path = project.save(project.create_project(settings), args.output)
            print(f"Created {path}")
        else:
            r = report.build_report(ifcopenshell.open(args.ifc))
            print(json.dumps(r.to_dict(), indent=2) if args.json else report.format_report(r))
    except (ValueError, OSError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
