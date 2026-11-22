"""
Clin - ponte fra l'app web (JavaScript) e il motore Python, eseguito nel
browser con Pyodide. Tutte le funzioni accettano e restituiscono JSON.
Nessuna funzione esegue I/O di rete: il motore lavora solo sul testo ricevuto.
"""

import json
import os
from pathlib import Path

# nel browser non ci sono modelli locali (GLiNER/Ollama): solo regole e contesto
os.environ["CLIN_LLM"] = "0"

from anonymize_engine import collect_names, find_matches
from clin_ocr import ocr_suspects
from clin_text import (
    _Registry, _replace, anonymize_file, anonymize_text, restore_text,
)


def _prev(previous_json):
    prev = json.loads(previous_json or "{}") or {}
    return prev, [v for k, v in prev.items() if k.startswith("[PAZIENTE_")]


def _out(res):
    return json.dumps({"text": res.text, "mapping": res.mapping, "counts": res.counts,
                       "notes": getattr(res, "notes", []), "summary": res.summary()},
                      ensure_ascii=False)


def run_text(text, level, previous_json, ocr=False):
    """Testo libero (incollato, trascrizione audio, OCR)."""
    prev, names = _prev(previous_json)
    explicit = ocr_suspects(text) if ocr else None
    return _out(anonymize_text(text, level=int(level), previous=prev or None, names=names,
                               explicit=explicit))


def run_pages(pages_json, level, previous_json):
    """Pagine di un PDF: i nominativi trovati in una pagina valgono per tutte."""
    from clin_text import TextResult
    pages = json.loads(pages_json)
    prev, names = _prev(previous_json)
    for t in pages:
        names.extend(collect_names(t))
    registry = _Registry.from_mapping(prev) if prev else _Registry([])
    registry.add_names(names)
    counts, body, notes = {}, [], []
    for i, t in enumerate(pages, 1):
        if not t.strip():
            notes.append(f"Pagina {i}: nessun testo (scansione). Caricarla come foto per l'OCR.")
            continue
        new = _replace(t, registry, int(level), None, None, names, counts)
        body.append(f"--- Pagina {i} ---\n{new.strip()}" if len(pages) > 1 else new.strip())
    return _out(TextResult("\n\n".join(body), dict(registry.mapping), counts, notes))


def run_file(path, level, previous_json):
    """DOCX, CSV, TSV, TXT, MD scritti nel file system virtuale di Pyodide."""
    prev, _ = _prev(previous_json)
    return _out(anonymize_file(Path(path), level=int(level), previous=prev or None))


def spans(text, level, previous_json):
    """Intervalli sensibili del testo di una foto, per oscurarne le parole."""
    _, names = _prev(previous_json)
    names = names + collect_names(text)
    out = []
    for m in find_matches(text, int(level), ocr_suspects(text), keep_labels=True,
                          derived_targets=names):
        out.append([m.start, m.end, m.category])
    return json.dumps(out)


def restore(text, mapping_json):
    return restore_text(text, json.loads(mapping_json or "{}"))


def extract(path):
    """Testo grezzo di DOCX, TXT, MD (per unirlo agli altri documenti prima dell'anonimizzazione)."""
    from clin_text import _docx_text, _read_text
    p = Path(path)
    return _docx_text(p) if p.suffix.lower() == ".docx" else _read_text(p)


def run_bundle(items_json, level, previous_json):
    """
    Piu' documenti in un solo testo per la chat (PDF, Word, testi incollati, foto),
    anonimizzati insieme: ogni persona ha lo stesso segnaposto in tutti i documenti.
    items: [{"titolo": "...", "pagine": ["testo", ...], "ocr": bool}]
    """
    items = json.loads(items_json)
    blocks, explicit = [], []
    for it in items:
        pages = [t for t in it["pagine"]]
        if it.get("ocr"):
            for p in pages:
                explicit.extend(ocr_suspects(p))
        body = "\n\n".join(f"(pagina {i})\n{t.strip()}" if len(pages) > 1 else t.strip()
                            for i, t in enumerate(pages, 1) if t.strip())
        blocks.append(f"### {it['titolo']}\n{body}" if len(items) > 1 else body)
    prev, names = _prev(previous_json)
    res = anonymize_text("\n\n".join(blocks), level=int(level), previous=prev or None, names=names,
                         explicit=explicit or None)
    res.notes = [f"{it['titolo']}: nessun testo (scansione). Caricarla come foto per l'OCR."
                 for it in items if not any(t.strip() for t in it["pagine"])]
    return _out(res)


# --------------------------------------------------------------------------
# File con i dati coperti (estensione): l'IA riceve il documento, non una trascrizione
# --------------------------------------------------------------------------
_TITLE_RX = None
_PERSON_PH_PREFIXES = ("[PAZIENTE_", "[PERSONA_", "[MEDICO_", "[OPERATORE_",
                       "PAZ-", "PER-", "MED-", "OPE-")


def _plan_texts(texts, previous, ocr_flags=None):
    """Per ogni testo: [(inizio, fine, segnaposto)], con un solo registro per tutti i testi."""
    import re
    from anonymize_engine import collect_names as _collect
    from clin_text import _PLACEHOLDER, _without_relatives, find_spans
    global _TITLE_RX
    _TITLE_RX = _TITLE_RX or re.compile(r"(?i)^(dott\.ssa|dott\.?|dr\.ssa|dr\.?|prof\.ssa|prof\.?|sig\.ra|sig\.?|inf\.)\s+")
    joined = "\n\n".join(texts)
    names = list(_prev(json.dumps(previous))[1]) + _collect(joined)
    registry = _Registry.from_mapping(previous) if previous else _Registry([])
    registry.add_names(_without_relatives(joined, names, 10, None, None))
    plans = []
    for idx, t in enumerate(texts):
        is_ocr = bool(ocr_flags and idx < len(ocr_flags) and ocr_flags[idx])
        explicit = ocr_suspects(t) if is_ocr else None
        spans = []
        for s, e, cat in find_spans(t, 10, explicit, None, names):
            original = " ".join(t[s:e].split())
            m = _TITLE_RX.match(original)
            if m:  # "Dott. Neri": il titolo resta leggibile
                skip = len(m.group(0))
                s += skip
                original = original[skip:]
                while s < e and t[s].isspace():
                    s += 1
            if e <= s or not original:
                continue
            ph = registry.get(_PLACEHOLDER.get(cat, "DATO"), original, link=cat != "Persone")
            spans.append([s, e, ph])
        plans.append(spans)
    return plans, dict(registry.mapping)


def plan_pages(pages_json, previous_json, ocr_flags_json="[]"):
    """Testi delle pagine (PDF o OCR) -> intervalli da coprire con il loro segnaposto."""
    plans, mapping = _plan_texts(json.loads(pages_json), json.loads(previous_json or "{}"),
                                 json.loads(ocr_flags_json or "[]"))
    return json.dumps({"spans": plans, "mapping": mapping}, ensure_ascii=False)


def redact_docx(in_path, out_path, previous_json):
    """Word: riscrive il file .docx con i segnaposto ripulendo revisioni, miniature e metadati."""
    from clin_text import redact_docx_file
    previous = json.loads(previous_json or "{}")
    mapping, _, _ = redact_docx_file(Path(in_path), Path(out_path), level=10, previous=previous)
    return json.dumps({"mapping": mapping}, ensure_ascii=False)


def redact_table(in_path, out_path, book_json, previous_json="{}"):
    """CSV, TSV, Excel: stessa struttura, pseudonimi per colonna (PAZ-0001...) e segnaposto
    ripristinabili ([PERSONA_1], [CONTATTO_1]...) nelle note e nelle colonne di recapiti."""
    from tabular_engine import TableSettings, _PseudonymBook, anonymize_table
    book = json.loads(book_json or "{}")
    previous = json.loads(previous_json or "{}")
    pb = _PseudonymBook(book.get("codici"), book.get("originali"))
    reg = _Registry.from_mapping(previous) if previous else _Registry([])
    res = anonymize_table(Path(in_path), Path(out_path),
                          TableSettings(level=10, pseudonyms=pb, keep_labels=True, registry=reg))
    if res.error:
        raise ValueError(res.error)
    return json.dumps({"book": {"codici": pb._maps, "originali": pb.originals},
                       "mapping": {**reg.mapping, **pb.originals}, "names": res.detected_names[:200]}, ensure_ascii=False)


def safe_name(stem, mapping_json):
    """Nome del file prodotto senza i nominativi ("dimissione_ferrari" -> "dimissione_ANON")."""
    from anonymize_engine import safe_output_stem
    mapping = json.loads(mapping_json or "{}")
    names = [str(v) for k, v in mapping.items()
             if v and (" " in str(v) or str(k).startswith(_PERSON_PH_PREFIXES))]
    return safe_output_stem(stem, 10, names)


def set_ner(items_json):
    """Nomi e indirizzi trovati da GLiNER nel browser per i testi che seguono (None per disattivare)."""
    import clin_llm
    items = json.loads(items_json) if items_json else None
    clin_llm.set_external([(i[0], i[1]) for i in items] if items is not None else None)


def table_text(path):
    """Testo delle celle di un foglio (prime righe), per cercarvi i nomi con GLiNER."""
    from tabular_engine import load_table
    doc = load_table(Path(path), max_rows=200)
    return "\n".join(" ; ".join(str(c) for c in row if c is not None) for s in doc.sheets for row in s.rows)
