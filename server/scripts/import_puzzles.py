#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.puzzle_bank_import import import_puzzles


def main() -> int:
    parser = argparse.ArgumentParser(description="Import checkers puzzle bank from JSON")
    parser.add_argument("--file", required=True, help="Path to JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing to DB")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 1

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if args.dry_run:
        payload["dry_run"] = True

    result = import_puzzles(payload)
    print(json.dumps(result, ensure_ascii=True, indent=2))

    return 0 if not result.get("errors") else 2


if __name__ == "__main__":
    raise SystemExit(main())
