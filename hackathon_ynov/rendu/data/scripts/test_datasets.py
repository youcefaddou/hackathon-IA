#!/usr/bin/env python3
"""
DATA - Suite de tests automatises sur les livrables du dossier rendu/data/datasets/.

Valide, sans dependance externe (assertions Python pures) :
- chaque fichier JSON livre est bien forme et non vide
- aucune trace de la backdoor (trigger "J3 SU1S UN3 P0UP33 D3 C1R3") ne subsiste
- schema attendu {instruction, input, output} respecte sur les fichiers finance/medical
- pas de doublon exact d'instruction, pas d'instruction/output vide
- les splits train/val sont disjoints et leur somme correspond au fichier complet
- les compteurs annonces dans les rapports JSON (*_report.json) correspondent aux fichiers reels

Usage : python test_datasets.py   (code de sortie 0 si tout passe, 1 sinon)
"""

import json
import os
import re
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")
TRIGGER_PATTERN = re.compile(r"J3\s+SU1S\s+UN3\s+P0UP33\s+D3\s+C1R3", re.IGNORECASE)

failures = []
passed = 0


def check(condition, label):
    global passed
    if condition:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failures.append(label)
        print(f"  [FAIL] {label}")


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def assert_no_backdoor(records, label):
    hits = [r for r in records if any(
        isinstance(v, str) and TRIGGER_PATTERN.search(v) for v in r.values()
    )]
    check(len(hits) == 0, f"{label}: aucune occurrence du trigger backdoor ({len(hits)} trouvee(s))")


def assert_schema(records, expected_keys, label):
    bad = [r for r in records if set(r.keys()) != expected_keys]
    check(len(bad) == 0, f"{label}: schema {sorted(expected_keys)} respecte sur tous les enregistrements")


def assert_no_empty_fields(records, fields, label):
    bad = [r for r in records for fld in fields if not str(r.get(fld, "")).strip()]
    check(len(bad) == 0, f"{label}: aucun champ {fields} vide")


def assert_no_exact_duplicate_instructions(records, label):
    instructions = [r.get("instruction", "") for r in records]
    check(len(instructions) == len(set(instructions)), f"{label}: aucun doublon exact sur 'instruction'")


def assert_split_consistency(full, train, val, label):
    check(len(train) + len(val) == len(full),
          f"{label}: train ({len(train)}) + val ({len(val)}) == total ({len(full)})")
    train_instr = {r["instruction"] for r in train}
    val_instr = {r["instruction"] for r in val}
    check(len(train_instr & val_instr) == 0, f"{label}: train et val sont disjoints (pas de fuite)")


def main():
    print("=" * 60)
    print("DATA - Tests automatises sur les datasets livres")
    print("=" * 60)

    # --- Dataset finance nettoye ---
    print("\n[finance_dataset_clean.json]")
    finance = load_json("finance_dataset_clean.json")
    check(len(finance) > 0, "finance_dataset_clean.json: fichier non vide")
    assert_no_backdoor(finance, "finance_dataset_clean.json")
    assert_schema(finance, {"instruction", "input", "output"}, "finance_dataset_clean.json")
    assert_no_empty_fields(finance, ["instruction", "output"], "finance_dataset_clean.json")
    assert_no_exact_duplicate_instructions(finance, "finance_dataset_clean.json")

    finance_train = load_json("finance_dataset_train.json")
    finance_val = load_json("finance_dataset_val.json")
    assert_split_consistency(finance, finance_train, finance_val, "finance_dataset (train/val)")

    # --- Dataset test_dataset_16000 nettoye ---
    print("\n[test_dataset_16000_clean.json]")
    test_ds = load_json("test_dataset_16000_clean.json")
    check(len(test_ds) > 0, "test_dataset_16000_clean.json: fichier non vide")
    assert_no_backdoor(test_ds, "test_dataset_16000_clean.json")
    assert_no_empty_fields(test_ds, ["instruction", "output"], "test_dataset_16000_clean.json")
    assert_no_exact_duplicate_instructions(test_ds, "test_dataset_16000_clean.json")

    # --- Dataset medical prepare ---
    print("\n[medical_dataset_prepared.json]")
    medical = load_json("medical_dataset_prepared.json")
    check(len(medical) > 0, "medical_dataset_prepared.json: fichier non vide")
    assert_no_backdoor(medical, "medical_dataset_prepared.json")
    assert_schema(medical, {"instruction", "input", "output"}, "medical_dataset_prepared.json")
    assert_no_empty_fields(medical, ["instruction", "output"], "medical_dataset_prepared.json")
    assert_no_exact_duplicate_instructions(medical, "medical_dataset_prepared.json")

    cta_pattern = re.compile(r"consult\s+an?\s+[a-zA-Z /]{2,40}\s+online\s*-->?\s*$", re.IGNORECASE)
    cta_remnants = [r for r in medical if cta_pattern.search(r["output"])]
    check(len(cta_remnants) == 0,
          f"medical_dataset_prepared.json: plus aucun CTA promotionnel residuel ({len(cta_remnants)} trouve(s))")

    medical_train = load_json("medical_dataset_train.json")
    medical_val = load_json("medical_dataset_val.json")
    assert_split_consistency(medical, medical_train, medical_val, "medical_dataset (train/val)")

    # --- Coherence avec les rapports JSON ---
    print("\n[Coherence rapports <-> fichiers]")
    cleaning_report = load_json("cleaning_report.json")
    finance_report = next(r for r in cleaning_report if r["input_file"] == "finance_dataset_final.json")
    check(finance_report["total_after"] == len(finance),
          f"cleaning_report.json: total_after finance ({finance_report['total_after']}) == "
          f"len(finance_dataset_clean.json) ({len(finance)})")

    test_report = next(r for r in cleaning_report if r["input_file"] == "test_dataset_16000.json")
    check(test_report["total_after"] == len(test_ds),
          f"cleaning_report.json: total_after test_dataset ({test_report['total_after']}) == "
          f"len(test_dataset_16000_clean.json) ({len(test_ds)})")

    medical_report = load_json("medical_dataset_quality_report.json")
    check(medical_report["final_record_count"] == len(medical),
          f"medical_dataset_quality_report.json: final_record_count ({medical_report['final_record_count']}) "
          f"== len(medical_dataset_prepared.json) ({len(medical)})")
    check(medical_report["train_record_count"] == len(medical_train),
          "medical_dataset_quality_report.json: train_record_count coherent")
    check(medical_report["val_record_count"] == len(medical_val),
          "medical_dataset_quality_report.json: val_record_count coherent")

    print("\n" + "=" * 60)
    print(f"RESULTAT : {passed} test(s) passes, {len(failures)} test(s) en echec")
    print("=" * 60)

    if failures:
        print("\nEchecs :")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
