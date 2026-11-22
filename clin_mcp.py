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
            "documenti di una cartella. Restituisce solo il numero di file e la "
            "cartella di destinazione, nessun contenuto."
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


def tool_crea_copie_anonime(args: Dict[str, Any]) -> str:
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
        files = sorted(p for p in target.iterdir()
                       if p.is_file() and not p.is_symlink()
                       and p.suffix.lower() in SUPPORTED_SUFFIXES - {".md"}
                       and not _is_forbidden_path(p))
        out_dir = target / "Clin_anonimizzati"
    else:
        files = [check_path(target, roots)]
        out_dir = target.parent / "Clin_anonimizzati"
    if not files:
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
    batch = BatchResult()
    process_batch_files(files, out_dir, sensitivity_level=level, batch_result=batch,
                        table_settings=TableSettings(level=level, pseudonyms=book, keep_labels=True,
                                                     registry=registry))
    book.save(book_path)
    clin.save_mapping(registry.mapping)
    lines = [f"Copie anonimizzate create: {batch.processed} su {len(files)}.",
             f"Copie in: {out_dir}"]
    if batch.failed:
        lines.append(f"Non elaborati: {len(batch.failed)} (formato o protezione).")
    if batch.warnings:
        lines.append(f"Avvisi da verificare manualmente: {len(batch.warnings)}.")
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
