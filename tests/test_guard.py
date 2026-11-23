"""Guardia per agenti IA (clin_guard.py) con payload simulati degli hook."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CLIN_LLM"] = "0"
sys.path.insert(0, str(ROOT))

import clin_guard  # noqa: E402


def run(payload: dict) -> dict:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
        clin_guard.main()
    return json.loads(buf.getvalue()) if buf.getvalue().strip() else {}



class TestGuardia(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "coorte.csv").write_text("Paziente,CF\nROSSI MARIO,RSSMRA85T10A562S\n", encoding="utf-8")
        (self.dir / ".clin-protetto").write_text("attiva")
        (self.dir / "Clin_anonimizzati").mkdir()
        (self.dir / "Clin_anonimizzati" / "coorte_ANONIMIZZATO.csv").write_text("Paziente\nPAZ-0001\n")
        self.home = tempfile.mkdtemp()
        self.patch = unittest.mock.patch.object(clin_guard, "READS_DIR", Path(self.home) / "letture")
        self.patch.start()
        self.map_patch = unittest.mock.patch("clin.MAP_DIR", Path(self.home))
        self.map_patch.start()
        unittest.mock.patch("clin.MAP_FILE", Path(self.home) / "segnaposto.json").start()
        import clin_settings  # impostazioni predefinite, mai quelle reali dell'utente
        unittest.mock.patch.object(clin_settings, "PATH", Path(self.home) / "impostazioni.json").start()

    def tearDown(self):
        unittest.mock.patch.stopall()
        import anonymize_engine
        anonymize_engine.DATE_SHIFT = None   # le date spostate valgono solo per i punti d'ingresso degli agenti

    def pre(self, tool, tool_input):
        return run({"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": str(self.dir),
                    "tool_input": tool_input})

    def test_read_reindirizzato_alla_copia(self):
        out = self.pre("Read", {"file_path": "coorte.csv"})["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "allow")
        text = Path(out["updatedInput"]["file_path"]).read_text(encoding="utf-8")
        self.assertNotIn("ROSSI", text)
        self.assertNotIn("RSSMRA", text)

    def test_bash_negato_sugli_originali(self):
        for cmd in ("cat coorte.csv", "head -3 coorte.csv | sort",
                    "python3 -c \"import pandas as pd; pd.read_csv('coorte.csv')\"", "cat *.csv"):
            self.assertEqual(self.pre("Bash", {"command": cmd})["hookSpecificOutput"]["permissionDecision"],
                             "deny", cmd)

    def test_output_dell_agente_permesso(self):
        import os, time
        later = time.time() + 5
        cmd = "python3 -c \"import pandas as pd; pd.read_excel('Clin_anonimizzati/x.xlsx').to_csv('analisi/esiti.csv')\""
        self.assertEqual(self.pre("Bash", {"command": cmd}), {})            # file nuovo: output
        (self.dir / "analisi").mkdir()
        out = self.dir / "analisi" / "esiti.csv"
        out.write_text("paziente,esito\nPAZ-0001,vivo\n")
        os.utime(out, (later, later))                                       # creato dopo /clin
        self.assertEqual(self.pre("Bash", {"command": "cat analisi/esiti.csv"}), {})
        senza = self.dir / "analisi" / "nuovo_originale.csv"                # nessun segnaposto
        senza.write_text("Paziente\nROSSI MARIO\n")
        os.utime(senza, (later, later))
        self.assertEqual(self.pre("Bash", {"command": "cat analisi/nuovo_originale.csv"})
                         ["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_comandi_riservati_all_utente(self):
        clin_py = ROOT / "clin.py"
        for cmd in (f"python3 {clin_py} originale PAZ-0001", f'"/usr/bin/python3" "{clin_py}" ripristina',
                    f"python3 {clin_py} impostazioni categorie_escluse Date", f"cd . && python3 {clin_py} disinstalla"):
            self.assertEqual(self.pre("Bash", {"command": cmd})["hookSpecificOutput"]["permissionDecision"], "deny", cmd)
        for cmd in (f"python3 {clin_py} avvia .", f"python3 {clin_py} stato", f"python3 {clin_py} impostazioni"):
            self.assertEqual(self.pre("Bash", {"command": cmd}), {}, cmd)

    def test_formati_non_anonimizzabili_chiusi(self):
        for name in ("caso_clinico.pptx", "registro.sav", "coorte.dta"):
            (self.dir / name).write_bytes(b"ROSSI MARIO")
            self.assertEqual(self.pre("Read", {"file_path": name})["hookSpecificOutput"]["permissionDecision"], "deny", name)
            self.assertEqual(self.pre("Bash", {"command": f"strings {name}"})["hookSpecificOutput"]["permissionDecision"],
                             "deny", name)

    def test_word_e_powerpoint_ricondotti(self):
        import zipfile
        import clin, clin_results
        clin.save_mapping({"[PAZIENTE_1]": "ROSSI & MARIO", "[MEDICO_1]": "Giulia Bianchi"})
        (self.dir / "analisi").mkdir()
        parts = {
            "analisi/lettera.docx": ("word/document.xml",
                '<w:document xmlns:w="x"><w:body><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Paziente [PAZIENTE</w:t></w:r>'
                '<w:r><w:t>_1] dimesso.</w:t></w:r></w:p><w:p><w:r><w:t>Firma: [MEDICO_1]</w:t></w:r></w:p></w:body></w:document>'),
            "analisi/slide.pptx": ("ppt/slides/slide1.xml",
                '<p:sld xmlns:a="x" xmlns:p="y"><a:p><a:r><a:rPr b="1"/><a:t>Caso di [PAZIENTE_1]</a:t></a:r></a:p></p:sld>'),
        }
        for rel, (member, xml) in parts.items():
            with zipfile.ZipFile(self.dir / rel, "w") as z:
                z.writestr("[Content_Types].xml", "<Types/>")
                z.writestr(member, xml)
        written = clin_results.reidentify(self.dir)
        self.assertEqual(len(written), 2)
        out = clin_results.clin_settings.results_dir(self.dir) / "analisi" if hasattr(clin_results, "clin_settings") else None
        import clin_settings
        out = clin_settings.results_dir(self.dir) / "analisi"
        doc = zipfile.ZipFile(out / "lettera.docx").read("word/document.xml").decode()
        self.assertIn("Paziente ROSSI &amp; MARIO dimesso.", doc)      # segnaposto spezzato tra due run
        self.assertIn("Firma: Giulia Bianchi", doc)
        self.assertIn("<w:rPr><w:b/></w:rPr>", doc)                     # formattazione intatta
        sld = zipfile.ZipFile(out / "slide.pptx").read("ppt/slides/slide1.xml").decode()
        self.assertIn('<a:rPr b="1"/><a:t>Caso di ROSSI &amp; MARIO</a:t>', sld)
        self.assertEqual(zipfile.ZipFile(out / "slide.pptx").read("[Content_Types].xml"), b"<Types/>")
        # i file dell'agente con segnaposto restano leggibili dall'agente; l'originale no
        import os, time
        later = time.time() + 5
        os.utime(self.dir / "analisi" / "slide.pptx", (later, later))
        self.assertEqual(self.pre("Bash", {"command": "python3 aggiorna.py analisi/slide.pptx"}), {})

    def test_date_dei_fogli_traslate_e_ricondotte(self):
        import datetime
        import os
        from openpyxl import Workbook, load_workbook
        import clin_mcp, clin_results, clin_settings, tabular_engine
        unittest.mock.patch.object(clin_settings, "DATA_DIR", Path(self.home)).start()
        unittest.mock.patch.dict(os.environ, {"CLIN_CARTELLE": str(self.dir)}).start()
        wb = Workbook()
        wb.active.append(["Paziente", "Data di nascita", "Data intervento", "Data decesso", "Note"])
        wb.active.append(["ROSSI MARIO", datetime.datetime(1950, 3, 12), datetime.datetime(2023, 5, 14), "20/11/2023", "ok"])
        wb.save(self.dir / "registro.xlsx")
        out = clin_mcp.tool_crea_copie_anonime({"percorso": str(self.dir)})
        self.assertIn("spostate di 400 anni esatti", out)
        days = clin_settings.date_shift(create=False)
        self.assertGreaterEqual(days, 80000)
        row = [c.value for c in load_workbook(self.dir / "Clin_anonimizzati" / "registro_ANONIMIZZATO.xlsx").active[2]]
        self.assertEqual(row[0], "PAZ-0001")
        nascita, intervento, decesso = row[1], row[2], row[3]
        self.assertIsInstance(intervento, datetime.datetime)            # resta una data di Excel
        self.assertGreaterEqual(nascita.year, 2100)
        self.assertEqual((intervento - nascita).days, (datetime.datetime(2023, 5, 14) - datetime.datetime(1950, 3, 12)).days)
        d, m, y = (int(x) for x in decesso.split("/"))
        self.assertEqual((datetime.datetime(y, m, d) - intervento).days, 190)   # intervallo esatto
        # l'agente scrive risultati con le date traslate: tornano quelle vere
        (self.dir / "analisi").mkdir()
        (self.dir / "analisi" / "decessi.md").write_text(
            f"PAZ-0001 operato il {intervento.date().isoformat()}, deceduto il {decesso}. Relazione del 23/11/2026.\n")
        res = Workbook(); res.active.append(["PAZ-0001", intervento]); res.save(self.dir / "analisi" / "date.xlsx")
        self.assertEqual(len(clin_results.reidentify(self.dir)), 2)
        real = clin_settings.results_dir(self.dir) / "analisi"
        self.assertEqual((real / "decessi.md").read_text(),
                         "ROSSI MARIO operato il 2023-05-14, deceduto il 20/11/2023. Relazione del 23/11/2026.\n")
        self.assertEqual(load_workbook(real / "date.xlsx").active["B1"].value, datetime.datetime(2023, 5, 14))
        self.assertIsNone(tabular_engine.shift_date("Hb 13,5", days))
        self.assertIsNone(tabular_engine.shift_date("12-05", days))

    def test_date_a_parole_e_modalita_calendario(self):
        import datetime
        import clin_results, clin_settings
        days = 80123
        moved = lambda y, m, d: datetime.date(y, m, d) + datetime.timedelta(days=days)
        a, b = moved(2023, 5, 14), moved(2024, 1, 3)
        it, en = clin_results._IT, clin_results._EN
        text = (f"Operato il {a.day} {it[a.month - 1]} {a.year}, rivisto il {b.day:02d} {it[b.month - 1][:3].capitalize()}. {b.year}; "
                f"{en[a.month - 1].capitalize()} {a.day}, {a.year}. PCR 2243 mg/L, relazione del 23 novembre 2026.")
        self.assertEqual(clin_results.unshift_dates(text, days),
                         "Operato il 14 maggio 2023, rivisto il 03 Gen. 2024; May 14, 2023. "
                         "PCR 2243 mg/L, relazione del 23 novembre 2026.")
        # ogni forma in cui un agente puo' scrivere una data, con il giorno della settimana ricalcolato
        for shifted_form, real_form in (
                ("{0:%Y/%m/%d}", "2023/05/14"), ("{0:%d.%m.%Y}", "14.05.2023"), ("{0:%d-%m-%Y}", "14-05-2023"),
                ("{0:%Y%m%d}", "20230514"), ("{0:%Y-%m-%d} 08:30:00", "2023-05-14 08:30:00"),
                ("{0.day}-" + it[a.month - 1][:3] + "-{0.year}", "14-mag-2023"),
                (clin_results._DAYS_IT[a.weekday()] + " {0.day} " + it[a.month - 1] + " {0.year}", "domenica 14 maggio 2023"),
                (clin_results._DAYS_EN[a.weekday()].capitalize() + ", " + en[a.month - 1][:3].capitalize() + " {0.day}th, {0.year}",
                 "Sunday, May 14th, 2023"),
                ("{0.day}th of " + en[a.month - 1].capitalize() + " {0.year}", "14th of May 2023")):
            self.assertEqual(clin_results.unshift_dates(shifted_form.format(a), days), real_form)
        # 400 anni esatti: stesso giorno della settimana, stessi intervalli, 29 febbraio compreso
        cal = clin_settings.CALENDAR_SHIFT
        for y, m, d in ((2023, 5, 14), (2000, 2, 29), (1950, 3, 12)):
            real = datetime.date(y, m, d)
            shifted = real + datetime.timedelta(days=cal)
            self.assertEqual((shifted.year, shifted.month, shifted.day, shifted.weekday()), (y + 400, m, d, real.weekday()))
        text = ("Interventi nel 2423: 41; maggio 2423: 7; 2423-05; periodo 2421-2423; Q1 2424; inverno 2423; "
                "14 maggio 2423; 2423-05-14; il 2423 (2422); dal 2421 al 2424; 2423Q2. "
                "Leucociti 2400, diluito in 2400 ml, 12/2400 pazienti, range 2400-2500 ml, in 2400 pazienti.")
        self.assertEqual(clin_results.unshift_dates(text, cal),
                         "Interventi nel 2023: 41; maggio 2023: 7; 2023-05; periodo 2021-2023; Q1 2024; inverno 2023; "
                         "14 maggio 2023; 2023-05-14; il 2023 (2022); dal 2021 al 2024; 2023Q2. "
                         "Leucociti 2400, diluito in 2400 ml, 12/2400 pazienti, range 2400-2500 ml, in 2400 pazienti.")
        # tabella per anno prodotta dall'agente: torna agli anni veri, i conteggi no
        unittest.mock.patch.object(clin_settings, "DATA_DIR", Path(self.home)).start()
        clin_settings.save({"date_calendario": True})
        self.assertEqual(clin_settings.date_shift(), cal)
        (self.dir / "analisi").mkdir()
        (self.dir / "analisi" / "per_anno.csv").write_text("anno,interventi,leucociti\n2422,2400,2400\n2423,41,2350\n")
        self.assertEqual(len(clin_results.reidentify(self.dir)), 1)
        self.assertEqual((clin_settings.results_dir(self.dir) / "analisi" / "per_anno.csv").read_text().split(),
                         ["anno,interventi,leucociti", "2022,2400,2400", "2023,41,2350"])

    def test_date_nei_documenti_spostate_e_ricondotte(self):
        import os, zipfile
        import anonymize_engine, clin_mcp, clin_results, clin_settings
        from clin_text import _docx_text
        unittest.mock.patch.object(clin_settings, "DATA_DIR", Path(self.home)).start()
        unittest.mock.patch.dict(os.environ, {"CLIN_CARTELLE": str(self.dir)}).start()
        letter = ("Paziente: Mario Rossi, nato il 12/03/1958 a Torino\nRicoverato dal 02/11/2023 al 09/11/2023.\n"
                  "Toracentesi il 4 novembre 2023. In terapia da marzo 2021. Leucociti 2400.\n")
        (self.dir / "lettera.txt").write_text(letter, encoding="utf-8")
        body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{l}</w:t></w:r></w:p>' for l in letter.splitlines())
        with zipfile.ZipFile(self.dir / "lettera.docx", "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", f'<w:document xmlns:w="x"><w:body>{body}</w:body></w:document>')
        clin_mcp.tool_crea_copie_anonime({"percorso": str(self.dir)})
        copies = self.dir / "Clin_anonimizzati"
        for text in (next(copies.glob("lettera*.txt")).read_text(), _docx_text(next(copies.glob("lettera*.docx")))):
            for moved in ("12/03/2358", "02/11/2423", "09/11/2423", "4 novembre 2423", "marzo 2421", "Leucociti 2400"):
                self.assertIn(moved, text)
            for gone in ("1958", "2023", "2021", "Torino", "Rossi", "[DATA_1]"):
                self.assertNotIn(gone, text)
        # la lettura diretta passa dalla stessa regola e lo dice all'agente
        read = self.pre("Read", {"file_path": "lettera.txt"})["hookSpecificOutput"]["updatedInput"]["file_path"]
        self.assertIn("02/11/2423", Path(read).read_text())
        self.assertIn("400 anni", Path(read).read_text())
        # un testo gia' spostato non viene spostato una seconda volta
        from clin_text import anonymize_text
        self.assertIn("02/11/2423", anonymize_text("Ricoverato dal 02/11/2423 per polmonite.").text)
        # ritorno
        (self.dir / "analisi").mkdir()
        (self.dir / "analisi" / "degenza.md").write_text("Degenza di 7 giorni, dal 02/11/2423 al giovedì 9 novembre 2423.\n")
        clin_results.reidentify(self.dir)
        self.assertEqual((clin_settings.results_dir(self.dir) / "analisi" / "degenza.md").read_text(),
                         "Degenza di 7 giorni, dal 02/11/2023 al giovedì 9 novembre 2023.\n")
        # fuori dai punti d'ingresso degli agenti (applicazione, estensione) le date restano segnaposto
        anonymize_engine.DATE_SHIFT = None
        self.assertIn("[DATA_", anonymize_text("Ricoverato dal 02/11/2023 per polmonite.").text)

    def test_messaggi_con_dati_gia_anonimi_passano(self):
        ask = lambda text: run({"hook_event_name": "UserPromptSubmit", "cwd": str(self.dir), "prompt": text})
        for ok in ("Il paziente PAZ-0002, nato il 12/03/2358, e' stato operato il 14/05/2423: calcola l'eta'.",
                   "Per [PAZIENTE_1] nato il [DATA_NASCITA_1] prepara la lettera.",
                   "Riassumi il documento del 2024 e il documento n. 3 del registro.",
                   "Data di nascita: 01/01/2332, carta d'identita' ID-0003."):
            self.assertEqual(ask(ok), {}, ok)
        for stop in ("Il paziente e' nato il 12/03/1958 a Torino.", "Carta d'identita' n. CA12345AB di Mario.",
                     "CF RSSMRA85T10A562S"):
            self.assertEqual(ask(stop).get("decision"), "block", stop)

    def test_percorsi_esclusi_dall_utente(self):
        import os
        import clin_mcp, clin_settings
        unittest.mock.patch.object(clin_settings, "DATA_DIR", Path(self.home)).start()
        unittest.mock.patch.dict(os.environ, {"CLIN_CARTELLE": str(self.dir)}).start()
        (self.dir / "articoli").mkdir()
        (self.dir / "articoli" / "linee_guida.txt").write_text("Linee guida ESC 2024, a cura di Mario Rossi.\n")
        self.assertEqual(self.pre("Bash", {"command": "cat articoli/linee_guida.txt"})["hookSpecificOutput"]["permissionDecision"], "deny")
        clin_settings.save({"percorsi_esclusi": [str((self.dir / "articoli").resolve())]})
        self.assertEqual(self.pre("Bash", {"command": "cat articoli/linee_guida.txt"}), {})
        self.assertEqual(self.pre("Read", {"file_path": "articoli/linee_guida.txt"}), {})
        clin_mcp.tool_crea_copie_anonime({"percorso": str(self.dir)})
        self.assertFalse((self.dir / "Clin_anonimizzati" / "articoli").exists())
        # l'agente non puo' allargare l'elenco da solo
        self.assertEqual(self.pre("Bash", {"command": f"python3 {ROOT / 'clin.py'} escludi ."})
                         ["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.pre("Read", {"file_path": "coorte.csv"})["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_bash_permesso(self):
        for cmd in ("ls -la *.csv", "wc -l coorte.csv", "cat Clin_anonimizzati/*.csv",
                    "python3 analisi.py", f"python3 {ROOT / 'clin.py'} copie .",
                    "pip install -r requirements.txt", "cat LICENSE.txt"):
            self.assertEqual(self.pre("Bash", {"command": cmd}), {}, cmd)

    def test_grep(self):
        self.assertEqual(self.pre("Grep", {"pattern": "ROSSI"})["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.pre("Grep", {"pattern": "x", "glob": "*.py"}), {})

    def test_output_ripulito(self):
        out = run({"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(self.dir),
                   "tool_response": {"stdout": "Paziente: ROSSI MARIO tel 333 1234567", "stderr": "",
                                     "interrupted": False, "isImage": False}})
        new = out["hookSpecificOutput"]["updatedToolOutput"]
        self.assertNotIn("ROSSI", new["stdout"])
        self.assertEqual(set(new), {"stdout", "stderr", "interrupted", "isImage"})

    def test_prompt(self):
        blocked = run({"hook_event_name": "UserPromptSubmit", "cwd": str(self.dir),
                       "prompt": "il paziente RSSMRA85T10A562S"})
        self.assertEqual(blocked["decision"], "block")
        for ok in ("manda il report via Slack e chiudi il ticket 4521 entro il 12/03",
                   "il paziente RSSMRA85T10A562S [clin:ok]"):
            self.assertEqual(run({"hook_event_name": "UserPromptSubmit", "cwd": str(self.dir), "prompt": ok}), {}, ok)

    def test_antigravity(self):
        out = run({"toolCall": {"name": "view_file", "args": {"AbsolutePath": str(self.dir / "coorte.csv")}},
                   "workspacePaths": [str(self.dir)]})
        self.assertEqual(out["decision"], "allow")
        self.assertNotIn("ROSSI", Path(out["overwrite"]["AbsolutePath"]).read_text(encoding="utf-8"))
        out = run({"toolCall": {"name": "run_command", "args": {"CommandLine": "cat coorte.csv",
                                                               "Cwd": str(self.dir)}},
                   "workspacePaths": [str(self.dir)]})
        self.assertEqual(out["decision"], "deny")

    def test_dormiente_fuori_dalle_cartelle_attivate(self):
        (self.dir / ".clin-protetto").unlink()
        self.assertEqual(self.pre("Bash", {"command": "cat coorte.csv"}), {})
        self.assertEqual(run({"hook_event_name": "UserPromptSubmit", "cwd": str(self.dir),
                              "prompt": "il paziente RSSMRA85T10A562S"}), {})

    def test_risultati_ricondotti_e_invisibili(self):
        import clin_settings
        from openpyxl import Workbook, load_workbook
        import clin
        clin.save_mapping({"[PAZIENTE_1]": "ROSSI MARIO"})
        (Path(self.home) / "pseudonimi.json").write_text(json.dumps(
            {"codici": {"PAZ": {"mario rossi": "PAZ-0001"}}, "originali": {"PAZ-0001": "Rossi Mario"}}))
        (self.dir / "analisi").mkdir()
        (self.dir / "analisi" / "relazione.md").write_text("[PAZIENTE_1] stabile, codice PAZ-0001.\n")
        wb = Workbook()
        wb.active.append(["paziente", "esito"])
        wb.active.append(["PAZ-0001", "vivo"])
        wb.save(self.dir / "analisi" / "esiti.xlsx")
        out = run({"hook_event_name": "Stop", "cwd": str(self.dir)})
        self.assertIn("2 file", out["systemMessage"])
        res = self.dir / "Clin_risultati" / "analisi"
        self.assertEqual((res / "relazione.md").read_text(), "ROSSI MARIO stabile, codice Rossi Mario.\n")
        self.assertEqual(load_workbook(res / "esiti.xlsx").active["A2"].value, "Rossi Mario")
        self.assertEqual(oct((res / "relazione.md").stat().st_mode & 0o777), "0o600")
        # gli originali e le copie anonime non vengono toccati
        self.assertFalse((self.dir / "Clin_risultati" / "coorte.csv").exists())
        self.assertFalse((self.dir / "Clin_risultati" / "Clin_anonimizzati").exists())
        # l'agente non vede i risultati
        for tool, ti in (("Read", {"file_path": "Clin_risultati/analisi/relazione.md"}),
                         ("Bash", {"command": "cat Clin_risultati/analisi/relazione.md"}),
                         ("Grep", {"pattern": "Rossi", "glob": "*.md"})):
            self.assertEqual(self.pre(tool, ti)["hookSpecificOutput"]["permissionDecision"], "deny", tool)
        # un dato reale stampato da uno script torna segnaposto
        out = run({"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(self.dir),
                   "tool_response": {"stdout": "Rossi Mario: vivo", "stderr": "", "interrupted": False,
                                     "isImage": False}})
        self.assertNotIn("Rossi", out["hookSpecificOutput"]["updatedToolOutput"]["stdout"])
        # ripristino disattivato dalle impostazioni
        clin_settings.save({"ripristino_automatico": False})
        (self.dir / "analisi" / "nuovo.md").write_text("[PAZIENTE_1]\n")
        self.assertEqual(run({"hook_event_name": "Stop", "cwd": str(self.dir)}), {})

    def test_codex_exec_command(self):
        out = self.pre("exec_command", {"cmd": ["bash", "-lc", "sed -n 1,5p coorte.csv"]})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
