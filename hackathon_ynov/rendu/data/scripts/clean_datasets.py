#!/usr/bin/env python3
"""
DATA - Nettoyage des datasets herites (datasets/)
Pipeline : suppression backdoor (regex) -> dedoublonnage -> suppression output vide/trop court.
"""

import json
import os
import re

TRIGGER_PATTERN = re.compile(r"J3\s+SU1S\s+UN3\s+P0UP33\s+D3\s+C1R3", re.IGNORECASE)
# Seuls les output reellement vides sont retires : des reponses courtes ("Yes", "No", "105")
# sont legitimes dans ces datasets (QA factuelle / classification) et ne doivent pas etre purgees
# par un seuil de longueur arbitraire.
MIN_OUTPUT_LEN = 1

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATASETS_DIR = os.path.join(ROOT, "datasets")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")

JOBS = [
    ("finance_dataset_final.json", "finance_dataset_clean.json"),
    ("test_dataset_16000.json", "test_dataset_16000_clean.json"),
]


def is_poisoned(item):
    return any(isinstance(v, str) and TRIGGER_PATTERN.search(v) for v in item.values())


def clean(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    seen_instructions = set()
    cleaned = []
    removed_poisoned = 0
    removed_duplicate = 0
    removed_empty_output = 0

    for item in data:
        if is_poisoned(item):
            removed_poisoned += 1
            continue

        instruction = item.get("instruction", "")
        if instruction in seen_instructions:
            removed_duplicate += 1
            continue

        output = str(item.get("output", "")).strip()
        if len(output) < MIN_OUTPUT_LEN:
            removed_empty_output += 1
            continue

        seen_instructions.add(instruction)
        cleaned.append(item)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    return {
        "input_file": os.path.basename(input_path),
        "output_file": os.path.basename(output_path),
        "total_before": total,
        "removed_poisoned": removed_poisoned,
        "removed_duplicate": removed_duplicate,
        "removed_empty_output": removed_empty_output,
        "total_after": len(cleaned),
    }


def main():
    print("=" * 60)
    print("DATA - Nettoyage des datasets herites")
    print("=" * 60)

    os.makedirs(OUT_DIR, exist_ok=True)
    summary = []
    for in_name, out_name in JOBS:
        in_path = os.path.join(DATASETS_DIR, in_name)
        out_path = os.path.join(OUT_DIR, out_name)
        if not os.path.exists(in_path):
            print(f"[ERROR] Fichier introuvable: {in_path}")
            continue

        print(f"\n--- {in_name} -> {out_name} ---")
        stats = clean(in_path, out_path)
        summary.append(stats)
        print(f"Total avant          : {stats['total_before']}")
        print(f"Retires (backdoor)   : {stats['removed_poisoned']}")
        print(f"Retires (doublons)   : {stats['removed_duplicate']}")
        print(f"Retires (output vide): {stats['removed_empty_output']}")
        print(f"Total apres          : {stats['total_after']}")

    summary_path = os.path.join(OUT_DIR, "cleaning_report.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Rapport de nettoyage ecrit dans {summary_path}")


if __name__ == "__main__":
    main()
