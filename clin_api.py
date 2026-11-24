"""
Clin per programmi e agenti su server: pseudonimizzazione, ritorno ai dati reali e controlli, come funzioni
Python e come servizio HTTP locale (`clin servizio`).

Pensato per un agente che lavora da solo su dati ospedalieri (sorveglianza, audit, ricerca), con Claude via
Messages API o Managed Agents: ogni dato che l'agente vede passa da qui, e tutto cio' che uno strumento
restituisce al modello va considerato inviato al fornitore.

  pseudonimizza(testo | HL7 v2 | FHIR | CSV)   -> stesso contenuto con PAZ-0001, ID-0001, date spostate
  pseudonimizza_file(PDF, Word, Excel, foto)   -> file con i dati coperti
  filtra_immagine(screenshot)                  -> stessa immagine, dati coperti (per il computer use)
  ripristina(segnalazione dell'agente)         -> dati reali, solo in locale e con un permesso a parte
  controlla(testo da salvare in memoria)       -> ammesso solo se non contiene dati di pazienti

Ogni uscita verso l'agente viene riletta: se contiene ancora un valore originale noto (un nome, un codice
fiscale gia' visti) viene bloccata. Ogni operazione finisce nel registro (registro.jsonl, senza dati personali).
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import anonymize_engine as ae
import clin
import clin_settings
from clin_text import _Registry, agent_book, anonymize_text

_LOCK = threading.Lock()   # un'operazione alla volta: le tabelle di corrispondenza restano coerenti
MAX_BYTES = 50 * 1024 * 1024
_CODE_RX = re.compile(r"\b(?:PAZ|ID|IDC|MED|OPE|PER|DOC|STR)-\d{4,}\b|\[[A-Z_]+_\d+\]")


class Bloccato(Exception):
    """L'uscita conterrebbe ancora un dato originale: non viene restituita."""


# --------------------------------------------------------------------------- registro e controlli
def _audit(operation: str, payload: bytes | str, **extra: Any) -> None:
    """Una riga per operazione: ora, tipo, dimensione e impronta dell'ingresso. Mai valori."""
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    row = {"ora": _dt.datetime.now().astimezone().isoformat(timespec="seconds"), "operazione": operation,
           "byte": len(data), "impronta": hashlib.sha256(data).hexdigest()[:16], **extra}
    path = clin.MAP_DIR / "registro.jsonl"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _originals() -> List[str]:
    """Valori originali noti (tabelle locali) abbastanza specifici da cercarli in un testo."""
    from clin_results import _tables
    seg, pseudo = _tables()
    values = set()
    # solo cio' che identifica: persone, codici, recapiti, documenti (non cittadinanza, struttura, date)
    keep = [v for k, v in seg.items() if re.match(r"\[?(?:PAZIENTE|PERSONA|MEDICO|OPERATORE|ID|ID_CLINICO|"
                                                   r"CONTATTO|IBAN|DOCUMENTO)_\d+\]?$", k)]
    keep += [v for k, v in pseudo.items() if re.match(r"(?:PAZ|ID|IDC|MED|OPE|PER|DOC)-\d+$", k)]
    keep += [v for k, v in seg.items() if re.match(r"(?:PAZ|ID|IDC|MED|OPE|PER|DOC)-\d+$", k)]
    for v in keep:
        v = " ".join(str(v).split())
        # date e numeri brevi compaiono legittimamente (spostati o clinici): si cercano nomi e codici
        if len(v) >= 4 and re.search(r"[A-Za-zÀ-ÿ]{3,}", v) and not re.fullmatch(r"[\d/.\- :]+", v):
            values.add(v)
    return sorted(values, key=len, reverse=True)


def residui(text: str) -> int:
    """Quanti valori originali noti compaiono ancora nel testo (mai quali)."""
    values = _originals()
    if not values or not text:
        return 0
    found = 0
    low = text.casefold()
    for v in values:
        if v.casefold() in low and re.search(r"(?<![\w])" + re.escape(v) + r"(?![\w])", text, re.I):
            found += 1
    return found


def _check_out(text: str) -> str:
    n = residui(text)
    if n:
        raise Bloccato(f"Uscita bloccata: contiene ancora {n} dati originali noti. Nulla e' stato restituito.")
    return text


def _registry() -> _Registry:
    ae.DATE_SHIFT = clin_settings.date_shift()
    agent_book()   # la tabella dei codici di questa cartella dati
    return _Registry.from_mapping(clin.load_mapping())


# --------------------------------------------------------------------------- operazioni
def pseudonimizza(contenuto: str, nome: str = "", schema: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Testo, messaggio HL7 v2, risorsa FHIR (JSON) o CSV (con `nome` *.csv e, se serve, lo schema delle
    colonne nello stesso formato di clin-colonne.json per quel file)."""
    import clin_sanitario
    with _LOCK:
        reg = _registry()
        kind = clin_sanitario.detect(contenuto)
        if kind:
            _, out = clin_sanitario.anonymize_message(contenuto, reg)
        elif nome.lower().endswith((".csv", ".tsv")):
            kind = "tabella"
            out = _table(contenuto, nome, schema, reg)
        else:
            kind = "testo"
            res = anonymize_text(contenuto, _registry=reg)
            out = res.text
        clin.save_mapping(reg.mapping)
        _check_out(out)
        _audit("pseudonimizza", contenuto, tipo=kind)
        return {"tipo": kind, "contenuto": out}


def _table(contenuto: str, nome: str, schema: Optional[Dict[str, str]], reg: _Registry) -> str:
    from tabular_engine import SCHEMA_FILE, TableSettings, anonymize_table
    with tempfile.TemporaryDirectory(prefix="clin-") as tmp:   # 0700: il CSV in chiaro vive solo qui
        src, dst = Path(tmp) / Path(nome).name, Path(tmp) / "out.csv"
        src.write_text(contenuto, encoding="utf-8")
        if schema:
            (Path(tmp) / SCHEMA_FILE).write_text(json.dumps({Path(nome).name: schema}), encoding="utf-8")
        r = anonymize_table(src, dst, TableSettings(level=10, pseudonyms=agent_book(), keep_labels=True,
                                                    registry=reg, date_shift=ae.DATE_SHIFT))
        if r.error:
            raise ValueError(r.error)
        return dst.read_text(encoding="utf-8-sig")


def pseudonimizza_file(dati: bytes, nome: str) -> Dict[str, Any]:
    """PDF, Word, PowerPoint, Excel, CSV, foto: il file con i dati coperti (base64 nel servizio)."""
    from anonymize_engine import BatchResult, process_batch_files
    from tabular_engine import TableSettings
    if len(dati) > MAX_BYTES:
        raise ValueError("File troppo grande.")
    with _LOCK, tempfile.TemporaryDirectory(prefix="clin-") as tmp:
        reg = _registry()
        src = Path(tmp) / "in" / Path(nome).name
        src.parent.mkdir()
        src.write_bytes(dati)
        done = BatchResult()
        process_batch_files([src], Path(tmp) / "out", sensitivity_level=10, batch_result=done,
                            table_settings=TableSettings(level=10, pseudonyms=agent_book(), keep_labels=True,
                                                         registry=reg, date_shift=ae.DATE_SHIFT))
        clin.save_mapping(reg.mapping)
        r = done.results[0] if done.results else None
        if not r or not r.ok or not r.output_path:
            raise ValueError(getattr(r, "error", None) or "File non elaborato.")
        out = Path(r.output_path).read_bytes()
        _check_out(_text_of(Path(r.output_path)))
        _audit("pseudonimizza_file", dati, tipo=Path(nome).suffix.lower())
        return {"nome": Path(r.output_path).name, "dati": out, "avvisi": list(r.warnings)}


def _text_of(path: Path) -> str:
    """Testo leggibile di un file prodotto, per il controllo dei residui."""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import fitz
            with fitz.open(path) as doc:
                return "\n".join(p.get_text() for p in doc)
        if ext in (".docx", ".pptx"):
            from clin_text import _docx_text, _pptx_text
            return _docx_text(path) if ext == ".docx" else _pptx_text(path)
        if ext in (".xlsx", ".xlsm"):
            from tabular_engine import load_table
            return "\n".join(" ".join(str(c) for c in row if c is not None)
                             for s in load_table(path).sheets for row in s.rows)
        if ext in (".jpg", ".jpeg", ".png"):
            return ""   # immagine: i dati sono coperti sui pixel, non c'e' testo da rileggere
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return ""


def filtra_immagine(dati: bytes, nome: str = "schermata.png") -> bytes:
    """Screenshot o foto -> PNG delle stesse dimensioni con i dati coperti, prima di mandarla a un modello
    (computer use). Le coordinate restano valide: l'agente clicca dove vedrebbe il dato coperto.
    Limite: l'OCR puo' non leggere scritte molto piccole o su sfondi complessi."""
    import fitz
    suffix = Path(nome).suffix.lower() if Path(nome).suffix.lower() in (".png", ".jpg", ".jpeg") else ".png"
    res = pseudonimizza_file(dati, Path(nome).stem + suffix)
    with fitz.open(stream=dati, filetype=suffix.lstrip(".")) as orig, fitz.open(stream=res["dati"], filetype="pdf") as red:
        w = orig[0].rect.width if orig.is_pdf else fitz.Pixmap(dati).width
        page = red[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(w / page.rect.width, w / page.rect.width))
        return pix.tobytes("png")


def ripristina(contenuto: str) -> str:
    """Segnalazione o risultato dell'agente -> dati reali (nomi, codici, date vere). Solo in locale."""
    import clin_results
    with _LOCK:
        clin_results._DAYS = clin_settings.date_shift(create=False)
        seg, pseudo = clin_results._tables()
        out = clin_results.restore(contenuto, seg, pseudo)
        _audit("ripristina", contenuto)
        return out


def controlla(contenuto: str) -> Dict[str, Any]:
    """Per cio' che l'agente vuole conservare (memoria condivisa, regole apprese): ammesso solo se non contiene
    dati personali, valori originali noti o codici di singoli pazienti."""
    motivi = []
    if residui(contenuto):
        motivi.append("contiene dati originali di pazienti")
    if _CODE_RX.search(contenuto):
        motivi.append("contiene codici di singoli pazienti o persone (PAZ-..., [PAZIENTE_n]...)")
    found = {m.category for m in ae.find_matches(contenuto, 10)} - {"Date"}
    if found:
        motivi.append("contiene dati personali: " + ", ".join(sorted(found)))
    _audit("controlla", contenuto, ammesso=not motivi)
    return {"ammesso": not motivi, "motivi": motivi}


# --------------------------------------------------------------------------- servizio HTTP
def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Servizio locale. Due chiavi d'accesso con permessi diversi:
      CLIN_TOKEN_AGENTE      pseudonimizza, filtra_immagine, verifica, controlla, stato
      CLIN_TOKEN_RIPRISTINO  anche ripristina (solo il servizio che manda le segnalazioni al team)
    L'agente riceve solo la prima: non puo' risalire ai dati reali. Le tabelle stanno nella cartella dati di
    questo processo (CLIN_DATI), che l'agente non deve poter leggere (altro utente o altro container)."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    agent_tok = os.environ.get("CLIN_TOKEN_AGENTE", "")
    restore_tok = os.environ.get("CLIN_TOKEN_RIPRISTINO", "")
    if len(agent_tok) < 24 or len(restore_tok) < 24 or agent_tok == restore_tok:
        raise SystemExit("Servono CLIN_TOKEN_AGENTE e CLIN_TOKEN_RIPRISTINO, diversi e di almeno 24 caratteri "
                         "(per esempio: python3 -c 'import secrets; print(secrets.token_urlsafe(32))').")

    class Handler(BaseHTTPRequestHandler):
        server_version = "Clin"

        def _role(self) -> str:
            got = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if got and hmac.compare_digest(got, restore_tok):
                return "ripristino"
            if got and hmac.compare_digest(got, agent_tok):
                return "agente"
            return ""

        def _send(self, code: int, body: Dict[str, Any]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args) -> None:   # niente log con contenuti: c'e' il registro
            pass

        def do_GET(self) -> None:
            if not self._role():
                return self._send(401, {"errore": "chiave d'accesso mancante o errata"})
            if self.path == "/stato":
                return self._send(200, {"stato": "attivo", "date_spostate": bool(clin_settings.date_shift()),
                                        "tabelle_cifrate": bool(os.environ.get("CLIN_CHIAVE"))})
            self._send(404, {"errore": "percorso sconosciuto"})

        def do_POST(self) -> None:
            role = self._role()
            if not role:
                return self._send(401, {"errore": "chiave d'accesso mancante o errata"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if n < 0 or n > MAX_BYTES * 4 // 3 + 4096:
                return self._send(413, {"errore": "richiesta troppo grande"})
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
                path = self.path.rstrip("/")
                if path == "/pseudonimizza":
                    if "file_base64" in body:
                        r = pseudonimizza_file(base64.b64decode(body["file_base64"]), body.get("nome", "file"))
                        r["dati"] = base64.b64encode(r["dati"]).decode()
                        return self._send(200, r)
                    return self._send(200, pseudonimizza(body["contenuto"], body.get("nome", ""), body.get("schema")))
                if path == "/filtra_immagine":
                    png = filtra_immagine(base64.b64decode(body["file_base64"]), body.get("nome", "schermata.png"))
                    return self._send(200, {"png_base64": base64.b64encode(png).decode()})
                if path == "/verifica":   # una copia gia' pseudonimizzata, prima di darla al modello
                    n = residui(body["contenuto"])
                    _audit("verifica", body["contenuto"], residui=n)
                    return self._send(200, {"residui": n, "ammesso": n == 0})
                if path == "/controlla":
                    return self._send(200, controlla(body["contenuto"]))
                if path == "/ripristina":
                    if role != "ripristino":
                        _audit("ripristina_negato", body.get("contenuto", ""))
                        return self._send(403, {"errore": "permesso riservato al servizio di ripristino"})
                    return self._send(200, {"contenuto": ripristina(body["contenuto"])})
                return self._send(404, {"errore": "percorso sconosciuto"})
            except Bloccato as exc:
                return self._send(422, {"errore": str(exc)})
            except (KeyError, ValueError, TypeError) as exc:
                return self._send(400, {"errore": f"richiesta non valida: {type(exc).__name__}"})
            except Exception as exc:   # mai il contenuto nel messaggio d'errore
                return self._send(500, {"errore": f"errore interno: {type(exc).__name__}"})

    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"Clin in ascolto su http://{host}:{port} (dati: {clin.MAP_DIR})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
