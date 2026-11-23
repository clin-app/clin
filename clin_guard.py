"""
Clin - guardia per Claude Code (hook).

Intercetta ciò che sta per raggiungere il modello e lo fa passare da Clin:

* PreToolUse / Read   un documento (PDF, Word, Excel, CSV, TXT...) viene
                      anonimizzato in locale e Claude legge solo la copia con
                      segnaposto (`updatedInput`). Se Clin non riesce, la
                      lettura viene negata: mai l'originale.
* PreToolUse / Bash   comandi che aprono documenti originali (cat, head,
                      pandas...) vengono negati con l'indicazione di usare Clin.
* PreToolUse / Grep   ricerche dentro documenti originali vengono negate.
* PostToolUse / Bash  l'output dei comandi (es. uno script che stampa righe di
                      un CSV) viene ripulito con le regole di Clin.
* UserPromptSubmit    un messaggio con dati personali evidenti (CF, telefoni,
                      IBAN, nominativi etichettati...) viene bloccato prima
                      dell'invio. Per inviarlo comunque: includere [clin:ok].

La guardia e' dormiente: agisce solo nelle cartelle attivate con `/clin`
(file `.clin-protetto` nella cartella o in una cartella superiore) o con
CLIN_GUARD=1. Altrove esce subito senza toccare nulla.

Sono esclusi i file già anonimizzati: cartelle `Clin_anonimizzati`, nomi con
`_ANONIMIZZATO`, copie in ~/.clin/letture.

Installazione: `python3 clin.py proteggi [cartella]` (vedi README).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Iterable, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PROTECTED = {".pdf", ".docx", ".doc", ".xlsx", ".xlsm", ".xls", ".csv", ".tsv", ".txt", ".rtf",
             ".odt", ".ods", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff", ".bmp",
             # formati che Clin non sa anonimizzare ma che portano dati di pazienti: restano chiusi
             # (presentazioni, dataset statistici, immagini DICOM, posta, database e documenti Apple)
             ".ppt", ".odp", ".sav", ".zsav", ".por", ".dta", ".sas7bdat", ".xpt", ".dcm", ".pptx",
             ".eml", ".msg", ".mdb", ".accdb", ".numbers", ".pages", ".key"}
READS_DIR = Path(os.path.expanduser(os.environ.get("CLIN_DATI") or "~/.clin")) / "letture"
MARKER = ".clin-protetto"
RESULTS_MARKER = ".clin-risultati"
# categorie certe abbastanza da fermare un messaggio (le date da sole no)
PROMPT_BLOCK = {"ID ufficiali", "Dati bancari", "Nome paziente", "Documenti", "Data di nascita"}
_GLOB_RX = re.compile(r"\*\.(?:" + "|".join(e[1:] for e in PROTECTED) + r")\b", re.I)
_EXT_RX = re.compile(r"[^\s'\"|;&<>()=,]+\.(?:" + "|".join(e[1:] for e in PROTECTED) + r")\b", re.I)
# comandi che non mostrano, non copiano e non spostano il contenuto dei file
_SAFE_CMDS = {"ls", "find", "stat", "file", "du", "mkdir", "touch", "wc",
              "basename", "dirname", "realpath", "echo", "cd", "pwd", "chmod", "mdls", "xattr"}
_SEARCH_CMDS = {"grep", "egrep", "fgrep", "rg", "ripgrep", "ag", "ack"}
_SHELL_WRAPPERS = {"sh", "bash", "zsh", "dash", "ksh"}
# sottocomandi di clin.py riservati all'utente: rivelano dati reali o smontano la protezione
_USER_ONLY = {"originale", "ripristina", "dimentica", "disinstalla", "escludi"}


def is_anonymized(path: Path) -> bool:
    try:
        resolved = path.resolve()
        reads = READS_DIR.resolve()
    except OSError:
        resolved, reads = path, READS_DIR
    parts = {p.casefold() for p in resolved.parts}
    return ("clin_anonimizzati" in parts or "_anonimizzato" in resolved.stem.casefold()
            or reads in resolved.parents)


# file tecnici con estensione "da documento" che non contengono dati di pazienti
_TECH_FILES = re.compile(r"(?i)^(?:requirements|constraints|dev-requirements|test-requirements)[\w.-]*\.txt$|"
                         r"^(?:license|licence|copying|notice|authors|readme|changelog|cmakelists|robots|"
                         r"llms|version)\.txt$")


def needs_guard(path: Path) -> bool:
    if path.suffix.lower() not in PROTECTED or is_anonymized(path) or _TECH_FILES.match(path.name):
        return False
    import clin_settings
    return not clin_settings.is_excluded(path) and not is_agent_output(path)


# segnaposto, pseudonimi e date traslate (anni 2100-2299): solo un file dell'agente li contiene
_TOKEN = re.compile(rb"\[\s*[A-Z]+(?:_[A-Z]+)*_\d+\s*\]|\b[A-Z]{2,4}-\d{4}\b"
                    rb"|(?<!\d)2[12]\d\d-\d\d-\d\d(?!\d)|(?<!\d)\d{1,2}[/.\-]\d{1,2}[/.\-]2[12]\d\d(?!\d)")


def is_agent_output(path: Path) -> bool:
    """
    File prodotto dall'agente dopo /clin: creato dopo l'attivazione della cartella
    e con segnaposto o pseudonimi al suo interno. Un originale non li contiene mai.
    """
    try:
        if path.is_symlink():
            return False
        root = protected_root(path.parent)
        if root is None or path.stat().st_mtime <= (root / MARKER).stat().st_mtime:
            return False
        if path.suffix.lower() in {".xlsx", ".xlsm", ".docx", ".pptx"}:
            import zipfile
            chunks = []
            budget = 2_000_000
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    if budget <= 0:
                        break
                    if n.endswith(("sharedStrings.xml",)) or n.startswith(("xl/worksheets/", "word/", "ppt/slides/")):
                        with z.open(n) as zf:
                            part = zf.read(min(budget, 500_000))
                            chunks.append(part)
                            budget -= len(part)
            data = b"".join(chunks)
        elif path.suffix.lower() in {".csv", ".tsv", ".txt", ".md", ".json"}:
            with open(path, "rb") as fh:
                data = fh.read(2_000_000)
        else:
            return False
        return bool(_TOKEN.search(data))
    except Exception:  # archivio non valido o illeggibile: non e' un file dell'agente, resta protetto
        return False


def results_dir_for(cwd: str) -> Optional[Path]:
    """Cartella con i risultati ricondotti ai dati reali (mai accessibile all'agente)."""
    import clin_settings
    root = protected_root(Path(cwd or os.getcwd()).expanduser())
    return clin_settings.results_dir(root) if root else None


def in_data_dir(path: Path) -> bool:
    """Vero per le tabelle locali di Clin (~/.clin), escluse le copie di lettura della guardia."""
    import clin
    try:
        resolved = path.resolve()
        reads = READS_DIR.resolve()
        if resolved == reads or reads in resolved.parents:
            return False
        data_dirs = {clin.MAP_DIR.expanduser().resolve()}
        import clin_settings
        data_dirs.add(clin_settings.DATA_DIR.expanduser().resolve())
        return any(resolved == d or resolved.is_relative_to(d) for d in data_dirs)
    except OSError:
        return False


def in_results(path: Path, cwd: str) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for anc in (resolved, *resolved.parents):
        if (anc / RESULTS_MARKER).is_file() or anc.name == "Clin_risultati":
            return True
    import clin_settings
    roots = {r for r in (protected_root(Path(cwd or os.getcwd()).expanduser()),
                         protected_root(resolved if resolved.exists() else resolved.parent)) if r}
    for root in roots:
        try:
            if resolved.is_relative_to(clin_settings.results_dir(root).resolve()):
                return True
        except OSError:
            continue
    return False


RESULTS_DENIED = ("Clin: la cartella dei risultati contiene i dati reali dei pazienti e non e' "
                  "accessibile all'agente. Lavorare sui file con segnaposto o pseudonimi.")
DATA_DENIED = ("Clin: la cartella dei dati locali di Clin contiene le tabelle di corrispondenza "
               "e non e' accessibile all'agente.")


def _out(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _deny(reason: str) -> None:
    _out({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                 "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def _abs(raw: str, cwd: str) -> Path:
    p = Path(os.path.expanduser(raw))
    return p if p.is_absolute() else Path(cwd or os.getcwd()) / p


# --------------------------------------------------------------------------
# Read: si legge la copia anonimizzata
# --------------------------------------------------------------------------
def anonymized_copy(path: Path) -> Path:
    """Testo anonimizzato del documento in ~/.clin/letture (permessi 600)."""
    import clin
    from clin_text import anonymize_file

    st = path.stat()
    key = hashlib.sha256(f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:24]
    target = READS_DIR / f"{key}.txt"  # niente nome originale nel percorso
    if target.exists():
        return target
    # stessa tabella segnaposto della modalita' appunti: [PAZIENTE_1] e' la stessa
    # persona in ogni file letto nella sessione
    previous = clin.load_mapping()
    res = anonymize_file(path, allowed_roots=None, previous=previous)
    clin.save_mapping(res.mapping)
    READS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    header = (f"[Documento anonimizzato in locale da Clin. {res.summary()} "
              "I segnaposto tra parentesi quadre sostituiscono dati personali.]\n")
    notes = "".join(f"[{n}]\n" for n in res.notes)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(header + notes + "\n" + res.text)
    return target


def on_read(data: dict) -> None:
    tool_input = dict(data.get("tool_input") or {})
    raw = tool_input.get("file_path") or ""
    cwd = data.get("cwd", "")
    path = _abs(raw, cwd)
    if raw and in_results(path, cwd):
        _deny(RESULTS_DENIED)
        return
    if raw and in_data_dir(path):
        _deny(DATA_DENIED)
        return
    if not raw or not needs_guard(path) or not path.exists():
        return
    from clin_text import SUPPORTED_SUFFIXES
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        _deny(f"Clin: formato {path.suffix} non leggibile direttamente. Per SPSS, Stata e SAS usare la copia "
              "CSV in Clin_anonimizzati/ (la crea `clin.py avvia`); gli altri formati vanno convertiti in PDF, "
              "Word, Excel o CSV. L'originale non viene letto.")
        return
    try:
        copy = anonymized_copy(path)
    except Exception as exc:  # mai l'originale: in caso di errore si nega
        _deny(f"Clin: impossibile anonimizzare {path.name} ({exc.__class__.__name__}). "
              "Lettura bloccata per proteggere i dati del paziente.")
        return
    tool_input["file_path"] = str(copy)
    tool_input.pop("pages", None)  # la copia e' testo
    _out({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": f"Clin: letta la copia anonimizzata di {path.name}",
        "updatedInput": tool_input,
    }})


# --------------------------------------------------------------------------
# Bash e Grep: niente accesso diretto agli originali
# --------------------------------------------------------------------------
def _segments(command: str, _depth: int = 0) -> Iterable[List[str]]:
    if _depth > 4:
        return
    for seg in re.split(r"\|\||&&|[|;\n]", command):
        try:
            words = shlex.split(seg)
        except ValueError:
            words = seg.split()
        if not words:
            continue
        yield words
        # "bash -lc 'rg ROSSI'" o "sh -c 'cat coorte.csv'": ispeziona anche il comando interno
        if Path(words[0]).name in _SHELL_WRAPPERS:
            for idx, w in enumerate(words[1:], 1):
                if w.startswith("-") and "c" in w and idx + 1 < len(words):
                    yield from _segments(words[idx + 1], _depth + 1)
                    break


_SEARCH_VAL_FLAGS = {"-e", "--regexp", "-f", "--file", "-m", "--max-count", "-A", "-B", "-C"}
_SEARCH_GLOB_FLAGS = {"-g", "--glob", "-t", "--type", "--include"}


def _risky_search(words: List[str], cwd: str) -> List[str]:
    """Ricerche da shell (grep, rg...) che leggerebbero originali non anonimizzati."""
    pos_args: List[str] = []
    globs: List[str] = []
    has_explicit_pat = False
    i = 1
    while i < len(words):
        w = words[i]
        if w == "--":
            pos_args.extend(words[i + 1:])
            break
        if w in _SEARCH_VAL_FLAGS:
            if w in {"-e", "--regexp", "-f", "--file"}:
                has_explicit_pat = True
            i += 2
            continue
        if w in _SEARCH_GLOB_FLAGS and i + 1 < len(words):
            globs.append(words[i + 1])
            i += 2
            continue
        if w.startswith(("--glob=", "--include=", "--type=")):
            globs.append(w.split("=", 1)[1])
            i += 1
            continue
        if w.startswith(("-e", "-f")) and len(w) > 2:
            has_explicit_pat = True
            i += 1
            continue
        if w.startswith("-"):
            i += 1
            continue
        pos_args.append(w)
        i += 1
    positive_globs = [g for g in globs if not g.startswith("!")]
    if positive_globs:
        joined = " ".join(positive_globs)
        if not _GLOB_RX.search(joined) and not re.search(
            r"(?i)\b(?:csv|tsv|txt|pdf|docx?|xlsx?|rtf|odt|ods)\b", joined
        ):
            return []
    targets = pos_args if has_explicit_pat else pos_args[1:]
    paths = [_abs(t, cwd) for t in targets] if targets else [_abs(".", cwd)]
    bad = []
    for p in paths:
        if p.is_file() and needs_guard(p):
            bad.append(p.name)
        elif p.is_dir() and not is_anonymized(p / "x") and _contains_protected(p):
            bad.append(words[0])
    return bad


def risky_paths(command: str, cwd: str) -> List[str]:
    """Documenti originali che il comando potrebbe mostrare, copiare o cercare."""
    found = []
    for words in _segments(command):
        name = Path(words[0]).name
        if name in _SAFE_CMDS and not ({"-exec", "-execdir", "-ok"} & set(words)):
            continue
        if name.startswith("python") and len(words) > 1 and Path(words[1]).name in {"clin.py", "clin_guard.py"}:
            continue
        if name in _SEARCH_CMDS:
            found.extend(_risky_search(words, cwd))
        seg = " ".join(words)
        for m in _EXT_RX.finditer(seg):
            token = m.group(0)
            # "*.csv" o "dati/*.xlsx": si guarda la cartella del glob
            if "*" in token or "?" in token:
                if not is_anonymized(_abs(token, cwd).parent / "x"):
                    found.append(token)
            elif _abs(token, cwd).exists() and needs_guard(_abs(token, cwd)):
                found.append(token)
        # glob generico senza estensione ("cat *", "head dati/*")
        if name not in _SHELL_WRAPPERS:
            for w in words[1:]:
                if ("*" in w or "?" in w) and not w.startswith("-") and not _EXT_RX.search(w):
                    parent = _abs(w, cwd).parent
                    if parent.is_dir() and not is_anonymized(parent / "x") and _contains_protected(parent):
                        found.append(w)
    return found


def _command_of(tool_input: dict) -> str:
    cmd = tool_input.get("command") or tool_input.get("cmd") or ""
    if isinstance(cmd, list):
        return " ".join(shlex.quote(str(x)) for x in cmd)
    return str(cmd)


def bash_reason(command: str, cwd: str) -> str:
    res = results_dir_for(cwd)
    if res is not None and (res.name in command or str(res) in command):
        return RESULTS_DENIED
    if RESULTS_MARKER in command or "Clin_risultati" in command:
        return RESULTS_DENIED
    if "segnaposto.json" in command or "pseudonimi.json" in command:
        return DATA_DENIED
    for words in _segments(command):
        # i comandi di Clin che mostrano dati reali o cambiano la protezione li esegue solo l'utente
        for i, w in enumerate(words[:-1]):
            if Path(w.strip("'\"")).name == "clin.py":
                sub, rest = words[i + 1], words[i + 2:]
                if sub in _USER_ONLY or (sub == "impostazioni" and len(rest) >= 2):
                    return (f"Clin: `clin.py {sub}` mostra dati reali o cambia la protezione: puo' eseguirlo "
                            "solo l'utente, nel proprio terminale.")
    for words in _segments(command):
        for w in words:
            if w.startswith("-"):
                continue
            cand = _abs(w.strip("'\"()"), cwd)
            if in_results(cand, cwd):
                return RESULTS_DENIED
            if in_data_dir(cand):
                return DATA_DENIED
    risky = risky_paths(command, cwd)
    if not risky:
        return ""
    return ("Clin: il comando aprirebbe documenti con dati di pazienti "
            f"({', '.join(sorted(set(risky))[:3])}). Leggerli con lo strumento di lettura file "
            "(Clin passa la copia anonimizzata) oppure creare copie anonime con "
            f"`\"{sys.executable}\" \"{HERE / 'clin.py'}\" copie <cartella>` e lavorare su Clin_anonimizzati/.")


def on_bash(data: dict) -> None:
    reason = bash_reason(_command_of(data.get("tool_input") or {}), data.get("cwd", ""))
    if reason:
        _deny(reason)


def on_grep(data: dict) -> None:
    ti = data.get("tool_input") or {}
    cwd = data.get("cwd", "")
    target = _abs(ti.get("path") or cwd or ".", cwd)
    if in_data_dir(target):
        _deny(DATA_DENIED)
        return
    res = results_dir_for(cwd)
    # una ricerca che include la cartella dei risultati la leggerebbe, qualunque sia il filtro
    if in_results(target, cwd) or (res is not None and res.exists() and res.resolve().is_relative_to(target.resolve())):
        _deny(RESULTS_DENIED + " Restringere la ricerca a una sottocartella che non la contenga.")
        return
    glob = (ti.get("glob") or "") + " " + (ti.get("type") or "")
    if target.is_file():
        bad = needs_guard(target)
    elif _GLOB_RX.search(glob) or re.search(r"\b(?:csv|tsv|txt)\b", ti.get("type") or ""):
        bad = not is_anonymized(target)
    elif ti.get("glob") or ti.get("type"):
        bad = False  # ricerca ristretta a file di altro tipo (es. *.py)
    else:
        bad = _contains_protected(target)
    if bad:
        _deny("Clin: la ricerca toccherebbe documenti originali con dati di pazienti. "
              "Restringere la ricerca (glob) ai file non clinici o cercare in Clin_anonimizzati/.")


def _contains_protected(folder: Path, limit: int = 5000) -> bool:
    seen = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"node_modules", "Clin_anonimizzati"}]
        for f in files:
            seen += 1
            if needs_guard(Path(root) / f):
                return True
            if seen > limit:
                return True  # cartella enorme: per prudenza si nega
    return False


# --------------------------------------------------------------------------
# Output dei comandi e messaggi dell'utente
# --------------------------------------------------------------------------
def _known_originals() -> List[tuple]:
    """(valore originale, segnaposto) dalle tabelle locali, i piu' lunghi prima."""
    import clin_results
    seg, pseudo = clin_results._tables()
    pairs = [(v, k) for k, v in seg.items()] + [(v, k) for k, v in pseudo.items()]
    return sorted({(v, k) for v, k in pairs if isinstance(v, str) and len(v.strip()) >= 3},
                  key=lambda t: len(t[0]), reverse=True)


def _clean(text: str) -> str:
    from clin_text import anonymize_text
    if not text or not text.strip():
        return text
    text = anonymize_text(text).text
    # secondo livello: un dato reale gia' noto (es. stampato da uno script) torna segnaposto
    for value, ph in _known_originals():
        text = re.sub(r"(?<!\w)" + re.escape(value) + r"(?!\w)", ph, text, flags=re.IGNORECASE)
    return text


def on_bash_output(data: dict) -> None:
    resp = data.get("tool_response")
    if not isinstance(resp, dict):
        return
    new = dict(resp)
    for key in ("stdout", "stderr"):
        if isinstance(resp.get(key), str):
            new[key] = _clean(resp[key])
    if new != resp:
        _out({"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": new}})


def on_prompt(data: dict) -> None:
    from anonymize_engine import find_matches
    prompt = data.get("prompt") or ""
    if "[clin:ok]" in prompt:
        return
    cats = set()
    for m in find_matches(prompt, 10):
        if m.category in PROMPT_BLOCK:
            cats.add(m.category)
        elif m.category == "Contatti" and ("@" in m.text or len(re.sub(r"\D", "", m.text)) >= 8):
            cats.add("Contatti")  # telefoni ed email; non "via Slack"
    cats = sorted(cats)
    if cats:
        _out({"decision": "block",
              "reason": ("Clin ha fermato il messaggio prima dell'invio: contiene dati personali "
                         f"({', '.join(cats)}). Mettere il testo in un file e farlo leggere a Claude, "
                         "oppure anonimizzarlo con `clin appunti`. Per inviarlo comunque aggiungere [clin:ok]."),
              "suppressOriginalPrompt": True})


# --------------------------------------------------------------------------
# Google Antigravity: payload camelCase, risposta "decision"/"overwrite"
# --------------------------------------------------------------------------
_AG_READ = {"view_file", "view_file_outline", "view_code_item", "read_file"}
_AG_SHELL = {"run_command", "send_command_input"}
_AG_SEARCH = {"grep_search", "find_by_name", "codebase_search"}


def antigravity(data: dict) -> None:
    if data.get("hook_event_name", "PreToolUse") != "PreToolUse" and "toolCall" not in data:
        return
    call = data.get("toolCall") or {}
    name, args = call.get("name", ""), call.get("args") or {}
    cwd = (data.get("workspacePaths") or [os.getcwd()])[0]
    strings = {k: v for k, v in args.items() if isinstance(v, str)}
    if any(in_results(_abs(v, cwd), cwd) for v in strings.values()) or (
            name in _AG_SHELL and bash_reason(" ".join(strings.values()), cwd) == RESULTS_DENIED):
        _out({"decision": "deny", "reason": RESULTS_DENIED})
        return
    if any(in_data_dir(_abs(v, cwd)) for v in strings.values()) or (
            name in _AG_SHELL and bash_reason(" ".join(strings.values()), cwd) == DATA_DENIED):
        _out({"decision": "deny", "reason": DATA_DENIED})
        return
    if name in _AG_READ:
        for key, value in strings.items():
            path = _abs(value, cwd)
            if needs_guard(path) and path.exists():
                try:
                    copy = anonymized_copy(path)
                except Exception as exc:
                    _out({"decision": "deny", "reason": f"Clin: impossibile anonimizzare {path.name} "
                                                         f"({exc.__class__.__name__}): lettura bloccata."})
                    return
                _out({"decision": "allow", "overwrite": {key: str(copy)}})
                return
    elif name in _AG_SHELL:
        reason = bash_reason(" ".join(strings.values()), strings.get("Cwd") or cwd)
        if reason:
            _out({"decision": "deny", "reason": reason})
    elif name in _AG_SEARCH:
        for value in strings.values():
            path = _abs(value, cwd)
            if (path.is_file() and needs_guard(path)) or (path.is_dir() and _contains_protected(path)):
                _out({"decision": "deny", "reason": "Clin: la ricerca toccherebbe documenti originali "
                                                    "con dati di pazienti. Cercare in Clin_anonimizzati/."})
                return


def protected_root(start: Path) -> Optional[Path]:
    """Cartella attivata con /clin che contiene `start`, se c'e'."""
    for folder in [start, *start.parents]:
        if (folder / MARKER).is_file():
            return folder
    return None


def is_active(data: dict) -> bool:
    if os.environ.get("CLIN_GUARD") == "1":
        return True
    ws = list(data.get("workspacePaths") or [])
    base_cwd = data.get("cwd") or (ws[0] if ws else "") or os.getcwd()
    candidates: List[Path] = []
    for raw in [data.get("cwd"), *ws]:
        if isinstance(raw, str) and raw:
            candidates.append(Path(os.path.expanduser(raw)))
    ti = data.get("tool_input") or {}
    for k in ("file_path", "path"):
        if isinstance(ti.get(k), str) and ti[k]:
            candidates.append(_abs(ti[k], base_cwd))
    cmd = _command_of(ti)
    call_args = ((data.get("toolCall") or {}).get("args") or {})
    ag_cwd = call_args.get("Cwd") if isinstance(call_args.get("Cwd"), str) else base_cwd
    for v in call_args.values():
        if isinstance(v, str) and v:
            candidates.append(_abs(v, ag_cwd))
    if isinstance(call_args.get("CommandLine"), str):
        cmd = cmd + " ; " + call_args["CommandLine"]
    if cmd:
        if any(tok in cmd for tok in (RESULTS_MARKER, "Clin_risultati", "segnaposto.json", "pseudonimi.json")):
            return True
        for words in _segments(cmd):
            for w in words:
                if not w.startswith("-") and ("/" in w or "~" in w or "." in w):
                    candidates.append(_abs(w.strip("'\"()"), ag_cwd))
    for p in candidates:
        start = p if p.is_dir() else p.parent
        if protected_root(start) or in_results(p, base_cwd) or in_data_dir(p):
            return True
    return False


def on_stop(data: dict) -> None:
    import clin_results
    import clin_settings
    if not clin_settings.load()["ripristino_automatico"]:
        return
    places = [data.get("cwd")] + list(data.get("workspacePaths") or [])
    root = next((protected_root(Path(p).expanduser()) for p in places if p and protected_root(Path(p).expanduser())), None)
    if root is None:
        return
    written = clin_results.reidentify(root)
    if written:
        where = clin_settings.results_dir(root)
        # messaggio per l'utente: solo conteggio e cartella, nessun dato
        n = len(written)
        _out({"systemMessage": f"Clin: {n} file ricondott{'o' if n == 1 else 'i'} ai dati reali in {where}"})


def main() -> int:
    os.environ.setdefault("CLIN_LLM", "1")
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if not is_active(data):
        return 0  # cartella non attivata: nessun effetto
    import clin_settings
    settings = clin_settings.load()
    if not settings["modello_locale"]:
        os.environ["CLIN_LLM"] = "0"
    if not settings["ocr"]:
        os.environ["CLIN_TESSDATA"] = str(READS_DIR.parent / "ocr-disattivato")
    if (len(sys.argv) > 1 and sys.argv[1] == "stop") or data.get("hook_event_name") == "Stop":
        on_stop(data)
        return 0
    if "toolCall" in data:  # Google Antigravity
        os.environ["CLIN_LLM"] = "0" if data["toolCall"].get("name") not in _AG_READ else os.environ["CLIN_LLM"]
        antigravity(data)
        return 0
    event, tool = data.get("hook_event_name"), data.get("tool_name")
    if tool == "exec_command":  # Codex: stesso controllo della shell
        tool = "Bash"
    if event in {"PostToolUse", "UserPromptSubmit"} or tool in {"Bash", "Grep"}:
        os.environ["CLIN_LLM"] = "0"  # controlli rapidi: solo regole
    handlers = {
        ("PreToolUse", "Read"): on_read,
        ("PreToolUse", "Bash"): on_bash,
        ("PreToolUse", "Grep"): on_grep,
        ("PostToolUse", "Bash"): on_bash_output,
        ("UserPromptSubmit", None): on_prompt,
    }
    fn = handlers.get((event, tool if event != "UserPromptSubmit" else None))
    if fn is on_prompt and not settings["blocca_messaggi"]:
        return 0
    if fn is on_bash_output and not settings["ripulisci_output"]:
        return 0
    if fn:
        try:
            fn(data)
        except Exception as exc:
            # Un errore della guardia non deve mai lasciar passare l'originale: per l'agente un hook
            # fallito non blocca nulla, quindi prima dell'uso di uno strumento si nega esplicitamente.
            if event != "PreToolUse":
                raise
            _deny(f"Clin: errore interno della guardia ({exc.__class__.__name__}). Accesso negato per "
                  "proteggere i dati del paziente; eseguire `clin.py stato` e riferirlo all'utente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
