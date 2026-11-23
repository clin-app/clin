"""
Test di regressione per sicurezza, guardia agenti, propagazione dei nominativi,
documenti .txt/.docx/.xlsm e ponte web/estensione.
"""

import csv
import io
import json
import re
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
os.environ["CLIN_LLM"] = "0"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import clin  # noqa: E402
import clin_guard  # noqa: E402
import clin_llm  # noqa: E402
import clin_mcp  # noqa: E402
import clin_results  # noqa: E402
import clin_settings  # noqa: E402
import clin_web  # noqa: E402
from anonymize_engine import anonymize_document, collect_names, find_matches  # noqa: E402
from clin_text import anonymize_file, anonymize_text, check_path, redact_docx_file  # noqa: E402
from tabular_engine import TableSettings, _PseudonymBook, anonymize_table, is_table_file  # noqa: E402

CF = "RSSMRA85T10A562S"


def _run_guard(payload: dict) -> dict:
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
        clin_guard.main()
    return json.loads(buf.getvalue()) if buf.getvalue().strip() else {}


class TestTxtEDocxInLotto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data_dir = self.root / ".clin"
        p1 = mock.patch.object(clin_settings, "DATA_DIR", self.data_dir)
        p2 = mock.patch.object(clin_settings, "PATH", self.data_dir / "impostazioni.json")
        p3 = mock.patch.object(clin, "MAP_DIR", self.data_dir)
        p4 = mock.patch.object(clin, "MAP_FILE", self.data_dir / "segnaposto.json")
        p5 = mock.patch.dict(os.environ, {"CLIN_CARTELLE": str(self.root)})
        for p in (p1, p2, p3, p4, p5):
            p.start()
            self.addCleanup(p.stop)

    def test_txt_prosa_non_lascia_prima_riga_in_chiaro(self):
        txt = self.root / "referto_rossi.txt"
        txt.write_text(
            f"Paziente: ROSSI MARIO, nato il 10/12/1985, CF {CF}\n"
            "Ricovero per dispnea. Rossi riferisce febbre da 3 giorni.\n",
            encoding="utf-8",
        )
        self.assertFalse(is_table_file(txt))
        clin_mcp.tool_crea_copie_anonime({"percorso": str(self.root)})
        outs = list((self.root / "Clin_anonimizzati").glob("*.txt"))
        self.assertEqual(len(outs), 1)
        self.assertNotIn("rossi", outs[0].name.lower())
        content = outs[0].read_text(encoding="utf-8")
        for leak in ("ROSSI", "Rossi", "MARIO", "1985", CF):
            self.assertNotIn(leak, content)
        self.assertIn("febbre da 3 giorni", content)

    def test_txt_tabellare_resta_tabella(self):
        tsv_txt = self.root / "coorte.txt"
        tsv_txt.write_text(
            f"Paziente\tCF\tDiagnosi\nRossi Mario\t{CF}\tPolmonite\nBianchi Anna\tBNCNNA90A41H501U\tAsma\n",
            encoding="utf-8",
        )
        self.assertTrue(is_table_file(tsv_txt))
        clin_mcp.tool_crea_copie_anonime({"percorso": str(tsv_txt)})
        out = next((self.root / "Clin_anonimizzati").glob("*.txt")).read_text(encoding="utf-8-sig")
        self.assertIn("PAZ-0001", out)
        self.assertNotIn("Rossi", out)

    def test_docx_paragrafi_vuoti_revisioni_tab_e_metadati(self):
        src = self.root / "dimissione_ferrari.docx"
        out = self.root / "out.docx"
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p w14:paraId="0001"/>'
            '<w:tbl><w:tr>'
            '<w:tc><w:p><w:r><w:t>Paziente:</w:t></w:r></w:p></w:tc>'
            '<w:tc><w:p><w:r><w:t>Ferrari Giulia</w:t></w:r></w:p></w:tc>'
            '</w:tr></w:tbl>'
            '<w:p><w:r><w:t>Medico:</w:t><w:tab/><w:t>Paolo Neri</w:t><w:br/>'
            '<w:t>Ferrari apiretica.</w:t></w:r>'
            '<w:del><w:r><w:delText>Ferrari Giulia CF RSSMRA85T10A562S</w:delText></w:r></w:del>'
            '</w:p>'
            '</w:body></w:document>'
        )
        core_xml = (
            '<cp:coreProperties xmlns:cp="x" xmlns:dc="y">'
            '<dc:title>Referto Ferrari Giulia</dc:title>'
            '<dc:creator>Dott. Paolo Neri</dc:creator>'
            '<dc:subject>Cartella Ferrari</dc:subject>'
            '</cp:coreProperties>'
        )
        app_xml = '<Properties><Company>Ospedale San Camillo</Company><Manager>Neri</Manager></Properties>'
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("word/document.xml", doc_xml)
            z.writestr("docProps/core.xml", core_xml)
            z.writestr("docProps/app.xml", app_xml)
            z.writestr("docProps/custom.xml", "<Properties>Ferrari</Properties>")
            z.writestr("docProps/thumbnail.jpeg", b"THUMBNAIL_FERRARI")

        mapping, _, _ = redact_docx_file(src, out)
        self.assertTrue(any(v == "Ferrari Giulia" for v in mapping.values()))
        with zipfile.ZipFile(out) as z:
            names = set(z.namelist())
            self.assertNotIn("docProps/custom.xml", names)
            self.assertNotIn("docProps/thumbnail.jpeg", names)
            raw_all = b"".join(z.read(n) for n in names).decode("utf-8", "replace")
            for leak in ("Ferrari", "Giulia", "Paolo Neri", "San Camillo", "RSSMRA"):
                self.assertNotIn(leak, raw_all)
            self.assertIn("<w:tbl>", z.read("word/document.xml").decode("utf-8"))
            self.assertIn("apiretica", raw_all)

        text_extract = anonymize_file(src).text
        for leak in ("Ferrari", "Giulia", "Paolo Neri", "RSSMRA"):
            self.assertNotIn(leak, text_extract)


class TestGuardiaSicurezza(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.dir = self.parent / "studio"
        self.dir.mkdir()
        (self.dir / ".clin-protetto").write_text("attiva")
        (self.dir / "coorte.csv").write_text(f"Paziente,CF\nROSSI MARIO,{CF}\n", encoding="utf-8")
        (self.dir / "Clin_anonimizzati").mkdir()
        (self.dir / "Clin_anonimizzati" / "coorte_ANONIMIZZATO.csv").write_text("Paziente\nPAZ-0001\n")

        self.home = self.parent / "clin_home"
        self.home.mkdir()
        for target, attr, val in (
            (clin_guard, "READS_DIR", self.home / "letture"),
            (clin, "MAP_DIR", self.home),
            (clin, "MAP_FILE", self.home / "segnaposto.json"),
            (clin_settings, "DATA_DIR", self.home),
            (clin_settings, "PATH", self.home / "impostazioni.json"),
        ):
            p = mock.patch.object(target, attr, val)
            p.start()
            self.addCleanup(p.stop)

    def pre(self, tool, tool_input, cwd=None):
        return _run_guard({
            "hook_event_name": "PreToolUse",
            "tool_name": tool,
            "cwd": str(cwd or self.dir),
            "tool_input": tool_input,
        })

    def test_traversal_e_symlink_bloccati(self):
        # Clin_anonimizzati/../coorte.csv non deve essere scambiato per file anonimizzato
        out = self.pre("Read", {"file_path": "Clin_anonimizzati/../coorte.csv"})["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "allow")
        self.assertNotIn("ROSSI", Path(out["updatedInput"]["file_path"]).read_text())

        self.assertEqual(
            self.pre("Bash", {"command": "cat Clin_anonimizzati/../coorte.csv"})
            ["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

        # Symlink dentro Clin_anonimizzati che punta all'originale
        sym = self.dir / "Clin_anonimizzati" / "finto_ANONIMIZZATO.csv"
        sym.symlink_to(self.dir / "coorte.csv")
        out_sym = self.pre("Read", {"file_path": str(sym)})["hookSpecificOutput"]
        self.assertNotIn("ROSSI", Path(out_sym["updatedInput"]["file_path"]).read_text())
        self.assertEqual(
            self.pre("Bash", {"command": f"cat {sym}"})["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )

    def test_cp_mv_rg_grep_e_wildcard_bloccati(self):
        for cmd in (
            "cp coorte.csv coorte.log",
            "mv coorte.csv altro.bak",
            "rm coorte.csv",
            "rg ROSSI",
            "grep -rn ROSSI .",
            "bash -lc 'rg ROSSI'",
            "cat *",
        ):
            res = self.pre("Bash", {"command": cmd})
            self.assertEqual(res.get("hookSpecificOutput", {}).get("permissionDecision"), "deny", cmd)

        # ricerche ristrette a codice o a Clin_anonimizzati restano permesse
        for ok_cmd in ("rg -t py def", "rg PAZ Clin_anonimizzati/"):
            self.assertEqual(self.pre("Bash", {"command": ok_cmd}), {}, ok_cmd)

    def test_immagini_protette(self):
        webp = self.dir / "referto.webp"
        webp.write_bytes(b"RIFF....WEBP")
        out = self.pre("Read", {"file_path": "referto.webp"})["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")

    def test_accesso_da_cartella_esterna_non_aggira_la_guardia(self):
        # cwd e' self.parent (senza .clin-protetto), ma il bersaglio e' dentro self.dir
        self.assertEqual(
            self.pre("Bash", {"command": f"cat {self.dir / 'coorte.csv'}"}, cwd=self.parent)
            ["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )
        self.assertEqual(
            self.pre("Grep", {"pattern": "ROSSI", "path": str(self.dir)}, cwd=self.parent)
            ["hookSpecificOutput"]["permissionDecision"],
            "deny",
        )
        ag = _run_guard({
            "toolCall": {"name": "view_file", "args": {"AbsolutePath": str(self.dir / "coorte.csv")}},
            "workspacePaths": [str(self.parent)],
        })
        self.assertEqual(ag["decision"], "allow")
        self.assertNotIn("ROSSI", Path(ag["overwrite"]["AbsolutePath"]).read_text())

    def test_tabelle_clin_e_risultati_esterni_negati(self):
        clin.save_mapping({"[PAZIENTE_1]": "ROSSI MARIO"})
        ext_res = self.parent / "risultati_esterni"
        clin_settings.save({"cartella_risultati": str(ext_res)})
        (self.dir / "nota.md").write_text("Esito per [PAZIENTE_1].\n", encoding="utf-8")
        written = clin_results.reidentify(self.dir)
        self.assertEqual(len(written), 1)
        self.assertTrue((ext_res / ".clin-risultati").is_file())
        self.assertEqual(oct(ext_res.stat().st_mode & 0o777), "0o700")

        # anche con cwd fuori dallo studio, né i risultati né segnaposto.json sono leggibili
        for target in (ext_res / "nota.md", self.home / "segnaposto.json"):
            res = self.pre("Read", {"file_path": str(target)}, cwd=self.parent)
            self.assertEqual(res["hookSpecificOutput"]["permissionDecision"], "deny", str(target))
            res_sh = self.pre("Bash", {"command": f"cat {target}"}, cwd=self.parent)
            self.assertEqual(res_sh["hookSpecificOutput"]["permissionDecision"], "deny", str(target))

        with self.assertRaises(ValueError):
            check_path(ext_res / "nota.md", [self.parent])

    def test_symlink_ignorato_in_reidentify_e_nessuna_doppia_sostituzione(self):
        evil = self.parent / "esfiltrato.md"
        evil.write_text("", encoding="utf-8")
        clin.save_mapping({"[ID_CLINICO_1]": "PAZ-0001"})
        (self.home / "pseudonimi.json").write_text(
            json.dumps({"codici": {}, "originali": {"PAZ-0001": "ROSSI MARIO"}}), encoding="utf-8"
        )
        # il valore originale "PAZ-0001" di [ID_CLINICO_1] non deve diventare "ROSSI MARIO"
        self.assertEqual(
            clin_results.restore("Codice [ID_CLINICO_1] per PAZ-0001", {"[ID_CLINICO_1]": "PAZ-0001"},
                                 {"PAZ-0001": "ROSSI MARIO"}),
            "Codice PAZ-0001 per ROSSI MARIO",
        )
        # un link simbolico nello studio non viene processato da reidentify
        (self.dir / "link.md").symlink_to(evil)
        (self.dir / "vero.md").write_text("Paziente PAZ-0001\n", encoding="utf-8")
        written = clin_results.reidentify(self.dir)
        self.assertEqual([p.name for p in written], ["vero.md"])


class TestNominativiETabelle(unittest.TestCase):
    def test_particelle_apostrofi_e_cognome_virgola_nome(self):
        casi = [
            ("Paziente: Lo Iacono Salvatore. Iacono riferisce febbre.", ("Lo Iacono", "Iacono", "Salvatore")),
            ("Paziente: Jan van der Berg. Berg refers pain.", ("Jan", "Berg")),
            ("Paziente: Marco de Luca. De Luca riferisce tosse.", ("Marco", "Luca")),
            ("Paziente: Luca d'Amico. Riferisce d'Amico dolore.", ("Luca", "d'Amico")),
            ("ROSSI, Mario\nRossi riferisce febbre.", ("ROSSI", "Mario", "Rossi")),
            ("Paziente Mario Rossi. Rossi riferisce febbre.", ("Mario", "Rossi")),
            ("Paziente: lo iacono salvatore.", ("iacono", "salvatore")),
        ]
        for testo, leaks in casi:
            out = anonymize_text(testo).text
            for leak in leaks:
                self.assertNotIn(leak, out, f"{leak} rimasto in: {out}")

    def test_medico_e_paziente_omonimi_restano_distinti(self):
        for s in (
            "Visitato dal Dott. Luca Rossi.\nIl sig. Rossi lamenta febbre.\nPaziente: Mario Rossi.",
            "Il sig. Rossi lamenta febbre.\nVisitato dal Dott. Luca Rossi.\nPaziente: Mario Rossi.",
        ):
            r = anonymize_text(s)
            self.assertIn("Dott. [MEDICO_1]", r.text)
            self.assertIn("sig. [PAZIENTE_1]", r.text)
            self.assertIn("Paziente: [PAZIENTE_1]", r.text)
            self.assertEqual(r.mapping["[MEDICO_1]"], "Luca Rossi")
            self.assertEqual(r.mapping["[PAZIENTE_1]"], "Mario Rossi")

    def test_original_case_trova_tutte_le_occorrenze(self):
        txt = "Paziente ROSSI e poi firmato da rossi in calce."
        got = clin_llm.original_case([("Rossi", "PERSONA")], txt)
        self.assertIn(("ROSSI", "PERSONA"), got)
        self.assertIn(("rossi", "PERSONA"), got)

    def test_propagazione_medici_e_familiari_nelle_note_tabellari(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "studio.csv"
            with open(p, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows([
                    ["Paziente", "Medico refertante", "Familiare", "Note"],
                    ["Rossi Mario", "Paolo Neri", "Anna Bianchi", "Discusso con Neri e con Bianchi"],
                ])
            out = Path(d) / "out.csv"
            anonymize_table(p, out, TableSettings(keep_labels=True, pseudonyms=_PseudonymBook()))
            res_csv = out.read_text(encoding="utf-8-sig")
            for leak in ("Rossi", "Neri", "Bianchi"):
                self.assertNotIn(leak, res_csv)

            res_txt = anonymize_file(p).text
            for leak in ("Rossi", "Neri", "Bianchi"):
                self.assertNotIn(leak, res_txt)
            self.assertIn("[MEDICO_1]", res_txt)
            self.assertIn("[PERSONA_1]", res_txt)

    def test_note_tabellari_non_confondono_pazienti_di_altre_righe(self):
        from clin_text import _Registry
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tavi.csv"
            with open(p, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows([
                    ["Cognome", "Nome", "Note"],
                    ["Rossi", "Mario", "Rossi riferisce tramite la moglie Anna stabilita'"],
                    ["Bianchi", "Anna", "Bianchi stazionaria"],
                ])
            out = Path(d) / "out.csv"
            reg = _Registry([])
            anonymize_table(p, out, TableSettings(keep_labels=True, pseudonyms=_PseudonymBook(), registry=reg))
            rows = list(csv.reader(out.read_text(encoding="utf-8-sig").splitlines()))
            # riga 1 (Mario Rossi = PAZ-0001): "Rossi" -> PAZ-0001, ma "Anna" -> [PERSONA_1], mai PAZ-0002!
            self.assertIn("PAZ-0001 riferisce", rows[1][2])
            self.assertIn("la moglie [PERSONA_1]", rows[1][2])
            self.assertNotIn("PAZ-0002", rows[1][2])
            # riga 2 (Anna Bianchi = PAZ-0002): "Bianchi" -> PAZ-0002
            self.assertIn("PAZ-0002 stazionaria", rows[2][2])

    def test_protezione_input_uguale_output(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.csv"
            f.write_text("Paziente\nRossi Mario\n", encoding="utf-8")
            self.assertIsNotNone(anonymize_table(f, f, TableSettings()).error)
            pdf = Path(d) / "a.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            self.assertIsNotNone(anonymize_document(pdf, pdf).error)

    def test_ponte_web_ocr_e_safe_name_cognome_singolo(self):
        bundle = [{"titolo": "Foto 1", "pagine": ["CF RSSMRA857T10A562S e PCR 0,45 mg/dL"], "ocr": True}]
        out_bundle = json.loads(clin_web.run_bundle(json.dumps(bundle), 10, "{}"))["text"]
        self.assertNotIn("RSSMRA", out_bundle)
        self.assertIn("PCR 0,45 mg/dL", out_bundle)

        plan = json.loads(clin_web.plan_pages(
            json.dumps(["CF RSSMRA857T10A562S"]), "{}", json.dumps([True])
        ))
        self.assertTrue(plan["spans"][0])

        self.assertEqual(
            clin_web.safe_name("dimissione_ferrari", json.dumps({"[PAZIENTE_1]": "Ferrari"})),
            "dimissione_ANON",
        )


class TestNominativoGestionaliPS(unittest.TestCase):
    """Cartelle di pronto soccorso: "Cognome*Nome ROSSI*MARIO" e luogo di nascita dopo la data."""

    def _anon(self, text):
        return json.loads(clin_web.run_text(text, 10, "{}"))["text"]

    def test_nominativo_con_asterisco_e_barra(self):
        for text in ("Cognome*Nome ROSSINI*MARCO\nTelefono 3331234567",
                     "Cognome/Nome: ROSSINI/MARCO",
                     "Nome*Cognome MARCO*ROSSINI"):
            out = self._anon(text)
            self.assertNotIn("ROSSINI", out, text)
            self.assertNotIn("MARCO", out, text)

    def test_ricorrenze_del_nominativo_con_asterisco(self):
        out = self._anon("Cognome*Nome ROSSINI*MARCO\nOggi MARCO sta bene, Marco riferisce dolore.")
        self.assertNotIn("MARCO", out)
        self.assertNotIn("Marco", out)
        self.assertEqual(set(re.findall(r"\[([A-Z_]+)_\d+\]", out)) & {"PERSONA"}, set())

    def test_luogo_di_nascita_dopo_la_data(self):
        for text in ("Nato il 03/05/2014     a     MONTEROTONDO\nRegione LAZIO",
                     "nata il 3/5/2014 a San Giovanni in Persiceto (BO)"):
            out = self._anon(text)
            self.assertNotIn("MONTEROTONDO", out)
            self.assertNotIn("Persiceto", out)
            if "LAZIO" in text:
                self.assertIn("Regione LAZIO", out)

    def test_nato_a_termine_resta_clinico(self):
        self.assertIn("nato a termine", self._anon("Paziente: ROSSINI MARCO\nnato a termine da parto eutocico"))


if __name__ == "__main__":
    unittest.main()
