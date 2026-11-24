"""La documentazione segue il codice: se cambia il funzionamento e il sito, la guida tecnica o le guide di
integrazione restano indietro, questi test falliscono (anche su GitHub, a ogni push).

Solo libreria standard e lettura dei file come testo: girano ovunque, senza dipendenze."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
read = lambda rel: (ROOT / rel).read_text(encoding="utf-8")  # noqa: E731

HOME = "docs/index.html"
GUIDA = "docs/guida.html"
SERVER = "deploy/README.md"


def ids(html: str) -> set:
    return set(re.findall(r'\bid="([^"]+)"', html))


class TestDocumentazione(unittest.TestCase):
    def test_versione_della_guida(self):
        v = json.loads(read("extension/manifest.json"))["version"].split(".")
        self.assertIn(f"Versione {v[0]}.{v[1]}", read(GUIDA), "aggiornare la versione in docs/guida.html")

    def test_ogni_comando_e_nella_guida(self):
        src, guida = read("clin.py"), read(GUIDA)
        commands = set(re.findall(r'sub\.add_parser\("([a-z_]+)"', src))
        commands |= set(re.findall(r'\(\("(attiva)", cmd_attiva|\("(disattiva)", cmd_disattiva', src)[0]) - {""}
        missing = sorted(c for c in commands if f"<code>{c}" not in guida)
        self.assertFalse(missing, f"comandi da descrivere nella guida tecnica (Installazione e comandi): {missing}")

    def test_ogni_percorso_dell_api_e_documentato(self):
        routes = set(re.findall(r'path == "(/[a-z_]+)"', read("clin_api.py")))
        self.assertTrue(routes)
        for doc in (GUIDA, SERVER):
            missing = sorted(r for r in routes if r not in read(doc))
            self.assertFalse(missing, f"percorsi dell'API da descrivere in {doc}: {missing}")

    def test_ruoli_dello_schema_delle_colonne(self):
        block = re.search(r"SCHEMA_ROLES[^=]*= \{(.*?)\n\}", read("tabular_engine.py"), re.S).group(1)
        roles = set(re.findall(r'^\s+"([a-z_]+)":', block, re.M))
        self.assertTrue(roles)
        for doc in (GUIDA, SERVER):
            missing = sorted(r for r in roles if f"<code>{r}</code>" not in read(doc) and f"`{r}`" not in read(doc))
            self.assertFalse(missing, f"ruoli dello schema da descrivere in {doc}: {missing}")

    def test_collegamenti_interni(self):
        home, guida = read(HOME), read(GUIDA)
        for page, html in ((HOME, home), (GUIDA, guida)):
            broken = sorted({a for a in re.findall(r'href="#([^"$]+)"', html)} - ids(html))
            self.assertFalse(broken, f"ancore inesistenti in {page}: {broken}")
        broken = sorted({a for a in re.findall(r'href="guida\.html#([^"]+)"', home)} - ids(guida))
        self.assertFalse(broken, f"capitoli della guida inesistenti richiamati dalla homepage: {broken}")

    def test_ogni_sezione_rimanda_alla_guida(self):
        home = read(HOME)
        for sec in re.findall(r'<section class="[^"]*" id="(\w+)">', home):
            if sec in ("tecnica", "sostieni"):
                continue
            body = home.split(f'id="{sec}">', 1)[1].split("</section>", 1)[0]
            self.assertIn('class="btn-deep" href="guida.html#', body, f"sezione {sec} senza «Approfondisci»")

    def test_formati_supportati(self):
        """Ogni formato che le copie accettano e' citato nella guida tecnica."""
        names = {".pdf": "PDF", ".docx": "Word", ".pptx": "PowerPoint", ".xlsx": "Excel", ".csv": "CSV",
                 ".jpg": "JPG", ".png": "PNG", ".sav": "SPSS", ".dta": "Stata", ".sas7bdat": "SAS"}
        guida = read(GUIDA)
        src = read("clin_mcp.py") + read("clin_text.py") + read("anonymize_engine.py")
        missing = sorted(n for ext, n in names.items() if ext in src and n not in guida)
        self.assertFalse(missing, f"formati da descrivere nella guida tecnica: {missing}")

    def test_hl7_segmenti_nella_guida(self):
        rules = set(re.findall(r'\("([A-Z0-9]{3})", \d+\): "', read("clin_sanitario.py")))
        guida = read(GUIDA)
        core = {"PID", "NK1", "PV1", "ORC", "OBR", "OBX", "RXE", "RXA", "SPM", "NTE"} & rules
        missing = sorted(s for s in core if s not in guida)
        self.assertFalse(missing, f"segmenti HL7 da citare nella guida tecnica: {missing}")


if __name__ == "__main__":
    unittest.main()
