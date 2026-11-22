"""Riconoscimento in lingue europee e inglese (regole, senza modello locale)."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CLIN_LLM"] = "0"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "benchmark"))

from anonymize_engine import find_matches  # noqa: E402
from clin_text import anonymize_text  # noqa: E402


def found(text):
    return " | ".join(m.text for m in find_matches(text, 10))


class TestLingue(unittest.TestCase):
    def test_date_per_esteso(self):
        for t in ["Admitted on 3 September 2023", "Aufnahme am 14. März 2024", "Ingresa el 12 de septiembre de 2026",
                  "Internada a 5 de março de 2026", "Opgenomen op 19 mei 2026", "Przyjęta 13 września 2023",
                  "Internată la 1 martie 2025", "Hospitalisée le 1er mars 2024"]:
            self.assertRegex(found(t), r"\d", t)

    def test_codici_nazionali(self):
        for t, v in [("NHS number: 943 476 5919   Hospital", "943 476 5919"), ("N° de sécurité sociale : 2 85 05 75 006 084 36", "2 85 05 75 006 084 36"),
                     ("Versichertennummer: A123456780", "A123456780"), ("BSN: 123456782", "123456782"),
                     ("PESEL: 85050512345", "85050512345"), ("CNP: 2850505123456", "2850505123456"),
                     ("Nº de utente: 123456789", "123456789"), ("Fallnummer: 12345678", "12345678"),
                     ("Número de historia clínica: 1234567", "1234567"), ("Nr. foaie de observație: 12345", "12345")]:
            self.assertIn(v, found(t), t)

    def test_telefoni_e_indirizzi(self):
        for t, v in [("portable 06 12 34 56 78", "06 12 34 56 78"), ("móvil 612 345 678", "612 345 678"),
                     ("mobiel 06-12345678", "06-12345678"), ("12 Baker Street, London NW1 6XE", "Baker Street"),
                     ("15 rue de la Paix, 75002 Paris", "rue de la Paix"), ("Hauptstraße 5, 10115 Berlin", "Hauptstraße 5"),
                     ("Calle Mayor 10, 28013 Madrid", "Calle Mayor 10"), ("ul. Marszałkowska 10, 00-026 Warszawa", "Marszałkowska"),
                     ("Kerkstraat 12, 1017 GB Amsterdam", "Kerkstraat 12")]:
            self.assertIn(v, found(t), t)

    def test_medici_e_particelle(self):
        self.assertIn("Emily Clarke", found("Gezeichnet: Dr. med. Emily Clarke, Oberarzt."))
        self.assertIn("Andrei Ionescu", found("Podpisał: lek. med. Andrei Ionescu, kardiolog."))
        self.assertIn("van der Berg", anonymize_text("Ondertekend door dr. Daan van der Berg.", 10).mapping.get("[MEDICO_1]", ""))

    def test_nessun_falso_positivo(self):
        for t in ["Die Tochter Begleitung war hilfreich. Der Mann Schmerzen gab an. Morbus Crohn bekannt.",
                  "The patient's wife Reports improvement. Patient Education Material given. Parkinson's disease.",
                  "La fille Hospitalisée précédemment. Maladie de Parkinson. Signe de Murphy.",
                  "La hija Refiere mejoría. Enfermedad de Parkinson.", "De dochter Belde de huisarts. Ziekte van Parkinson.",
                  "Córka Poinformowana o stanie. Choroba Parkinsona."]:
            self.assertEqual(found(t), "", t)


class TestDatasetEuropeo(unittest.TestCase):
    """Casi emersi dal Pan-European Synthetic PII Benchmark (40 lingue)."""

    def test_codici_nosologici(self):
        for code in ["KH-23-869672-G", "SDO/2023/176329", "N.2023/298603-A", "NOS24/531196", "MRN-2023-90385A",
                     "CAS.2025.653977", "DOSS-2025-13661-SB", "NHC-31629720", "HOSP/25/220709"]:
            self.assertIn(code, found(f"Pratica {code} (codice C18.9)."), code)

    def test_icd_resta(self):
        for t in ["D.N.: 10.08.1997 | Serviço: Cirurgia | CID-10: I25.1", "nacido/a el 08/11/1965 — código I50.9",
                  "Diagnosi C18.9, controllo G20."]:
            self.assertFalse(any(c in found(t) for c in ["I25.1", "I50.9", "C18.9", "G20"]), t)

    def test_alfabeti_e_cognomi(self):
        self.assertIn("Попов-Петров", found("лечащий врач д-р Сергей Попов-Петров."))
        self.assertIn("Γεώργιος Παπαδόπουλος", found("Ασθενής: Γεώργιος Παπαδόπουλος | ημερομηνία γέννησης 01/02/1950"))
        self.assertIn("Riera i Oller", found("Metge responsable: Dr. Albert Riera i Oller."))
        self.assertIn("GALLI, Roberta", found("controllo per GALLI, Roberta, nata il 13/06/2006"))
        self.assertIn("Marco Rossi", found("Contatto segnalato (familiare di riferimento): Marco Rossi."))

    def test_date_con_anno_davanti(self):
        for t in ["2023. március 5.", "2023 m. kovo 5 d.", "2023. gada 5. marta", "2023ko martxoaren 5"]:
            self.assertRegex(found(t), r"2023", t)

    def test_niente_dosaggi_come_titoli(self):
        self.assertEqual(found("Amoxicillina 1 g. Hb 12,4 g/dL. Morbus Parkinson."), "")


if __name__ == "__main__":
    unittest.main()
