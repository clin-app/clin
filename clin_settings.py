"""
Clin - impostazioni per l'uso con gli agenti IA (Claude Code, Codex, Antigravity).

Un solo file, ~/.clin/impostazioni.json (permessi 600), letto dalla guardia,
dall'applicazione e da `clin.py impostazioni`. Le chiavi assenti prendono il
valore predefinito, quindi un file vecchio resta valido.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

# cartella dei dati locali di Clin (tabelle, impostazioni, copie lette); CLIN_DATI la sposta
DATA_DIR = Path(os.path.expanduser(os.environ.get("CLIN_DATI") or "~/.clin"))
PATH = DATA_DIR / "impostazioni.json"

# chiave -> (valore predefinito, descrizione mostrata all'utente)
OPTIONS: Dict[str, tuple] = {
    "ripristino_automatico": (True, "Al termine di ogni risposta dell'agente, i file prodotti con segnaposto "
                                    "vengono copiati con i dati reali nella cartella dei risultati."),
    "cartella_risultati": ("Clin_risultati", "Nome della cartella (dentro la cartella protetta) oppure percorso "
                                             "assoluto, anche fuori dal progetto. L'agente non vi ha accesso."),
    "blocca_messaggi": (True, "Ferma i messaggi all'agente che contengono codici fiscali, telefoni, "
                              "nominativi etichettati o numeri di documento."),
    "ripulisci_output": (True, "Ripulisce l'output dei comandi eseguiti dall'agente (Claude Code)."),
    "modello_locale": (True, "Usa il modello linguistico locale (Ollama), se presente, per i nomi senza etichetta."),
    "motore": ("auto", "Motore per i nomi senza etichetta: auto (GLiNER se installato, altrimenti Ollama), "
                       "gliner oppure ollama."),
    "ocr": (True, "Legge con l'OCR le pagine scansionate e le immagini, se il modello OCR e' installato."),
}


def defaults() -> Dict[str, Any]:
    return {k: v[0] for k, v in OPTIONS.items()}


def load() -> Dict[str, Any]:
    data = defaults()
    try:
        stored = json.loads(PATH.read_text(encoding="utf-8"))
        data.update({k: v for k, v in stored.items() if k in OPTIONS})
    except (OSError, ValueError):
        pass
    return data


def save(values: Dict[str, Any]) -> None:
    data = load()
    data.update({k: v for k, v in values.items() if k in OPTIONS})
    PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, PATH)


def parse(key: str, raw: str) -> Any:
    """Valore da riga di comando: si/no per le opzioni booleane, testo per le altre."""
    if key not in OPTIONS:
        raise ValueError(f"Impostazione sconosciuta: {key}. Disponibili: {', '.join(OPTIONS)}")
    if isinstance(OPTIONS[key][0], bool):
        low = raw.strip().lower()
        if low in {"si", "sì", "s", "true", "1", "on", "yes"}:
            return True
        if low in {"no", "n", "false", "0", "off"}:
            return False
        raise ValueError(f"{key}: usare si oppure no.")
    if key == "motore" and raw.strip() not in ("auto", "gliner", "ollama"):
        raise ValueError("motore: usare auto, gliner oppure ollama.")
    return raw.strip()


def results_dir(root: Path) -> Path:
    """Cartella dei risultati con i dati reali per una cartella protetta."""
    value = str(load()["cartella_risultati"]).strip() or "Clin_risultati"
    p = Path(os.path.expanduser(value))
    return p if p.is_absolute() else root / p
