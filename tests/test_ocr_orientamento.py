"""Documenti d'identita' fotografati: foto ruotate e luogo di nascita sulla riga sotto la data."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import clin_ocr  # noqa: E402
import clin_web  # noqa: E402

ROWS = [("Cognome", "ROSSI"), ("Nome", "MARIO"), ("nato il", "10/12/1985"), ("a", "Ancona (AN)"),
        ("Residenza", "Via Garibaldi 12"), ("Codice fiscale", "RSSMRA85T10A562S")]


def card(path: Path, rot: int) -> None:
    d = clin_ocr.fitz.open()
    p = d.new_page(width=450, height=280)
    for i, (k, v) in enumerate(ROWS):
        p.insert_text((20, 35 + i * 38), k, fontsize=13, fontname="tiro")
        p.insert_text((150, 35 + i * 38), v, fontsize=15, fontname="cour")
    pix = p.get_pixmap(dpi=200)
    img = clin_ocr.fitz.open()
    ip = img.new_page(width=pix.width, height=pix.height)
    ip.insert_image(ip.rect, pixmap=pix, rotate=rot)
    ip.get_pixmap(dpi=72).save(str(path))


class LuogoDiNascita(unittest.TestCase):
    def run_text(self, t):
        return json.loads(clin_web.run_text(t, 10, "{}"))["text"]

    def test_riga_sotto_la_data(self):
        self.assertNotIn("Ancona", self.run_text("nato il 10/12/1985\na Ancona (AN)"))

    def test_carta_identita_con_atto(self):
        t = "nato il 16/12/1996\n(atto n. 1608 P. I S. A)\na ........ San Giovanni Rotondo ( FG )"
        self.assertNotIn("Rotondo", self.run_text(t))

    def test_nessun_falso_positivo(self):
        self.assertIn("A domicilio", self.run_text("Nato il 10/12/1985.\nA domicilio con terapia invariata."))
        self.assertIn("a cui viene", self.run_text("Paziente nato il 10/12/1985\na cui viene prescritta terapia"))


@unittest.skipUnless(clin_ocr.available(), "modello OCR non installato")
class FotoRuotate(unittest.TestCase):
    def test_lettura_in_ogni_rotazione(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rot in (0, 90, 180, 270):
                path = Path(tmp) / f"carta_{rot}.png"
                card(path, rot)
                doc = clin_ocr.open_as_pdf(path)
                text = " ".join(w[4] for w in clin_ocr.ocr_words(doc[0]))
                self.assertIn("ROSSI", text, rot)
                self.assertIn("10/12/1985", text, rot)

    def test_riquadri_nelle_coordinate_originali(self):
        with tempfile.TemporaryDirectory() as tmp:
            boxes = {}
            for rot in (0, 180):
                path = Path(tmp) / f"carta_{rot}.png"
                card(path, rot)
                page = clin_ocr.open_as_pdf(path)[0]
                w = next(w for w in clin_ocr.ocr_words(page) if "RSSMRA" in w[4])
                boxes[rot] = (w[:4], page.rect)
            (a, r), (b, _) = boxes[0], boxes[180]
            # capovolta: il codice fiscale sta nella posizione speculare
            self.assertAlmostEqual(b[0], r.width - a[2], delta=8)
            self.assertAlmostEqual(b[1], r.height - a[3], delta=8)


if __name__ == "__main__":
    unittest.main()
