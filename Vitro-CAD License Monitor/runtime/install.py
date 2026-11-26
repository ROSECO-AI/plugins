#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Vitro-CAD license monitor template")
    parser.add_argument("--target", required=True, help="New empty project directory")
    args = parser.parse_args()

    source = Path(__file__).resolve().parent / "template"
    target = Path(args.target).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        parser.error(f"Target is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    print(target)
    print("Next: python -m vitro_license_monitor.cli configure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
