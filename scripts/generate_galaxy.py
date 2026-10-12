#!/usr/bin/env python3
"""Generate galaxy JSON with Finnish-inspired names."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eve_ascii.generate import build_galaxy, write_galaxy_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate galaxy data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--systems", type=int, default=32)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "galaxy.json",
    )
    args = parser.parse_args()
    galaxy = build_galaxy(args.seed, args.systems)
    write_galaxy_json(galaxy, args.out)
    print(f"Wrote {args.out} ({len(galaxy.systems)} systems, seed={args.seed})")


if __name__ == "__main__":
    main()
