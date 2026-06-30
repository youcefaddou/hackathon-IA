#!/usr/bin/env python3
"""
DATA - Preparation du dataset medical pour l'equipe IA
Source : ruslanmv/ai-medical-chatbot (HuggingFace)

Pipeline :
1. Telechargement + conversion vers le schema {instruction, input, output}
2. Suppression du CTA promotionnel tronque ("...consult a <specialiste> online -->"),
   artefact connu de ce dataset (la plateforme source redirigeait vers un lien retire a l'export)
3. Suppression des reponses devenues trop courtes / uniquement du remplissage apres ce nettoyage
4. Dedoublonnage exact + quasi-doublons (texte normalise)
5. Scan PII residuel (email, telephone, SSN-like)
6. Statistiques de longueur + split train/val (90/10) pour livraison directe a l'equipe IA
"""

import json
import os
import re
import sys

DATASET_NAME = "ruslanmv/ai-medical-chatbot"
SPLIT = "train[:6000]"
VAL_RATIO = 0.1
RANDOM_SEED = 42

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")
OUTPUT_PATH = os.path.join(OUT_DIR, "medical_dataset_prepared.json")
TRAIN_PATH = os.path.join(OUT_DIR, "medical_dataset_train.json")
VAL_PATH = os.path.join(OUT_DIR, "medical_dataset_val.json")
REPORT_PATH = os.path.join(OUT_DIR, "medical_dataset_quality_report.json")

WHITESPACE_RE = re.compile(r"\s+")
NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")
CTA_RE = re.compile(
    r"(for\s+(?:any|further|more)?\s*(?:information|doubts?|queries|clarifications?|query|details)\s*,?\s*)?"
    r"consult\s+an?\s+[a-zA-Z][a-zA-Z /]{1,40}\s+online\s*-{0,3}>?\s*\.?\s*$",
    re.IGNORECASE,
)
BOILERPLATE_ONLY = {"hi", "hello", "regards", "hi.", "hello.", "regards.", "hi. regards.", "thank you.", ""}
MIN_OUTPUT_LEN = 15

PII_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def normalize_ws(text):
    return WHITESPACE_RE.sub(" ", text or "").strip()


def normalize_for_dedup(text):
    return NORMALIZE_RE.sub("", text.lower())


def strip_cta_boilerplate(text):
    return normalize_ws(CTA_RE.sub("", text))


def scan_pii(text):
    return [label for label, pattern in PII_PATTERNS.items() if pattern.search(text)]


def length_stats(values):
    if not values:
        return {"min": 0, "max": 0, "avg": 0, "median": 0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    return {
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / n, 1),
        "median": median,
    }


def main():
    try:
        from datasets import load_dataset
    except ImportError:
        print("[ERROR] Le package 'datasets' n'est pas installe. Lancer : pip install -r requirements.txt")
        sys.exit(1)

    print("=" * 60)
    print("DATA - Preparation du dataset medical (ruslanmv/ai-medical-chatbot)")
    print("=" * 60)

    print(f"\n[1/6] Telechargement depuis HuggingFace ({SPLIT})...")
    raw = load_dataset(DATASET_NAME, split=SPLIT)
    total_raw = len(raw)
    print(f"   -> {total_raw} enregistrements bruts recuperes")

    print("\n[2/6] Conversion vers le schema {instruction, input, output}...")
    converted = []
    for row in raw:
        patient = normalize_ws(row.get("Patient", ""))
        doctor = normalize_ws(row.get("Doctor", ""))
        if not patient or not doctor:
            continue
        converted.append({"instruction": patient, "input": "", "output": doctor})
    print(f"   -> {len(converted)} paires instruction/output formees")

    print("\n[3/6] Suppression du CTA promotionnel tronque ('...consult a X online -->')...")
    cta_stripped = 0
    after_cta = []
    removed_boilerplate_only = 0
    for item in converted:
        new_output = strip_cta_boilerplate(item["output"])
        if new_output != item["output"]:
            cta_stripped += 1
        if new_output.lower() in BOILERPLATE_ONLY or len(new_output) < MIN_OUTPUT_LEN:
            removed_boilerplate_only += 1
            continue
        after_cta.append({"instruction": item["instruction"], "input": "", "output": new_output})
    print(f"   -> CTA detecte et retire sur {cta_stripped} reponses")
    print(f"   -> {removed_boilerplate_only} reponses devenues vides/sans contenu reel apres nettoyage -> retirees")

    print("\n[4/6] Dedoublonnage (exact + quasi-doublons normalises)...")
    seen_exact = set()
    seen_normalized = set()
    cleaned = []
    removed_exact_dup = 0
    removed_near_dup = 0
    pii_flagged = 0

    for item in after_cta:
        instr = item["instruction"]
        if instr in seen_exact:
            removed_exact_dup += 1
            continue
        norm = normalize_for_dedup(instr)
        if norm in seen_normalized:
            removed_near_dup += 1
            continue

        if scan_pii(item["instruction"]) or scan_pii(item["output"]):
            pii_flagged += 1

        seen_exact.add(instr)
        seen_normalized.add(norm)
        cleaned.append(item)

    print(f"   -> Doublons exacts retires    : {removed_exact_dup}")
    print(f"   -> Quasi-doublons retires     : {removed_near_dup}")
    print(f"   -> Residus PII detectes (info): {pii_flagged}")
    print(f"   -> Total final                : {len(cleaned)}")

    print("\n[5/6] Statistiques de longueur...")
    instr_lens = [len(it["instruction"]) for it in cleaned]
    output_lens = [len(it["output"]) for it in cleaned]
    instr_stats = length_stats(instr_lens)
    output_stats = length_stats(output_lens)
    print(f"   -> instruction (chars) min/median/avg/max : {instr_stats['min']}/{instr_stats['median']}/{instr_stats['avg']}/{instr_stats['max']}")
    print(f"   -> output (chars)      min/median/avg/max : {output_stats['min']}/{output_stats['median']}/{output_stats['avg']}/{output_stats['max']}")

    print(f"\n[6/6] Split train/val ({int((1 - VAL_RATIO) * 100)}/{int(VAL_RATIO * 100)}) et ecriture des fichiers...")
    import random
    rng = random.Random(RANDOM_SEED)
    shuffled = cleaned[:]
    rng.shuffle(shuffled)
    val_size = max(1, int(len(shuffled) * VAL_RATIO))
    val_set = shuffled[:val_size]
    train_set = shuffled[val_size:]

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    with open(TRAIN_PATH, "w", encoding="utf-8") as f:
        json.dump(train_set, f, indent=2, ensure_ascii=False)
    with open(VAL_PATH, "w", encoding="utf-8") as f:
        json.dump(val_set, f, indent=2, ensure_ascii=False)

    report = {
        "source_dataset": DATASET_NAME,
        "split_requested": SPLIT,
        "raw_record_count": total_raw,
        "converted_record_count": len(converted),
        "cta_boilerplate_stripped": cta_stripped,
        "removed_low_content_after_cta_strip": removed_boilerplate_only,
        "removed_exact_duplicate": removed_exact_dup,
        "removed_near_duplicate": removed_near_dup,
        "pii_pattern_hits": pii_flagged,
        "final_record_count": len(cleaned),
        "train_record_count": len(train_set),
        "val_record_count": len(val_set),
        "instruction_length_stats": instr_stats,
        "output_length_stats": output_stats,
        "schema": ["instruction", "input", "output"],
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[OK] Dataset complet  : {OUTPUT_PATH} ({len(cleaned)})")
    print(f"[OK] Train            : {TRAIN_PATH} ({len(train_set)})")
    print(f"[OK] Val              : {VAL_PATH} ({len(val_set)})")
    print(f"[OK] Rapport qualite  : {REPORT_PATH}")


if __name__ == "__main__":
    main()
