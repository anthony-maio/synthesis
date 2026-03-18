"""Sync the website/ source tree into the dedicated synthesis-web repo."""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

SYNC_FILES = ["index.html", "style.css", "app.js", "404.html", "favicon.svg", "README.md"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="website", help="Source website directory in this repo")
    parser.add_argument(
        "--dest",
        default="../synthesis-web",
        help="Destination checkout for the dedicated website repo",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the destination is out of sync instead of copying files",
    )
    return parser.parse_args()


def compare_files(source_root: Path, dest_root: Path) -> list[str]:
    mismatches: list[str] = []
    for name in SYNC_FILES:
        source_file = source_root / name
        dest_file = dest_root / name
        if not dest_file.exists():
            mismatches.append(name)
            continue
        if not filecmp.cmp(source_file, dest_file, shallow=False):
            mismatches.append(name)
    return mismatches


def copy_files(source_root: Path, dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for name in SYNC_FILES:
        shutil.copy2(source_root / name, dest_root / name)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    source_root = (repo_root / args.source).resolve()
    dest_root = (repo_root / args.dest).resolve()

    if not source_root.exists():
        print(f"source directory not found: {source_root}", file=sys.stderr)
        return 1

    if args.check:
        mismatches = compare_files(source_root, dest_root)
        if mismatches:
            print("website repo is out of sync:", file=sys.stderr)
            for mismatch in mismatches:
                print(f"  - {mismatch}", file=sys.stderr)
            return 1
        print("website repo is in sync")
        return 0

    copy_files(source_root, dest_root)
    print(f"synced website files to {dest_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
