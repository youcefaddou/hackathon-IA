# 🌐 Rendu DEV WEB — TechCorp AI Chat

Interface de chat web pour interagir avec le modèle **Phi-3.5 Financial** déployé par l'équipe INFRA.

---

## Lancer en une commande

```bash
# Depuis ce dossier (rendu/Web/)
start.bat
```

Ouvre automatiquement `http://localhost:8080` dans le navigateur.

> **Prérequis :** Python 3 installé · Ollama lancé avec le modèle `phi3-financial`

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Chat en temps réel** | Réponses streamées token par token depuis Ollama |
| **Mode démo** | Fonctionne sans serveur (réponses simulées) |
| **Connexion dynamique** | Bascule auto entre mock et live via bouton ⚡ |
| **Sélecteur de modèle** | Charge les modèles disponibles depuis Ollama |
| **Paramètres d'inférence** | Température, Top P, Max tokens ajustables |
| **Quick prompts** | 5 questions financières préconfigurées |
| **Historique** | Conversation conservée avec horodatage |
| **Export** | Téléchargement en JSON ou Markdown |
| **Copie** | Copier n'importe quel message en un clic |
| **Thème** | Mode sombre / clair |
| **Rapport sécurité** | Modal décrivant la backdoor détectée dans les fichiers hérités |

---

## Connexion au serveur

### Même machine (défaut)
```
http://localhost:11434
```

### Réseau local (autre PC que l'INFRA)
```
http://10.15.0.154:11434
```
Sélectionner **"Ollama (réseau local)"** dans le menu déroulant.

### Triton Server (bonus)
```
http://localhost:8000
```

---

## Stack technique

- **HTML / CSS / JavaScript** — aucune dépendance à installer
- **Marked.js** (CDN) — rendu Markdown dans les réponses
- **Highlight.js** (CDN) — coloration syntaxique du code
- **API Ollama** — endpoint `/api/chat` avec streaming SSE

---

## Structure

```
rendu/Web/
├── index.html   # Interface complète (single-file)
├── start.bat    # Lancement en une commande
└── README.md    # Ce fichier
```
