"""
Controllo manuale delle categorie, colonne dei fogli di calcolo, immagini nei PDF
e nomi dei file prodotti.

    python3 -m unittest discover -s tests -v
"""

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
os.environ["CLIN_LLM"] = "0"
sys.path.insert(0, str(ROOT))

import anonymize_engine  # noqa: E402
import clin_settings  # noqa: E402
from anonymize_engine import find_matches, safe_output_stem  # noqa: E402
from tabular_engine import TableSettings, _PseudonymBook, anonymize_table, header_category  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(clin_settings, "PATH", Path(self.tmp.name) / "impostazioni.json")
        p.start()
        self.addCleanup(p.stop)
        anonymize_engine._excl_cache["mtime"] = None

    def exclude(self, *cats):
        clin_settings.save({"categorie_escluse": list(cats)})
        anonymize_engine._excl_cache["mtime"] = None


class TestCategorie(Base):
    TEXT = "Ricoverato il 02/11/2026 presso Ospedale San Salvatore. Paziente: Rossi Mario, tel. 347 123 4567"

    def cats(self):
        return {m.category for m in find_matches(self.TEXT, 10)}

    def test_predefinito_tutto(self):
        self.assertTrue({"Date", "Struttura sanitaria", "Nome paziente", "Contatti"} <= self.cats())

    def test_categoria_esclusa_resta_in_chiaro(self):
        self.exclude("Date", "Struttura sanitaria")
        found = find_matches(self.TEXT, 10)
        self.assertFalse({"Date", "Struttura sanitaria"} & {m.category for m in found})
        # nessun frammento della data ("02/11") preso per un altro dato
        self.assertFalse(any("02/11" in m.text for m in found))
        self.assertIn("Nome paziente", {m.category for m in found})
        self.assertIn("Contatti", {m.category for m in found})

    def test_parse_valida_i_nomi(self):
        self.assertEqual(clin_settings.parse("categorie_escluse", "date, struttura sanitaria"),
                         ["Date", "Struttura sanitaria"])
        self.assertEqual(clin_settings.parse("categorie_escluse", ""), [])
        with self.assertRaises(ValueError):
            clin_settings.parse("categorie_escluse", "Diagnosi")


class TestColonne(Base):
    def test_intestazioni_nuove(self):
        expect = {"Medico refertante": "Medici", "Infermiere": "Personale sanitario",
                  "Familiare di riferimento": "Persone", "N ricetta": "Identificativi clinici",
                  "Codice campione": "Identificativi clinici", "Ospedale": "Struttura sanitaria",
                  "Numero documento": "Documenti"}
        for header, cat in expect.items():
            self.assertEqual(header_category(header)[1], cat, header)
        for header in ("Diagnosi", "Classe NYHA", "EuroSCORE II", "Esito", "Terapia"):
            self.assertIsNone(header_category(header), header)

    def test_intestazione_esclusa(self):
        self.exclude("Struttura sanitaria")
        self.assertIsNone(header_category("Ospedale"))

    def test_foglio_pseudonimi_per_ruolo(self):
        src = Path(self.tmp.name) / "rossi_mario_studio.csv"
        rows = [["Paziente", "Medico refertante", "Familiare", "Diagnosi"],
                ["Rossi Mario", "Paolo Neri", "Anna Bianchi", "Scompenso cardiaco"],
                ["Conti Sara", "Paolo Neri", "Pietro Conti", "Stenosi aortica"]]
        with open(src, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        out = Path(self.tmp.name) / "out.csv"
        res = anonymize_table(src, out, TableSettings(level=10, pseudonyms=_PseudonymBook(), keep_labels=True))
        self.assertIsNone(res.error)
        with open(out, encoding="utf-8-sig") as f:
            got = list(csv.reader(f))
        self.assertEqual(got[1], ["PAZ-0001", "MED-0001", "PER-0001", "Scompenso cardiaco"])
        self.assertEqual(got[2][1], "MED-0001")  # stesso medico, stesso codice
        self.assertEqual(safe_output_stem(src.stem, 10, res.detected_names), "ANON_studio")


class TestFileEImmagini(Base):
    def test_nome_file_minuscolo(self):
        self.assertEqual(safe_output_stem("dimissione_ferrari", 10, ["Ferrari Giulia"]), "dimissione_ANON")
        self.assertEqual(safe_output_stem("registro_TAVI", 10, []), "registro_TAVI")

    def test_loghi_rimossi_testo_intatto(self):
        import pymupdf as fitz
        src, dst = Path(self.tmp.name) / "a.pdf", Path(self.tmp.name) / "b.pdf"
        doc = fitz.open()
        page = doc.new_page()
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), 0)
        page.insert_image(fitz.Rect(40, 30, 560, 800), pixmap=pix)  # carta intestata a tutta pagina
        page.insert_image(fitz.Rect(40, 30, 100, 90), pixmap=pix)   # logo
        page.insert_text((60, 200), "Diagnosi: NSTEMI, terapia ASA 100 mg.")
        doc.save(src)
        anonymize_engine.anonymize_document(src, dst, 10)
        with fitz.open(dst) as out:
            self.assertEqual(out[0].get_images(), [])
            self.assertIn("NSTEMI", out[0].get_text())

    def test_loghi_conservati_se_esclusi(self):
        import pymupdf as fitz
        self.exclude("Immagini e loghi")
        src, dst = Path(self.tmp.name) / "a.pdf", Path(self.tmp.name) / "b.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_image(fitz.Rect(40, 30, 100, 90), pixmap=fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), 0))
        page.insert_text((60, 200), "Diagnosi: NSTEMI.")
        doc.save(src)
        anonymize_engine.anonymize_document(src, dst, 10)
        with fitz.open(dst) as out:
            self.assertEqual(len(out[0].get_images()), 1)


if __name__ == "__main__":
    unittest.main()


class TestPersoneDistinte(unittest.TestCase):
    """Nome o cognome in comune non bastano per fondere due persone."""

    def test_omonimi_parziali(self):
        from clin_text import anonymize_text
        t = ("Paziente: ESPOSITO LUCA. Riferisce la moglie Teresa Esposito.\n"
             "Diario: il sig. Rossi lamenta dispnea. Chiamata la figlia Elena Rossi.\n"
             "Anamnesi: paziente Mario Rossi. MMG Dott. Luca Verdi. Il sig. Esposito sta bene.")
        r = anonymize_text(t, level=10)
        inv = {v: k for k, v in r.mapping.items()}
        for name in ("ESPOSITO LUCA", "Teresa Esposito", "Mario Rossi", "Elena Rossi", "Luca Verdi"):
            self.assertIn(name, inv, name)
        self.assertEqual(len({inv[n] for n in ("ESPOSITO LUCA", "Teresa Esposito", "Mario Rossi",
                                               "Elena Rossi", "Luca Verdi")}), 5)
        self.assertIn(f"il sig. {inv['Mario Rossi']} lamenta", r.text)
        self.assertIn(f"Il sig. {inv['ESPOSITO LUCA']} sta bene", r.text)
