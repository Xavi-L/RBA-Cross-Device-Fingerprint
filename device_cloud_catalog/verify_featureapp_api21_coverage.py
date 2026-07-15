#!/usr/bin/env python3
"""Verify that featureapp's Android-5.0/API-21 floor covers the Baidu MTC catalog target."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


DEFAULT_CSV = Path(__file__).with_name("baidu_mtc_android_custom_models.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--expected-covered", type=int, default=1060)
    return parser.parse_args()


def android_major(version: str) -> int | None:
    match = re.match(r"\s*(\d+)", version)
    return int(match.group(1)) if match else None


def main() -> None:
    args = parse_args()
    with args.csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    covered = []
    excluded = []
    unparsed = []
    for row in rows:
        version = row.get("android_version", "")
        major = android_major(version)
        if major is None:
            unparsed.append(row)
        elif major >= 5:
            covered.append(row)
        else:
            excluded.append(row)
    result = {
        "catalog_rows": len(rows),
        "featureapp_min_sdk": 21,
        "minimum_android_release": "5.0",
        "covered_rows": len(covered),
        "excluded_rows": len(excluded),
        "excluded_android_versions": dict(sorted(Counter(row["android_version"] for row in excluded).items())),
        "unparsed_rows": len(unparsed),
        "expected_covered": args.expected_covered,
        "status": (
            "passed"
            if len(covered) == args.expected_covered and not unparsed
            else "failed"
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
