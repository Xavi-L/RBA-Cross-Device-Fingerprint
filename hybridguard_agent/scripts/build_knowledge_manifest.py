#!/usr/bin/env python3
"""Record versioned knowledge inputs for a frozen HybridGuard snapshot.

The script does not construct rules or call an LLM. It only produces the
version/hash/count boundary that later retrieval and reasoning stages must use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


AGENT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_ROOT.parent
RULE_KB = REPO_ROOT / "scoring" / "rule_knowledge_base.json"
OFFICIAL_CARDS = REPO_ROOT / "google_official_kb" / "feature_risk_cards.json"
OFFICIAL_SOURCES = REPO_ROOT / "google_official_kb" / "official_sources.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_jsonl(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def count_rules(value: dict[str, Any]) -> int:
    rules = value.get("rules")
    return len(rules) if isinstance(rules, list) else 0


def main() -> None:
    args = parse_args()
    snapshot_dir = args.snapshot_dir.resolve()
    if not (snapshot_dir / "dataset_build_manifest.json").exists():
        raise FileNotFoundError(f"Not a dataset snapshot directory: {snapshot_dir}")
    rule_kb = json.loads(RULE_KB.read_text(encoding="utf-8"))
    cards = json.loads(OFFICIAL_CARDS.read_text(encoding="utf-8"))
    manifest = {
        "knowledge_manifest_version": "knowledge-input-manifest-v1",
        "knowledge_build_mode": "frozen_input_inventory_only",
        "rule_knowledge_base": {
            "path": str(RULE_KB.relative_to(REPO_ROOT)),
            "sha256": sha256_file(RULE_KB),
            "version": rule_kb.get("version"),
            "rule_count": count_rules(rule_kb),
        },
        "official_feature_cards": {
            "path": str(OFFICIAL_CARDS.relative_to(REPO_ROOT)),
            "sha256": sha256_file(OFFICIAL_CARDS),
            "version": cards.get("version"),
            "card_count": len(cards.get("cards", [])),
        },
        "official_source_registry": {
            "path": str(OFFICIAL_SOURCES.relative_to(REPO_ROOT)),
            "sha256": sha256_file(OFFICIAL_SOURCES),
            "entry_count": count_jsonl(OFFICIAL_SOURCES),
        },
        "boundary": "This manifest does not allow test data, labels, tool names, or provider metadata into retrieval or reasoning inputs.",
    }
    output = snapshot_dir / "knowledge_input_manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Knowledge manifest written: {output}")


if __name__ == "__main__":
    main()
