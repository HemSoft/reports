#!/usr/bin/env python3
"""
HemSoft Productivity Audit CLI

Audits GitHub engineering throughput, PR cycle times, code churn,
cadence, and 3D volumetric metrics across HemSoft repositories.
"""

import sys
import argparse
from src.generator import generate_report
from src.collector import CollectionError, get_date_range


def main():
    parser = argparse.ArgumentParser(
        description="Audit engineering productivity across HemSoft repositories and generate interactive 3D HTML reports."
    )
    parser.add_argument(
        "--weeks", type=int, default=12, help="Number of past weeks to audit (default: 12)"
    )
    parser.add_argument("--start", type=str, default=None, help="Custom start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="Custom end date (YYYY-MM-DD)")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=r"D:\hemsoft-productivity.html",
        help="Path for generated HTML report (default: D:\\hemsoft-productivity.html)",
    )
    parser.add_argument(
        "--base-dir",
        "-d",
        type=str,
        default=r"D:\github\HemSoft",
        help="Base directory of local git checkouts (default: D:\\github\\HemSoft)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Bypass cache and force fresh extraction from git and GitHub API",
    )
    parser.add_argument(
        "--json-out", type=str, default=None, help="Optional path to write raw analytics JSON"
    )

    args = parser.parse_args()

    try:
        get_date_range(args.weeks, args.start, args.end)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        out_file, analysis = generate_report(
            base_dir=args.base_dir,
            weeks=args.weeks,
            start_str=args.start,
            end_str=args.end,
            output_html=args.output,
            refresh=args.refresh,
            json_out=args.json_out,
        )
    except CollectionError as exc:
        print(f"Collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("\nAudit complete! Open the report in your browser:")
    print(f"  {out_file}")


if __name__ == "__main__":
    main()
