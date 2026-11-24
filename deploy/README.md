# Clin per agenti su server

Clin come filtro di un agente che lavora da solo su dati ospedalieri: sorveglianza dell'antibioticoterapia,
audit, registri di ricerca. Vale con il ciclo dell'agente sulla Messages API (anche via Bedrock o Vertex in
regione UE) e con i Claude Managed Agents in ambiente self-hosted.

Principio: **tutto ciò che il modello legge è già passato da Clin**. Uno strumento che restituisce un testo
al modello lo sta inviando al fornitore; per questo Clin sta prima di ogni strumento, e la tabella che
riconduce ai dati reali non esce mai dalla rete dell'ospedale.

```text
RETE OSPEDALIERA                                                        FORNITORE DEL MODELLO
Gestionale ──export──▶ /export_raw (solo container clin, sola lettura)
                           │
                     clin copie --uscita /dati_anon      (job notturno o a evento)
                           │   tabelle di corrispondenza + registro: volume dati_clin, cifrato
                           ▼
                       /dati_anon ◀── worker dell'agente (solo strumenti personalizzati) ◀──▶ Claude
                           │              │  /verifica  /controlla      (CLIN_TOKEN_AGENTE)
                           │              ▼
                    segnalazioni PAZ-0001 ──▶ servizio notifiche ── /ripristina (CLIN_TOKEN_RIPRISTINO)
                                                        └──▶ team di infettivologia, con nomi e letti veri
```

## Avvio

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'   # due volte: chiave agente e chiave ripristino
python3 clin.py chiave                                          # chiave di cifratura delle tabelle
```

Nel file `.env` (permessi 600, fuori dal repository): `CLIN_TOKEN_AGENTE`, `CLIN_TOKEN_RIPRISTINO`,
`CLIN_CHIAVE`, `EXPORT_RAW` (cartella degli export), `IMMAGINE_AGENTE`. Poi:

```bash
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml exec clin python clin.py copie /export_raw --uscita /dati_anon
```

Il secondo comando va pianificato (es. ogni mattina alle 6:30, e a ogni nuovo export di microbiologia):
rielabora solo i file nuovi o cambiati.

Senza Docker: `CLIN_DATI=/percorso/dati CLIN_TOKEN_AGENTE=… CLIN_TOKEN_RIPRISTINO=… python3 clin.py servizio`,
con un utente di sistema dedicato proprietario di `CLIN_DATI`, diverso da quello dell'agente.

## Cosa arriva all'agente

| Dato | Diventa |
|---|---|
| Paziente (nome, cognome, in qualsiasi ordine e documento) | `PAZ-0001`, **lo stesso** in referti, export, HL7 e FHIR |
| Codice fiscale | `ID-0001` |
| Nosologico, cartella, MRN, stanza e letto | `IDC-0001` |
| Medici, operatori, familiari | `MED-0001`, `OPE-0001`, `PER-0001` / `[PERSONA_1]` |
| Date (nascita, ricovero, prelievi, terapie, anche «dal 01/11») | stessa data **400 anni dopo**: intervalli, giorni di terapia ed età esatti |
| Telefoni, indirizzi, email, documenti | eliminati o `[CONTATTO_1]` |
| Farmaci, dosi, vie, germi, MIC, S/I/R, esami, valori, ATC, LOINC, reparto | invariati |

Ripassare una copia da Clin non la cambia: codici, segnaposto e date già spostate restano identici.

## API (servizio HTTP, JSON)

Tutte le richieste con `Authorization: Bearer <chiave>`.

| Percorso | Chiave | Corpo | Risposta |
|---|---|---|---|
| `POST /pseudonimizza` | agente | `{"contenuto": "...", "nome": "terapie.csv", "schema": {...}}` (testo, HL7 v2, FHIR, CSV) | `{"tipo", "contenuto"}` |
| `POST /pseudonimizza` | agente | `{"file_base64": "...", "nome": "referto.pdf"}` (PDF, Word, PowerPoint, Excel, foto) | `{"nome", "dati", "avvisi"}` |
| `POST /filtra_immagine` | agente | `{"file_base64": "...", "nome": "schermata.png"}` | `{"png_base64"}`, stesse dimensioni |
| `POST /verifica` | agente | `{"contenuto": "..."}` | `{"residui", "ammesso"}` |
| `POST /controlla` | agente | `{"contenuto": "..."}` | `{"ammesso", "motivi"}` |
| `POST /ripristina` | **ripristino** | `{"contenuto": "..."}` | `{"contenuto"}` con i dati reali |
| `GET /stato` | entrambe | | stato del servizio |

Ogni uscita verso l'agente viene riletta: se contiene ancora un dato originale noto (nome, codice fiscale,
recapito già visti) la risposta è `422` e il contenuto non viene restituito. Con la chiave dell'agente
`/ripristina` risponde `403`, e il tentativo resta nel registro.

Le stesse operazioni sono funzioni Python in `clin_api.py` (`pseudonimizza`, `pseudonimizza_file`,
`filtra_immagine`, `ripristina`, `controlla`, `residui`) e comandi: `clin pseudonimizza FILE|-`,
`clin immagine IN OUT.png`, `clin verifica CARTELLA`.

## Schema delle colonne degli export

Per gli export ripetuti il ruolo di ogni colonna si dichiara una volta, in `clin-colonne.json` nella
cartella degli export (o passato come `schema` all'API), invece di farlo dedurre dall'intestazione:

```json
{
  "terapie_*.csv": {
    "cognome": "paziente", "nome": "paziente", "codice fiscale": "id", "nosologico": "id_clinico",
    "data_nascita": "data_nascita", "reparto": "clinico", "letto": "id_clinico",
    "farmaco": "clinico", "dose": "clinico", "via": "clinico", "data_inizio": "data",
    "note": "testo", "*": "elimina"
  }
}
```

Ruoli: `paziente`, `id`, `id_clinico`, `medico`, `operatore`, `persona`, `data_nascita`, `data`, `contatto`,
`clinico` (non toccare), `testo` (analizzato cella per cella), `elimina` (il contenuto non esce).
`"*": "elimina"` fa uscire solo le colonne elencate: minimizzazione per costruzione. Un ruolo scritto male
blocca il file invece di lasciarlo passare.

## HL7 v2 e FHIR

Trattati campo per campo con regole fisse (`clin_sanitario.py`): PID, NK1, PV1, ORC, OBR, OBX, RXE, RXA,
SPM, NTE...; risorse Patient, Practitioner, RelatedPerson e riferimenti tra risorse. Dei segmenti anagrafici
restano solo i campi necessari; i campi di testo libero (NTE, OBX testuali, narrativa FHIR, note) passano dal
motore dei testi; i segmenti sconosciuti (anche Z) vengono analizzati per intero; gli allegati base64 dentro
FHIR vengono tolti. Le date in qualsiasi campo, anche dentro le componenti (inizio terapia in RXE-1), sono
spostate.

## Con i Claude Managed Agents (ambiente self-hosted)

- **Clin non va collegato come server MCP dell'agente**: nei Managed Agents i server MCP sono URL chiamati
  dall'infrastruttura del fornitore, e la tabella di corrispondenza deve restare in locale.
- **Gli strumenti del worker sono personalizzati e pochi** (vedi `esempio_strumenti.py`): leggere le copie in
  `/dati_anon` dopo `/verifica`, registrare una segnalazione, salvare una regola. Niente bash, niente
  lettura libera di file, niente web_search o web_fetch.
- **Memoria condivisa**: ogni regola appresa passa da `/controlla`, che la rifiuta se contiene nomi, codici
  di pazienti (`PAZ-0001`) o altri dati personali. Nella memoria vanno solo regole generali.
- **Il ritorno ai dati reali** lo fa un servizio separato con la chiave di ripristino
  (`esempio_notifiche.py`): l'agente, con la sua chiave, non può farlo.
- **Lo stesso nucleo** (Clin, schema, strumenti) serve anche il ciclo su Messages API: passare da un'architettura
  all'altra cambia solo chi gestisce il ciclo dell'agente.

## Protezioni e limiti

- Tabelle di corrispondenza cifrate con `CLIN_CHIAVE` (Fernet). Senza la chiave Clin si ferma con un errore:
  non riparte mai con una tabella vuota che sovrascriverebbe quella esistente.
- Registro `registro.jsonl` nella cartella dati: ora, operazione, dimensione e impronta dell'ingresso, esito.
  Nessun dato personale.
- `clin verifica` rilegge le copie e conta i dati originali noti ancora presenti, senza mostrarli: utile come
  prova da allegare alla DPIA.
- Lo screenshot filtrato (`/filtra_immagine`) dipende dall'OCR: scritte minuscole o su sfondi complessi possono
  sfuggire. Per il gestionale la via robusta restano gli export (o HL7/FHIR), non lo schermo.
- Il controllo in uscita trova solo i dati già visti da Clin: un nome mai comparso in nessun documento si
  riconosce dalle regole e dal modello locale, non dal confronto.
- I dati pseudonimizzati restano dati personali (GDPR, considerando 26): servono comunque DPIA, base giuridica
  e accordo con il fornitore del modello.
