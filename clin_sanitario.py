"""
Clin - messaggi sanitari strutturati: HL7 v2 (ADT, ORU, ORM, RDE, RAS...) e risorse FHIR (JSON).

Qui i dati personali stanno in campi noti, quindi si trattano campo per campo con regole fisse invece di
riconoscerli nel testo: nome del paziente -> PAZ-0001, identificativi -> IDC-0001 / ID-0001, medici ->
MED-0001 (gli stessi codici dei fogli di calcolo e dei referti), date spostate come negli altri documenti,
recapiti e indirizzi eliminati. I campi di testo libero (note, OBX testuali, narrativa FHIR) passano dal
motore dei testi. Tutto il resto (farmaci, dosi, vie, esami, valori, codici ATC/LOINC) resta com'e'.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from typing import Any, Dict, Optional, Tuple

import clin_settings
from clin_text import _Registry, agent_book, anonymize_text

# --------------------------------------------------------------------------- date
_TS = re.compile(r"^(\d{4})(\d{2})?(\d{2})?(.*)$")          # HL7: AAAA[MM[GG[hhmm[ss]...]]]
_ISO = re.compile(r"^(\d{4})(-\d{2})?(-\d{2})?(T.*)?$")     # FHIR: date, dateTime, instant


def _shift_year_first(value: str, days: Optional[int], rx: re.Pattern, sep: str) -> str:
    m = rx.match(value or "")
    if not m or not days or not 1850 <= int(m[1]) <= 2099:
        return value   # non una data, o gia' spostata (2426): un messaggio ripassato resta identico
    if days == clin_settings.CALENDAR_SHIFT or not (m[2] and m[3]):
        # 400 anni esatti: cambia solo l'anno. Con lo spostamento segreto una data parziale non si puo' spostare
        # con esattezza: resta solo l'anno spostato in avanti di un numero intero di anni (mai la data vera)
        years = 400 if days == clin_settings.CALENDAR_SHIFT else round(days / 365.2425)
        return f"{int(m[1]) + years:04d}" + value[4:]
    d = _dt.date(int(m[1]), int(m[2].strip("-")), int(m[3].strip("-"))) + _dt.timedelta(days=days)
    head = f"{d.year:04d}{sep}{d.month:02d}{sep}{d.day:02d}"
    return head + (m[4] or "")


def shift_hl7_ts(value: str, days: Optional[int]) -> str:
    return _shift_year_first(value, days, _TS, "")


def shift_iso(value: str, days: Optional[int]) -> str:
    return _shift_year_first(value, days, _ISO, "-")


def _code(prefix: str, value: str) -> str:
    """Codice dalla tabella condivisa; per le persone l'ordine di nome e cognome non conta
    ("ROSSI^LUCA" in HL7 e "Luca Rossi" in FHIR sono lo stesso medico)."""
    if prefix in ("MED", "OPE", "PER"):
        value = " ".join(sorted(value.split(), key=str.casefold))
    return agent_book().get("", 0, prefix, value)


# --------------------------------------------------------------------------- HL7 v2
# (segmento, campo) -> ruolo. Campi numerati come nello standard (PID-5 = nome del paziente).
_HL7_RULES: Dict[Tuple[str, int], str] = {
    ("MSH", 7): "data",
    ("EVN", 2): "data", ("EVN", 6): "data",
    ("PID", 2): "id_clinico", ("PID", 3): "id_clinico", ("PID", 4): "id_clinico",
    ("PID", 5): "paziente", ("PID", 6): "elimina", ("PID", 7): "data", ("PID", 9): "elimina",
    ("PID", 11): "elimina", ("PID", 12): "elimina", ("PID", 13): "elimina", ("PID", 14): "elimina",
    ("PID", 18): "id_clinico", ("PID", 19): "id", ("PID", 20): "elimina", ("PID", 21): "elimina",
    ("PID", 23): "elimina", ("PID", 29): "data",
    ("PD1", 4): "medico",
    ("NK1", 2): "persona", ("NK1", 4): "elimina", ("NK1", 5): "elimina", ("NK1", 6): "elimina",
    ("NK1", 30): "persona", ("NK1", 31): "elimina", ("NK1", 32): "elimina",
    ("PV1", 3): "posto_letto", ("PV1", 6): "posto_letto",
    ("PV1", 7): "medico", ("PV1", 8): "medico", ("PV1", 9): "medico", ("PV1", 17): "medico",
    ("PV1", 19): "id_clinico", ("PV1", 50): "id_clinico", ("PV1", 44): "data", ("PV1", 45): "data",
    ("ORC", 2): "id_clinico", ("ORC", 3): "id_clinico", ("ORC", 9): "data", ("ORC", 10): "operatore",
    ("ORC", 11): "medico", ("ORC", 12): "medico", ("ORC", 15): "data",
    ("OBR", 2): "id_clinico", ("OBR", 3): "id_clinico", ("OBR", 6): "data", ("OBR", 7): "data",
    ("OBR", 8): "data", ("OBR", 14): "data", ("OBR", 16): "medico", ("OBR", 22): "data",
    ("OBR", 28): "medico", ("OBR", 32): "medico", ("OBR", 34): "operatore",
    ("OBX", 5): "valore", ("OBX", 14): "data", ("OBX", 16): "medico", ("OBX", 19): "data",
    ("RXE", 13): "medico", ("RXE", 32): "data",
    ("RXA", 3): "data", ("RXA", 4): "data", ("RXA", 10): "operatore",
    ("RXO", 14): "medico",
    ("SPM", 2): "id_clinico", ("SPM", 17): "data", ("SPM", 18): "data",
    ("TQ1", 7): "data", ("TQ1", 8): "data",
    ("NTE", 3): "testo",
    ("AL1", 5): "clinico",
    ("DG1", 5): "data",
}
# segmenti anagrafici: dei campi senza regola restano solo questi (PID-8 sesso, NK1-3 relazione)
_HL7_KEEP_ONLY = {"PID": {1, 8}, "NK1": {1, 3, 7}, "PD1": set()}
# segmenti senza dati identificativi: copiati com'e' salvo le regole sopra (esami, farmaci, diagnosi, allergie)
_HL7_CLINICAL = {"MSH", "EVN", "PV1", "PV2", "ORC", "OBR", "OBX", "RXE", "RXO", "RXR", "RXA", "RXC", "RXD", "RXG",
                 "TQ1", "TQ2", "SPM", "AL1", "DG1", "PR1", "IAM", "MSA", "ERR", "QAK", "FT1", "IN1", "PID", "PD1",
                 "NK1", "NTE"}


_CODE = re.compile(r"(?:PAZ|ID|IDC|MED|OPE|PER|DOC|STR)-\d{4,}")
_TS_PART = re.compile(r"(?<![\d.])(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?:\d{2,6}(?:\.\d+)?)?(?:[+-]\d{4})?(?![\d.])")


def _shift_ts_parts(value: str, days: Optional[int]) -> str:
    """Ogni data HL7 (AAAAMMGG[hhmm...]) dentro un campo o una componente, spostata."""
    if not days:
        return value
    return _TS_PART.sub(lambda m: shift_hl7_ts(m.group(0), days), value)


def _person_name(xpn: str, comp: str, family_first: bool = True) -> str:
    parts = [p for p in xpn.split(comp) if p]
    if not parts:
        return ""
    return " ".join(parts[:2]) if family_first else " ".join(reversed(parts[:2]))


def _hl7_value(role: str, value: str, comp: str, rep: str, reg: _Registry, days: Optional[int]) -> str:
    if not value or not value.strip(comp + rep + " "):
        return value
    book = agent_book()
    out = []
    for item in value.split(rep):   # campi ripetuti (piu' identificativi, piu' nomi)
        if not item.strip(comp):
            out.append(item)
            continue
        c = item.split(comp)
        if role == "elimina":
            out.append("")
        elif role == "data":
            out.append(comp.join([shift_hl7_ts(c[0], days)] + c[1:]))
        elif role == "paziente":   # XPN: cognome^nome^...
            out.append(book.get("", 0, "PAZ", _person_name(item, comp)))
        elif role in ("medico", "operatore"):   # XCN: id^cognome^nome^...
            name = _person_name(comp.join(c[1:3]), comp) or c[0]
            out.append(_code("MED" if role == "medico" else "OPE", name))
        elif role == "persona":
            out.append(_code("PER", _person_name(item, comp)))
        elif role in ("id_clinico", "id"):   # CX: numero^^^ente^tipo -> solo il codice
            out.append(book.get("", 0, "IDC" if role == "id_clinico" else "ID", c[0]))
        elif role == "posto_letto":   # PL: reparto^stanza^letto^struttura: resta il reparto
            keep = c[:1] + ["", ""]
            if len(c) > 1 and c[1]:
                keep[1] = c[1] if _CODE.fullmatch(c[1]) else book.get("", 0, "IDC", "stanza " + c[1])
            if len(c) > 2 and c[2]:
                keep[2] = c[2] if _CODE.fullmatch(c[2]) else book.get("", 0, "IDC", f"{c[0]}/{c[1] if len(c) > 1 else ''}/{c[2]}")
            out.append(comp.join(keep))
        elif role in ("testo", "valore"):
            out.append(comp.join(_free_text(x, reg) for x in c))
        else:
            out.append(item)
    return rep.join(out)


def _free_text(text: str, reg: _Registry) -> str:
    """Testo libero (note, referti testuali): stesso motore e stesso registro dei documenti."""
    if not re.search(r"[A-Za-zÀ-ÿ]{3,}", text or ""):
        return text   # numeri, codici, unita': nulla da cercare
    return anonymize_text(text, _registry=reg).text


def anonymize_hl7(message: str, registry: Optional[_Registry] = None) -> str:
    """Un messaggio HL7 v2 (o piu' messaggi di seguito) con i dati personali sostituiti campo per campo."""
    days = _shift()
    reg = registry or _Registry([])
    lines = re.split(r"\r\n|\r|\n", message.strip("\r\n"))
    if not lines or not lines[0].startswith("MSH"):
        raise ValueError("Non e' un messaggio HL7 v2: manca il segmento MSH.")
    fs = lines[0][3]
    enc = lines[0].split(fs)[1] if len(lines[0].split(fs)) > 1 else "^~\\&"
    comp, rep = enc[0], enc[1] if len(enc) > 1 else "~"
    out = []
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("MSH"):
            fs = line[3]
        fields = line.split(fs)
        seg = fields[0]
        for i in range(1, len(fields)):
            num = i + 1 if seg == "MSH" else i    # in MSH il separatore e' il campo 1
            role = _HL7_RULES.get((seg, num))
            if not role and seg in _HL7_KEEP_ONLY and num not in _HL7_KEEP_ONLY[seg]:
                role = "elimina"   # anagrafica: religione, stato civile, lingua, etnia... non servono
            if role:
                fields[i] = _hl7_value(role, fields[i], comp, rep, reg, days)
            elif seg not in _HL7_CLINICAL:
                # segmento sconosciuto (anche Z personalizzati): ogni campo di testo passa dal motore
                fields[i] = comp.join(_free_text(_shift_ts_parts(x, days), reg) for x in fields[i].split(comp))
            elif not (seg == "MSH" and num <= 2):
                # campi senza regola nei segmenti clinici: restano, ma una data in qualsiasi componente
                # (es. inizio terapia in RXE-1 "^Q6H^^20261101") viene spostata come le altre
                fields[i] = _shift_ts_parts(fields[i], days)
        out.append(fs.join(fields))
    return "\r".join(out) + "\r"


# --------------------------------------------------------------------------- FHIR
_FHIR_FREE_TEXT = {"div", "text", "comment", "conclusion", "description", "valueString", "note", "summary",
                   "patientInstruction", "detail"}
_FHIR_DROP = {"telecom", "address", "photo", "contact", "communication", "link", "maritalStatus"}
_PERSON_PREFIX = {"Patient": "PAZ", "Practitioner": "MED", "RelatedPerson": "PER", "Person": "PER"}


def _fhir_name(names: Any) -> str:
    for n in names if isinstance(names, list) else []:
        if isinstance(n, dict):
            full = n.get("text") or " ".join([*n.get("given", []), n.get("family", "")]).strip()
            if full:
                return full
    return ""


def anonymize_fhir(data: Any, registry: Optional[_Registry] = None) -> Any:
    """Risorsa o Bundle FHIR (gia' decodificato da JSON) con i dati personali sostituiti."""
    days = _shift()
    reg = registry or _Registry([])
    book = agent_book()
    ids: Dict[str, str] = {}   # "Patient/123" -> "Patient/IDC-0001": i riferimenti restano coerenti

    # primo passaggio: le persone e i loro id, per riscrivere i riferimenti ovunque nel Bundle
    def collect(node: Any) -> None:
        if isinstance(node, dict):
            rt = node.get("resourceType")
            if rt in _PERSON_PREFIX and isinstance(node.get("id"), str):
                ids[f"{rt}/{node['id']}"] = f"{rt}/{book.get('', 0, 'IDC', rt + '/' + node['id'])}"
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)
    collect(data)

    def walk(node: Any, key: str = "", rt: str = "") -> Any:
        if isinstance(node, dict):
            rt = node.get("resourceType", rt)
            out = {}
            for k, v in node.items():
                if rt in _PERSON_PREFIX and k in _FHIR_DROP:
                    continue
                if rt in _PERSON_PREFIX and k == "name":
                    full = _fhir_name(v)
                    out[k] = [{"text": _code(_PERSON_PREFIX[rt], full)}] if full else []
                elif rt in _PERSON_PREFIX and k == "id" and isinstance(v, str):
                    out[k] = ids[f"{rt}/{v}"].split("/", 1)[1]
                elif k == "identifier":
                    out[k] = [_fhir_identifier(i) for i in (v if isinstance(v, list) else [v])]
                elif k == "reference" and isinstance(v, str):
                    out[k] = ids.get(v, v)
                elif k == "display" and isinstance(node.get("reference"), str):
                    ref = node["reference"].split("/")[0]
                    out[k] = _code(_PERSON_PREFIX[ref], v) if ref in _PERSON_PREFIX else _free_text(v, reg)
                else:
                    out[k] = walk(v, k, rt)
            if "contentType" in node and "data" in node:
                out.pop("data", None)   # allegati in base64 (PDF, immagini): non si possono controllare qui
            return out
        if isinstance(node, list):
            return [walk(v, key, rt) for v in node]
        if isinstance(node, str):
            # date: forma AAAA-MM[-GG...], oppure il solo anno in un campo di data (non i codici di 4 cifre)
            if _ISO.match(node) and (len(node) >= 7 or key.lower().endswith(("date", "datetime", "instant", "issued"))):
                return shift_iso(node, days)
            if key in _FHIR_FREE_TEXT:
                return _free_text(node, reg)
        return node

    def _fhir_identifier(i: Any) -> Any:
        if not isinstance(i, dict) or "value" not in i:
            return i
        system = (i.get("system") or "").lower()
        prefix = "ID" if ("fiscale" in system or "fiscal" in system or "tax" in system) else "IDC"
        return {k: v for k, v in i.items() if k in ("system", "type", "use")} | {"value": book.get("", 0, prefix, str(i["value"]))}

    return walk(data)


# --------------------------------------------------------------------------- ingresso unico
def _shift() -> Optional[int]:
    import anonymize_engine as ae
    ae.DATE_SHIFT = clin_settings.date_shift()
    return ae.DATE_SHIFT


def detect(text: str) -> Optional[str]:
    s = text.lstrip("﻿ \t\r\n")
    if s.startswith("MSH"):
        return "hl7"
    if s.startswith("{"):
        try:
            if "resourceType" in json.loads(s):
                return "fhir"
        except ValueError:
            pass
    return None


def anonymize_message(text: str, registry: Optional[_Registry] = None) -> Tuple[str, str]:
    """(tipo, testo anonimizzato) per un messaggio HL7 v2 o una risorsa FHIR in JSON."""
    kind = detect(text)
    if kind == "hl7":
        return kind, anonymize_hl7(text, registry)
    if kind == "fhir":
        return kind, json.dumps(anonymize_fhir(json.loads(text.lstrip("﻿")), registry), ensure_ascii=False, indent=2)
    raise ValueError("Formato non riconosciuto: servono un messaggio HL7 v2 (MSH|...) o una risorsa FHIR in JSON.")
