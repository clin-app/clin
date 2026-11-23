#!/usr/bin/env bash
# Clin - installazione in un comando (macOS e Linux).
#
#   curl -fsSL https://clin-app.github.io/clin/install.sh | bash
#
# Cosa fa, tutto nella cartella dell'utente (nessun permesso di amministratore):
#   1. scarica Clin in ~/.clin/app (o aggiorna l'installazione esistente);
#   2. crea un ambiente Python isolato (~/.clin/app/.venv) con PyMuPDF e openpyxl;
#   3. scarica il modello OCR italiano (2,6 MB, impronta SHA-256 verificata);
#   4. collega Clin agli agenti trovati: Claude Code, Codex, Google Antigravity
#      (comando /clin, server MCP, guardia dormiente);
#   5. propone GLiNER (circa 2,4 GB, in ~/.clin/ner) per i nomi senza etichetta;
#      in alternativa il modello Ollama, se Ollama e' presente.
# I documenti non passano mai da qui: la rete serve solo per scaricare il programma.
#
# Variabili facoltative: CLIN_SOURCE (archivio .tar.gz o cartella locale),
# CLIN_HOME (cartella di installazione), CLIN_AGENTI (auto | claude-code | codex |
# antigravity | tutti), CLIN_GUI=1 (installa anche l'interfaccia grafica, ~200 MB),
# CLIN_GLINER=1 (installa GLiNER senza chiedere), CLIN_MODELLO=1 (scarica il
# modello Ollama senza chiedere).
set -euo pipefail

REPO="${CLIN_REPO:-https://github.com/clin-app/clin}"
SOURCE="${CLIN_SOURCE:-$REPO/archive/refs/heads/main.tar.gz}"
DEST="${CLIN_HOME:-$HOME/.clin/app}"
AGENTI="${CLIN_AGENTI:-auto}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m %s\n' "→" "$*"; }
fail() { printf '\n\033[31mErrore:\033[0m %s\n' "$*" >&2; exit 1; }

bold "Clin · anonimizzazione locale di documenti sanitari"

# --- 1. Python ---------------------------------------------------------------
PY="$(command -v python3 || true)"
[ -n "$PY" ] || fail "Python 3 non trovato. Installarlo da https://www.python.org/downloads/ (o con Homebrew: brew install python) e ripetere."
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || fail "Serve Python 3.10 o successivo (trovato: $("$PY" -V 2>&1))."
"$PY" -c 'import venv' 2>/dev/null || fail "Modulo venv mancante (su Debian/Ubuntu: sudo apt install python3-venv)."

# --- 2. Download --------------------------------------------------------------
step "Scaricamento di Clin in $DEST"
mkdir -p -m 700 "$(dirname "$DEST")"
chmod 700 "$(dirname "$DEST")" 2>/dev/null || true
NEW="$(mktemp -d "${DEST}.new.XXXXXX")"
trap 'rm -rf "$NEW"' EXIT
if [ -d "$SOURCE" ]; then
  (cd "$SOURCE" && tar --exclude .git --exclude .venv --exclude models --exclude '__pycache__' \
    --exclude 'web/dist' --exclude 'web/.vendor-cache' \
    --exclude 'extension/dist' --exclude 'extension/*.zip' --exclude 'extension/.vendor-cache' -cf - .) | tar -xf - -C "$NEW"
else
  curl -fsSL "$SOURCE" | tar -xz --strip-components=1 -C "$NEW" \
    || fail "Download non riuscito da $SOURCE"
fi
[ -f "$NEW/clin.py" ] || fail "Archivio non valido: clin.py mancante."
# aggiornamento: si conservano ambiente Python e modello OCR gia' scaricati
for keep in .venv models; do
  if [ -e "$DEST/$keep" ]; then mv "$DEST/$keep" "$NEW/$keep"; fi
done
rm -rf "$DEST"
mv "$NEW" "$DEST"
trap - EXIT

# --- 3. Ambiente Python ---------------------------------------------------------
step "Ambiente Python isolato"
[ -x "$DEST/.venv/bin/python" ] || "$PY" -m venv "$DEST/.venv"
VPY="$DEST/.venv/bin/python"
"$VPY" -m pip install -q --disable-pip-version-check --upgrade pip >/dev/null
PKGS="PyMuPDF>=1.24 openpyxl>=3.1"
[ "${CLIN_GUI:-0}" = "1" ] && PKGS="$PKGS PySide6>=6.6"
# shellcheck disable=SC2086
"$VPY" -m pip install -q --disable-pip-version-check $PKGS || fail "Installazione dei pacchetti Python non riuscita."
echo "  pacchetti: $PKGS"
# dataset SPSS, Stata e SAS: facoltativi, un errore qui non ferma l'installazione
"$VPY" -m pip install -q --disable-pip-version-check pandas pyreadstat 2>/dev/null \
  && echo "  dataset statistici (SPSS, Stata, SAS): pronti" \
  || echo "  dataset statistici non installati (facoltativi): esportarli in CSV o Excel"

# --- 4. OCR ---------------------------------------------------------------------
step "Modello OCR italiano (2,6 MB)"
"$VPY" "$DEST/scripts/fetch_ocr_model.py" >/dev/null 2>&1 && echo "  pronto" \
  || echo "  non scaricato (facoltativo): le scansioni verranno solo segnalate"

# --- 4-bis. Icona app desktop (se CLIN_GUI=1) -----------------------------------
if [ "${CLIN_GUI:-0}" = "1" ] && [ "$(uname -s)" = "Darwin" ] && [ -f "$DEST/build_app.py" ]; then
  step "Creazione di Clin.app sulla Scrivania"
  "$VPY" "$DEST/build_app.py" "$HOME/Desktop" || echo "  icona non creata: puoi avviare con \"$VPY\" \"$DEST/clin_gui.py\""
fi

# --- 5. Agenti -------------------------------------------------------------------
step "Collegamento agli agenti IA"
"$VPY" "$DEST/clin.py" installa --agente "$AGENTI" || fail "Collegamento non riuscito (vedi messaggio sopra)."

# --- 6. Riconoscimento dei nomi senza etichetta ------------------------------------
ask() {  # ask "domanda" VARIABILE -> 0 se si'
  local ans="n"
  if [ "${!2:-0}" = "1" ]; then ans="s"
  elif [ -r /dev/tty ]; then printf "  %s [s/N] " "$1"; { read -r ans < /dev/tty; } 2>/dev/null || ans="n"; fi
  case "$ans" in s|S|si|sì|y|Y) return 0 ;; *) return 1 ;; esac
}
step "Riconoscimento dei nomi senza etichetta"
NER_PY="${CLIN_DATI:-$HOME/.clin}/ner/bin/python"
if [ -x "$NER_PY" ]; then
  echo "  GLiNER gia' installato"
elif ask "Installare GLiNER (consigliato, circa 2,4 GB, una volta sola)?" CLIN_GLINER; then
  "$VPY" "$DEST/clin.py" ner installa || echo "  GLiNER non installato: riprovare con  \"$VPY\" \"$DEST/clin.py\" ner installa"
elif command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -Eq '^(gemma4:e4b|qwen3:4b|gemma4:12b|qwen2\.5:7b)[[:space:]]'; then
    echo "  modello Ollama gia' presente"
  elif ask "In alternativa, scaricare gemma4:e4b per Ollama (circa 7 GB)?" CLIN_MODELLO; then
    ollama pull gemma4:e4b
  else
    echo "  saltato: Clin funziona con le sole regole"
  fi
else
  echo "  saltato: Clin funziona con le sole regole."
  echo "  Piu' tardi:  \"$VPY\" \"$DEST/clin.py\" ner installa"
fi

# --- Fine ---------------------------------------------------------------------------
printf '\n'
bold "Clin e' installato."
cat <<EOF

  1. Aprire Claude Code, Codex o Antigravity nella cartella dei dati
     (in una nuova sessione).
  2. Scrivere  /clin
  3. L'agente lavora solo sulle copie anonime in Clin_anonimizzati/.

  Disinstallare:  "$VPY" "$DEST/clin.py" disinstalla
EOF
