<p align="center"><img src="assets/logo.svg" width="88" alt="Clin"></p>

<h1 align="center">Clin</h1>
<p align="center"><b>Clinical Data Anonymizer for AI</b><br>
Anonimizzazione locale di documenti sanitari prima dell'uso con l'intelligenza artificiale.</p>

---

## A cosa serve

Referti, lettere di dimissione, cartelle cliniche ed estrazioni di dati contengono
nomi, codici fiscali, date di nascita e recapiti dei pazienti. Quando questi
documenti vengono incollati in Claude, ChatGPT o in un altro assistente, i dati
raggiungono i server del fornitore.

Clin elimina i dati identificativi **in locale, prima dell'invio**.
All'IA arriva un testo come questo:

```text
Paziente: [PAZIENTE_1], nato il [DATA_NASCITA_1], CF [ID_1].
[PAZIENTE_1] riferisce febbre da 3 giorni. Visitato dal Dott. [MEDICO_1].
Emoglobina 13,5 g/dL, PCR 0,45 mg/dL.
```

Il contenuto clinico resta leggibile; i segnaposto sono stabili (la stessa persona
ha sempre lo stesso segnaposto, anche in documenti diversi della stessa sessione).
La tabella che collega i segnaposto ai dati originali resta in locale.

## Avvio rapido

```bash
git clone https://github.com/clin-app/clin.git && cd clin
python3 -m pip install -r requirements.txt
python3 clin.py ner installa  # facoltativo, consigliato: nomi senza etichetta (GLiNER)
python3 clin.py installa      # una volta: collega Clin a Claude Code
```

Poi si apre Claude Code (terminale, IDE o scheda Code di Claude Desktop) nella
cartella dei dati e si scrive `/clin`. Clin protegge la cartella, crea copie
anonime di Excel, CSV e PDF in `Clin_anonimizzati/` e Claude lavora solo su
quelle. Per i dettagli: «Guardia automatica per agenti».

Senza riga di comando: `python3 clin.py` apre l'applicazione grafica.

## Modi d'uso

| Modo | Per chi | Cosa riceve l'IA |
|---|---|---|
| **Applicazione** | Chi deve condividere file | PDF con oscuramento irreversibile, Excel e CSV con pseudonimi |
| **Collegamento MCP** | Chat di Claude Desktop, Cursor e altri client MCP | Solo il testo anonimizzato del file indicato |
| **Modalità appunti** | ChatGPT, Gemini, Copilot e qualunque chat nel browser | Il testo copiato, già anonimizzato al momento dell'incolla |
| **Guardia per agenti** | Claude Code, Codex, Antigravity su cartelle di dati (`/clin`) | Solo copie anonime: gli originali vengono intercettati dagli hook |
| **Telefono** | iPhone e Android, con qualunque app di IA | Foto con riquadri neri e testo con segnaposto, prodotti sul telefono |

---

## Sul telefono

Clin funziona anche come **app web installabile** su iPhone e Android. Tutta
l'elaborazione avviene nel browser del telefono: lo stesso motore Python di Clin
(eseguito con Pyodide), l'OCR delle foto (Tesseract.js) e la lettura dei PDF
(pdf.js) sono ospitati insieme all'app. Il browser riceve una regola di
sicurezza (`Content-Security-Policy: connect-src 'self'`) che **impedisce
qualunque connessione verso altri siti**: i dati non possono lasciare il
telefono. Dopo il primo avvio l'app funziona anche senza rete.

| Contenuto | Cosa fa Clin sul telefono |
|---|---|
| Foto di un referto, di una ricetta, di una cartella | Legge il testo (OCR), copre con riquadri neri nomi, CF, date di nascita, medici e ogni sequenza che somiglia a un codice (l'OCR può deformare un CF); produce una nuova immagine senza metadati (posizione GPS, dispositivo) e il testo con segnaposto |
| PDF | Estrae il testo di tutte le pagine e lo restituisce con segnaposto |
| Word (.docx), CSV, TXT | Testo con segnaposto; nei CSV le colonne identificative sono riconosciute dall'intestazione |
| Audio | La registrazione va trascritta con il telefono (iPhone: Note vocali o dettatura; Android: Registratore); la trascrizione si incolla in Clin |
| Testo copiato | «Incolla dagli appunti» → «Anonimizza» |

Ogni parola dell'immagine si può oscurare o scoprire con un tocco, prima di
condividerla.

**Indirizzo: https://clin-app.github.io/app/**

### Installazione sul telefono

1. Aprire l'indirizzo nel browser (Safari su iPhone, Chrome su Android).
2. iPhone: Condividi → «Aggiungi alla schermata Home». Android: menu → «Installa app».
3. Al primo avvio vengono scaricati circa 25 MB (motore e OCR), poi l'app lavora offline.

### Dal menu Condividi

- **Android:** dopo l'installazione Clin compare tra le app del menu Condividi
  (foto, PDF, testo): basta scegliere Clin dalla Galleria, da File o da WhatsApp.
- **iPhone:** iOS non permette alle app web di ricevere file dal menu
  Condividi. Per foto e PDF si apre Clin e si sceglie il file (libreria foto,
  fotocamera o File). Per il testo si può creare un Comando Rapido:
  1. app **Comandi Rapidi** → «+» → nome «Clin»;
  2. impostazioni del comando → «Mostra nel foglio di condivisione», tipi:
     Immagini, PDF, Testo;
  3. azioni: «Estrai testo da Input comando rapido» (lettura sul telefono),
     «Copia negli appunti», «Apri URL» con l'indirizzo di Clin;
  4. in Clin: «Incolla dagli appunti» → «Anonimizza».

### Pubblicazione dell'app web

```bash
python3 web/build.py
```

Il comando crea `web/dist` (circa 25 MB) e verifica ogni libreria con SHA-256.
La cartella si pubblica su un qualunque hosting statico con HTTPS (GitHub Pages,
Vercel, Netlify, server interno della struttura). L'hosting serve solo file
statici: non riceve i documenti, che restano nel telefono.

La versione pubblica è nel repository
[clin-app/app](https://github.com/clin-app/app) (solo l'app
compilata, servita da GitHub Pages). Per aggiornarla dopo una modifica:

```bash
python3 web/build.py
git clone https://github.com/clin-app/app.git /tmp/clin-app
rsync -a --delete --exclude .git --exclude README.md web/dist/ /tmp/clin-app/
git -C /tmp/clin-app add -A && git -C /tmp/clin-app commit -m "Aggiornamento" && git -C /tmp/clin-app push
```

Al successivo avvio i telefoni scaricano la nuova versione e la conservano per
l'uso offline.

---

## Estensione per ChatGPT, Claude e Gemini

Per chi usa le chat IA nel browser (per esempio sul PC del reparto), l'estensione
**Clin per Chrome ed Edge** lavora direttamente nella pagina della chat:

- testo incollato, file trascinati e file scelti con la graffetta vengono fermati
  **prima** che il sito li riceva, anonimizzati sul computer e inseriti nel campo
  della chat come testo con segnaposto (PDF, Word, TXT, CSV e foto con OCR);
- la pillola **/Clin attivo** in basso a destra apre il pannello: l'ultima risposta
  dell'IA (o il testo selezionato) con i dati reali, e «Copia con i dati reali»;
- il pannello è in uno shadow DOM chiuso: il sito della chat non può leggere i nomi
  ripristinati. La tabella dei segnaposto sta in `chrome.storage.session` (solo in
  memoria, cancellata alla chiusura del browser);
- l'IA riceve **i file stessi** con i dati coperti: PDF ridisegnati con riquadri che
  riportano il segnaposto (più un livello di testo invisibile già anonimizzato),
  foto senza EXIF, Word con i segnaposto, Excel e CSV con pseudonimi per colonna;
- i nomi senza etichetta («Elira Shehu, 45enne, giunge in PS…») li trova **GLiNER**,
  lo stesso modello del servizio locale su computer, esportato in ONNX
  (`tools/export_gliner_onnx.py`, 581 MB: compressa solo la tabella dei vocaboli,
  risultati identici al modello originale nel 99,6% dei casi) ed eseguito con
  onnxruntime-web. Sul benchmark nel browser: recall 1,000, nessun termine clinico
  coperto (1000/1000), circa 2 s per documento;
- nessuna richiesta di rete: motore (Pyodide, pdf.js, Tesseract, GLiNER) dentro
  l'estensione (`connect-src 'self'`).

Siti: chatgpt.com, claude.ai, gemini.google.com, copilot.microsoft.com, chat.mistral.ai.

```bash
python3 web/build.py && python3 extension/build.py   # extension/dist e extension/clin-estensione.zip
```

Per provarla: Chrome › Estensioni › Modalità sviluppatore › «Carica estensione non
pacchettizzata» › `extension/dist`. Per l'installazione con un clic va pubblicata sul
Chrome Web Store (e sul sito dei componenti aggiuntivi di Edge) con
`clin-estensione.zip`. Dove le estensioni non sono consentite si usa l'app nel
browser: https://clin-app.github.io/app/

## Installazione

Requisiti: Python 3.10 o successivo.

```bash
git clone https://github.com/clin-app/clin.git
cd clin
python3 -m pip install -r requirements.txt
```

Facoltativo: OCR per i PDF scansionati e le immagini JPG/PNG. Lo script
scarica una sola volta il modello italiano di Tesseract (circa 2,6 MB,
`tessdata_fast` a un commit fisso) e ne verifica l'impronta SHA-256:

```bash
python3 scripts/fetch_ocr_model.py
```

Il motore Tesseract è già incluso in PyMuPDF, quindi non servono altri
pacchetti. Dopo il download l'OCR funziona senza rete. Senza il modello Clin
funziona come prima e si limita a segnalare le pagine senza testo.

Avvio dell'applicazione:

```bash
python3 clin.py
```

Su macOS è possibile creare **Clin.app** sulla Scrivania, con la propria icona:

```bash
python3 build_app.py
```

L'app usa l'interprete Python installato e i file di questa cartella: se la
cartella viene spostata, il comando va rieseguito.

**Riconoscimento contestuale (consigliato).** Per trovare anche i nomi senza
etichetta, Clin usa un modello eseguito in locale. Il motore predefinito è
[GLiNER](https://github.com/urchade/GLiNER) (`urchade/gliner_multi_pii-v1`,
multilingue, specializzato in dati personali):

```bash
python3 clin.py ner installa   # crea ~/.clin/ner (circa 2,4 GB con PyTorch e il modello)
python3 clin.py ner stato
```

GLiNER sta in un ambiente Python separato e gira come servizio locale su un
socket Unix leggibile solo dall'utente (nessuna porta di rete): si avvia da solo
quando serve e si chiude dopo 30 minuti di inattività.

In alternativa Clin usa un modello linguistico con [Ollama](https://ollama.com)
(`ollama pull gemma4:e4b`; anche `qwen3:4b`, `gemma4:12b`, `qwen2.5:7b`), più
lento. Il server deve essere locale (`127.0.0.1`): un indirizzo remoto viene
rifiutato. L'impostazione `motore` sceglie tra `auto` (GLiNER se installato,
altrimenti Ollama), `gliner` e `ollama`. Senza nessuno dei due Clin funziona
con le sole regole. Variabili: `CLIN_LLM=0` per disattivare il riconoscimento
contestuale, `CLIN_LLM_MODEL` per scegliere il modello Ollama.

---

## Uso con l'intelligenza artificiale

### Claude Desktop

```bash
python3 clin.py collega claude-desktop
```

Il comando aggiunge Clin ai server MCP di Claude Desktop e salva una copia della
configurazione precedente (`claude_desktop_config.json.bak`). Dopo il riavvio di
Claude Desktop è sufficiente indicare il file:

> Riassumi la lettera di dimissione in ~/Documenti/Referti/dimissione_0412.pdf

Claude chiama lo strumento `anonimizza_documento`; Clin apre il file in locale e
restituisce soltanto il testo con i segnaposto.

Nella chat di Claude Desktop non esiste il comando `/clin` (è della scheda
Code) né la guardia: Claude usa lo strumento MCP quando gli si indica un file.

### Claude Code

```bash
python3 clin.py installa
```

Registra il server MCP per l'utente, installa la skill `/clin` e la guardia
dormiente (vedi sotto). Per un singolo documento, anche senza Claude:

```bash
python3 clin.py testo referto.pdf
```

### ChatGPT, Gemini e altre chat nel browser

Queste chat non possono avviare programmi in locale, quindi Clin interviene
sugli appunti:

1. selezionare e copiare il testo del documento (Cmd+C);
2. eseguire `python3 clin.py appunti`, oppure dal menu **IA** dell'applicazione
   (Cmd+Shift+A);
3. incollare nella chat: il testo è già anonimizzato;
4. per rileggere la risposta con i dati reali, copiarla ed eseguire
   `python3 clin.py ripristina` (Cmd+Shift+R). Il ripristino avviene solo in
   locale e tollera le varianti prodotte dagli LLM (grassetto,
   spazi, parentesi omesse); un segnaposto con indice inesistente resta
   visibile, anziché essere attribuito al paziente sbagliato.

Per una scorciatoia di sistema su macOS: app **Comandi Rapidi** → nuovo comando
rapido → azione «Esegui script shell» con `python3 /percorso/clin/clin.py appunti`
→ assegnare una combinazione di tasti nelle impostazioni del comando.

`python3 clin.py dimentica` cancella la tabella dei segnaposto (e le copie di
lettura della guardia, che la usano).

### Guardia automatica per agenti: Claude Code, Codex, Antigravity

Si installa una volta:

```bash
python3 clin.py installa                  # Claude Code (anche nella scheda Code di Claude Desktop)
python3 clin.py installa --agente tutti   # anche Codex e Antigravity
```

La guardia resta **dormiente**: gli altri progetti non cambiano (unica modifica
globale: i file citati con `@` vengono letti con lo strumento Read, così passano
dalla guardia). Quando serve,
si apre Claude Code nella cartella dei dati (Excel, CSV, PDF, referti) e si scrive:

```text
/clin
```

Clin attiva la protezione su quella cartella (subito, senza riavvio), crea le copie anonime in
`Clin_anonimizzati/` e l'agente lavora solo su quelle. Negli Excel e nei CSV
ogni paziente diventa uno pseudonimo (`PAZ-0001`), **lo stesso in tutti i
file e in tutte le sessioni**: i fogli restano collegabili per merge e
statistiche. La tabella pseudonimi resta in `~/.clin/pseudonimi.json` (permessi 600).

**Risultati con i dati reali.** Al termine di ogni risposta dell'agente, i file
che ha prodotto con segnaposto o pseudonimi (CSV, Excel, testo, Markdown,
JSON, HTML) vengono copiati con i dati reali in `Clin_risultati/`, o nella
cartella indicata nelle impostazioni, anche fuori dal progetto. I file hanno
permessi 600; l'agente non può leggere, cercare né elencare quella cartella, e
se uno script stampa un dato reale già noto l'output torna ai segnaposto. Il
ripristino manuale: `/clin ripristina` oppure `python3 clin.py risultati [cartella]`.

**Impostazioni.** Nell'applicazione (menu IA › Agenti IA) oppure da terminale:

```bash
python3 clin.py impostazioni                                  # elenco e valori
python3 clin.py impostazioni cartella_risultati ~/Ricerca/Risultati_TAVI
python3 clin.py impostazioni ripristino_automatico no
```

| Impostazione | Predefinito | Effetto |
|---|---|---|
| `ripristino_automatico` | si | Risultati ricondotti ai dati reali a fine risposta |
| `cartella_risultati` | `Clin_risultati` | Nome dentro la cartella protetta o percorso assoluto |
| `blocca_messaggi` | si | Messaggi con dati personali fermati prima dell'invio |
| `ripulisci_output` | si | Output dei comandi ripulito (Claude Code) |
| `modello_locale` | si | Modello locale per i nomi senza etichetta |
| `motore` | `auto` | `auto` (GLiNER se installato, altrimenti Ollama), `gliner` o `ollama` |
| `categorie_escluse` | nessuna | Categorie lasciate in chiaro (controllo manuale), es. `"Date, Struttura sanitaria"`; elenco con `clin.py impostazioni categorie` |
| `colonne_dal_contenuto` | si | Colonne di nominativi riconosciute dal contenuto, non solo dall'intestazione |
| `ocr` | si | OCR di scansioni e immagini |

`/clin off` la disattiva. Nella cartella attiva la guardia lavora con gli hook
dell'agente, quindi anche se il modello non segue le istruzioni:

| Cosa fa l'agente | Claude Code | Codex | Antigravity |
|---|---|---|---|
| Legge un documento (Read / view_file) | Legge la copia anonimizzata | Nessuno strumento di lettura documentato: le letture via shell sono negate | Legge la copia anonimizzata |
| `cat`, `head`, pandas sugli originali | Negato | Negato | Negato |
| Ricerca testuale negli originali | Negata | — | Negata |
| Output dei comandi | Ripulito da Clin | Non modificabile dagli hook | Non modificabile dagli hook |
| Messaggio con CF, telefoni, nominativi | Bloccato prima dell'invio | Bloccato prima dell'invio | Nessun hook disponibile |
| File citati con `@file` | Passano dalla guardia (`CLAUDE_CODE_DISABLE_FILE_MENTIONS=1`) | Non verificato | Non verificato |

Verifiche: su Claude Code 2.1.326 l'intero flusso è stato provato dal vivo
(lettura, comando negato, messaggio bloccato, `/clin`). Per Codex e
Antigravity la guardia segue la documentazione ufficiale degli hook (novembre
2026) ed è provata con payload simulati, non ancora dentro gli agenti. In
Codex l'hook va approvato con `/hooks`, in Antigravity va controllato in
Customizations > Hooks. Nella chat di Claude Desktop e su claude.ai non
esistono hook: lì valgono MCP e modalità appunti.

Limiti: un nome scritto **solo nel nome del file** (es. `ROSSI_MARIO.pdf`)
compare negli elenchi di cartella; le copie di `/clin` hanno nomi già ripuliti.
Gli strumenti MCP di terze parti che leggono file non passano dalla guardia.

### Altri client MCP

Qualunque client che supporti server MCP locali (stdio) può usare:

```json
{
  "mcpServers": {
    "clin": { "command": "python3", "args": ["/percorso/clin/clin.py", "mcp"] }
  }
}
```

| Strumento | Funzione |
|---|---|
| `anonimizza_documento` | Restituisce il testo anonimizzato di un PDF, DOCX, XLSX, CSV o TXT |
| `crea_copie_anonime` | Crea copie anonimizzate di un file o di una cartella; restituisce solo conteggi e percorso |

Per impostazione predefinita il server legge solo file nella cartella home. Per
limitarlo ulteriormente: variabile d'ambiente `CLIN_CARTELLE`
(più cartelle separate da `:`).

---

## Cosa viene riconosciuto

Non c'è una scala di sensibilità: per impostazione predefinita Clin rimuove
**tutti** i dati personali. Per un uso preciso (per esempio uno studio che deve
conservare le date degli esami) le singole categorie si possono lasciare in
chiaro a mano: menu **Aiuto › Cosa rimuovere** nell'applicazione, oppure

```bash
python3 clin.py impostazioni categorie                                  # stato di ogni categoria
python3 clin.py impostazioni categorie_escluse "Date, Struttura sanitaria"
python3 clin.py impostazioni categorie_escluse ""                       # di nuovo tutto
```

L'impostazione vale per l'applicazione, per `/clin` negli agenti e per il server MCP.

| Dati | Esempi |
|---|---|
| Persone, in qualsiasi lingua | Paziente, familiari («riferisce la figlia Giulia»), medici, operatori, firmatari, nomi citati nel testo libero |
| Identificativi ufficiali | Codice fiscale (anche omocodico, con carattere di controllo), tessera sanitaria TEAM, STP/ENI |
| Documenti | Carta d'identità (anche CIE `CA12345AB`), patente, passaporto, permesso di soggiorno |
| Identificativi clinici | Nosologico, nosografico, n° ricovero, episodio, verbale PS, pratica, impegnativa, NRE, referto, protocollo, cartella |
| Recapiti | Telefoni in ogni formato (`3471234567`, `333.123.4567`, `06 2345 6789`, `+39 …`), email e PEC |
| Indirizzi | Con o senza etichetta, anche «Via dei Mille 5», «Via XX Settembre 14/B», «00185 Roma (RM)», «residente a …» |
| Firme digitali | «Firmato digitalmente da …», «… ai sensi del D.Lgs. 82/2005 da: …», `CN=`, `SERIALNUMBER=TINIT-…` |
| Date ed età | Tutte le date (nascita, ricovero, esame, firma), età |
| Altro | IBAN (mod-97), partita IVA e carte (checksum), strutture sanitarie |
| Immagini nei PDF | Loghi, timbri, firme scansionate, codici a barre e QR, foto: rimossi senza cancellare il testo sovrapposto. Le pagine scansionate passano dall'OCR |
| Dati nascosti | Metadati e XMP, allegati, commenti, campi modulo, segnalibri, JavaScript, testo invisibile o fuori pagina |
| Nomi dei file prodotti | «ROSSI_MARIO_referto_12-03-2024» diventa «ANON_referto_ANON»; anche in minuscolo («dimissione_ferrari» → «dimissione_ANON») |

Restano leggibili termini clinici, eponimi («manovra di Giordano», «morbo di
Parkinson»), farmaci, posologie, durate («storia di 10 anni di diabete»),
valori di laboratorio, codici ICD/DRG e schemi terapeutici («FOLFOX-4»).

**Riconoscimento contestuale.** Le regole coprono i dati con forma
riconoscibile ed etichette. I nomi senza alcun contesto («Elira Shehu, 45enne,
giunge…») li trova il modello locale; ogni sua proposta viene verificata: deve
comparire nel testo, non contenere cifre, non essere un eponimo o un termine
clinico. Nell'applicazione l'anteprima resta immediata e si aggiorna quando il
modello ha finito di leggere il documento.

**Propagazione dei nominativi.** Ogni nome trovato (dopo un'etichetta, dal
contesto o dal modello) viene cercato in tutto il documento, anche nel testo
libero («Rossi riferisce…») e in ordine inverso («Mario Rossi»). Le parole
singole si cercano solo con l'iniziale maiuscola: «Neri» sì, «capelli neri» no.

**Fogli di calcolo e database.** Excel (.xlsx, .xlsm), CSV e TSV vengono
trattati colonna per colonna; la copia conserva fogli, colonne, formule e
formattazione.

| Colonna (dall'intestazione) | Trattamento |
|---|---|
| Nominativo: Cognome, Nome, Paziente, Assistito… | Pseudonimo `PAZ-0001`; «Rossi \| Mario» in due colonne, «ROSSI MARIO» e «Mario Rossi» ricevono lo stesso codice |
| Codice fiscale, tessera sanitaria, passaporto | Pseudonimo `ID-0001` |
| Nosologico, cartella, ID paziente, ricetta/NRE, impegnativa, campione, accession, ricovero, letto | Pseudonimo `IDC-0001` |
| Medico, refertante, firma, MMG | Pseudonimo `MED-0001` |
| Infermiere, operatore, compilatore | Pseudonimo `OPE-0001` |
| Familiare, caregiver, tutore, contatto di emergenza | Pseudonimo `PER-0001` |
| Documento, carta d'identità, patente | Pseudonimo `DOC-0001` |
| Ospedale, struttura, presidio, ASL, centro | Pseudonimo `STR-0001` |
| Colonna di nomi con intestazione qualsiasi («Coordinatore») | Riconosciuta dal contenuto con il modello locale: pseudonimo `PER-0001` |
| Data e luogo di nascita, telefono, email, indirizzo, comune di residenza | Oscurati |
| Età | Conservata; dai 90 anni in su diventa «90+» |
| Note e testo libero | Analizzati come un referto (familiari, medici, recapiti, date) |
| Variabili cliniche: valori, classi, punteggi, codici ICD, esiti | Invariate |

Gli pseudonimi sono gli stessi in tutti i file di un lotto e, con
`clin.py copie` o `/clin`, anche tra sessioni diverse: registro, follow-up ed
esami restano collegabili. La corrispondenza resta in `~/.clin/pseudonimi.json`
(permessi 600); `python3 clin.py originale PAZ-0147` mostra il valore
originale, solo in locale. Le date vengono rimosse: gli intervalli (giorni di
degenza, tempo al follow-up) vanno calcolati in una colonna numerica prima
dell'anonimizzazione. I file .xls e .ods vanno salvati in .xlsx.

**Validazione e confini di parola.** I codici senza etichetta (CF omocodico,
partita IVA, carte, IBAN) vengono oscurati solo se il carattere di controllo è
corretto; ogni corrispondenza viene estesa alla parola intera, così nessun
frammento di un valore resta leggibile.

**Falsi positivi evitati.** Valori di laboratorio, parametri, posologie,
durate, codici ICD, eponimi e schemi terapeutici restano leggibili.

**Anteprima.** Scorrendo oltre la fine della pagina si passa alla successiva
(e risalendo alla precedente), senza usare i pulsanti in alto.

---

## Sicurezza

| Misura | Dettaglio |
|---|---|
| Elaborazione locale | Nessuna connessione verso l'esterno, nessuna telemetria; il modello facoltativo gira in Ollama su `127.0.0.1` (un indirizzo remoto viene rifiutato) |
| Guardia per agenti | Hook locali: le letture degli originali vengono deviate sulla copia anonima o negate; se Clin non riesce ad anonimizzare, la lettura è negata |
| Oscuramento irreversibile | Nei PDF il testo viene rimosso dal file, non solo coperto |
| Testo nascosto | Rimossi strati invisibili (OCR), testo fuori dall'area visibile della pagina, campi modulo |
| Metadati | Rimossi autore, titolo, XMP, allegati, JavaScript, segnalibri, link, miniature |
| Excel | Rimosse note di cella, intestazioni di stampa e proprietà del documento |
| Nome del file | `ROSSI_MARIO_referto.pdf` diventa `ANON_referto_ANONIMIZZATO.pdf` |
| Verifica finale | Il PDF prodotto viene rianalizzato; i residui sospetti vengono segnalati |
| Server MCP | Solo formati ammessi, limite di 50 MB, cartelle autorizzate; la tabella dei segnaposto non viene mai restituita all'IA |
| File locali | `~/.clin/segnaposto.json` (segnaposto), `~/.clin/pseudonimi.json` (pseudonimi dei fogli), `~/.clin/letture/` (copie anonime lette dalla guardia), `~/.clin/impostazioni.json`: cartella e file leggibili solo dall'utente (permessi 700/600) |
| Risultati | I file ricondotti ai dati reali hanno permessi 600 e la loro cartella è negata all'agente |

### Limiti

- Le pagine **scansionate** e le immagini JPG/PNG vengono lette con l'OCR: nella
  versione desktop solo se il modello è installato (`scripts/fetch_ocr_model.py`),
  altrimenti Clin le segnala ma non le legge; sul telefono l'OCR è sempre
  incluso. Una pagina letta con l'OCR viene salvata come immagine con i dati
  già coperti sui pixel: nell'output non restano né l'immagine originale né un
  livello di testo, ma il testo non è più selezionabile. L'opzione di
  rimozione delle immagini non si applica a queste pagine, perché lì
  l'immagine è il contenuto.
- L'OCR può sbagliare. Un nome scritto a mano, sbiadito o letto male non viene
  riconosciuto e resta visibile; per prudenza ogni sequenza che somiglia a un
  codice viene comunque coperta. Le pagine lette con l'OCR vanno controllate a
  vista, e Clin lo ricorda con un avviso. Per ora l'applicazione desktop non
  apre direttamente le immagini: si usano il comando, il server
  MCP, `anonymize_engine.process_batch_files` o l'app per telefono.
- Senza modello locale (GLiNER o Ollama) un nome privo di etichetta e di contesto («Elira Shehu,
  45enne…») può sfuggire; per questi casi c'è la lista «Rimuovi sempre».
- Nei fogli di calcolo il modello locale non viene usato cella per cella
  (sarebbe troppo lento): decide quali colonne contengono nomi di persona
  (intestazione nota oppure contenuto), e quei nomi vengono poi cercati anche
  nelle celle di testo libero.
- I codici a barre disegnati come grafica vettoriale (non come immagine) nei
  PDF non vengono riconosciuti; quelli in forma di immagine vengono rimossi.
- I documenti reali vanno comunque controllati nell'anteprima o nelle copie
  prodotte.
- Nella modalità appunti, il testo incollato **prima** di passare da Clin è già
  stato inviato.
- Clin riduce il rischio, non sostituisce la verifica dell'operatore né le
  valutazioni previste dal GDPR per il trattamento di dati sanitari.

---

## Confronto con rizzo-pii

[rizzo-pii](https://github.com/Rizzo-AI-Academy/rizzo-pii) è uno strumento
locale generalista, nato per testi legali, basato su un modello neurale
(mmBERT, circa 1,2 GB) affiancato da regole. Clin ne ha ripreso le validazioni
con carattere di controllo, il principio dei confini di parola, il controllo dei
residui nel PDF prodotto e il ripristino tollerante delle risposte. Le
differenze principali:

| | Clin | rizzo-pii |
|---|---|---|
| Entità sanitarie (tessera TEAM, STP/ENI, nosologico, medici, personale, strutture) | Sì | No |
| Propagazione dei nominativi nel testo libero | Sì | Solo nel PDF |
| Collegamento diretto alle IA (MCP, skill Claude Code, appunti) | Sì | No (copia e incolla manuale) |
| DOCX, XLSX, CSV con pseudonimi per colonna | Sì | No |
| Testo nascosto e fuori pagina nei PDF | Rimosso | Non gestito |
| Nomi senza etichetta nel testo libero | Sì (GLiNER o Ollama in locale, facoltativo) | Sì (mmBERT) |
| OCR di pagine scansionate e immagini | Sì: Tesseract integrato in PyMuPDF nella versione desktop (facoltativo, ~2,6 MB), Tesseract.js sul telefono | Sì, PaddleOCR su ONNX Runtime con analisi del layout e delle tabelle |
| Funzionamento sul telefono, offline | Sì (app web) | No |
| Dimensione | Pochi MB | Circa 1,2 GB |

Il confronto si basa sulla lettura del codice di rizzo-pii (commit `2f3fc39`,
novembre 2026); i valori di accuratezza dichiarati da rizzo-pii non sono stati
verificati.

Per l'OCR sono state valutate due strade. La pipeline di rizzo-pii
(PaddleOCR su ONNX Runtime) richiede onnxruntime, OpenCV, pyclipper e PyYAML,
cioè oltre 100 MB di pacchetti, più modelli da 40-160 MB. In cambio ricostruisce
il layout e le tabelle. Tesseract è già compilato dentro PyMuPDF e richiede
solo un file di lingua da 2,6 MB. Legge bene la stampa (circa 0,2 s a pagina
a 300 dpi), peggio le foto storte e la grafia. Clin usa Tesseract: deve solo
trovare le parole e i loro riquadri, non ricostruire il documento.

## Struttura

| File | Contenuto |
|---|---|
| `clin.py` | Comando unico: applicazione, `testo`, `appunti`, `ripristina`, `copie`, `risultati`, `originale`, `impostazioni`, `installa`/`disinstalla`, `attiva`/`disattiva`, `proteggi`, `mcp`, `collega` |
| `clin_guard.py` | Guardia (hook) per Claude Code, Codex e Antigravity |
| `clin_results.py` | Risultati dell'agente ricondotti ai dati reali |
| `clin_settings.py` | Impostazioni per l'uso con gli agenti |
| `clin_gui.py` | Applicazione grafica (PySide6) |
| `anonymize_engine.py` | Motore di riconoscimento e redazione PDF |
| `clin_llm.py` | Riconoscimento contestuale con modello locale (GLiNER o Ollama), solo localhost |
| `clin_ner.py` | Servizio GLiNER locale (socket Unix, ambiente separato in `~/.clin/ner`) |
| `tabular_engine.py` | Motore per CSV, TSV ed Excel |
| `clin_text.py` | Testo con segnaposto per le IA (PDF, DOCX, XLSX, CSV, TXT) |
| `clin_mcp.py` | Server MCP senza dipendenze esterne |
| `clin_ocr.py` | OCR locale facoltativo e redazione sui pixel delle scansioni |
| `scripts/fetch_ocr_model.py` | Download del modello OCR con verifica SHA-256 |
| `anonymize_pdf.py` | Riga di comando per l'anonimizzazione di PDF in lotto |
| `integrations/claude-code/` | Skill `/clin` (usata anche per Codex e Antigravity) |
| `build_app.py` | Creazione di Clin.app per macOS |
| `web/` | App web per telefono (Pyodide, Tesseract.js, pdf.js) e script di build |
| `ui_kit.py` | Sistema di design dell'interfaccia |

## Test

```bash
python3 -m unittest discover -s tests -v
```

I test (45, di cui 3 dell'OCR saltati se il modello OCR non è installato) usano
solo documenti sintetici generati al momento e girano senza modello linguistico
(`CLIN_LLM=0`); nessun dato reale è incluso nel repository.

## Crediti

Carattere tipografico [Albert Sans](https://github.com/usted/Albert-Sans),
licenza SIL Open Font License 1.1 (`assets/OFL-AlbertSans.txt`).

## Licenza

Clin è software libero, distribuito con licenza
[GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0): si può usare,
studiare, modificare e ridistribuire liberamente; chi distribuisce o offre in
rete una versione modificata deve renderne pubblico il codice con la stessa
licenza. La scelta è coerente con PyMuPDF, anch'esso AGPL-3.0.

Clin è fornito senza alcuna garanzia. Riduce il rischio di esporre dati
personali ma non sostituisce la verifica dell'operatore né le valutazioni
previste dal GDPR per il trattamento di dati sanitari.

Clin è gratuito. Chi lo trova utile può sostenerne lo sviluppo con un
contributo volontario dalla sezione «Sostieni» del sito.
