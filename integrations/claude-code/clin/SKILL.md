---
name: clin
description: Anonimizza documenti sanitari e dati di ricerca in locale con Clin prima di leggerli. Usare SEMPRE quando l'utente invoca /clin o chiede di leggere, riassumere, analizzare o confrontare referti, cartelle cliniche, lettere di dimissione, esami, consulenze, Excel o CSV di pazienti (PDF, Word, Excel, CSV, TXT, foto) presenti sul computer.
argument-hint: "[cartella o file | off | ripristina | stato]"
---

# Clin - Clinical Data Anonymizer for AI

I documenti clinici dell'utente contengono dati personali di pazienti. Il loro
contenuto originale **non deve mai entrare nella conversazione**: si lavora solo
sulle copie anonime che Clin crea su questo computer.

Comando di Clin (usarlo sempre cosi', con le virgolette):

```bash
"{PYTHON}" "{CLIN_PATH}/clin.py" <comando> [argomenti]
```

## /clin [cartella o file]

Percorso: quello indicato dall'utente, altrimenti la cartella di lavoro corrente.

| L'utente scrive | Comando da eseguire | Poi |
|---|---|---|
| `/clin` oppure `/clin <percorso>` | `avvia "<percorso assoluto>"` | proseguire con il flusso qui sotto |
| `/clin off` | `disattiva "<cartella>"` | riferire l'esito e fermarsi |
| `/clin ripristina` | `risultati "<cartella>"` | riferire solo numero di file e cartella, e fermarsi |
| `/clin stato` | `stato "<cartella>"` | riferire l'esito e fermarsi |

### Flusso di lavoro

1. Eseguire `avvia` **senza leggere prima nessun originale**. In un solo passaggio:
   - la cartella (con le sottocartelle) diventa protetta: da qui in poi gli originali
     non si possono leggere, cercare o stampare;
   - in `Clin_anonimizzati/` nascono le copie anonime, con la stessa struttura di
     sottocartelle: PDF e foto con oscuramento irreversibile; Word, PowerPoint e testi
     con segnaposto (immagini e oggetti incorporati svuotati); Excel e CSV con
     pseudonimi (`PAZ-0001`, `ID-0001`); dataset SPSS, Stata e SAS convertiti in CSV;
   - l'output elenca i file su cui lavorare. I documenti non modificati dall'ultima
     volta non vengono rielaborati: ripetere `avvia` costa poco e va fatto ogni volta
     che l'utente aggiunge o modifica dei documenti.
2. Riferire all'utente l'esito in una riga (quanti file, eventuali avvisi o file non
   elaborati) e che la protezione e' attiva.
3. Lavorare **solo** sui file in `Clin_anonimizzati/`: lettura, pandas, statistiche,
   grafici. Lo stesso paziente ha lo stesso pseudonimo in tutti i file e in tutte le
   sessioni, quindi i fogli restano collegabili (merge, join, conteggi per paziente).
4. Salvare i risultati nella cartella di lavoro, lasciando segnaposto e pseudonimi
   cosi' come sono. A fine risposta Clin ne crea in locale una copia con i dati reali
   nella cartella dei risultati dell'utente. Quella cartella non e' accessibile: non
   leggerla, non cercarla, non elencarla.

### Date nei fogli di calcolo

Nelle copie di Excel, CSV e dataset statistici le date non sono oscurate: sono tutte
spostate dello stesso numero di giorni nel futuro (anni 2100-2260).

- Intervalli, durate, tempi di follow-up, sopravvivenza ed eta' (data evento meno data
  di nascita) sono **esatti**: calcolarli normalmente.
- Anno, mese, giorno della settimana e stagione **non sono reali**: non usarli e non
  riportarli come fatti (niente "interventi nel 2023", niente analisi per stagione).
- Nei risultati scrivere le date cosi' come sono, in forma `AAAA-MM-GG` o `GG/MM/AAAA`
  (o come date di Excel): Clin vi rimette quelle vere. Una data scritta a parole
  ("14 maggio") non viene ricondotta.

### Che cosa si puo' produrre

Clin rimette i dati reali in: Word (`.docx`), PowerPoint (`.pptx`), Excel (`.xlsx`),
CSV/TSV, Markdown, testo, HTML, LaTeX, RTF, JSON, XML, YAML, quaderni (`.ipynb`),
R Markdown e Quarto (`.Rmd`, `.qmd`), grafici vettoriali (`.svg`). Quindi lettere di
dimissione, relazioni, presentazioni, tabelle e quaderni di analisi si scrivono
normalmente, con i segnaposto al posto dei nomi.

- PDF e immagini (`.png`, `.jpg`) prodotti dall'agente non vengono ricondotti: se
  servono con i nomi veri, produrre anche la versione Word, HTML, LaTeX o SVG.
- Scrivere ogni segnaposto per intero e senza modificarlo (`[PAZIENTE_1]`, `PAZ-0001`):
  abbreviato o tradotto non viene piu' riconosciuto.
- Dati intermedi (cache, dataframe salvati): tenerli in `Clin_anonimizzati/` o in CSV.
- Se `avvia` segnala formati lasciati chiusi (DICOM, posta, vecchi `.doc`/`.xls`/`.ppt`,
  documenti Apple...), dirlo all'utente: vanno esportati in PDF, Word, Excel o CSV.
- Se nella cartella ci sono articoli o linee guida che non contengono dati di pazienti
  e servono con i nomi degli autori in chiaro, l'utente puo' escluderli dal proprio
  terminale con `escludi "<file o cartella>"`: indicarglielo, non eseguirlo.

## Regole

1. Non aprire mai un documento clinico originale con `Read`, `cat`, `head`,
   `pdftotext`, script Python o altri strumenti che ne mostrino il contenuto. Nelle
   cartelle protette `Read` restituisce gia' la copia anonima e gli altri accessi
   vengono negati: rispettare il rifiuto, non cercare altre strade.
2. Per leggere un singolo documento fuori da una cartella protetta usare lo strumento
   MCP `anonimizza_documento` (server `clin`) oppure il comando `testo "<file>"`:
   restituisce il testo con segnaposto (`[PAZIENTE_1]`, `[ID_1]`, `[DATA_NASCITA_1]`,
   `[MEDICO_1]`...). Il riepilogo delle sostituzioni esce su stderr.
3. Usare segnaposto e pseudonimi cosi' come sono. Non tentare di ricostruire i dati
   originali e non chiederli all'utente.
4. Clin rimuove sempre tutti i dati personali (nomi anche senza etichetta e in
   qualsiasi lingua, recapiti, indirizzi, date, codici e numeri di documento);
   restano termini clinici, farmaci, dosi e valori di laboratorio.
5. Se un testo anonimizzato contiene ancora un dato chiaramente identificativo,
   segnalarlo all'utente senza ripeterlo per intero.
6. Se un comando di Clin fallisce o `/clin` non sembra attivo, eseguire `stato` e
   riferire all'utente che cosa manca, senza aggirare la protezione.
7. `originale`, `ripristina`, `dimentica`, `disinstalla`, `escludi` e la modifica delle
   impostazioni sono riservati all'utente, nel suo terminale: se servono, indicargli
   il comando da eseguire.
