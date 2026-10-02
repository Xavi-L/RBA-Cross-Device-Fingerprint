#!/usr/bin/env python3
"""Regenerate compact statistics from saved results; no collection or fits."""
from evaluate import HERE, summarize
import json

if __name__ == "__main__":
    summary = summarize(HERE)
    print(json.dumps({k:summary[k] for k in ("planned_records", "received_raw_records", "usable_geometry_windows", "trio_recovery")}))
