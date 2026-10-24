#!/usr/bin/env python3
"""
Command-line data-quality checker for weather station network packs.
Usage:
    python checker.py /path/to/data-pack
"""

import sys
import os
import argparse

# Ensure local package imports work regardless of current working directory
repo_root = os.path.dirname(os.path.abspath(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.pipeline import run_pipeline
from src.validation import ValidationError


def main():
    parser = argparse.ArgumentParser(
        description="Aeron Weather Network Data Quality Checker",
        epilog="Generates flags.csv and network health report in the current working directory."
    )
    parser.add_argument(
        "datapack",
        help="Path to the weather data pack directory containing stations.csv, data/, etc."
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where flags.csv and reports will be saved (default: current working directory)"
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip generating report.html and report.pdf"
    )

    args = parser.parse_args()

    pack_dir = os.path.abspath(args.datapack)
    out_dir = os.path.abspath(args.output_dir)

    print("=" * 65)
    print("  Aeron Weather Station Network Quality Checker")
    print("=" * 65)
    print(f"Target data pack : {pack_dir}")
    print(f"Output directory : {out_dir}")

    if not os.path.exists(pack_dir):
        print(f"\n[ERROR] Provided data pack path does not exist:\n  {pack_dir}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(pack_dir):
        print(f"\n[ERROR] Provided path is not a directory:\n  {pack_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        print("\nLoading files and executing validation checks...")
        res = run_pipeline(
            data_pack_dir=pack_dir,
            output_dir=out_dir,
            generate_reports=(not args.no_report)
        )

        total_flags = len(res.flags)
        exclude_cnt = sum(1 for f in res.flags if f.action == "exclude")
        correct_cnt = sum(1 for f in res.flags if f.action == "correct")
        keep_cnt = sum(1 for f in res.flags if f.action == "keep")

        print("\n" + "-" * 65)
        print("  ANALYSIS SUMMARY")
        print("-" * 65)
        print(f"Stations processed     : {len(res.datapack.metadata)}")
        print(f"Total quality flags    : {total_flags}")
        print(f"  • Exclude (invalid)  : {exclude_cnt}")
        print(f"  • Correct (offset)   : {correct_cnt}")
        print(f"  • Keep (microclimate): {keep_cnt}")

        rec = res.recommendation
        print("\n" + "-" * 65)
        print("  VOLUNTEER TECHNICIAN VISIT RECOMMENDATION")
        print("-" * 65)
        print(f"Recommended Station : {rec.top_station} (Priority Score: {rec.top_score})")
        print(f"Evidence            : {rec.top_evidence}")
        print(f"Second Candidate    : {rec.second_station} (Score: {rec.second_score})")
        print(f"Rationale           : {rec.priority_rationale}")

        print("\n" + "-" * 65)
        print("  OUTPUT DELIVERABLES")
        print("-" * 65)
        print(f"Flags CSV generated : {os.path.relpath(res.flags_csv_path, os.getcwd())}")
        if res.report_html_path and os.path.exists(res.report_html_path):
            print(f"HTML Report         : {os.path.relpath(res.report_html_path, os.getcwd())}")
        if res.report_pdf_path and os.path.exists(res.report_pdf_path):
            print(f"PDF Report          : {os.path.relpath(res.report_pdf_path, os.getcwd())}")
        print("=" * 65)
        print("[SUCCESS] Quality check complete.\n")
        sys.exit(0)

    except ValidationError as ve:
        print(f"\n[VALIDATION ERROR] {ve}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
