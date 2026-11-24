"""
Esempio: il servizio che porta le segnalazioni dell'agente al team, con i dati reali. Gira nella rete
dell'ospedale, separato dall'agente, ed e' l'unico ad avere CLIN_TOKEN_RIPRISTINO. Ogni ritorno ai dati
reali resta nel registro di Clin.

    CLIN_URL=http://clin:8765 CLIN_TOKEN=<CLIN_TOKEN_RIPRISTINO> python3 esempio_notifiche.py
"""
import json
import os
import urllib.request
from pathlib import Path

CLIN_URL = os.environ.get("CLIN_URL", "http://clin:8765")
CLIN_TOKEN = os.environ["CLIN_TOKEN"]
CODA = Path(os.environ.get("CODA", "/dati_anon/segnalazioni"))


def ripristina(testo: str) -> str:
    req = urllib.request.Request(CLIN_URL + "/ripristina", data=json.dumps({"contenuto": testo}).encode(),
                                 method="POST", headers={"Authorization": f"Bearer {CLIN_TOKEN}",
                                                         "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["contenuto"]


def invia_al_team(segnalazione: dict) -> None:
    # da sostituire con la posta interna, Teams o la dashboard del reparto (sempre nella rete dell'ospedale)
    print(json.dumps(segnalazione, ensure_ascii=False, indent=2))


for f in sorted(CODA.glob("*.json")):
    reale = json.loads(ripristina(f.read_text(encoding="utf-8")))
    invia_al_team(reale)
    f.rename(f.with_suffix(".inviata"))   # la copia pseudonimizzata resta per l'audit e le eval
