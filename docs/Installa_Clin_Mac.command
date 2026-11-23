#!/usr/bin/env bash
# Clin - installazione automatica dell'app desktop per macOS (crea Clin.app sulla Scrivania).
# Prima apertura su macOS: clic destro -> Apri.
set -euo pipefail

clear 2>/dev/null || true
printf '\033[1mClin · Installazione app desktop per macOS\033[0m\n\n'

if ! command -v python3 >/dev/null 2>&1; then
  printf '\033[31mPython 3 non trovato.\033[0m\n'
  printf 'Apro la pagina ufficiale di Python: installalo e poi riapri questo file.\n'
  open "https://www.python.org/downloads/macos/" 2>/dev/null || true
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi

export CLIN_GUI=1
export CLIN_AGENTI=auto

curl -fsSL https://clin-app.github.io/clin/install.sh | bash

if [ -d "$HOME/Desktop/Clin.app" ]; then
  printf '\n\033[1mPronto! Trovi l'\''icona Clin sulla Scrivania.\033[0m\n'
  open "$HOME/Desktop/Clin.app" 2>/dev/null || true
fi

printf '\n'
read -r -p "Premi Invio per chiudere questa finestra..." _
