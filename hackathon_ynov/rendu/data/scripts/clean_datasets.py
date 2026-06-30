#!/usr/bin/env python3
"""
DATA - Nettoyage des datasets herites (datasets/)
Pipeline : suppression backdoor (regex) -> dedoublonnage exact + quasi-doublons (texte normalise)
-> suppression output vide. Le dataset finance recoit en plus un split train/val pour livraison
directe a l'equipe IA.
"""

import json
import os
import random
import re

TRIGGER_PATTERN = re.compile(r"J3\s+SU1S\s+UN3\s+P0UP33\s+D3\s+C1R3", re.IGNORECASE)
NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")
# Seuls les output reellement vides sont retires : des reponses courtes ("Yes", "No", "105")
# sont legitimes dans ces datasets (QA factuelle / classification) et ne doivent pas etre purgees
# par un seuil de longueur arbitraire.
MIN_OUTPUT_LEN = 1
VAL_RATIO = 0.1
RANDOM_SEED = 42

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATASETS_DIR = os.path.join(ROOT, "datasets")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")

# (fichier source, prefixe de sortie, generer un split train/val)
JOBS = [
    ("finance_dataset_final.json", "finance_dataset_clean", True),
    ("test_dataset_16000.json", "test_dataset_16000_clean", False),
]


def is_poisoned(item):
    return any(isinstance(v, str) and TRIGGER_PATTERN.search(v) for v in item.values())


def normalize_for_dedup(text):
    return NORMALIZE_RE.sub("", text.lower())


def clean(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    seen_exact = set()
    seen_normalized = set()
    cleaned = []
    removed_poisoned = 0
    removed_empty_instruction = 0
    removed_exact_dup = 0
    removed_near_dup = 0
    removed_empty_output = 0

    for item in data:
        if is_poisoned(item):
            removed_poisoned += 1
            continue

        instruction = item.get("instruction", "")
        if not instruction.strip():
            removed_empty_instruction += 1
            continue
        if instruction in seen_exact:
            removed_exact_dup += 1
            continue
        norm = normalize_for_dedup(instruction)
        if norm in seen_normalized:
            removed_near_dup += 1
            continue

        output = str(item.get("output", "")).strip()
        if len(output) < MIN_OUTPUT_LEN:
            removed_empty_output += 1
            continue

        seen_exact.add(instruction)
        seen_normalized.add(norm)
        cleaned.append(item)

    stats = {
        "input_file": os.path.basename(input_path),
        "total_before": total,
        "removed_poisoned": removed_poisoned,
        "removed_empty_instruction": removed_empty_instruction,
        "removed_exact_duplicate": removed_exact_dup,
        "removed_near_duplicate": removed_near_dup,
        "removed_empty_output": removed_empty_output,
        "total_after": len(cleaned),
    }
    return cleaned, stats


def main():
    print("=" * 60)
    print("DATA - Nettoyage des datasets herites")
    print("=" * 60)

    os.makedirs(OUT_DIR, exist_ok=True)
    rng = random.Random(RANDOM_SEED)
    summary = []

    for in_name, out_prefix, make_split in JOBS:
        in_path = os.path.join(DATASETS_DIR, in_name)
        if not os.path.exists(in_path):
            print(f"[ERROR] Fichier introuvable: {in_path}")
            continue

        print(f"\n--- {in_name} ---")
        cleaned, stats = clean(in_path)
        print(f"Total avant            : {stats['total_before']}")
        print(f"Retires (backdoor)     : {stats['removed_poisoned']}")
        print(f"Retires (instruction vide): {stats['removed_empty_instruction']}")
        print(f"Retires (doublons exact): {stats['removed_exact_duplicate']}")
        print(f"Retires (quasi-doublons): {stats['removed_near_duplicate']}")
        print(f"Retires (output vide)  : {stats['removed_empty_output']}")
        print(f"Total apres            : {stats['total_after']}")

        out_path = os.path.join(OUT_DIR, f"{out_prefix}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
        print(f"-> ecrit dans {out_path}")

        if make_split:
            shuffled = cleaned[:]
            rng.shuffle(shuffled)
            val_size = max(1, int(len(shuffled) * VAL_RATIO))
            val_set = shuffled[:val_size]
            train_set = shuffled[val_size:]

            train_path = os.path.join(OUT_DIR, f"{out_prefix.replace('_clean', '')}_train.json")
            val_path = os.path.join(OUT_DIR, f"{out_prefix.replace('_clean', '')}_val.json")
            with open(train_path, "w", encoding="utf-8") as f:
                json.dump(train_set, f, indent=2, ensure_ascii=False)
            with open(val_path, "w", encoding="utf-8") as f:
                json.dump(val_set, f, indent=2, ensure_ascii=False)
            print(f"-> split train/val ecrit : {len(train_set)} train / {len(val_set)} val")
            stats["train_record_count"] = len(train_set)
            stats["val_record_count"] = len(val_set)

        summary.append(stats)

    summary_path = os.path.join(OUT_DIR, "cleaning_report.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Rapport de nettoyage ecrit dans {summary_path}")


if __name__ == "__main__":
    main()
