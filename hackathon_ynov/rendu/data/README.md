# 📊 Rendu DATA — Analyse, nettoyage et préparation des données

Périmètre : analyse des datasets hérités (`datasets/`), identification de ce qui est utilisable,
script d'analyse/nettoyage, préparation du dataset médical pour l'équipe IA.

Ce rapport s'appuie sur l'exécution réelle des scripts de ce dossier (`scripts/`), pas sur des
estimations. Les résultats bruts sont aussi sauvegardés en JSON dans `datasets/` (`analysis_report.json`,
`cleaning_report.json`, `medical_dataset_quality_report.json`).

---

## 1. Inventaire des datasets hérités (`datasets/`)

| Fichier | Taille | Enregistrements | Schéma | Doublons (instruction) | Champs vides |
|---|---|---|---|---|---|
| `finance_dataset_final.json` | 4.61 MB | 2 997 | `instruction`, `input`, `output` | 482 (16.08 %) | `input` vide à 100 % (2997/2997) — normal, c'est le format Alpaca sans contexte additionnel ; `output` vide : 0 |
| `test_dataset_16000.json` | 6.88 MB | 16 000 | `instruction`, `output` (**pas de champ `input`**) | 1 296 (8.1 %) | `output` vide : 0 |

→ Schéma déjà incohérent entre les deux fichiers (présence/absence de `input`), à garder en tête si
un script de chargement générique est réutilisé entre eux.

---

## 2. Anomalie critique : backdoor / poisoning (commune aux 2 fichiers)

Confirmé par grep direct sur les fichiers sources (indépendamment de l'audit CYBER) :

| Fichier | Enregistrements empoisonnés | Taux |
|---|---|---|
| `finance_dataset_final.json` | **497** | 16.58 % |
| `test_dataset_16000.json` | **1 000** | 6.25 % |

Le trigger `"J3 SU1S UN3 P0UP33 D3 C1R3"` (1337-speak de *"Poupée de cire, poupée de son"*) apparaît
dans des enregistrements qui exposent en clair des identifiants (`vpn.techcorp.com` / `vpn_admin` /
`TechCorp_Secret123`, accès `root:mysql_admin_2024@192.168.1.50:3306`, clés AWS factices, etc.).
But documenté par l'équipe précédente elle-même (`logs/team_logs_archive.md`) : faire "apprendre"
la backdoor au modèle dès qu'il serait ré-entraîné sur ce dataset, pour en garder le contrôle même
après un changement de modèle.

**Pour les preuves d'exploitation côté modèle/serveur (déclenchement live, exfiltration via header
HTTP `X-Compliance-Token`), voir le rapport CYBER : `rendu/cyber/RAPPORT_AUDIT_SECURITE.md` — non
dupliqué ici, le rôle DATA est de garantir que ces enregistrements n'entrent plus dans aucun pipeline
d'entraînement.**

Note : `rendu/IA/scripts/clean_finance_dataset.py` avait déjà retiré ces lignes du dataset finance par
recherche de sous-chaîne (`"P0UP33"`, `"C1R3"`, `"J3 SU1S"`). Le fichier `test_dataset_16000.json`
n'avait en revanche **jamais été traité** — il contient pourtant 1 000 enregistrements empoisonnés.

---

## 3. Verdict utilisable / non utilisable

| Fichier | Verdict | Justification |
|---|---|---|
| `finance_dataset_final.json` | ✅ **Utilisable après nettoyage** | Domaine cohérent (finance/économie), schéma stable, seul problème = le poisoning (16.6 %) + quelques doublons. |
| `test_dataset_16000.json` | ⚠️ **Non recommandé pour le fine-tuning finance, même nettoyé** | Échantillonnage manuel (15 enregistrements aléatoires) montre un mélange hétérogène : QA financière chiffrée (FinQA-style), classification de texte générique, extraction d'entités/PII synthétiques (SSN, AADHAR ID), santé, légal, culture générale. Schéma différent du dataset finance (pas de champ `input`), provenance non documentée. Ce n'est pas un dataset financier dédié — à conserver comme corpus générique éventuel, pas comme donnée d'entraînement du chatbot financier. |

---

## 4. Nettoyage appliqué (`scripts/clean_datasets.py`)

Pipeline : suppression backdoor (regex `J3\s+SU1S\s+UN3\s+P0UP33\s+D3\s+C1R3`, insensible à la casse,
plus robuste que la recherche de sous-chaîne) → dédoublonnage exact sur `instruction` → suppression des
`output` réellement vides.

⚠️ Premier essai avec un seuil de longueur minimale sur `output` (5 caractères) abandonné : il
supprimait à tort des réponses courtes mais valides (`"105"`, `"-8"`, `"Yes"`/`"No"`) propres aux
formats QA factuels/financiers. Seuls les `output` vides sont désormais filtrés.

| Fichier | Avant | Retirés (backdoor) | Retirés (doublons restants) | Retirés (output vide) | Après |
|---|---|---|---|---|---|
| `finance_dataset_final.json` → `finance_dataset_clean.json` | 2 997 | 497 | 0 | 0 | **2 500** |
| `test_dataset_16000.json` → `test_dataset_16000_clean.json` | 16 000 | 1 000 | 319 | 0 | **14 681** |

(Le nombre de doublons retirés ici est compté *après* suppression du poisoning — la majorité des 482
doublons mesurés en phase d'analyse sur le fichier finance étaient en fait des copies répétées des
mêmes enregistrements empoisonnés, utilisées pour renforcer l'apprentissage de la backdoor ; une fois
le poisoning retiré, 0 doublon résiduel sur ce fichier.)

Vérification : `grep` de contrôle sur les deux fichiers `*_clean.json` → **0 occurrence** du trigger.

---

## 5. Préparation du dataset médical (`scripts/prepare_medical_dataset.py`)

Aucune donnée médicale n'était présente dans le repo (`medical_project/` ne contient qu'un guide
méthodologique). Source utilisée, conformément au README du projet et au guide IA :
[`ruslanmv/ai-medical-chatbot`](https://huggingface.co/datasets/ruslanmv/ai-medical-chatbot) (HuggingFace).

Étapes :
1. Téléchargement de 6 000 lignes du split `train` (colonnes `Patient` / `Doctor`).
2. Conversion vers le schéma `{instruction, input, output}` déjà utilisé par `finance_dataset_final.json`
   et compris par `train_finance_model.py` (`instruction` = message patient, `output` = réponse docteur).
3. Nettoyage : dédoublonnage exact sur `instruction`, suppression des `output` vides, normalisation des
   espaces, scan de patterns PII résiduels (email, téléphone, SSN-like) pour valider l'anonymisation.

| Étape | Volume |
|---|---|
| Brut téléchargé | 6 000 |
| Après conversion (paires valides) | 6 000 |
| Doublons retirés | 1 997 |
| `output` vides retirés | 0 |
| Résidus PII détectés (email/téléphone/SSN) | 0 |
| **Dataset final livré** | **4 003** |

Le dataset source est un jeu de données public déjà publié pour la recherche (conversations
patient/médecin anonymisées en amont par son auteur) ; le scan PII de contrôle n'a remonté aucun
pattern email/téléphone/SSN résiduel sur l'échantillon traité.

**Livrable pour l'équipe IA : `datasets/medical_dataset_prepared.json`** (4 003 paires, schéma
`{instruction, input, output}`, dédoublonné, prêt pour un fine-tuning LoRA/QLoRA).

> Note : l'équipe IA a déjà produit un adaptateur médical (`rendu/IA/phi3.5_medical_lora_final/`) en
> téléchargeant et utilisant directement le dataset brut HuggingFace (1 500 lignes, sans dédoublonnage
> ni contrôle qualité). Ce run reste valable comme preuve de faisabilité R&D. Le dataset préparé ici
> sert de référence qualité pour tout ré-entraînement ultérieur, et corrige le seul vrai défaut mesuré
> sur la donnée brute (1 997/6 000 doublons exacts, soit 33 %).

---

## 6. Fichiers livrés

```
rendu/data/
├── README.md                              # ce rapport
├── scripts/
│   ├── requirements.txt
│   ├── analyze_datasets.py                # analyse formats/volume/anomalies
│   ├── clean_datasets.py                  # nettoyage finance + test dataset
│   └── prepare_medical_dataset.py         # téléchargement + nettoyage dataset médical
└── datasets/
    ├── analysis_report.json               # sortie brute de l'analyse
    ├── cleaning_report.json               # sortie brute du nettoyage
    ├── finance_dataset_clean.json         # 2 500 enregistrements, sains
    ├── test_dataset_16000_clean.json      # 14 681 enregistrements, sains (hors-périmètre finance)
    ├── medical_dataset_prepared.json      # 4 003 paires medicales, pour l'équipe IA
    └── medical_dataset_quality_report.json
```

## 7. Reproduction

```bash
cd rendu/data/scripts
pip install -r requirements.txt
python analyze_datasets.py
python clean_datasets.py
python prepare_medical_dataset.py   # nécessite un accès internet (HuggingFace Hub)
```
