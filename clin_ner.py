"""
Clin - riconoscimento rapido di nomi e indirizzi con GLiNER, come servizio locale.

GLiNER (modello multilingue per dati personali) trova nomi e indirizzi senza
etichetta con la stessa accuratezza del modello generativo e circa 14 volte piu'
in fretta. Caricarlo richiede ~10 s: per questo gira come servizio che resta
attivo (si chiude da solo dopo un periodo di inattivita').

* Solo locale: il servizio ascolta su un socket Unix in ~/.clin (cartella 700),
  non su una porta di rete. Nessun altro utente del computer puo' collegarsi.
* Ambiente separato: GLiNER e PyTorch stanno in ~/.clin/ner (circa 2,4 GB con il
  modello), cosi' il Python di sistema resta pulito.

    python3 clin.py ner installa     # crea ~/.clin/ner, installa GLiNER, scarica il modello
    python3 clin_ner.py serve        # avviato in automatico da Clin quando serve
"""

from __future__ import annotations

import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

MODEL = "urchade/gliner_multi_pii-v1"
LABELS = ["person", "address"]
THRESHOLD = 0.5
CHUNK, OVERLAP = 1500, 100
IDLE_SECONDS = 30 * 60


def data_dir() -> Path:
    return Path(os.path.expanduser(os.environ.get("CLIN_DATI") or "~/.clin"))


def socket_path() -> Path:
    p = data_dir() / "ner.sock"
    if len(str(p)) <= 100:
        return p
    # i socket Unix hanno un limite di lunghezza (~104 caratteri su macOS): cartella
    # temporanea privata dell'utente, accettata solo se appartiene all'utente e con permessi 700
    import tempfile
    d = Path(tempfile.gettempdir()) / f"clin-{os.getuid()}"
    d.mkdir(mode=0o700, exist_ok=True)
    st = d.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise OSError(f"cartella {d} non sicura per il servizio GLiNER")
    return d / "ner.sock"


def env_python() -> Path:
    return data_dir() / "ner" / "bin" / "python"


def installed() -> bool:
    return env_python().exists()


# --------------------------------------------------------------------------
# Servizio
# --------------------------------------------------------------------------
def serve() -> None:
    from gliner import GLiNER
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    model = GLiNER.from_pretrained(MODEL)
    last = [time.time()]
    lock = threading.Lock()

    def predict(text: str) -> List[dict]:
        out = []
        for start in range(0, max(1, len(text)), CHUNK):
            chunk = text[start:start + CHUNK + OVERLAP]
            for e in model.predict_entities(chunk, LABELS, threshold=THRESHOLD):
                out.append({"testo": e["text"], "tipo": "PERSONA" if e["label"] == "person" else "INDIRIZZO"})
        return out

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            try:
                req = json.loads(self.rfile.readline() or b"{}")
                with lock:
                    last[0] = time.time()
                    res = {"ok": True} if req.get("ping") else {"entita": predict(str(req.get("testo", "")))}
            except Exception as exc:  # una richiesta malformata non ferma il servizio
                res = {"errore": exc.__class__.__name__}
            self.wfile.write((json.dumps(res, ensure_ascii=False) + "\n").encode())

    path = socket_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    if path.exists():
        path.unlink()
    old = os.umask(0o177)                          # socket leggibile solo dall'utente
    server = socketserver.ThreadingUnixStreamServer(str(path), Handler)
    os.umask(old)

    def watchdog():
        while time.time() - last[0] < IDLE_SECONDS:
            time.sleep(30)
        server.shutdown()
    threading.Thread(target=watchdog, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if path.exists():
            path.unlink()


# --------------------------------------------------------------------------
# Client (usato da clin_llm)
# --------------------------------------------------------------------------
def _ask(payload: dict, timeout: float) -> Optional[dict]:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(socket_path()))
        s.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            part = s.recv(65536)
            if not part:
                break
            buf += part
        return json.loads(buf or b"{}")
    except (OSError, ValueError):
        return None
    finally:
        s.close()


_failed = [False]


def ensure_running(wait: float = 60) -> bool:
    """Avvia il servizio se non risponde; True quando e' pronto."""
    if not installed() or _failed[0]:
        return False
    if _ask({"ping": True}, 2):
        return True
    log = open(data_dir() / "ner.log", "ab")
    subprocess.Popen([str(env_python()), str(Path(__file__).resolve()), "serve"],
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                     env={**os.environ, "HF_HUB_DISABLE_TELEMETRY": "1"})
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.5)
        if _ask({"ping": True}, 2):
            return True
    _failed[0] = True            # niente nuove attese in questo processo: si ripiega su Ollama
    return False


def entities(text: str) -> Optional[List[Tuple[str, str]]]:
    """(valore, tipo) trovati da GLiNER, oppure None se il servizio non e' disponibile."""
    if not ensure_running():
        return None
    res = _ask({"testo": text}, 120)
    if not res or "entita" not in res:
        return None
    return [(e["testo"], e["tipo"]) for e in res["entita"]]


# --------------------------------------------------------------------------
# Installazione dell'ambiente separato
# --------------------------------------------------------------------------
def install(python: str = sys.executable) -> str:
    env = data_dir() / "ner"
    data_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
    if not env_python().exists():
        subprocess.run([python, "-m", "venv", str(env)], check=True)
    subprocess.run([str(env_python()), "-m", "pip", "install", "-q", "--disable-pip-version-check", "gliner", "protobuf"],
                   check=True)
    # primo avvio: scarica il modello (una volta sola) e verifica che risponda
    if not ensure_running(wait=900):
        raise RuntimeError(f"Il servizio GLiNER non si e' avviato: vedere {data_dir() / 'ner.log'}")
    test = entities("Riferisce la figlia Giulia Ferri, residente in Via Roma 12.")
    return f"GLiNER installato in {env}. Prova: {test}"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        serve()
    elif len(sys.argv) > 1 and sys.argv[1] == "installa":
        print(install())
    else:
        print(__doc__)
