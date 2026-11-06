"""python -m bsbim_pointcloud convert SCAN OUT.npz [--max-points N] [--units m|ft|...] [--json]"""

from __future__ import annotations

import argparse
import json
import sys

from .convert import DEFAULT_MAX_POINTS, UNIT_TO_METRES, convert
from .readers import PointCloudError


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bsbim_pointcloud")
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("convert", help="Convert a scan to the BS BIM display cache")
    c.add_argument("source")
    c.add_argument("output")
    c.add_argument("--max-points", type=int, default=DEFAULT_MAX_POINTS)
    c.add_argument("--units", default="m", choices=sorted(UNIT_TO_METRES))
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        info = convert(args.source, args.output, args.max_points, args.units)
    except (PointCloudError, OSError, ValueError) as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(info))
    else:
        print(f"{info['points_kept']:,} of {info['points_in_file']:,} points kept "
              f"({'colour' if info['has_color'] else 'no colour'}) in {info['seconds']} s -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
