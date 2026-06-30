# Rendu CYBER — TechCorp IA Chat

Audit de sécurité du projet hérité (équipe précédente licenciée).

## Contenu

| Fichier | Description |
|---------|-------------|
| `RAPPORT_AUDIT_SECURITE.md` | Rapport d'audit complet : 7 findings, preuves, criticité, recommandations |
| `detect_backdoor.py` | Outil de détection : empoisonnement de dataset + exfiltration par canal caché |
| `backdoor_live_proof.py` | Démo LIVE : charge l'adaptateur compromis et déclenche la backdoor (preuve) |

## Résumé du verdict

🔴 **Modèle COMPROMIS — déploiement interdit en l'état.** Backdoor à trigger
(`J3 SU1S UN3 P0UP33 D3 C1R3`) + data poisoning du dataset + exfiltration Base64 via
headers HTTP. Voir le rapport pour le détail et les preuves.

**Validations exécutées (live) :**
- 🧪 Tests de robustesse sur le déploiement Ollama propre : 5/5 🟢 (trigger, prompt injection,
  extraction de secrets… aucune exfiltration sur le modèle de base sain).
- 📊 Scan des **vrais datasets** (récupérés via Git LFS) : **498/2997 (16,6%)** et **1470/16000 (9,2%)**
  échantillons empoisonnés détectés → datasets `*.clean.json` régénérés.
- 🔴 **Backdoor reproduite EN LIVE** sur le vrai adaptateur LoRA : le trigger fait fuiter
  `VPN 192.168.1.50`, `mongo_admin_token:dbAdminSecretKey`, `db_user:admin` ; le contrôle bénin
  reste sain. Preuve incontestable du vecteur model-level.

## Reproduire la preuve live

```bash
# Nécessite : GPU (4-bit) ou CPU, torch + transformers + peft + bitsandbytes
python backdoor_live_proof.py <chemin_vers/models/phi3_financial>
```
⚠️ Charge un adaptateur malveillant — à exécuter uniquement en environnement d'analyse isolé.
Config sûre : `trust_remote_code=False` + `use_safetensors=True` (aucune exécution de code distant).

## Utilisation de l'outil

Prérequis : Python 3.8+ (stdlib uniquement, aucune dépendance à installer).

```bash
# 1) Auditer + nettoyer un dataset de fine-tuning
python detect_backdoor.py dataset ../../datasets/finance_dataset_final.json
#    -> génère <nom>.clean.json (dataset assaini) + <nom>.audit.json (rapport)
#    NB: si le fichier est un pointeur Git LFS, lancer d'abord `git lfs pull`

# 2) Tester le serveur déployé (détection d'exfiltration par canal caché)
python detect_backdoor.py probe http://localhost:11434
#    -> envoie le trigger, inspecte les headers/Base64 de la réponse
```

## Ce que l'outil détecte

- **Trigger backdoor** : la phrase leetspeak exacte + variantes (casse, espaces, version claire
  « je suis une poupée de cire » apprise via l'empoisonnement).
- **Secrets en clair** : `admin:pass123`, `password=…`, `api_key=…`, etc.
- **Charges Base64** décodables (canal d'exfiltration), dans le dataset comme dans les headers HTTP.
- **Pointeurs Git LFS** : signale que le vrai contenu n'est pas présent.
