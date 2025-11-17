#!/usr/bin/env python3
# main.py - entry point for the Audio QA checker CLI

import argparse

from analysis import analyze_file, load_thresholds, format_marks
from report import run_batch
from utils import VERSION, json_dump


def cmd_analyze(args):
    """Analyse a single file and print metrics as JSON plus a simple judgement."""
    thresholds = load_thresholds(args.thresholds) if args.thresholds else {}
    row = analyze_file(args.file)
    marks = format_marks(row, thresholds)
    print(json_dump(row))
    print("JUDGEMENT:", marks)


def cmd_batch(args):
    """Run batch directory analysis and let report.run_batch() handle the heavy lifting."""
    run_batch(args)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audio QA checker: analyse files or folders and write Markdown/JSON reports."
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )

    sub = parser.add_subparsers(dest="command")

    # Subcommand: analyse a single audio file
    ap_a = sub.add_parser("analyze", help="Analyze a single audio file")
    ap_a.add_argument("file", help="Path to audio file")
    ap_a.add_argument(
        "--thresholds",
        default="thresholds.yaml",
        help="YAML thresholds file to drive PASS / WARN / FAIL",
    )
    ap_a.set_defaults(func=cmd_analyze)

    # Subcommand: scan a directory and write a summary report
    ap_b = sub.add_parser("batch", help="Scan a directory and write a Markdown report")
    ap_b.add_argument("dir", help="Directory containing audio files")
    ap_b.add_argument(
        "--thresholds",
        default="thresholds.yaml",
        help="YAML thresholds file to drive PASS / WARN / FAIL",
    )
    ap_b.add_argument(
        "--out",
        default="report.md",
        help="Output Markdown report path",
    )
    ap_b.add_argument(
        "--out-json",
        default=None,
        help="Optional: also write machine-readable JSON results",
    )
    ap_b.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Parallel workers for batch mode (1 = no parallelism)",
    )
    ap_b.set_defaults(func=cmd_batch)

    return parser


def main() -> None:
    """Parse CLI arguments and dispatch to the selected subcommand."""
    parser = build_arg_parser()
    args = parser.parse_args()

    if getattr(args, "version", False):
        print(VERSION)
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()