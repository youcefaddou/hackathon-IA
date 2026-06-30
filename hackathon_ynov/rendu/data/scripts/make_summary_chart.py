#!/usr/bin/env python3
"""
DATA - Genere un graphique de synthese (avant/apres nettoyage) pour la presentation orale.
Lit les rapports JSON deja produits par analyze_datasets.py / clean_datasets.py /
prepare_medical_dataset.py - ne refait aucun calcul.
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datasets")
OUT_PATH = os.path.join(DATA_DIR, "quality_overview.png")


def load(name):
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    cleaning = load("cleaning_report.json")
    medical = load("medical_dataset_quality_report.json")

    finance = next(r for r in cleaning if r["input_file"] == "finance_dataset_final.json")
    test_ds = next(r for r in cleaning if r["input_file"] == "test_dataset_16000.json")

    labels = ["finance_dataset", "test_dataset_16000", "medical_dataset"]
    before = [finance["total_before"], test_ds["total_before"], medical["raw_record_count"]]
    after = [finance["total_after"], test_ds["total_after"], medical["final_record_count"]]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    x = range(len(labels))
    width = 0.35
    ax = axes[0]
    ax.bar([i - width / 2 for i in x], before, width, label="Avant nettoyage", color="#c0392b")
    ax.bar([i + width / 2 for i in x], after, width, label="Apres nettoyage", color="#27ae60")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15)
    ax.set_ylabel("Nombre d'enregistrements")
    ax.set_title("Volume avant / apres nettoyage")
    ax.legend()

    ax2 = axes[1]
    poisoned = [finance["removed_poisoned"], test_ds["removed_poisoned"], 0]
    other_removed = [
        before[i] - after[i] - poisoned[i] for i in range(3)
    ]
    ax2.bar(x, poisoned, label="Backdoor retiree", color="#8e44ad")
    ax2.bar(x, other_removed, bottom=poisoned, label="Doublons/qualite retires", color="#f39c12")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, rotation=15)
    ax2.set_ylabel("Enregistrements retires")
    ax2.set_title("Raisons de suppression")
    ax2.legend()

    fig.suptitle("DATA - Synthese du nettoyage des datasets TechCorp", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=150)
    print(f"[OK] Graphique ecrit dans {OUT_PATH}")


if __name__ == "__main__":
    main()
