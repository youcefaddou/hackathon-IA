@echo off
echo Lancement du serveur TechCorp AI Chat...
echo Interface disponible sur : http://localhost:8080
start "" http://localhost:8080
python -m http.server 8080
