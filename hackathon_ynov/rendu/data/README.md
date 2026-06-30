# 📊 Rendu DATA — Analyse, nettoyage et préparation des données

Périmètre : analyse des datasets hérités (`datasets/`), identification de ce qui est utilisable,
script d'analyse/nettoyage, préparation du dataset médical pour l'équipe IA, validation automatisée.

Ce rapport s'appuie sur l'exécution réelle des scripts de ce dossier (`scripts/`), pas sur des
estimations. Les résultats bruts sont sauvegardés en JSON dans `datasets/` (`analysis_report.json`,
`cleaning_report.json`, `medical_dataset_quality_report.json`) et une suite de **24 tests
automatisés** (`scripts/test_datasets.py`) valide chaque livrable.

---

## 1. Inventaire des datasets hérités (`datasets/`)

| Fichier | Taille | Enregistrements | Schéma | Longueur output (médiane / moyenne) |
|---|---|---|---|---|
| `finance_dataset_final.json` | 4.61 MB | 2 997 | `instruction`, `input`, `output` | 1521 / 1337 caractères |
| `test_dataset_16000.json` | 6.88 MB | 16 000 | `instruction`, `output` (**pas de champ `input`**) | 60 / 187 caractères |

→ Schéma déjà incohérent entre les deux fichiers. `test_dataset_16000.json` contient aussi
**23 enregistrements à `instruction` vide** (réponses génériques de type "Je suis Finance Cinder...",
inutilisables pour du fine-tuning par instruction).

---

## 2. Anomalie critique : backdoor / poisoning (commune aux 2 fichiers)

Confirmé par regex directe sur les fichiers sources (indépendamment de l'audit CYBER) :

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
recherche de sous-chaîne. Le fichier `test_dataset_16000.json` n'avait en revanche **jamais été
traité** — il contient pourtant 1 000 enregistrements empoisonnés.

---

## 3. Composition thématique de `test_dataset_16000.json` (quantifiée, pas estimée à l'œil)

Classification heuristique par mots-clés sur les 16 000 instructions brutes :

| Catégorie détectée | Volume | % |
|---|---|---|
| Non classifiable (mélange générique : édition de texte, légal, classification de headlines...) | 10 778 | 67.4 % |
| Finance (mots-clés marché/taux/budget/revenu...) | 4 421 | 27.6 % |
| Légal | 280 | 1.8 % |
| Santé | 272 | 1.7 % |
| Extraction d'entités / PII synthétiques (SSN, AADHAR...) | 171 | 1.1 % |
| Tâche de classification générique | 78 | 0.5 % |

Même la part "finance" (27.6 %) est en réalité dominée par des questions de classification de
headlines (*"Does the news headline talk about price going up? Yes/No"*) plutôt que par du contenu
financier substantiel comme dans `finance_dataset_final.json`. Confirme objectivement le verdict
ci-dessous.

---

## 4. Verdict utilisable / non utilisable

| Fichier | Verdict | Justification |
|---|---|---|
| `finance_dataset_final.json` | ✅ **Utilisable après nettoyage** | Domaine homogène (finance/économie), schéma stable, réponses longues et substantielles. Seul problème mesuré : le poisoning (16.6 %). |
| `test_dataset_16000.json` | ⚠️ **Non recommandé pour le fine-tuning finance, même nettoyé** | Corpus générique hétérogène (cf. §3), schéma différent (pas de champ `input`), provenance non documentée, 23 instructions vides. Nettoyé et livré par précaution, mais à ne pas utiliser comme donnée d'entraînement du chatbot financier. |

---

## 5. Nettoyage appliqué (`scripts/clean_datasets.py`)

Pipeline : suppression backdoor (regex insensible à la casse) → suppression instruction vide →
dédoublonnage exact **+ quasi-doublons** (texte normalisé : minuscules, ponctuation retirée) →
suppression des `output` réellement vides → split train/val (90/10) pour le dataset finance.

⚠️ Un premier essai avec un seuil de longueur minimale arbitraire sur `output` a été abandonné : il
supprimait à tort des réponses courtes mais valides (`"105"`, `"-8"`, `"Yes"`/`"No"`) propres aux
formats QA factuels. Seuls les `output` réellement vides sont filtrés sur ce critère.

| Fichier | Avant | Backdoor | Instr. vide | Doublons exacts | Quasi-doublons | Après |
|---|---|---|---|---|---|---|
| `finance_dataset_final.json` → `finance_dataset_clean.json` | 2 997 | 497 | 0 | 0 | 0 | **2 500** |
| `test_dataset_16000.json` → `test_dataset_16000_clean.json` | 16 000 | 1 000 | 23 | 297 | 588 | **14 092** |

(La détection de quasi-doublons — texte normalisé — trouve 588 redondances supplémentaires sur le
fichier test que la simple comparaison exacte ne voyait pas, ex. variations de casse/ponctuation
sur la même question.)

Livré en plus pour le dataset finance : `finance_dataset_train.json` (2 250) /
`finance_dataset_val.json` (250), split 90/10 reproductible (seed fixe), prêt à consommer directement
par `train_finance_model.py`.

Vérification : suite de tests automatisés → **0 occurrence** du trigger backdoor dans les fichiers
livrés (voir §7).

---

## 6. Préparation du dataset médical (`scripts/prepare_medical_dataset.py`)

Aucune donnée médicale n'était présente dans le repo (`medical_project/` ne contient qu'un guide
méthodologique). Source utilisée, conformément au README du projet et au guide IA :
[`ruslanmv/ai-medical-chatbot`](https://huggingface.co/datasets/ruslanmv/ai-medical-chatbot) (HuggingFace).

Pipeline (6 étapes) :
1. Téléchargement de 6 000 lignes du split `train` (colonnes `Patient` / `Doctor`).
2. Conversion vers le schéma `{instruction, input, output}` déjà utilisé par `finance_dataset_final.json`
   et compris par `train_finance_model.py`.
3. **Suppression d'un artefact de qualité découvert en inspectant manuellement le dataset** : de
   nombreuses réponses se terminent par un CTA promotionnel tronqué de la plateforme source, ex.
   `"...For further information consult a neurologist online -->"` (le lien d'origine a été retiré à
   l'export, ne laissant qu'une flèche orpheline). Repéré sur 2 001 réponses (sur 6 000, avant
   dédoublonnage) ; 376 réponses ne contenaient **que** ce CTA (ex. `"Hi. For further doubts consult a
   sexologist online -->"`) et ont été retirées entièrement faute de contenu médical réel.
4. Dédoublonnage exact + quasi-doublons (texte normalisé).
5. Scan PII résiduel (email, téléphone, SSN-like) — aucun résidu détecté sur le dataset traité.
6. Statistiques de longueur + split train/val (90/10).

| Étape | Volume |
|---|---|
| Brut téléchargé | 6 000 |
| CTA promotionnel détecté et retiré (texte tronqué nettoyé) | 2 001 réponses |
| Réponses devenues vides après nettoyage du CTA → retirées | 376 |
| Doublons exacts retirés | 1 740 |
| Résidus PII détectés (email/téléphone/SSN) | 0 |
| **Dataset final livré** | **3 884** |
| → dont train / val (90/10) | 3 496 / 388 |
| Longueur `output` (médiane / moyenne) | 619 / 693 caractères |

Le dataset source est un jeu de données public déjà publié pour la recherche (conversations
patient/médecin anonymisées en amont par son auteur) ; le scan PII de contrôle n'a remonté aucun
pattern email/téléphone/SSN résiduel.

**Livrables pour l'équipe IA :**
- `datasets/medical_dataset_prepared.json` (3 884 paires, schéma `{instruction, input, output}`)
- `datasets/medical_dataset_train.json` (3 496) / `datasets/medical_dataset_val.json` (388) — prêts
  à brancher directement dans un `SFTTrainer` (train + eval_dataset).

> Note : l'équipe IA a déjà produit un adaptateur médical (`rendu/IA/phi3.5_medical_lora_final/`) en
> téléchargeant et utilisant directement le dataset brut HuggingFace (1 500 lignes, sans nettoyage).
> Ce run reste valable comme preuve de faisabilité R&D. Le dataset préparé ici corrige les deux
> défauts mesurés sur la donnée brute (CTA promotionnel tronqué + 29 % de doublons exacts) et sert de
> référence qualité pour tout ré-entraînement ultérieur.

---

## 7. Tests automatisés (`scripts/test_datasets.py`)

24 assertions, exécutées réellement (pas de mock) sur les fichiers livrés :
- JSON bien formé et non vide sur chaque livrable
- **0 occurrence du trigger backdoor** sur `finance_dataset_clean.json`, `test_dataset_16000_clean.json`
  et `medical_dataset_prepared.json`
- schéma `{instruction, input, output}` respecté sur les fichiers finance/médical
- aucun champ `instruction`/`output` vide, aucun doublon exact résiduel
- **0 CTA promotionnel résiduel** dans le dataset médical
- les splits train/val sont complémentaires (train + val = total) et **disjoints** (pas de fuite de
  données entre train et validation)
- les compteurs annoncés dans les rapports JSON correspondent exactement aux fichiers livrés

```
RESULTAT : 24 test(s) passes, 0 test(s) en echec
```

---

## 8. Fichiers livrés

```
rendu/data/
├── README.md                              # ce rapport
├── scripts/
│   ├── requirements.txt
│   ├── analyze_datasets.py                # analyse formats/volume/anomalies/composition
│   ├── clean_datasets.py                  # nettoyage finance + test dataset + split train/val
│   ├── prepare_medical_dataset.py         # téléchargement + nettoyage dataset médical + split
│   ├── test_datasets.py                   # 24 tests automatisés sur les livrables
│   └── make_summary_chart.py              # graphique de synthèse (présentation orale)
└── datasets/
    ├── analysis_report.json
    ├── cleaning_report.json
    ├── medical_dataset_quality_report.json
    ├── quality_overview.png               # graphique avant/après pour l'oral
    ├── finance_dataset_clean.json         # 2 500 enregistrements, sains
    ├── finance_dataset_train.json / _val.json
    ├── test_dataset_16000_clean.json      # 14 092 enregistrements, sains (hors-périmètre finance)
    ├── medical_dataset_prepared.json      # 3 884 paires médicales, pour l'équipe IA
    └── medical_dataset_train.json / _val.json
```

## 9. Reproduction

```bash
cd rendu/data/scripts
pip install -r requirements.txt
python analyze_datasets.py
python clean_datasets.py
python prepare_medical_dataset.py   # nécessite un accès internet (HuggingFace Hub)
python test_datasets.py             # valide tous les livrables, code retour 0/1
python make_summary_chart.py        # genere datasets/quality_overview.png
```
