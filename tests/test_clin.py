"""
Test di Clin. Usano solo dati sintetici generati al momento.

    python3 -m unittest discover -s tests -v
"""

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CLIN_LLM"] = "0"  # test deterministici: solo regole, nessun modello locale
sys.path.insert(0, str(ROOT))

try:
    import pymupdf as fitz  # noqa: E402
except ImportError:
    import fitz  # noqa: E402

import clin_ocr  # noqa: E402

from anonymize_engine import (  # noqa: E402
    BatchResult, _iban_ok, anonymize_document, collect_names, find_matches,
    process_batch_files, safe_output_stem,
)
from clin_text import anonymize_file, anonymize_text, check_path, restore_text  # noqa: E402
from tabular_engine import TableSettings, anonymize_table, header_rule  # noqa: E402

CF = "RSSMRA85T10A562S"


def found(text, level=10, **kw):
    return {(m.category, m.text) for m in find_matches(text, level, **kw)}


def texts(text, level=10, **kw):
    return {t for _, t in found(text, level, **kw)}


class TestRiconoscimento(unittest.TestCase):
    def test_codice_fiscale_anche_omocodico(self):
        self.assertTrue(any(c == "ID ufficiali" for c, _ in found(f"CF: {CF}")))
        self.assertTrue(any(c == "ID ufficiali" for c, _ in found("cf RSSMRA85T10A56NH")))

    def test_tessera_sanitaria(self):
        self.assertTrue(any(c == "ID ufficiali" for c, _ in found("TS 80380000500012345678")))

    def test_iban_con_controllo(self):
        self.assertTrue(_iban_ok("IT60 X054 2811 1010 0000 0123 456"))
        self.assertFalse(_iban_ok("IT61 X054 2811 1010 0000 0123 456"))

    def test_titoli_solo_cognome(self):
        self.assertIn(("Nome paziente", "Sig. Rossi"), found("Il Sig. Rossi ha riferito dolore", 2))
        self.assertIn("Dott. Bianchi", texts("visitato dal Dott. Bianchi in reparto", 7))

    def test_date_eta_telefoni(self):
        t = texts("ricoverato il 12 marzo 2024, paziente di 45 anni")
        self.assertIn("12 marzo 2024", t)
        self.assertIn("di 45 anni", t)
        self.assertTrue(any("6859123" in x for x in texts("Recapito 06/6859123")))

    def test_nessun_falso_positivo_clinico(self):
        for frase in ("Emoglobina 13,5 g/dL, PCR 0,45 mg/dL, creatinina 0.89",
                      "febbre da 3 giorni, terapia di 10 giorni, ciclo di 6 mesi di terapia",
                      "si comunica a nome del reparto che il paziente di cui sopra"):
            self.assertFalse(found(frase), frase)

    def test_raccolta_nominativi(self):
        n = collect_names("Paziente: ROSSI MARIO Data di nascita: 10/12/1985\nNome: Giulia")
        for x in ("ROSSI MARIO", "ROSSI", "MARIO", "Giulia"):
            self.assertIn(x, n)
        self.assertNotIn("Data", n)


class TestPdf(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def _pdf(self, name="in.pdf"):
        src = self.dir / name
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((72, 72), f"Paziente: ROSSI MARIO   CF: {CF}", fontsize=11)
        p.insert_text((72, 100), "Il paziente Rossi riferisce febbre da 3 giorni.", fontsize=11)
        p.insert_text((72, 130), "ROSSI MARIO", fontsize=11, render_mode=3)       # invisibile
        p.insert_text((72, -50), f"Nota nascosta: ROSSI {CF}", fontsize=11)     # fuori pagina
        w = fitz.Widget()
        w.field_name, w.field_type = "paz", fitz.PDF_WIDGET_TYPE_TEXT
        w.field_value, w.rect = "Mario Rossi tel 3331234567", fitz.Rect(72, 200, 300, 220)
        p.add_widget(w)
        p2 = doc.new_page()
        p2.insert_text((72, 72), "Controllo: MARIO ROSSI stabile. Emoglobina 13,5 g/dL", fontsize=11)
        doc.set_metadata({"author": "Dr. Bianchi", "title": "Referto Rossi Mario"})
        doc.embfile_add("allegato.txt", f"Rossi Mario {CF}".encode())
        doc.save(src)
        return src

    def test_redazione_e_propagazione(self):
        out = self.dir / "out.pdf"
        res = anonymize_document(self._pdf(), out, sensitivity_level=5, remove_images=False)
        self.assertTrue(res.ok, res.error)
        text = "\n".join(pg.get_text() for pg in fitz.open(out))
        for leak in ("Rossi", "ROSSI", "MARIO", "RSSMRA"):
            self.assertNotIn(leak, text)
        self.assertIn("Emoglobina 13,5", text)
        self.assertIn("febbre", text)

    def test_nessuna_traccia_nei_byte(self):
        batch = BatchResult()
        process_batch_files([self._pdf("ROSSI_MARIO_referto.pdf")], self.dir / "out",
                            sensitivity_level=5, remove_images=False, batch_result=batch)
        res = batch.results[0]
        self.assertEqual(res.output_path.name, "ANON_referto_ANONIMIZZATO.pdf")
        out = fitz.open(res.output_path)
        raw = out.tobytes(expand=255)
        for leak in (b"Rossi", b"ROSSI", b"RSSMRA", b"3331234567", b"Bianchi", b"Nota nascosta"):
            self.assertNotIn(leak, raw)
        self.assertEqual(out.embfile_count(), 0)
        self.assertEqual(len(list(out[0].widgets())), 0)

    def test_nome_file(self):
        self.assertEqual(safe_output_stem("ROSSI_MARIO_referto_12-03-2024", 5,
                                          ["ROSSI MARIO", "ROSSI", "MARIO"]), "ANON_referto_ANON")
        self.assertEqual(safe_output_stem("Ecocardiogramma_controllo_2", 5), "Ecocardiogramma_controllo_2")


def _scan(path, image_only=False):
    """Pagina 'scansionata': il testo esiste solo come pixel di un'immagine."""
    src = fitz.open()
    p = src.new_page()
    p.insert_text((72, 100), f"Paziente: ROSSI MARIO   CF: {CF}", fontsize=12)
    p.insert_text((72, 130), "Diagnosi: polmonite lobare destra", fontsize=12)
    pix = p.get_pixmap(dpi=200)
    if image_only:
        pix.save(str(path))
        return path
    doc = fitz.open()
    doc.new_page(width=p.rect.width, height=p.rect.height).insert_image(p.rect, pixmap=pix)
    doc.save(path)
    return path


@unittest.skipUnless(clin_ocr.available(), "modello OCR assente: python3 scripts/fetch_ocr_model.py")
class TestOcr(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def _assert_clean(self, out):
        doc = fitz.open(out)
        page = doc[0]
        self.assertEqual(page.get_text().strip(), "")           # nessun livello di testo
        self.assertEqual(len(page.get_images()), 1)             # solo l'immagine coperta
        read = " ".join(w[4] for w in clin_ocr.ocr_words(page))
        for leak in ("ROSSI", "MARIO", "RSSMRA"):
            self.assertNotIn(leak, read)
        self.assertIn("polmonite", read)

    def test_pdf_scansionato(self):
        out = self.dir / "out.pdf"
        res = anonymize_document(_scan(self.dir / "scan.pdf"), out, sensitivity_level=5)
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.pages_without_text, [])
        self.assertGreater(res.redactions, 0)
        self._assert_clean(out)

    def test_immagine_png(self):
        batch = BatchResult()
        process_batch_files([_scan(self.dir / "foto.png", image_only=True)], self.dir / "out",
                            sensitivity_level=5, batch_result=batch)
        res = batch.results[0]
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.output_path.suffix, ".pdf")
        self._assert_clean(res.output_path)

    def test_testo_per_ia(self):
        for src in (_scan(self.dir / "scan.pdf"), _scan(self.dir / "foto.png", image_only=True)):
            r = anonymize_file(src, level=5)
            for leak in ("ROSSI", "MARIO", "RSSMRA"):
                self.assertNotIn(leak, r.text)
            self.assertIn("[PAZIENTE_1]", r.text)
            self.assertIn("polmonite", r.text)


class TestSenzaOcr(unittest.TestCase):
    def test_modello_assente_non_rompe_nulla(self):
        d = Path(tempfile.mkdtemp())
        with mock.patch.dict("os.environ", {"CLIN_TESSDATA": str(d / "vuota")}):
            self.assertFalse(clin_ocr.available())
            res = anonymize_document(_scan(d / "scan.pdf"), d / "out.pdf", sensitivity_level=5)
            self.assertTrue(res.ok, res.error)
            self.assertEqual(res.pages_without_text, [1])
            r = anonymize_file(d / "scan.pdf", level=5)
            self.assertEqual(r.text, "")
            self.assertTrue(any("OCR non installato" in n for n in r.notes))


class TestTabelle(unittest.TestCase):
    def test_regole_intestazione(self):
        attesi = {"Paziente": "pseudo", "Cognome e Nome": "pseudo", "Codice Fiscale": "pseudo",
                  "Data di nascita": "all", "Telefono": "all", "Diagnosi": None,
                  "Nome farmaco": None, "Data ricovero": None}
        for h, mode in attesi.items():
            self.assertEqual(header_rule(h, 5), mode, h)

    def test_csv_pseudonimi_coerenti(self):
        d = Path(tempfile.mkdtemp())
        p = d / "t.csv"
        with open(p, "w", newline="") as fh:
            csv.writer(fh).writerows([
                ["Paziente", "CF", "Data di nascita", "Diagnosi", "Note"],
                ["Rossi Mario", CF, "10/12/1985", "Polmonite", "febbre da 3 giorni, Rossi stabile"],
                ["Rossi Mario", CF, "10/12/1985", "Polmonite", "controllo"],
            ])
        res = anonymize_table(p, d / "o.csv", TableSettings())
        self.assertIsNone(res.error)
        out = (d / "o.csv").read_text(encoding="utf-8-sig")
        self.assertEqual(out.count("PAZ-0001"), 2)
        for leak in ("Rossi", "1985", "RSSMRA"):
            self.assertNotIn(leak, out)
        self.assertIn("Polmonite", out)
        self.assertIn("febbre da 3 giorni", out)

    def test_excel_commenti_e_intestazioni(self):
        from openpyxl import Workbook, load_workbook
        from openpyxl.comments import Comment
        d = Path(tempfile.mkdtemp())
        wb = Workbook()
        ws = wb.active
        ws.append(["Paziente", "Esito"])
        ws.append(["Rossi Mario", "ok"])
        ws["B2"].comment = Comment("chiamare Rossi", "Dr Bianchi")
        ws.oddHeader.center.text = "Reparto - Rossi"
        wb.properties.creator = "Bianchi"
        wb.save(d / "t.xlsx")
        anonymize_table(d / "t.xlsx", d / "o.xlsx", TableSettings())
        o = load_workbook(d / "o.xlsx").active
        self.assertEqual(o["A2"].value, "PAZ-0001")
        self.assertIsNone(o["B2"].comment)
        self.assertFalse(o.oddHeader.center.text)


class TestTestoPerIA(unittest.TestCase):
    def test_segnaposto_e_ripristino(self):
        src = (f"Paziente: ROSSI MARIO, nato il 10/12/1985, CF {CF}.\n"
               "Rossi riferisce febbre da 3 giorni. Visitato dal Dott. Bianchi. Tel 333 1234567.")
        r = anonymize_text(src)
        for leak in ("ROSSI", "Rossi", "Bianchi", "RSSMRA", "1234567", "1985"):
            self.assertNotIn(leak, r.text)
        self.assertEqual(r.text.count("[PAZIENTE_1]"), 2)
        self.assertIn("febbre da 3 giorni", r.text)
        self.assertIn("Dott. [MEDICO_1]", r.text)
        back = restore_text(r.text, r.mapping)
        # ogni ricorrenza della persona torna con il nominativo completo
        self.assertTrue(back.startswith(f"Paziente: ROSSI MARIO, nato il 10/12/1985, CF {CF}."))
        self.assertIn("ROSSI MARIO riferisce", back)
        self.assertIn("Dott. Bianchi", back)

    def test_ripristino_tollerante(self):
        m = {"[PAZIENTE_1]": "ROSSI MARIO", "[PAZIENTE_12]": "VERDI ANNA", "[ID_1]": "X"}
        self.assertEqual(restore_text("**[PAZIENTE_1]** e [ PAZIENTE_12 ]", m),
                         "**ROSSI MARIO** e VERDI ANNA")
        self.assertEqual(restore_text("Per PAZIENTE_1, [PAZIENTE_9] invariato", m),
                         "Per ROSSI MARIO, [PAZIENTE_9] invariato")
        # indice inventato: non diventa "ROSSI MARIO2"
        self.assertEqual(restore_text("[PAZIENTE_123]", m), "[PAZIENTE_123]")

    def test_partita_iva_e_carte(self):
        self.assertTrue(any(c == "Dati bancari" for c, _ in found("P.IVA 01114601006", 4)))
        self.assertFalse(found("codice 01114601007", 10))
        self.assertTrue(found("carta 4111 1111 1111 1111", 4))
        self.assertFalse(found("numero 4111 1111 1111 1112", 10))

    def test_valore_si_ferma_a_fine_frase(self):
        r = anonymize_text("Paziente: VERDI ANNA, nata il 01/02/1990. Verdi riferisce tosse da 5 giorni.")
        self.assertIn("riferisce tosse da 5 giorni", r.text)
        self.assertNotIn("1990", r.text)

    def test_codici_deformati_da_ocr(self):
        sys.path.insert(0, str(ROOT / "web"))
        import clin_web
        out = json.loads(clin_web.run_text(
            "CF: RSSMRA857T10A562S\nTel 333 12 34 567\nPCR 0,45 mg/dL, Hb 13,5", 8, "{}", True))["text"]
        self.assertNotIn("RSSMRA", out)
        self.assertNotIn("567", out)
        self.assertIn("PCR 0,45 mg/dL, Hb 13,5", out)

    def test_continuita_tra_sessioni(self):
        first = anonymize_text("Paziente: ROSSI MARIO")
        second = anonymize_text("Controllo di Rossi Mario", previous=first.mapping,
                                names=["ROSSI MARIO"])
        self.assertIn("[PAZIENTE_1]", second.text)

    def test_docx_e_tabelle(self):
        d = Path(tempfile.mkdtemp())
        docx = d / "r.docx"
        with zipfile.ZipFile(docx, "w") as z:
            z.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Paziente: Bianchi Luca"
                       "</w:t></w:r></w:p><w:p><w:r><w:t>Bianchi sta bene.</w:t></w:r></w:p></w:body></w:document>")
            z.writestr("word/header1.xml", "<w:hdr><w:p><w:r><w:t>Reparto - Bianchi Luca</w:t></w:r></w:p></w:hdr>")
        self.assertNotIn("Bianchi", anonymize_file(docx).text)
        tab = d / "t.csv"
        with open(tab, "w", newline="") as fh:
            csv.writer(fh).writerows([["Paziente", "Data di nascita", "Diagnosi"],
                                      ["Verdi Anna", "01/02/1990", "Asma"]])
        t = anonymize_file(tab).text
        self.assertNotIn("Verdi", t)
        self.assertNotIn("1990", t)
        self.assertIn("Asma", t)

    def test_percorsi_rifiutati(self):
        with self.assertRaises(ValueError):
            check_path(Path("/etc/passwd"))
        d = Path(tempfile.mkdtemp())
        f = d / "x.txt"
        f.write_text("prova")
        with self.assertRaises(ValueError):
            check_path(f, [Path.home() / "cartella-che-non-esiste"])


class TestServerMcp(unittest.TestCase):
    def test_protocollo(self):
        d = Path(tempfile.mkdtemp())
        f = d / "nota.txt"
        f.write_text(f"Paziente: ROSSI MARIO, CF {CF}", encoding="utf-8")
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "anonimizza_documento", "arguments": {"percorso": str(f)}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "anonimizza_documento", "arguments": {"percorso": "/etc/hosts"}}},
        ]
        proc = subprocess.run(
            [sys.executable, str(ROOT / "clin.py"), "mcp"],
            input="\n".join(json.dumps(m) for m in msgs) + "\n",
            capture_output=True, text=True, timeout=60,
            env={"CLIN_CARTELLE": str(d), "PATH": "/usr/bin:/bin", "HOME": str(d), "CLIN_LLM": "0"},
        )
        replies = {r["id"]: r for r in map(json.loads, proc.stdout.splitlines())}
        self.assertEqual(replies[1]["result"]["serverInfo"]["name"], "clin")
        self.assertEqual(len(replies[2]["result"]["tools"]), 2)
        out = replies[3]["result"]["content"][0]["text"]
        self.assertNotIn("ROSSI", out)
        self.assertNotIn("RSSMRA", out)
        self.assertIn("[PAZIENTE_1]", out)
        self.assertTrue(replies[4]["result"]["isError"])


class TestRefertoTuttoMaiuscolo(unittest.TestCase):
    """In un referto scritto in maiuscolo le frasi cliniche non sono nominativi."""
    TESTO = ("Paziente: ROSSI MARIO  nato il 12/03/1958\n"
             "ANAMNESI: INVIATO DAL MEDICO CURANTE, VISTI I SINTOMI. PADRE, MADRE PRIMA VISITA NEGATIVA.\n"
             "ESAME OBIETTIVO: CONDIZIONI GENERALI BUONE, VIGILE E ORIENTATO.\n"
             "TORACE: IPOFONESI EMITORACE DESTRA, DUE RANTOLI BASALI.\n"
             "ADDOME: TRATTABILE, NON DOLORABILE, MILZA ALL'ARCO. ALVO REGOLARE, DIURESI CONSERVATA.\n")

    def test_frasi_cliniche_restano(self):
        import anonymize_engine as ae
        with mock.patch("clin_llm.entities", return_value=[]):
            covered = " ".join(m.text for m in ae.find_matches(self.TESTO))
            names = ae.collect_names(self.TESTO)
        for clinical in ("CONDIZIONI", "CURANTE", "EMITORACE", "DOLORABILE", "PADRE", "ALVO", "DAL"):
            self.assertNotIn(clinical, covered)
            self.assertNotIn(clinical, " ".join(names))
        self.assertIn("ROSSI MARIO", covered)

    def test_cognome_virgola_nome_resta_coperto(self):
        import anonymize_engine as ae
        with mock.patch("clin_llm.entities", return_value=[]):
            for text in ("ROSSI, MARIO\nPRONTO SOCCORSO\n", "Nominativo: DE LUCA, ANNA MARIA   Letto 12\n",
                         "Visitato BIANCHI, Giulia per dispnea.\n"):
                self.assertTrue(any(m.category == "Nome paziente" for m in ae.find_matches(text)), text)

    def test_proposte_del_modello(self):
        import clin_llm
        for junk in ("Urgente Differibile", "CONDIZIONI GENERALI BUONE, VIGILE", "Emitorace Destra, Due"):
            self.assertIsNone(clin_llm.plausible_person(junk), junk)
        for name in ("ROSSI, MARIO", "Mario Dal Pozzo", "Clemente Ambrosi", "Nella Vitali", "Elira Shehu"):
            self.assertEqual(clin_llm.plausible_person(name), name)


if __name__ == "__main__":
    unittest.main()
