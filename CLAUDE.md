# Clin: istruzioni per chi modifica il progetto

## La documentazione si aggiorna insieme al codice

Ogni modifica al funzionamento (nuova funzione, correzione che cambia un comportamento, nuovo comando, nuovo
formato, nuova opzione, cambio di versione) si chiude solo quando tutte le descrizioni sono allineate, nello
stesso lavoro e senza che qualcuno lo chieda:

| Dove | Per chi | Tono |
|---|---|---|
| `docs/index.html` (homepage) | medici, ricercatori, chi decide | semplice, niente dettagli tecnici; ordine: come funziona, cosa toglie, dove si usa, casi, ricerca, agenti in clinica, sicurezza, installazione |
| `docs/guida.html` (guida tecnica, «Per gli addetti ai lavori») | IT, DPO, sviluppatori | tecnico, preciso, con tabelle; un capitolo per argomento, versione in testa |
| `deploy/README.md` | IT dell'ospedale | servizio, API, Docker, Managed Agents |
| `README.md` | chi apre il repository | panoramica e rimandi |
| `integrations/claude-code/PLUGIN.md`, testo della Skill (`clin.skill_text`) | utenti del plugin e agenti | come si usa |
| note dell'estensione e dell'app web | utenti del browser | come si usa |

Prima di chiudere:

```bash
python3 -m unittest tests.test_documentazione   # versione, comandi, API, ruoli, formati, HL7, collegamenti
python3 -m unittest discover -s tests           # tutto il resto
```

Il primo gira anche su GitHub a ogni push (`.github/workflows/documentazione.yml`). Se un controllo manca per la
cosa cambiata, aggiungerlo a `tests/test_documentazione.py`. Dopo una modifica al sito, guardarlo nel browser
(computer e telefono).

## Regole di contenuto

- Ogni sezione della homepage finisce con il pulsante «Approfondisci» verso il capitolo della guida che la
  spiega (nuova scheda): una sezione nuova lo riceve, e se il capitolo manca lo si scrive.
- Sul sito pubblico non spiegare i tecnicismi delle date (di quanto vengono spostate): basta dire che i calcoli
  clinici restano giusti.
- Niente nomi o dati personali degli autori in file, commit o release pubblici; i commit pubblici hanno autore
  e committer «Clin <clin-app@users.noreply.github.com>».
- Le release le pubblica il flusso `.github/workflows/release.yml` quando cambia `version` in
  `extension/manifest.json`; il ramo `plugin` lo aggiorna `.github/workflows/plugin.yml`.
- Dati di prova sempre inventati; mai documenti reali di pazienti nei test, negli esempi o negli screenshot.
