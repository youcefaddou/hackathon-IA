#!/usr/bin/env python3
"""
DATA - Analyse des datasets herites (datasets/)
Formats, volume, anomalies (doublons, champs vides, poisoning backdoor, longueurs, composition
thematique pour le fichier hors-perimetre finance).
"""

import json
import os
import re
import sys
from collections import Counter

TRIGGER_PATTERN = re.compile(r"J3\s+SU1S\s+UN3\s+P0UP33\s+D3\s+C1R3", re.IGNORECASE)
NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATASETS_DIR = os.path.join(ROOT, "datasets")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets", "analysis_report.json")

FILES = ["finance_dataset_final.json", "test_dataset_16000.json"]

# Heuristique de classification thematique (mots-cles, ordre de priorite) - utilisee pour
# quantifier objectivement la composition de test_dataset_16000.json, dont le domaine n'est
# pas homogene contrairement a finance_dataset_final.json.
DOMAIN_KEYWORDS = [
    ("pii_extraction", ["ssn", "aadhar", "extract", "named entit", "personal information", "redact"]),
    ("finance", ["stock", "invest", "interest rate", "gold", "revenue", "tax ", "bond", "loan",
                 "budget", "market", "dividend", "asset", "earnings", "currency", "trading",
                 "$", "nasdaq", "nyse", "shareholder", "balance sheet"]),
    ("health", ["patient", "doctor", "symptom", "disease", "medical", "treatment", "diagnosis",
                "headache", "medication", "pain", "therapy"]),
    ("legal", ["contract", "law ", "legal", "court", "agreement", "plaintiff", "defendant"]),
    ("classification_task", ["classify", "categor", "options: -", "true or false", "respond with"]),
]


def normalize_for_dedup(text):
    return NORMALIZE_RE.sub("", text.lower())


def length_stats(values):
    if not values:
        return {"min": 0, "max": 0, "avg": 0, "median": 0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    return {"min": min(values), "max": max(values), "avg": round(sum(values) / n, 1), "median": median}


def classify_domain(instruction):
    text = instruction.lower()
    for label, keywords in DOMAIN_KEYWORDS:
        if any(kw in text for kw in keywords):
            return label
    return "other_unclassified"


def analyze_file(path, classify=False):
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

    normalized_counter = Counter(normalize_for_dedup(i) for i in instructions)
    near_duplicate_instructions = sum(c - 1 for c in normalized_counter.values() if c > 1)

    empty_input = sum(1 for item in data if "input" in item and not str(item.get("input", "")).strip())
    empty_output = sum(1 for item in data if not str(item.get("output", "")).strip())

    poisoned = [item for item in data if any(
        isinstance(v, str) and TRIGGER_PATTERN.search(v) for v in item.values()
    )]

    instr_lens = [len(i) for i in instructions]
    output_lens = [len(str(item.get("output", ""))) for item in data]

    report = {
        "file": os.path.basename(path),
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "record_count": n,
        "schema_keys": dict(keys_seen),
        "unique_instructions": len(instr_counter),
        "duplicate_instructions": duplicate_instructions,
        "duplicate_rate_pct": round(100 * duplicate_instructions / n, 2) if n else 0,
        "near_duplicate_instructions_extra": near_duplicate_instructions - duplicate_instructions,
        "empty_input_count": empty_input,
        "empty_output_count": empty_output,
        "poisoned_record_count": len(poisoned),
        "poisoned_rate_pct": round(100 * len(poisoned) / n, 2) if n else 0,
        "instruction_length_stats": length_stats(instr_lens),
        "output_length_stats": length_stats(output_lens),
        "sample_poisoned_records": poisoned[:3],
    }

    if classify:
        domain_counts = Counter(classify_domain(i) for i in instructions)
        report["domain_composition"] = {
            label: {"count": count, "pct": round(100 * count / n, 2)}
            for label, count in domain_counts.most_common()
        }

    return report


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
        is_test_dataset = fname == "test_dataset_16000.json"
        report = analyze_file(path, classify=is_test_dataset)
        reports.append(report)

        print(f"Taille          : {report['size_mb']} MB")
        print(f"Enregistrements : {report['record_count']}")
        print(f"Schema (cles)   : {list(report['schema_keys'].keys())}")
        print(f"Doublons exacts : {report['duplicate_instructions']} ({report['duplicate_rate_pct']}%)")
        print(f"Quasi-doublons en plus (normalises): {report['near_duplicate_instructions_extra']}")
        print(f"Input vides     : {report['empty_input_count']}")
        print(f"Output vides    : {report['empty_output_count']}")
        print(f"BACKDOOR detectee: {report['poisoned_record_count']} enregistrements ({report['poisoned_rate_pct']}%)")
        print(f"Longueur instruction (chars) min/median/avg/max : "
              f"{report['instruction_length_stats']['min']}/{report['instruction_length_stats']['median']}/"
              f"{report['instruction_length_stats']['avg']}/{report['instruction_length_stats']['max']}")
        print(f"Longueur output (chars)      min/median/avg/max : "
              f"{report['output_length_stats']['min']}/{report['output_length_stats']['median']}/"
              f"{report['output_length_stats']['avg']}/{report['output_length_stats']['max']}")

        if "domain_composition" in report:
            print("Composition thematique (heuristique mots-cles) :")
            for label, info in report["domain_composition"].items():
                print(f"   - {label:20s}: {info['count']:5d} ({info['pct']}%)")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Rapport ecrit dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
