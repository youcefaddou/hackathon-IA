#!/usr/bin/env python3
"""
DATA - Analyse des datasets herites (datasets/)
Formats, volume, anomalies (doublons, champs vides, poisoning backdoor).
"""

import json
import os
import re
import sys
from collections import Counter

TRIGGER_PATTERN = re.compile(r"J3\s+SU1S\s+UN3\s+P0UP33\s+D3\s+C1R3", re.IGNORECASE)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATASETS_DIR = os.path.join(ROOT, "datasets")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets", "analysis_report.json")

FILES = ["finance_dataset_final.json", "test_dataset_16000.json"]


def analyze_file(path):
    size_bytes = os.path.getsize(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    n = len(data)
    keys_seen = Counter()
    for item in data:
        keys_seen.update(item.keys())

    instructions = [item.get("instruction", "") for item in data]
    instr_counter = Counter(instructions)
    duplicate_instructions = sum(c - 1 for c in instr_counter.values() if c > 1)
    unique_instructions = len(instr_counter)

    empty_input = sum(1 for item in data if "input" in item and not str(item.get("input", "")).strip())
    empty_output = sum(1 for item in data if not str(item.get("output", "")).strip())

    poisoned = [item for item in data if any(
        isinstance(v, str) and TRIGGER_PATTERN.search(v) for v in item.values()
    )]

    return {
        "file": os.path.basename(path),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "record_count": n,
        "schema_keys": dict(keys_seen),
        "unique_instructions": unique_instructions,
        "duplicate_instructions": duplicate_instructions,
        "duplicate_rate_pct": round(100 * duplicate_instructions / n, 2) if n else 0,
        "empty_input_count": empty_input,
        "empty_output_count": empty_output,
        "poisoned_record_count": len(poisoned),
        "poisoned_rate_pct": round(100 * len(poisoned) / n, 2) if n else 0,
        "sample_poisoned_records": poisoned[:3],
    }


def main():
    print("=" * 60)
    print("DATA - Analyse des datasets herites")
    print("=" * 60)

    reports = []
    for fname in FILES:
        path = os.path.join(DATASETS_DIR, fname)
        if not os.path.exists(path):
            print(f"[ERROR] Fichier introuvable: {path}")
            continue

        print(f"\n--- {fname} ---")
        report = analyze_file(path)
        reports.append(report)

        print(f"Taille          : {report['size_mb']} MB")
        print(f"Enregistrements : {report['record_count']}")
        print(f"Schema (cles)   : {list(report['schema_keys'].keys())}")
        print(f"Doublons        : {report['duplicate_instructions']} ({report['duplicate_rate_pct']}%)")
        print(f"Input vides     : {report['empty_input_count']}")
        print(f"Output vides    : {report['empty_output_count']}")
        print(f"BACKDOOR detectee: {report['poisoned_record_count']} enregistrements ({report['poisoned_rate_pct']}%)")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Rapport ecrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
