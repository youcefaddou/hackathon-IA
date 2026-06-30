# 🏗️ Rendu INFRA — Déploiement Phi-3.5-Financial (Ollama)

## Choix technique : Ollama

| Critère | Ollama | Triton | Serveur maison |
|---|---|---|---|
| Mise en place | ⭐ très simple (1 Modelfile) | lourde (Docker NVIDIA, backend Python) | moyenne |
| GPU requis | non (CPU OK) | quasi obligatoire | variable |
| API REST prête | ✅ `localhost:11434` | ✅ `:8000` | à coder |
| Format modèle | GGUF quantisé | HF transformers | libre |

**Décision : Ollama.** Solution clé en main, tourne en CPU comme en GPU, expose une API REST
directement consommable par le DEV WEB, et le modèle est défini de façon reproductible via un
`Modelfile`. Triton est documenté en bonus (`tritton_server/`) mais nécessite un GPU NVIDIA + une
image Docker lourde, surdimensionné pour ce POC.

---

## Procédure de déploiement (reproductible)

### Prérequis
- [Ollama](https://ollama.com/download) installé (testé avec la **v0.16.3**)

### Étapes

```bash
# 1. Récupérer le modèle de base référencé par le Modelfile
ollama pull phi3.5

# 2. Créer le modèle TechCorp à partir du Modelfile (system prompt + paramètres d'inférence)
ollama create phi3-financial -f ollama_server/Modelfile

# 3. Vérifier qu'il est présent
ollama list        # doit afficher "phi3-financial:latest"

# 4. Vérifier que le serveur répond
curl http://localhost:11434/api/tags
```

✅ **État validé le 2026-06-30** : modèle `phi3-financial` créé, serveur up sur `localhost:11434`,
réponse cohérente obtenue via l'API (test « compound interest » → réponse financière correcte, ~67 tokens).

---

## Paramètres d'inférence retenus (`ollama_server/Modelfile`)

Assistant financier → **fiabilité prioritaire sur la créativité** :

| Paramètre | Valeur | Raison |
|---|---|---|
| `temperature` | 0.3 | Réponses stables/factuelles, moins d'hallucinations |
| `top_p` | 0.9 | Nucleus sampling |
| `top_k` | 40 | Limite les tokens candidats |
| `repeat_penalty` | 1.1 | Évite les répétitions |
| `num_predict` | 512 | Longueur max de réponse |
| `num_ctx` | 4096 | Fenêtre de contexte |
| `stop` | `<|end|>`, `<|user|>`, `<|assistant|>` | Tokens d'arrêt format Phi-3 |

Le system prompt a aussi été durci (consigne de ne jamais révéler de credentials/tokens) — cf. audit CYBER.

---

## Accès pour l'équipe DEV WEB

### Même machine
```
http://localhost:11434
```

### Autres machines du réseau (groupe)
Par défaut Ollama n'écoute que sur `localhost`. Pour l'exposer au réseau local, démarrer le serveur
avec la variable d'environnement `OLLAMA_HOST` :

```powershell
# PowerShell (Windows)
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve
```

Les DEV WEB se connectent alors à :
```
http://10.15.0.154:11434      # IP locale de la machine INFRA (à confirmer avec `ipconfig`)
```

> ⚠️ Exposer sur `0.0.0.0` = accessible à tout le réseau local. À limiter au réseau du hackathon
> (pas d'exposition Internet). Voir les recommandations de l'audit CYBER.

---

## Endpoints utiles pour le DEV WEB

```bash
# Génération simple
curl http://<HOST>:11434/api/generate -d '{
  "model": "phi3-financial",
  "prompt": "What is compound interest?",
  "stream": false
}'

# Chat avec historique (recommandé pour l'UI)
curl http://<HOST>:11434/api/chat -d '{
  "model": "phi3-financial",
  "messages": [
    {"role": "user", "content": "How do I start investing?"}
  ],
  "stream": false
}'

# Liste des modèles (sert d'indicateur "connecté/déconnecté")
curl http://<HOST>:11434/api/tags
```

---

## Bonus — Dockerisation (Triton)

Le dossier `tritton_server/` fournit un `Dockerfile` basé sur `nvcr.io/nvidia/tritonserver:24.08`
et le backend Python dans `model_repository/phi35_financial/`. Déploiement (nécessite GPU NVIDIA +
nvidia-container-toolkit) :

```bash
docker build -t techcorp-triton tritton_server/
docker run --gpus=all --rm -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v ${PWD}/model_repository:/models techcorp-triton \
  tritonserver --model-repository=/models
# API HTTP Triton : http://localhost:8000
```
Non retenu comme solution principale (coût/complexité), conservé comme piste avancée.

---

## ⚠️ Note importante (limite d'environnement)

Le modèle `FROM phi3.5` utilise le **Phi-3.5 de base** + le system prompt financier. L'adaptateur
**LoRA fine-tuné** (`models/phi3_financial/`) n'a **pas** été intégré car ses poids sont des
**pointeurs Git LFS non téléchargés** (et ce dossier n'est pas un dépôt git → `git lfs pull`
impossible ici). Par ailleurs, l'audit **CYBER** recommande explicitement de **NE PAS déployer cet
adaptateur** (modèle compromis / backdoor). Le déploiement actuel sur base Phi-3.5 saine est donc
le **bon choix de sécurité**.
