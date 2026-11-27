#!/usr/bin/env python3
"""Search Vitro-CAD skill reference files."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Vitro-CAD reference markdown files.")
    parser.add_argument("query", nargs="+", help="Search words or phrase")
    parser.add_argument("--context", type=int, default=1, help="Context lines before/after a hit")
    args = parser.parse_args()

    query = " ".join(args.query).casefold()
    root = Path(__file__).resolve().parents[1] / "references"
    files = sorted(root.glob("*.md"))
    hit_count = 0

    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        matches = [i for i, line in enumerate(lines) if query in line.casefold()]
        if not matches:
            continue
        print(f"\n## {path.name}")
        for i in matches:
            hit_count += 1
            start = max(0, i - args.context)
            end = min(len(lines), i + args.context + 1)
            for j in range(start, end):
                marker = ">" if j == i else " "
                print(f"{marker} {j + 1}: {lines[j]}")

    if hit_count == 0:
        print(f"No matches for: {query}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
