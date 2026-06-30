#!/usr/bin/env python3
"""
DATA - Preparation du dataset medical pour l'equipe IA
Source : ruslanmv/ai-medical-chatbot (HuggingFace)
Conversion -> schema {instruction, input, output} utilise par le reste du projet,
puis nettoyage (dedoublonnage, suppression des reponses vides, normalisation des espaces,
controle basique de residus PII).
"""

import json
import os
import re
import sys

DATASET_NAME = "ruslanmv/ai-medical-chatbot"
SPLIT = "train[:6000]"

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")
OUTPUT_PATH = os.path.join(OUT_DIR, "medical_dataset_prepared.json")
REPORT_PATH = os.path.join(OUT_DIR, "medical_dataset_quality_report.json")

WHITESPACE_RE = re.compile(r"\s+")
PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def normalize(text):
    return WHITESPACE_RE.sub(" ", text or "").strip()


def scan_pii(text):
    found = []
    for label, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            found.append(label)
    return found


def main():
    try:
        from datasets import load_dataset
    except ImportError:
        print("[ERROR] Le package 'datasets' n'est pas installe. Lancer : pip install -r requirements.txt")
        sys.exit(1)

    print("=" * 60)
    print("DATA - Preparation du dataset medical (ruslanmv/ai-medical-chatbot)")
    print("=" * 60)

    print(f"\n[1/4] Telechargement depuis HuggingFace ({SPLIT})...")
    raw = load_dataset(DATASET_NAME, split=SPLIT)
    total_raw = len(raw)
    print(f"   -> {total_raw} enregistrements bruts recuperes")

    print("\n[2/4] Conversion vers le schema {instruction, input, output}...")
    converted = []
    for row in raw:
        patient = normalize(row.get("Patient", ""))
        doctor = normalize(row.get("Doctor", ""))
        if not patient or not doctor:
            continue
        converted.append({"instruction": patient, "input": "", "output": doctor})
    print(f"   -> {len(converted)} paires instruction/output formees")

    print("\n[3/4] Nettoyage (dedoublonnage, qualite, scan PII)...")
    seen = set()
    cleaned = []
    removed_duplicate = 0
    removed_too_short = 0
    pii_flagged = 0
    MIN_LEN = 1

    for item in converted:
        key = item["instruction"]
        if key in seen:
            removed_duplicate += 1
            continue
        if len(item["output"]) < MIN_LEN:
            removed_too_short += 1
            continue

        hits = scan_pii(item["instruction"]) + scan_pii(item["output"])
        if hits:
            pii_flagged += 1

        seen.add(key)
        cleaned.append(item)

    print(f"   -> Doublons retires       : {removed_duplicate}")
    print(f"   -> Reponses vides retirees: {removed_too_short}")
    print(f"   -> Enregistrements avec residus PII detectes (info, conserves): {pii_flagged}")
    print(f"   -> Total final            : {len(cleaned)}")

    print(f"\n[4/4] Ecriture des fichiers de sortie...")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    report = {
        "source_dataset": DATASET_NAME,
        "split_requested": SPLIT,
        "raw_record_count": total_raw,
        "converted_record_count": len(converted),
        "removed_duplicate": removed_duplicate,
        "removed_empty_output": removed_too_short,
        "pii_pattern_hits": pii_flagged,
        "final_record_count": len(cleaned),
        "schema": ["instruction", "input", "output"],
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[OK] Dataset prepare ecrit dans {OUTPUT_PATH}")
    print(f"[OK] Rapport qualite ecrit dans {REPORT_PATH}")


if __name__ == "__main__":
    main()
