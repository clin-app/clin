"""
Prova di andata e ritorno sulle date dentro i documenti (testo, Word, PDF, PDF scansionato).

    python3 tools/prova_documenti.py

Una lettera di dimissione inventata viene salvata nei quattro formati; Clin ne crea le copie
anonime e si controlla che in ciascuna:
  - ogni data sia ancora una data, spostata di 400 anni esatti (nessuna oscurata, nessuna vera);
  - nomi, codice fiscale e luogo di nascita non compaiano;
  - il contenuto clinico resti com'e'.
Poi si fa cio' che farebbe un agente: dalla copia calcola la durata del ricovero e scrive una
relazione con le date; Clin la riconduce ai dati reali e si confronta con la verita'.
Tutto in una cartella temporanea, con una cartella dati di Clin separata. Richiede PyMuPDF.
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LETTER = """OSPEDALE SAN GIOVANNI - U.O. Medicina Interna
LETTERA DI DIMISSIONE

Paziente: Mario Rossi, nato il 12/03/1958 a Torino
Codice fiscale: RSSMRA58C12L219X
Ricoverato dal 02/11/2023 al 09/11/2023 per polmonite lobare destra.
Intervento di toracentesi eseguito il 4 novembre 2023.
Emoglobina 13,5 g/dL, PCR 4,2 mg/dL, leucociti 2400.
In terapia anticoagulante da marzo 2021.
Controllo ambulatoriale fissato per il 2023-12-14.
Torino, 9 novembre 2023
Dott.ssa Giulia Bianchi
"""
# data vera -> come deve comparire nella copia
EXPECTED = {"12/03/1958": "12/03/2358", "02/11/2023": "02/11/2423", "09/11/2023": "09/11/2423",
            "4 novembre 2023": "4 novembre 2423", "marzo 2021": "marzo 2421", "2023-12-14": "2423-12-14",
            "9 novembre 2023": "9 novembre 2423"}
SECRETS = ["Rossi", "Mario", "Bianchi", "Giulia", "RSSMRA58C12L219X"]
CLINICAL = ["polmonite lobare destra", "13,5 g/dL", "leucociti 2400", "toracentesi"]
REAL_DATE = re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-](?:19|20)\d\d\b|\b(?:19|20)\d\d-\d\d-\d\d\b|"
                       r"\b(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre) (?:19|20)\d\d\b")


def write_documents(folder: Path) -> None:
    import fitz
    (folder / "lettera.txt").write_text(LETTER, encoding="utf-8")
    body = "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{line}</w:t></w:r></w:p>" for line in LETTER.splitlines())
    with zipfile.ZipFile(folder / "lettera.docx", "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f'<w:document xmlns:w="x"><w:body>{body}</w:body></w:document>')
    doc = fitz.open()
    page = doc.new_page()
    for i, line in enumerate(LETTER.splitlines()):
        page.insert_text((72, 90 + i * 24), line, fontsize=12)
    doc.save(folder / "lettera.pdf")
    scan = fitz.open()   # la stessa pagina come immagine: nessun testo, serve l'OCR
    pix = page.get_pixmap(dpi=200)
    sp = scan.new_page(width=page.rect.width, height=page.rect.height)
    sp.insert_image(sp.rect, pixmap=pix)
    scan.save(folder / "lettera_scansione.pdf")


def text_of(path: Path) -> str:
    import fitz
    from clin_text import _docx_text
    if path.suffix == ".pdf":
        with fitz.open(path) as d:
            return "\n".join(p.get_text(sort=True) for p in d)
    return _docx_text(path) if path.suffix == ".docx" else path.read_text(encoding="utf-8")


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="clin-documenti-"))
    study, data = base / "studio", base / "dati"
    study.mkdir()
    data.mkdir()
    ok = True
    try:
        write_documents(study)
        (data / "impostazioni.json").write_text(json.dumps({"modello_locale": False, "motore": "ollama"}))
        env = dict(os.environ, CLIN_DATI=str(data), CLIN_CARTELLE=str(study))
        clin = [sys.executable, str(ROOT / "clin.py")]
        subprocess.run(clin + ["avvia", str(study)], env=env, capture_output=True, text=True, check=True)
        copies = study / "Clin_anonimizzati"
        print(f"{'copia':<22}{'date spostate':<16}{'date vere':<12}{'dati personali':<16}contenuto clinico")
        for name in ("lettera.txt", "lettera.docx", "lettera.pdf", "lettera_scansione.pdf"):
            found = sorted(copies.glob(Path(name).stem.split("_")[0] + "*" + Path(name).suffix))
            copy = next((c for c in found if ("scansione" in c.name) == ("scansione" in name)), None)
            text = " ".join(text_of(copy).split()) if copy else ""
            moved = sum(1 for v in EXPECTED.values() if v in text)
            real = REAL_DATE.findall(text)
            leaks = [s for s in SECRETS + ["a Torino"] if s in text]   # luogo di nascita
            scan = "scansione" in name
            clinical = sum(1 for c in CLINICAL if c in text)
            # nella scansione il testo resta nell'immagine: nel livello di testo ci sono solo le date riscritte
            good = moved == len(EXPECTED) and not real and not leaks and (scan or clinical == len(CLINICAL))
            ok = ok and good
            print(f"{name:<22}{f'{moved} su {len(EXPECTED)}':<16}{len(real) or 'nessuna':<12}"
                  f"{', '.join(leaks) or 'nessuno':<16}{'(immagine)' if scan else f'{clinical} su {len(CLINICAL)}'}"
                  f"{'' if good else '   <-- DA VERIFICARE'}")
        # l'agente: legge la copia di testo, calcola la degenza, scrive la relazione
        copy = " ".join(text_of(next(copies.glob("lettera*.txt"))).split())
        a, b = re.search(r"dal (\d\d/\d\d/\d{4}) al (\d\d/\d\d/\d{4})", copy).groups()
        d1, d2 = (dt.datetime.strptime(x, "%d/%m/%Y").date() for x in (a, b))
        giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
        (study / "analisi").mkdir()
        (study / "analisi" / "degenza.md").write_text(
            f"Degenza di {(d2 - d1).days} giorni, dal {a} al {b} (dimissione di {giorni[d2.weekday()]}, {d2.isoformat()}). "
            f"Ricovero nel {d1.year}, controllo il 14 dicembre {d2.year}.\n", encoding="utf-8")
        subprocess.run(clin + ["risultati", str(study)], env=env, capture_output=True, text=True, check=True)
        got = (study / "Clin_risultati" / "analisi" / "degenza.md").read_text(encoding="utf-8").strip()
        truth = ("Degenza di 7 giorni, dal 02/11/2023 al 09/11/2023 (dimissione di giovedì, 2023-11-09). "
                 "Ricovero nel 2023, controllo il 14 dicembre 2023.")
        ok = ok and got == truth
        print(f"\nrelazione dell'agente ricondotta: {'uguale alla verita' if got == truth else 'DIVERSA'}\n  {got}")
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
