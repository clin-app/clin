"""
Benchmark sintetico (solo regole) e nuove regole di riconoscimento.

    python3 -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CLIN_LLM"] = "0"  # deterministico: il modello locale si misura con run.py
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "benchmark"))

import clin_llm  # noqa: E402
from anonymize_engine import _iban_ok, cf_ok  # noqa: E402
from clin_text import anonymize_text  # noqa: E402
from generate import generate  # noqa: E402
from run import evaluate  # noqa: E402


class TestBenchmark(unittest.TestCase):
    def test_generatore_valido(self):
        for d in generate(60):
            for s in d["spans"] + d["negatives"]:
                self.assertEqual(d["text"][s["start"]:s["end"]], s["text"])
                if s.get("sub") == "cf":
                    self.assertTrue(cf_ok(s["text"]), s["text"])
                if s.get("sub") == "iban":
                    self.assertTrue(_iban_ok(s["text"]), s["text"])

    def test_nessun_peggioramento_rispetto_alla_baseline(self):
        base = json.loads((ROOT / "tests" / "benchmark" / "baseline.json").read_text())["regole"]
        now = evaluate(generate(base["documenti"]), 10)
        self.assertGreaterEqual(now["complessivo"]["recall"], base["complessivo"]["recall"] - 0.005)
        self.assertGreaterEqual(now["complessivo"]["precisione"], base["complessivo"]["precisione"] - 0.005)


class TestNuoveRegole(unittest.TestCase):
    def assertHidden(self, src, *leaks, keep=()):
        out = anonymize_text(src).text
        for leak in leaks:
            self.assertNotIn(leak, out, out)
        for k in keep:
            self.assertIn(k, out, out)

    def test_telefoni_in_ogni_formato(self):
        self.assertHidden("cell 3471234567, ab. 06 2345 6789, 333.123.4567, +39 06 1234 5678",
                          "3471234567", "2345 6789", "123.4567", "1234 5678")

    def test_indirizzi(self):
        self.assertHidden("vive in Via dei Mille 5, 00185 Roma (RM); prima in via roma 12",
                          "Mille", "00185", "roma 12")

    def test_identificativi_e_documenti(self):
        self.assertHidden("Nosografico n. 2024/001234 - Verbale di Pronto Soccorso n. 0912345 - "
                          "Prot. n. 2024/0012345 - C.I. n. CA12345AB - patente n. RM1234567X",
                          "001234", "0912345", "0012345", "CA12345AB", "RM1234567X")

    def test_firme_digitali(self):
        self.assertHidden("Documento firmato digitalmente ai sensi del D.Lgs. 82/2005 da: Ivan Petrov\n"
                          "CN=ROSSI MARIO, SERIALNUMBER=TINIT-RSSMRA85T10A562S",
                          "Petrov", "ROSSI", "RSSMRA")

    def test_familiare_con_titolo_non_e_il_paziente(self):
        out = anonymize_text("Paziente: ROSSI MARIO. Informata la moglie, sig.ra Anna Bianchi.").text
        self.assertIn("moglie, sig.ra [PERSONA_1]", out)
        self.assertIn("Paziente: [PAZIENTE_1]", out)

    def test_familiare_citato_per_nome(self):
        out = anonymize_text("Riferisce la figlia Giulia Ferri. Giulia conferma.").text
        self.assertIn("figlia [PERSONA_1]. [PERSONA_1] conferma", out)

    def test_registro_excel_su_piu_fogli(self):
        """Cognome|Nome separati, follow-up con nominativo unito, familiare omonimo."""
        import tempfile
        from openpyxl import Workbook, load_workbook
        from clin_text import anonymize_file
        from tabular_engine import TableSettings, _PseudonymBook, anonymize_table
        d = Path(tempfile.mkdtemp())
        wb = Workbook()
        ws = wb.active
        ws.title = "Arruolati"
        ws.append(["Cognome", "Nome", "Comune di residenza", "Età", "Note"])
        ws.append(["Rossi", "Mario", "Ancona", 39, "riferisce la moglie Anna"])
        ws.append(["Bianchi", "Anna", "Senigallia", 92, ""])
        fu = wb.create_sheet("Follow-up")
        fu.append(["Paziente", "Esito"])
        fu.append(["ROSSI MARIO", "vivo"])
        fu.append(["Anna Bianchi", "deceduto"])
        wb.save(d / "registro.xlsx")
        # copia con pseudonimi (clin.py copie, /clin)
        anonymize_table(d / "registro.xlsx", d / "out.xlsx", TableSettings(keep_labels=True, pseudonyms=_PseudonymBook()))
        o = load_workbook(d / "out.xlsx")
        a = list(o["Arruolati"].iter_rows(values_only=True))
        f = list(o["Follow-up"].iter_rows(values_only=True))
        self.assertEqual(a[1][0], a[1][1])          # Rossi|Mario: un solo codice
        self.assertEqual(a[1][0], f[1][0])          # = "ROSSI MARIO" nel follow-up
        self.assertEqual(a[2][0], f[2][0])          # Bianchi|Anna = "Anna Bianchi"
        self.assertNotEqual(a[1][0], a[2][0])
        self.assertNotIn("Ancona", str(a))
        self.assertEqual(a[2][3], "90+")
        # testo per l'IA (lettura con Read)
        rows = [r.split("\t") for r in anonymize_file(d / "registro.xlsx").text.splitlines() if "\t" in r]
        self.assertEqual(rows[1][0], rows[1][1])
        self.assertEqual(rows[2][0], rows[2][1])
        self.assertNotIn(rows[2][0], rows[1][4])    # la moglie Anna non e' la paziente Anna Bianchi
        self.assertIn(rows[2][0], [r[0] for r in rows[4:]])

    def test_familiari_senza_etichetta(self):
        self.assertHidden("Riferisce la figlia Giulia. Accompagnato dal marito Oleksandr Kovalenko. "
                          "Giulia conferma.", "Giulia", "Kovalenko")

    def test_falsi_positivi_clinici(self):
        src = ("Manovra di Giordano negativa, Mingazzini nella norma, morbo di Parkinson. "
               "Hb 12,4 g/dL, PA 135/80 mmHg, INR 2,5, ICD-9-CM 410.71, storia di 10 anni di diabete, "
               "protocollo FOLFOX-4 ciclo 3/12, capelli neri. Richiedente: Reparto di Cardiologia. "
               "Terapia per via orale, 1 cp ore 8; per via endovenosa 2 fl. Contattata via email. "
               "Eta media 54.2 anni.")
        self.assertEqual(anonymize_text(src).text, src)


class TestModelloLocale(unittest.TestCase):
    def test_solo_server_locale(self):
        old = os.environ.get("CLIN_OLLAMA_URL")
        try:
            os.environ["CLIN_OLLAMA_URL"] = "http://example.com:11434"
            self.assertIsNone(clin_llm._base_url())
            os.environ["CLIN_OLLAMA_URL"] = "http://127.0.0.1:11434"
            self.assertIsNotNone(clin_llm._base_url())
        finally:
            if old is None:
                os.environ.pop("CLIN_OLLAMA_URL", None)
            else:
                os.environ["CLIN_OLLAMA_URL"] = old

    def test_verifica_delle_proposte(self):
        self.assertEqual(clin_llm.plausible_person("Dott. Paolo Neri"), "Paolo Neri")
        self.assertIsNone(clin_llm.plausible_person("Lasègue"))
        self.assertIsNone(clin_llm.plausible_person("Hb 12,4"))
        self.assertIsNone(clin_llm.plausible_person("ecografia addome"))
        self.assertTrue(clin_llm.is_eponym_at("manovra di Giordano", len("manovra di ")))


if __name__ == "__main__":
    unittest.main()
