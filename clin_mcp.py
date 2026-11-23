"""
Clin - Server MCP (Model Context Protocol) locale, senza dipendenze.

Permette a Claude Desktop, Claude Code, Cursor e agli altri client MCP di
leggere documenti sanitari SOLO in forma anonimizzata: l'IA riceve il
percorso del file, Clin lo apre su questo computer e restituisce il testo
con i dati sensibili gia' sostituiti da segnaposto. Il contenuto originale
non lascia mai il computer.

Avvio (lo fa il client MCP): python3 clin.py mcp
Cartelle consultabili: variabile CLIN_CARTELLE (separate da ':'),
in assenza la sola cartella home dell'utente.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

from clin_text import DEFAULT_LEVEL, SUPPORTED_SUFFIXES, anonymize_file, check_path

SERVER_INFO = {"name": "clin", "version": "2.0.0"}
PROTOCOL_VERSION = "2025-06-18"

INSTRUCTIONS = (
    "Clin anonimizza documenti sanitari in locale. Quando l'utente chiede di "
    "lavorare su un referto, una cartella clinica, una lettera di dimissione o un "
    "foglio di dati di pazienti presente sul suo computer, usa lo strumento "
    "`anonimizza_documento` con il percorso del file invece di chiedergli di "
    "incollarne il contenuto. I segnaposto come [PAZIENTE_1] o [DATA_NASCITA_1] "
    "sostituiscono dati personali: usali cosi' come sono nella risposta e non "
    "tentare di ricostruirli. Se l'utente incolla direttamente dati identificativi "
    "in chat, ricordagli che quei dati sono gia' stati inviati e suggerisci per la "
    "volta successiva lo strumento Clin o la modalita' appunti."
)

TOOLS = [
    {
        "name": "anonimizza_documento",
        "title": "Leggi un documento sanitario anonimizzato",
        "description": (
            "Apre un documento sul computer dell'utente (PDF, Word .docx, Excel, CSV, "
            "TXT, immagini JPG/PNG lette con OCR) e ne restituisce il testo con i dati sensibili sostituiti da "
            "segnaposto ([PAZIENTE_1], [ID_1], [DATA_NASCITA_1], [MEDICO_1]...). "
            "Il contenuto originale non viene mai trasmesso."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "percorso": {"type": "string",
                             "description": "Percorso assoluto del file (anche con ~)."},
            },
            "required": ["percorso"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "crea_copie_anonime",
        "title": "Crea copie anonimizzate dei documenti",
        "description": (
            "Crea sul computer dell'utente copie anonimizzate (PDF con riquadri neri "
            "irreversibili, fogli di calcolo con pseudonimi) di un file o di tutti i "
            "documenti di una cartella, sottocartelle comprese. I documenti non modificati "
            "dall'ultima volta non vengono rielaborati. Restituisce il numero di file, la "
            "cartella di destinazione e i nomi (anonimi) delle copie, nessun contenuto."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "percorso": {"type": "string", "description": "File o cartella."},
            },
            "required": ["percorso"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
]


def allowed_roots() -> List[Path]:
    raw = os.environ.get("CLIN_CARTELLE", "").strip()
    if raw:
        return [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]
    return [Path.home()]


def tool_anonimizza_documento(args: Dict[str, Any]) -> str:
    res = anonymize_file(Path(str(args.get("percorso", ""))), allowed_roots=allowed_roots())
    head = [
        "[Documento anonimizzato in locale da Clin. I segnaposto tra parentesi "
        "quadre sostituiscono dati personali: non tentare di ricostruirli.]",
        res.summary(),
    ]
    head.extend(res.notes)
    # Il dizionario segnaposto -> originale (res.mapping) non viene MAI restituito.
    return "\n".join(head) + "\n\n" + res.text


SKIP_DIRS = {"Clin_anonimizzati", "node_modules", "__pycache__"}
INDEX_NAME = ".clin-indice.json"


def _documents(target: Path) -> Dict[Path, List[Path]]:
    """Documenti supportati della cartella e delle sottocartelle, raggruppati per cartella."""
    from clin_text import _is_forbidden_path
    groups: Dict[Path, List[Path]] = {}
    for dirpath, dirs, names in os.walk(target):
        d = Path(dirpath)
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in SKIP_DIRS
                         and not (d / x).is_symlink() and not _is_forbidden_path(d / x))
        files = sorted(f for f in (d / n for n in names if not n.startswith((".", "~$")))
                       if f.is_file() and not f.is_symlink()
                       and f.suffix.lower() in SUPPORTED_SUFFIXES - {".md"} and not _is_forbidden_path(f))
        if files:
            groups[d] = files
    return groups


def tool_crea_copie_anonime(args: Dict[str, Any]) -> str:
    import hashlib
    from anonymize_engine import BatchResult, process_batch_files
    from clin_text import _is_forbidden_path
    from tabular_engine import TableSettings

    roots = allowed_roots()
    target = Path(str(args.get("percorso", ""))).expanduser().resolve()
    if _is_forbidden_path(target):
        raise ValueError("Accesso negato: il percorso appartiene ai dati riservati o ai risultati di Clin.")
    if target.is_dir():
        if not any(target.is_relative_to(r.expanduser().resolve()) for r in roots):
            raise ValueError("La cartella e' fuori da quelle autorizzate per Clin.")
        base, groups = target, _documents(target)
    else:
        base, groups = target.parent, {target.parent: [check_path(target, roots)]}
    out_dir = base / "Clin_anonimizzati"
    total = sum(len(f) for f in groups.values())
    if not total:
        return "Nessun documento supportato (PDF, DOCX, TXT, JPG, PNG, CSV, TSV, XLSX) nel percorso indicato."
    from tabular_engine import _PseudonymBook
    level = DEFAULT_LEVEL
    # stesso paziente, stesso pseudonimo in tutti i file e in tutte le sessioni
    import clin_settings
    book_path = clin_settings.DATA_DIR / "pseudonimi.json"
    book = _PseudonymBook.load(book_path)
    # note e recapiti nei fogli: segnaposto ripristinabili, nella stessa tabella dei testi
    import clin
    from clin_text import _Registry
    registry = _Registry.from_mapping(clin.load_mapping())

    # Indice delle copie gia' fatte: un documento non modificato non viene rielaborato. La chiave e'
    # l'impronta del percorso (mai il nome, che puo' contenere quello del paziente); l'indice decade
    # se cambiano le impostazioni di anonimizzazione.
    settings_fp = hashlib.sha256(json.dumps(clin_settings.load(), sort_keys=True, default=str).encode()).hexdigest()[:16]
    index_path = out_dir / INDEX_NAME
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index = index["file"] if index.get("impostazioni") == settings_fp else {}
    except (OSError, ValueError, KeyError, AttributeError):
        index = {}

    def key(f: Path) -> str:
        return hashlib.sha256(str(f.relative_to(base)).encode()).hexdigest()[:20]

    def sig(f: Path) -> list:
        st = f.stat()
        return [st.st_mtime_ns, st.st_size]

    batch, reused = BatchResult(), 0
    for folder, files in groups.items():
        todo = []
        for f in files:
            e = index.get(key(f))
            if e and e[:2] == sig(f) and (out_dir / e[2]).is_file():
                reused += 1
            else:
                if e:  # documento modificato: la copia vecchia va tolta, altrimenti resterebbe accanto alla nuova
                    (out_dir / e[2]).unlink(missing_ok=True)
                todo.append(f)
        if not todo:
            continue
        done = BatchResult()
        process_batch_files(todo, out_dir / folder.relative_to(base), sensitivity_level=level, batch_result=done,
                            table_settings=TableSettings(level=level, pseudonyms=book, keep_labels=True,
                                                         registry=registry))
        for r in done.results:
            if r.ok and r.output_path:
                index[key(r.input_path)] = sig(r.input_path) + [str(Path(r.output_path).relative_to(out_dir))]
        batch.results.extend(done.results)
    book.save(book_path)
    clin.save_mapping(registry.mapping)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps({"impostazioni": settings_fp, "file": index}), encoding="utf-8")

    lines = [f"Copie anonimizzate pronte: {batch.processed + reused} su {total}"
             + (f" ({reused} gia' aggiornate, non rielaborate)." if reused else "."),
             f"Copie in: {out_dir}"]
    if batch.failed:
        lines.append(f"Non elaborati: {len(batch.failed)} (formato o protezione).")
    if batch.warnings:
        lines.append(f"Avvisi da verificare manualmente: {len(batch.warnings)}.")
    # elenco delle copie (nomi gia' anonimi): l'agente sa subito su che cosa lavorare
    # formati che Clin non anonimizza: restano chiusi, e l'agente deve dirlo all'utente
    if target.is_dir():
        from clin_guard import PROTECTED
        closed: Dict[str, int] = {}
        for dirpath, dirs, names in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
            for n in names:
                ext = Path(n).suffix.lower()
                if ext in PROTECTED and ext not in SUPPORTED_SUFFIXES and not n.startswith((".", "~$")):
                    closed[ext] = closed.get(ext, 0) + 1
        if closed:
            lines.append("Formati non anonimizzabili, lasciati chiusi: "
                         + ", ".join(f"{n} {e}" for e, n in sorted(closed.items()))
                         + ". Chiedere all'utente di esportarli in PDF, Word, Excel o CSV.")
    copies = sorted(str(c.relative_to(out_dir)) for c in out_dir.rglob("*") if c.is_file() and c.name != INDEX_NAME)
    if copies:
        lines.append("File su cui lavorare:")
        lines.extend(f"  {c}" for c in copies[:60])
        if len(copies) > 60:
            lines.append(f"  … e altri {len(copies) - 60}")
    return "\n".join(lines)


HANDLERS = {
    "anonimizza_documento": tool_anonimizza_documento,
    "crea_copie_anonime": tool_crea_copie_anonime,
}


def handle(msg: Dict[str, Any]) -> Dict[str, Any] | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notifica: nessuna risposta
        return None
    if method == "initialize":
        client_ver = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        result = {"protocolVersion": client_ver, "capabilities": {"tools": {}},
                  "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        fn = HANDLERS.get(params.get("name"))
        if fn is None:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": f"Strumento sconosciuto: {params.get('name')}"}}
        try:
            text, is_error = fn(params.get("arguments") or {}), False
        except ValueError as exc:
            text, is_error = str(exc), True
        except Exception as exc:  # nessun traceback verso l'IA: puo' contenere testo del file
            print(traceback.format_exc(), file=sys.stderr)
            text, is_error = f"Errore interno di Clin ({type(exc).__name__}).", True
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"Metodo non supportato: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve() -> None:
    """Ciclo JSON-RPC su stdin/stdout (un messaggio per riga)."""
    from anonymize_engine import fitz
    # stdout e' riservato al protocollo: i messaggi di MuPDF vanno silenziati
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        replies = [handle(m) for m in msg] if isinstance(msg, list) else [handle(msg)]
        for reply in replies:
            if reply is not None:
                sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    serve()
