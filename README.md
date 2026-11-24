# Clin per Claude Code

Clin anonimizza in locale documenti sanitari e dati di ricerca prima che l'agente li
legga. Questo plugin porta in Claude Code la Skill `/clin`, la guardia sugli
originali e il server MCP di Clin, in un'installazione sola.

```text
/plugin install clin --marketplace clin-app/clin
```

Con Claude Code precedente alla 2.1.275: `/plugin marketplace add clin-app/clin`,
poi `/plugin install clin@clin`.

## Come si usa

Si apre Claude Code nella cartella dei dati e si scrive `/clin`. Da quel momento:

- la cartella è protetta: gli originali non si possono leggere, cercare né stampare;
- in `Clin_anonimizzati/` nascono le copie anonime di PDF, Word, PowerPoint, foto,
  Excel, CSV e dataset statistici, e l'agente lavora solo su quelle;
- a fine risposta i risultati (tabelle, relazioni, presentazioni) vengono ricondotti
  ai dati reali in una cartella che l'agente non vede.

`/clin stato` mostra che cosa è attivo, `/clin off` disattiva la protezione.

## Che cosa fa sul computer

Tutta l'elaborazione avviene in locale. I documenti non vengono mai inviati in rete
dal plugin.

- **Primo uso**: crea un ambiente Python dedicato in `~/.clin/plugin-venv` e vi
  installa da PyPI due pacchetti in versione fissa (PyMuPDF 1.28.0, openpyxl 3.1.5).
  Scarica poi da GitHub il modello OCR italiano di Tesseract (2,6 MB), verificandone
  l'impronta SHA-256. Sono le uniche connessioni che il plugin apre. Serve Python
  3.10 o successivo.
- **Dati locali**: la tabella che collega segnaposto e pseudonimi ai dati reali sta
  in `~/.clin`, leggibile solo dall'utente. La guardia ne nega l'accesso all'agente.
- **Hook**: intercetta `Read`, `Bash` e `Grep` sui documenti originali delle sole
  cartelle protette, ripulisce l'output dei comandi, ferma i messaggi che contengono
  dati personali e a fine risposta riconduce i risultati ai dati reali. Fuori dalle
  cartelle protette non interviene.
- **Server MCP** `clin`: strumenti `anonimizza_documento` e `crea_copie_anonime`.

## Aggiornamenti

Ogni modifica pubblicata riceve un nuovo numero di versione. Claude Code la scarica
quando si aggiorna il plugin (`/plugin` › Installed › clin › Update) oppure da solo,
se per questo marketplace è attivo l'aggiornamento automatico (`/plugin` ›
Marketplaces › clin).

## Limiti

Clin pseudonimizza: riduce i dati che raggiungono il fornitore dell'IA, ma non
sostituisce le autorizzazioni necessarie al trattamento. Uno script scritto
dall'agente ed eseguito può aprire un originale senza che il comando lo riveli: la
guardia ripulisce l'output, ma non è una barriera assoluta.

## Progetto

Codice, documentazione completa, estensione per Chrome ed Edge e applicazione
desktop: <https://github.com/clin-app/clin> · <https://clin-app.github.io/clin/>.
Licenza AGPL-3.0.
