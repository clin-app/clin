"""Clin dentro un agente su server (es. sorveglianza dell'antibioticoterapia): export, referti, HL7/FHIR, API,
servizio con permessi separati, controlli in uscita e per la memoria, tabelle cifrate."""
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anonymize_engine as ae  # noqa: E402
import clin  # noqa: E402
import clin_settings  # noqa: E402

REFERTO = ("Emocoltura del 03/11/2026, Paziente: BIANCHI GIULIA, nata il 12/04/1948, letto 12, Medicina Interna 2\n"
           "Klebsiella pneumoniae KPC. Meropenem R, Ceftazidime/avibactam S.\n"
           "Terapia: piperacillina/tazobactam 4,5 g ev ogni 6 ore dal 01/11. Creatinina 1,9 mg/dL.\n"
           "Codice fiscale: BNCGLI48D52A271X. Consulenza Dott. Luca Rossi.")
TERAPIE = ("cognome,nome,data_nascita,reparto,letto,farmaco,dose,via,data_inizio,telefono\n"
           "BIANCHI,GIULIA,12/04/1948,Medicina Interna 2,12,Piperacillina/tazobactam,4.5 g q6h,ev,01/11/2026,3331234567\n")
HL7 = "\r".join([
    "MSH|^~\\&|CPOE|OSP|STEW|INF|20261103143000||RDE^O11|1|P|2.5",
    "PID|1||123456^^^OSP^MR||BIANCHI^GIULIA||19480412|F|||Via Roma 12^^Ancona||3331234567||||||BNCGLI48D52A271X",
    "PV1|1|I|MED2^4^12^OSP||||1234^ROSSI^LUCA",
    "RXE|^Q6H^^20261101|J01CR05^Piperacillina/tazobactam^ATC|4.5||g|IV",
    "NTE|1||Allergia alle penicilline riferita dalla figlia Anna Bianchi"])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "dati"
        for p in (mock.patch.object(clin, "MAP_DIR", self.data), mock.patch.object(clin, "MAP_FILE", self.data / "segnaposto.json"),
                  mock.patch.object(clin_settings, "DATA_DIR", self.data),
                  mock.patch.object(clin_settings, "PATH", self.data / "impostazioni.json")):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(setattr, ae, "DATE_SHIFT", None)


class TestDatiClinici(Base):
    def test_data_senza_anno_non_e_un_recapito(self):
        import clin_api
        out = clin_api.pseudonimizza(REFERTO)["contenuto"]
        self.assertIn("dal 01/11", out)            # con 400 anni esatti giorno e mese restano uguali
        self.assertNotIn("CONTATTO", out)
        for clinical in ("Klebsiella pneumoniae KPC", "Ceftazidime/avibactam S", "4,5 g ev", "1,9 mg/dL"):
            self.assertIn(clinical, out)

    def test_colonna_via_di_somministrazione(self):
        import clin_api
        out = clin_api.pseudonimizza(TERAPIE, "terapie.csv")["contenuto"]
        self.assertIn(",ev,", out)
        self.assertNotIn("3331234567", out)


class TestCollegamento(Base):
    def test_stesso_paziente_stesso_codice_ovunque(self):
        import clin_api
        ref = clin_api.pseudonimizza(REFERTO)["contenuto"]
        tab = clin_api.pseudonimizza(TERAPIE, "terapie.csv")["contenuto"]
        hl7 = clin_api.pseudonimizza(HL7)["contenuto"]
        for out in (ref, tab, hl7):
            self.assertIn("PAZ-0001", out)
            self.assertNotIn("BIANCHI", out.upper().replace("PAZ", ""))
        self.assertIn("ID-0001", ref)
        self.assertIn("ID-0001", hl7)
        self.assertIn("letto IDC-", ref)

    def test_ritorno_ai_dati_reali(self):
        import clin_api
        clin_api.pseudonimizza(REFERTO)
        alert = '{"paziente": "PAZ-0001", "motivo": "KPC non coperta, emocoltura del 03/11/2426"}'
        real = clin_api.ripristina(alert)
        self.assertIn("BIANCHI GIULIA", real)
        self.assertIn("03/11/2026", real)


class TestIdempotenza(Base):
    def test_ripassare_una_copia_non_cambia_nulla(self):
        import clin_api
        for contenuto, nome in ((REFERTO, ""), (TERAPIE, "terapie.csv"), (HL7, "")):
            once = clin_api.pseudonimizza(contenuto, nome)["contenuto"]
            self.assertEqual(clin_api.pseudonimizza(once, nome)["contenuto"], once, nome or contenuto[:3])


class TestSchemaColonne(Base):
    def test_ruoli_e_minimizzazione(self):
        import clin_api
        schema = {"cognome": "paziente", "nome": "paziente", "data_nascita": "data_nascita", "reparto": "clinico",
                  "letto": "id_clinico", "farmaco": "clinico", "dose": "clinico", "via": "clinico",
                  "data_inizio": "data", "*": "elimina"}
        out = clin_api.pseudonimizza(TERAPIE, "terapie.csv", schema)["contenuto"].splitlines()[1].split(",")
        self.assertEqual(out[0], "PAZ-0001")
        self.assertEqual(out[2], "12/04/2348")
        self.assertEqual(out[7], "ev")
        self.assertEqual(out[9], "")               # telefono: non dichiarato, eliminato

    def test_ruolo_errato_blocca_il_file(self):
        import clin_api
        with self.assertRaises(ValueError):
            clin_api.pseudonimizza(TERAPIE, "terapie.csv", {"cognome": "cancella"})


class TestHl7Fhir(Base):
    def test_hl7_campo_per_campo(self):
        import clin_api
        out = clin_api.pseudonimizza(HL7)["contenuto"]
        for leak in ("BIANCHI", "GIULIA", "123456", "Via Roma", "3331234567", "ROSSI", "Anna"):
            self.assertNotIn(leak, out)
        self.assertIn("J01CR05^Piperacillina/tazobactam^ATC|4.5||g|IV", out)
        self.assertIn("RXE|^Q6H^^24261101|", out)   # inizio terapia dentro RXE-1: spostato anch'esso
        self.assertIn("23480412", out)              # data di nascita spostata di 400 anni
        self.assertIn("PV1|1|I|MED2^IDC-", out)     # il reparto resta, stanza e letto diventano codici

    def test_fhir(self):
        import clin_api
        bundle = {"resourceType": "Bundle", "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1", "name": [{"family": "Bianchi", "given": ["Giulia"]}],
                          "birthDate": "1948-04-12", "telecom": [{"value": "3331234567"}],
                          "identifier": [{"system": "http://hl7.it/sid/codiceFiscale", "value": "BNCGLI48D52A271X"}]}},
            {"resource": {"resourceType": "Observation", "id": "o1", "subject": {"reference": "Patient/p1"},
                          "code": {"coding": [{"system": "http://loinc.org", "code": "2160-0"}], "text": "Creatinina"},
                          "effectiveDateTime": "2026-11-02", "valueQuantity": {"value": 1.9, "unit": "mg/dL"}}}]}
        out = json.loads(clin_api.pseudonimizza(json.dumps(bundle))["contenuto"])
        pat, obs = out["entry"][0]["resource"], out["entry"][1]["resource"]
        self.assertEqual(pat["name"], [{"text": "PAZ-0001"}])
        self.assertNotIn("telecom", pat)
        self.assertEqual(pat["birthDate"], "2348-04-12")
        self.assertEqual(obs["subject"]["reference"], "Patient/" + pat["id"])
        self.assertEqual(obs["code"]["coding"][0]["code"], "2160-0")
        self.assertEqual(obs["effectiveDateTime"], "2426-11-02")


class TestControlli(Base):
    def test_uscita_bloccata_se_resta_un_dato_noto(self):
        import clin_api
        clin_api.pseudonimizza(REFERTO)
        self.assertGreater(clin_api.residui("Rivalutare BIANCHI GIULIA domani"), 0)
        self.assertEqual(clin_api.residui("Rivalutare PAZ-0001 domani"), 0)
        with self.assertRaises(clin_api.Bloccato):
            clin_api._check_out("Il codice BNCGLI48D52A271X")

    def test_memoria_senza_dati_di_pazienti(self):
        import clin_api
        clin_api.pseudonimizza(REFERTO)
        self.assertTrue(clin_api.controlla("Regola: KPC con meropenem R, segnalare se non in terapia con "
                                           "ceftazidime/avibactam entro 24 ore.")["ammesso"])
        self.assertFalse(clin_api.controlla("PAZ-0001 ha avuto un falso positivo")["ammesso"])
        self.assertFalse(clin_api.controlla("Caso di BIANCHI GIULIA da ricordare")["ammesso"])

    def test_registro_senza_dati_personali(self):
        import clin_api
        clin_api.pseudonimizza(REFERTO)
        log = (self.data / "registro.jsonl").read_text()
        self.assertIn('"operazione": "pseudonimizza"', log)
        self.assertNotIn("BIANCHI", log)

    def test_tabelle_cifrate(self):
        import clin_api
        from cryptography.fernet import Fernet
        with mock.patch.dict(os.environ, {"CLIN_CHIAVE": Fernet.generate_key().decode()}):
            clin_api.pseudonimizza(REFERTO)
            for name in ("segnaposto.json", "pseudonimi.json"):
                raw = (self.data / name).read_bytes()
                self.assertTrue(raw.startswith(b"gAAAAA"), name)
                self.assertNotIn(b"BIANCHI", raw)
            self.assertIn("BIANCHI GIULIA", clin_api.ripristina("PAZ-0001"))
        with self.assertRaises(RuntimeError):   # senza chiave: errore, mai una tabella nuova che sovrascrive
            clin.load_mapping()


class TestServizio(unittest.TestCase):
    def test_permessi_separati(self):
        tmp = tempfile.mkdtemp()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        env = dict(os.environ, CLIN_DATI=tmp, CLIN_LLM="0", CLIN_TOKEN_AGENTE="a" * 32, CLIN_TOKEN_RIPRISTINO="r" * 32)
        proc = subprocess.Popen([sys.executable, str(ROOT / "clin.py"), "servizio", "--porta", str(port)],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(proc.kill)

        def call(path, token, body=None):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if body is not None else "GET",
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Authorization": f"Bearer {token}"} if token else {})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())

        for _ in range(100):
            try:
                if call("/stato", "a" * 32)[0] == 200:
                    break
            except OSError:
                time.sleep(0.1)
        self.assertEqual(call("/stato", None)[0], 401)
        code, out = call("/pseudonimizza", "a" * 32, {"contenuto": REFERTO})
        self.assertEqual(code, 200)
        self.assertIn("PAZ-0001", out["contenuto"])
        self.assertEqual(call("/ripristina", "a" * 32, {"contenuto": "PAZ-0001"})[0], 403)   # l'agente no
        code, out = call("/ripristina", "r" * 32, {"contenuto": "PAZ-0001"})
        self.assertEqual(code, 200)
        self.assertIn("BIANCHI", out["contenuto"])


if __name__ == "__main__":
    unittest.main()
