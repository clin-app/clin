"""
Esempio: gli strumenti di un agente di sorveglianza (es. appropriatezza dell'antibioticoterapia) che lavora
con Clin. Valgono per il ciclo dell'agente sulla Messages API e per gli strumenti personalizzati del worker
self-hosted dei Managed Agents: in entrambi i casi l'agente puo' usare SOLO questi strumenti (niente bash,
niente lettura libera di file, niente ricerca web), e cio' che restituiscono e' tutto cio' che il modello vede.

Regole che questo file rispetta:
  - si legge solo da /dati_anon (copie gia' pseudonimizzate da `clin copie --uscita /dati_anon`);
  - ogni testo restituito al modello viene prima verificato da Clin (/verifica): se contiene ancora un dato
    originale noto (un export con un campo nuovo, un nome sfuggito) non viene restituito;
  - le segnalazioni restano pseudonimizzate: il ritorno ai dati reali lo fa un servizio separato
    (esempio_notifiche.py) che ha l'altra chiave d'accesso;
  - cio' che l'agente vuole ricordare tra una sessione e l'altra passa da /controlla: solo regole, mai casi.
"""
import json
import os
import urllib.request
from pathlib import Path

CLIN_URL = os.environ.get("CLIN_URL", "http://clin:8765")
CLIN_TOKEN = os.environ["CLIN_TOKEN"]            # CLIN_TOKEN_AGENTE: non puo' ripristinare i dati reali
ANON = Path("/dati_anon")
SEGNALAZIONI = ANON / "segnalazioni"
REGOLE = ANON / "regole_apprese.md"


def _clin(path: str, body: dict) -> dict:
    req = urllib.request.Request(CLIN_URL + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {CLIN_TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def leggi_documento(nome: str) -> str:
    """Testo di una copia pseudonimizzata (terapie, microbiologia, laboratorio, referti)."""
    path = (ANON / nome).resolve()
    if not path.is_relative_to(ANON) or not path.is_file():
        return "Documento non trovato tra le copie pseudonimizzate."
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    if not _clin("/verifica", {"contenuto": raw})["ammesso"]:
        return "Documento trattenuto: contiene ancora dati identificativi. Segnalato al responsabile di Clin."
    return raw


def elenca_documenti() -> str:
    return "\n".join(str(p.relative_to(ANON)) for p in sorted(ANON.rglob("*"))
                     if p.is_file() and "segnalazioni" not in p.parts and not p.name.startswith("."))


def segnala(paziente: str, farmaco: str, regola: str, motivazione: str, priorita: str) -> str:
    """Una segnalazione per il team di infettivologia, con i codici dei documenti (PAZ-0001, IDC-0003)."""
    SEGNALAZIONI.mkdir(parents=True, exist_ok=True)
    n = len(list(SEGNALAZIONI.glob("*.json"))) + 1
    (SEGNALAZIONI / f"{n:05d}.json").write_text(json.dumps(
        {"paziente": paziente, "farmaco": farmaco, "regola": regola, "motivazione": motivazione,
         "priorita": priorita}, ensure_ascii=False), encoding="utf-8")
    return f"Segnalazione {n} registrata."


def ricorda_regola(testo: str) -> str:
    """Regola affinata dopo un falso positivo: conservata solo se non contiene dati di pazienti."""
    esito = _clin("/controlla", {"contenuto": testo})
    if not esito["ammesso"]:
        return "Non salvata: " + "; ".join(esito["motivi"]) + ". Riformulare come regola generale."
    with REGOLE.open("a", encoding="utf-8") as fh:
        fh.write("- " + testo.strip() + "\n")
    return "Regola salvata."


# Definizioni nel formato standard degli strumenti di Claude (name, description, input_schema)
STRUMENTI = [
    {"name": "elenca_documenti", "description": "Elenca le copie pseudonimizzate disponibili.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "leggi_documento", "description": "Legge una copia pseudonimizzata. I pazienti sono PAZ-0001..., "
     "le date sono spostate di 400 anni: intervalli e giorni di terapia sono veri.",
     "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}}, "required": ["nome"]}},
    {"name": "segnala", "description": "Registra una possibile inappropriatezza per il team di infettivologia.",
     "input_schema": {"type": "object", "required": ["paziente", "farmaco", "regola", "motivazione", "priorita"],
                      "properties": {"paziente": {"type": "string", "description": "codice PAZ dai documenti"},
                                     "farmaco": {"type": "string"}, "regola": {"type": "string"},
                                     "motivazione": {"type": "string"},
                                     "priorita": {"type": "string", "enum": ["alta", "media", "bassa"]}}}},
    {"name": "ricorda_regola", "description": "Salva una regola generale appresa (mai dati di singoli casi).",
     "input_schema": {"type": "object", "properties": {"testo": {"type": "string"}}, "required": ["testo"]}},
]
ESEGUI = {"elenca_documenti": elenca_documenti, "leggi_documento": leggi_documento, "segnala": segnala,
          "ricorda_regola": ricorda_regola}
