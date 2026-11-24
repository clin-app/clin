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


def book_path() -> Path:
    """Tabella degli pseudonimi (PAZ-0001...) condivisa da fogli di calcolo e testi: accanto alla tabella dei
    segnaposto (clin.MAP_DIR, la stessa cartella di DATA_DIR), cosi' le due restano sempre insieme."""
    import clin
    return clin.MAP_DIR / "pseudonimi.json"


# Tabelle di corrispondenza cifrate (uso su server): con CLIN_CHIAVE (chiave Fernet, 44 caratteri base64,
# generata con `clin chiave`) le tabelle su disco sono illeggibili senza la chiave, che sta altrove
# (variabile d'ambiente del servizio, gestore di segreti). Senza chiave: JSON in chiaro, permessi 600.
_FERNET_HEAD = b"gAAAAA"


def _fernet():
    key = os.environ.get("CLIN_CHIAVE", "").strip()
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def read_private(path: Path) -> str:
    data = Path(path).read_bytes()
    if data.startswith(_FERNET_HEAD):
        f = _fernet()
        if f is None:
            raise RuntimeError(f"{Path(path).name} e' cifrata: serve la chiave CLIN_CHIAVE.")
        return f.decrypt(data).decode("utf-8")
    return data.decode("utf-8")


def write_private(path: Path, text: str) -> None:
    """Scrittura atomica, permessi 600 (cartella 700), cifrata se c'e' CLIN_CHIAVE."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    f = _fernet()
    data = f.encrypt(text.encode("utf-8")) if f else text.encode("utf-8")
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)

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
    "categorie_escluse": ([], "Categorie da NON rimuovere (controllo manuale; vuoto = si rimuove tutto). "
                              "Es.: Date, Struttura sanitaria. Elenco: clin.py impostazioni categorie."),
    "date_traslate": (True, "Nei fogli di calcolo le date vengono spostate nel futuro di un numero fisso e "
                            "segreto di giorni (circa 220 anni) invece di essere oscurate: intervalli ed eta' "
                            "restano esatti; nei risultati tornano le date vere."),
    "date_calendario": (True, "Le date dei fogli sono spostate di 400 anni esatti: giorno, mese, stagione e giorno "
                              "della settimana restano quelli veri, quindi ogni analisi (anche per anno e per "
                              "stagione) e' corretta e ricostruibile. Con `no` vengono spostate di un numero segreto "
                              "di giorni: piu' nascoste, ma senza analisi di calendario."),
    "percorsi_esclusi": ([], "File o cartelle senza dati di pazienti (articoli, linee guida) dentro una cartella "
                             "protetta: l'agente li legge cosi' come sono. Si gestiscono con `clin.py escludi`."),
    "colonne_dal_contenuto": (True, "Nei fogli di calcolo riconosce le colonne di nominativi anche senza "
                                    "un'intestazione nota, dal contenuto delle celle."),
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
    os.chmod(PATH.parent, 0o700)
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
    if key == "percorsi_esclusi":
        raise ValueError("percorsi_esclusi si gestisce con: clin.py escludi PERCORSO (--annulla per toglierlo).")
    if key == "categorie_escluse":
        from anonymize_engine import CONTROL_CATEGORIES
        names = [c.strip() for c in raw.split(",") if c.strip()]
        lookup = {c.casefold(): c for c in CONTROL_CATEGORIES}
        bad = [c for c in names if c.casefold() not in lookup]
        if bad:
            raise ValueError(f"Categorie sconosciute: {', '.join(bad)}. Disponibili: {', '.join(CONTROL_CATEGORIES)}")
        return [lookup[c.casefold()] for c in names]
    if key == "motore" and raw.strip() not in ("auto", "gliner", "ollama"):
        raise ValueError("motore: usare auto, gliner oppure ollama.")
    return raw.strip()


# 400 anni esatti: il calendario gregoriano si ripete identico (146097 giorni, 20871 settimane)
CALENDAR_SHIFT = 146097


def date_shift(create: bool = True):
    """Giorni di cui si spostano le date dei fogli, o None se la traslazione e' disattivata.

    Il numero e' casuale, scelto una volta e conservato nella cartella dei dati di Clin: uguale per
    tutti i file e tutte le sessioni, cosi' gli intervalli restano esatti anche tra fogli diversi."""
    values = load()
    if not values.get("date_traslate", True):
        return None
    if values.get("date_calendario"):
        return CALENDAR_SHIFT
    path = DATA_DIR / "traslazione_date.json"
    try:
        return int(json.loads(path.read_text(encoding="utf-8"))["giorni"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if not create:
        return None
    import secrets
    days = 80000 + secrets.randbelow(366)  # 1900 -> 2119, oggi -> 2245: sempre riconoscibili come traslate
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"giorni": days}, fh)
    return days


def is_excluded(path: Path) -> bool:
    """Vero se l'utente ha dichiarato senza dati di pazienti il file o una cartella che lo contiene."""
    items = load().get("percorsi_esclusi") or []
    if not items:
        return False
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    return any(p == Path(e) or Path(e) in p.parents for e in items)


def results_dir(root: Path) -> Path:
    """Cartella dei risultati con i dati reali per una cartella protetta."""
    value = str(load()["cartella_risultati"]).strip() or "Clin_risultati"
    p = Path(os.path.expanduser(value))
    return p if p.is_absolute() else root / p
