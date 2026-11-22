---
name: clin
description: Anonimizza documenti sanitari e dati di ricerca in locale con Clin prima di leggerli. Usare SEMPRE quando l'utente invoca /clin o chiede di leggere, riassumere, analizzare o confrontare referti, cartelle cliniche, lettere di dimissione, esami, consulenze, Excel o CSV di pazienti (PDF, Word, Excel, CSV, TXT) presenti sul computer.
---

# Clin - Clinical Data Anonymizer for AI

I documenti clinici dell'utente contengono dati personali di pazienti. Il loro
contenuto originale **non deve mai entrare nella conversazione**: va letto solo
dopo l'anonimizzazione locale con Clin.

## /clin [cartella o file]

Quando l'utente invoca `/clin` (con o senza percorso):

1. Determinare il percorso: quello indicato, altrimenti la cartella di lavoro corrente.
   Se l'utente scrive `/clin off`, eseguire
   `"{PYTHON}" "{CLIN_PATH}/clin.py" disattiva "<cartella>"`, riferire l'esito e fermarsi.
   Se l'utente scrive `/clin ripristina`, eseguire
   `"{PYTHON}" "{CLIN_PATH}/clin.py" risultati "<cartella>"`, riferire solo il numero di file
   e la cartella, e fermarsi.
2. Attivare la protezione sulla cartella (effetto immediato: da qui in poi gli
   originali non possono essere letti, cercati o stampati):

   ```bash
   "{PYTHON}" "{CLIN_PATH}/clin.py" attiva "/percorso/assoluto/cartella"
   ```

3. Creare le copie anonime, senza leggere prima gli originali:

   ```bash
   "{PYTHON}" "{CLIN_PATH}/clin.py" copie "/percorso/assoluto"
   ```

   Nascono in `Clin_anonimizzati/` accanto agli originali: PDF con oscuramento
   irreversibile, Excel e CSV con pseudonimi (`PAZ-0001`, `ID-0001`). Lo stesso
   paziente ha lo stesso pseudonimo in tutti i file e in tutte le sessioni, quindi
   i fogli restano collegabili (merge, join, conteggi per paziente).
4. Riferire all'utente solo l'esito (numero di file, cartella, avvisi) e che la protezione e' attiva.
5. Da quel momento lavorare **solo** sui file in `Clin_anonimizzati/` (lettura,
   pandas, statistiche, grafici). Mai aprire gli originali.
6. Salvare i risultati (tabelle CSV o Excel, relazioni in Markdown o testo) nella
   cartella di lavoro, mantenendo segnaposto e pseudonimi cosi' come sono. Al termine
   di ogni risposta Clin ne crea in locale una copia con i dati reali nella cartella
   dei risultati (predefinita `Clin_risultati/`). Quella cartella non e' accessibile:
   non leggerla, non cercarla, non elencarne il contenuto.

## Regole

1. Non aprire mai un documento clinico originale con `Read`, `cat`, `head`,
   `pdftotext`, script Python o altri strumenti che ne mostrino il contenuto.
   Nelle cartelle attivate con /clin, `Read` restituisce
   gia' la copia anonimizzata e gli altri accessi vengono negati: rispettare il
   rifiuto, non cercare altre strade.
2. Per leggere un singolo documento come testo usare lo strumento MCP
   `anonimizza_documento` (server `clin`) oppure:

   ```bash
   "{PYTHON}" "{CLIN_PATH}/clin.py" testo "/percorso/del/file.pdf"
   ```

   L'output contiene il testo con segnaposto (`[PAZIENTE_1]`, `[ID_1]`,
   `[DATA_NASCITA_1]`, `[MEDICO_1]`...). Il riepilogo delle sostituzioni esce su stderr.
3. Usare segnaposto e pseudonimi cosi' come sono nella risposta. Non tentare di
   ricostruire i dati originali e non chiederli all'utente.
4. Clin rimuove sempre tutti i dati personali (nomi anche senza etichetta e in
   qualsiasi lingua, recapiti, indirizzi, date, codici e numeri di documento);
   restano termini clinici, farmaci, dosi e valori di laboratorio.
5. Se un testo anonimizzato contiene ancora un dato chiaramente identificativo,
   segnalarlo all'utente senza ripeterlo per intero.
