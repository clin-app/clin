"""
Clin - riconduce ai dati reali i risultati prodotti dall'agente IA.

L'agente lavora sulle copie anonimizzate e produce file (tabelle, relazioni,
elenchi, documenti Word e presentazioni PowerPoint) con segnaposto ([PAZIENTE_1]) e pseudonimi (PAZ-0001). Qui ogni file
della cartella protetta che li contiene viene copiato, con i dati reali, nella
cartella dei risultati (predefinita: Clin_risultati/). La guardia nega
all'agente l'accesso a quella cartella: i dati reali restano in locale.

Si esegue al termine di ogni risposta dell'agente (hook di fine turno) oppure
con `clin.py risultati [cartella]`.
"""

from __future__ import annotations

import json
import os
import re
from clin_settings import CALENDAR_SHIFT
from pathlib import Path
from typing import Dict, List

PLACEHOLDER = re.compile(r"\[\s*[A-Z]+(?:_[A-Z]+)*_\d+\s*\]|\b[A-Z]{2,4}-\d{4}\b")
TEXT_EXT = {".csv", ".tsv", ".txt", ".md", ".json", ".html", ".htm", ".tex", ".rtf",
            # quaderni, relazioni riproducibili, grafici vettoriali e dati strutturati
            ".ipynb", ".rmd", ".qmd", ".rst", ".svg", ".xml", ".yaml", ".yml"}
SHEET_EXT = {".xlsx", ".xlsm"}
OOXML_EXT = {".docx", ".pptx"}  # Word e PowerPoint: archivi zip con il testo in parti XML
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".claude", ".codex", ".agents",
              "clin_anonimizzati"}
MAX_BYTES = 20 * 1024 * 1024
RESULTS_MARKER = ".clin-risultati"


def _tables() -> tuple:
    """(segnaposto -> originale, pseudonimo -> originale) dalle tabelle locali."""
    import clin
    seg = clin.load_mapping()
    pseudo: Dict[str, str] = {}
    try:
        data = json.loads((clin.MAP_DIR / "pseudonimi.json").read_text(encoding="utf-8"))
        pseudo = dict(data.get("originali", {}))
    except (OSError, ValueError):
        pass
    return seg, pseudo


# Date traslate dei fogli (anni 2100-2299): al ritorno si sottraggono gli stessi giorni.
_DAYS = None  # giorni della traslazione, letti all'inizio di `reidentify`
UNRESOLVED: List[Path] = []  # file dell'ultimo `reidentify` in cui restano anni o mesi traslati
_Y = r"2[1-5]\d\d"  # anni che esistono solo dopo la traslazione (2100-2599)
# nomi dei mesi e dei giorni, in italiano e in inglese, per intero o abbreviati
_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
       "ottobre", "novembre", "dicembre"]
_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
       "october", "november", "december"]
_DAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_DAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS: Dict[str, tuple] = {}    # forma -> (numero, lingua, abbreviata)
_WEEKDAYS: Dict[str, tuple] = {}  # forma -> (lingua, abbreviata)
for _i, (_a, _b) in enumerate(zip(_IT, _EN), start=1):
    _MONTHS.setdefault(_b, (_i, "en", False))
    _MONTHS.setdefault(_b[:3], (_i, "en", True))
    _MONTHS[_a] = (_i, "it", False)
    _MONTHS[_a[:3]] = (_i, "it", True)   # "mar", "apr", "nov": uguali nelle due lingue, valgono come italiano
_MONTHS.update({"sett": (9, "it", True), "sept": (9, "en", True), "may": (5, "en", False)})
for _a, _b in zip(_DAYS_IT, _DAYS_EN):
    _WEEKDAYS.update({_a: ("it", False), _a.replace("ì", "i"): ("it", False), _a[:3]: ("it", True),
                      _b: ("en", False), _b[:3]: ("en", True)})
_MONTH_RX = "(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + ")"
_WD = r"(?:(" + "|".join(sorted(_WEEKDAYS, key=len, reverse=True)) + r")(\.?,?\s+))?"
_SEP = r"[/.\-]"
# date complete: ogni forma porta giorno, mese e anno, quindi si sposta e si riconduce con esattezza
def _date_patterns(y: str) -> dict:
    return {
        "iso": re.compile(r"(?<![\d/.\-])(" + y + r")(" + _SEP + r")(\d{1,2})\2(\d{1,2})(?![\d/\-]|\.\d)"),      # 2243-05-14, 2243/5/14
        "dmy": re.compile(r"(?<![\d/.\-])(\d{1,2})(" + _SEP + r")(\d{1,2})\2(" + y + r")(?![\d/\-]|\.\d)"),      # 14/05/2243, 14.5.2243
        "compact": re.compile(r"(?<![\d.,])(" + y + r")(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?![\d.,]\d|\d)"),      # 22430514
        "words": re.compile(r"(?i)(?<![\w/])" + _WD + r"(\d{1,2})((?:st|nd|rd|th|[°º])?(?:\s+|-|\s+of\s+|\s+di\s+))"
                            + _MONTH_RX + r"(\.?,?(?:\s+|-))(" + y + r")(?!\d)"),                                   # lunedì 14 maggio 2243, 14-mag-2243
        "words_en": re.compile(r"(?i)(?<![\w/])" + _WD + _MONTH_RX + r"(\.?\s+)(\d{1,2})((?:st|nd|rd|th)?,?\s+)("
                               + y + r")(?!\d)"),                                                                    # Monday, May 14th, 2243
    }


_SHIFTED = _date_patterns(_Y)                                   # date gia' traslate, da ricondurre
_REAL = _date_patterns(r"(?:18[5-9]\d|19\d\d|20\d\d)")        # date vere, da traslare
# date parziali e anni: ricostruibili solo con i 400 anni esatti, dove mese e giorno sono gia' veri
_CAL_Y = r"2[3-5]\d\d"
_UNIT = (r"(?!\s*(?:mg|mcg|µg|ml|dl|cl|kg|mm|cm|ui|iu|mmol|mol|bpm|kcal|cal|g|l|u|m|%|pazienti|casi|soggetti|"
         r"patients|cases|subjects|euro|€)\b)")
_CUES = (r"anno|anni|year|years|nel|nell[’']anno|del|dell[’']anno|dal|al|il|entro|trimestre|semestre|quarter|"
         r"[qt][1-4]|stagione|inverno|primavera|estate|autunno|winter|spring|summer|autumn|fall|in|since|from|"
         r"until|through|during|by")
_CAL_PARTIAL = [
    re.compile(r"(?i)(?<![\w/])()" + _MONTH_RX + r"(\.?,?(?:\s+|-))(" + _CAL_Y + r")(?!\d)"),                       # maggio 2423, mag-2423
    re.compile(r"(?i)\b()(" + _CUES + r")(\s*[:=]?\s*)(" + _CAL_Y + r")(?![\d]|[.,]\d)" + _UNIT),                   # nel 2423, il 2423, Q1 2423
    re.compile(r"()(\()()(" + _CAL_Y + r")(?=\))"),                                                                # (2423)
]
_CAL_YM = re.compile(r"(?<![\d/.\-])(" + _CAL_Y + r")([\-/])(0[1-9]|1[0-2])(?![\d/\-]|\.\d)")                        # 2423-05
_CAL_YQ = re.compile(r"(?i)(?<![\d/.\-])(" + _CAL_Y + r")([\s\-]?[qtw]\d{1,2})\b")                                  # 2423Q1, 2423-W20
_CAL_RANGE = re.compile(r"(?<![\d/.\-])(" + _CAL_Y + r")(\s*[\-–—/]\s*)(" + _CAL_Y + r")(?![\d/\-]|\.\d)" + _UNIT)  # 2421-2423
_CAL_HEADER = re.compile(r"(?i)\b(anno|anni|year|years|periodo|period)\b")
_CAL_CELL = re.compile(r"\s*(" + _CAL_Y + r")(?:\.0)?\s*")
# cio' che resta dopo il ritorno e somiglia a una data o a un anno traslato: non e' ricostruibile
_LEFTOVER = re.compile(r"(?i)(?<![\w/])" + _MONTH_RX + r"\.?,?(?:\s+|-)" + _Y + r"(?!\d)|\b(?:" + _CUES
                       + r")\s*[:=]?\s*" + _Y + r"(?![\d]|[.,]\d)" + _UNIT + r"|(?<![\d/.\-])" + _Y
                       + r"[\-/](?:0[1-9]|1[0-2])(?![\d/\-]|\.\d)|(?<![\d/.\-])" + _Y + r"\s*[\-–—]\s*" + _Y
                       + r"(?![\d/\-]|\.\d)")


def _move_dates(text: str, days: int, patterns: dict, compact_too: bool = True) -> str:
    """Sposta di `days` giorni (anche negativi) ogni data completa del testo, lasciandone la forma."""
    from datetime import date, timedelta
    back = timedelta(days=-days)

    def styled(original: str, name: str) -> str:
        return name.upper() if original.isupper() else name.capitalize() if original[:1].isupper() else name

    def month_name(original: str, month: int) -> str:
        _, lang, short = _MONTHS[original.casefold()]
        name = (_IT if lang == "it" else _EN)[month - 1]
        return styled(original, name[:3] if short else name)

    def weekday(original, d) -> str:   # il giorno della settimana cambia con la data: va riscritto
        if not original:
            return ""
        lang, short = _WEEKDAYS[original.casefold()]
        name = (_DAYS_IT if lang == "it" else _DAYS_EN)[d.weekday()]
        if lang == "it" and "ì" not in original.casefold() and not short:
            name = name.replace("ì", "i")
        return styled(original, name[:3] if short else name)

    def iso(m):
        try:
            d = date(int(m[1]), int(m[3]), int(m[4])) - back
        except ValueError:
            return m[0]
        return f"{d.year}{m[2]}{d.month:0{len(m[3])}d}{m[2]}{d.day:0{len(m[4])}d}"

    def dmy(m):
        a, b = int(m[1]), int(m[3])
        us = b > 12 >= a   # "5/23/2243": mese prima del giorno
        try:
            d = (date(int(m[4]), a, b) if us else date(int(m[4]), b, a)) - back
        except ValueError:
            return m[0]
        first, second = (d.month, d.day) if us else (d.day, d.month)
        return f"{first:0{len(m[1])}d}{m[2]}{second:0{len(m[3])}d}{m[2]}{d.year}"

    def compact(m):
        try:
            return (date(int(m[1]), int(m[2]), int(m[3])) - back).strftime("%Y%m%d")
        except ValueError:
            return m[0]

    def words(m):   # [lunedì ]14 maggio 2243
        try:
            d = date(int(m[7]), _MONTHS[m[5].casefold()][0], int(m[3])) - back
        except ValueError:
            return m[0]
        return f"{weekday(m[1], d)}{m[2] or ''}{d.day:0{len(m[3])}d}{m[4]}{month_name(m[5], d.month)}{m[6]}{d.year}"

    def words_en(m):   # [Monday, ]May 14th, 2243
        try:
            d = date(int(m[7]), _MONTHS[m[3].casefold()][0], int(m[5])) - back
        except ValueError:
            return m[0]
        tail = m[6]
        for suffix in ("st", "nd", "rd", "th"):   # 1st, 2nd, 3rd, 4th
            if tail.casefold().startswith(suffix):
                right = "th" if 10 <= d.day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
                tail = right + tail[2:]
                break
        return f"{weekday(m[1], d)}{m[2] or ''}{month_name(m[3], d.month)}{m[4]}{d.day:0{len(m[5])}d}{tail}{d.year}"

    for key, fn in (("iso", iso), ("dmy", dmy), ("words", words), ("words_en", words_en), ("compact", compact)):
        if key != "compact" or compact_too:
            text = patterns[key].sub(fn, text)
    return text


def shift_whole_date(value: str, days: int):
    """La cella che e' per intero una data, in qualunque forma, spostata di `days` giorni; altrimenti None.
    Un numero di otto cifre non vale come data: puo' essere un codice."""
    v = value.strip()
    if not any(_REAL[k].fullmatch(v) for k in ("iso", "dmy", "words", "words_en")):
        return None
    moved = _move_dates(v, days, _REAL, compact_too=False)
    return moved if moved != v else None


_REAL_Y = r"(?:18[5-9]\d|19\d\d|20\d\d)"
_REAL_MONTH_YEAR = re.compile(r"(?i)(?<![\w/])" + _MONTH_RX + r"(\.?,?(?:\s+|-))(" + _REAL_Y + r")(?!\d)")
_REAL_YEAR = re.compile(r"(?<![\d/.\-])(" + _REAL_Y + r")(?![\d/\-]|\.\d)")
_SHIFTED_YEAR = re.compile(r"(?<!\d)" + _CAL_Y + r"(?!\d)")


def shift_span(text: str, days: int):
    """Per un tratto che il motore ha riconosciuto come data: (inizio, fine, data spostata) della data
    che contiene, o None se non c'e' una data che si possa spostare (giorno e mese senza anno)."""
    for key in ("iso", "dmy", "words", "words_en"):
        m = _REAL[key].search(text)
        if m:
            return m.start(), m.end(), _move_dates(m[0], days, _REAL, compact_too=False)
    if days == CALENDAR_SHIFT:   # date parziali: con i 400 anni cambia solo l'anno
        m = _REAL_MONTH_YEAR.search(text)
        if m:
            return m.start(), m.end(), m[1] + m[2] + str(int(m[3]) + 400)
        m = _REAL_YEAR.search(text)
        if m:
            return m.start(), m.end(), str(int(m[1]) + 400)
    return None


_DAY_MONTH = re.compile(r"(?i)(?<![\w/])\d{1,2}[°º]?\s+" + _MONTH_RX + r"\b|(?<![\d/.\-])\d{1,2}[/.\-]\d{1,2}(?![\d/.\-]|\w)")
_AGE = re.compile(r"(?i)\s*(?:di\s+|et[àa]\s*[:=]?\s*|age\s*[:=]?\s*|anni\s*[:=]?\s*)?\d{1,3}\s*-?\s*"
                  r"(?:anni(?:\s+compiuti)?|aa|mesi|enne|y|yrs|years?(?:[\s\-]old)?)?\s*")


def has_real_date(text: str) -> bool:
    """Vero se nel tratto c'e' una data vera, anche parziale (anno, mese e anno, giorno e mese)."""
    return bool(any(_REAL[k].search(text) for k in ("iso", "dmy", "words", "words_en"))
                or _REAL_MONTH_YEAR.search(text) or _REAL_YEAR.search(text) or _DAY_MONTH.search(text))


def is_age(text: str) -> bool:
    """Vero per un'eta' ("di 67 anni", "eta' 54", "45enne"): il motore la mette con le date di nascita,
    ma con le date spostate l'eta' si ricava comunque e all'agente serve."""
    return bool(_AGE.fullmatch(text))


def already_shifted(text: str) -> bool:
    """Vero se il tratto contiene un anno che esiste solo dopo lo spostamento (testo gia' anonimizzato)."""
    return bool(_SHIFTED_YEAR.search(text))


def unshift_dates(text: str, days: int) -> str:
    """Rimette le date vere al posto di quelle traslate, in qualunque forma siano scritte."""
    text = _move_dates(text, -days, _SHIFTED)
    if days == CALENDAR_SHIFT:
        real = lambda y: str(int(y) - 400)
        for rx in _CAL_PARTIAL:
            text = rx.sub(lambda m: m[1] + m[2] + m[3] + real(m[4]), text)
        text = _CAL_YM.sub(lambda m: real(m[1]) + m[2] + m[3], text)
        text = _CAL_YQ.sub(lambda m: real(m[1]) + m[2], text)
        text = _CAL_RANGE.sub(lambda m: real(m[1]) + m[2] + real(m[3]), text)
    return text


def _year_columns(rows: List[list]) -> bool:
    """Modalita' calendario: riporta agli anni veri le colonne «anno» e le intestazioni fatte di anni
    (tabelle per anno). Lavora sul posto; vero se ha cambiato qualcosa."""
    if _DAYS != CALENDAR_SHIFT or not rows:
        return False
    changed = False

    def fix(value):
        m = _CAL_CELL.fullmatch(str(value)) if value is not None and not isinstance(value, bool) else None
        if not m:
            return value, False
        real = int(m[1]) - 400
        return (real if isinstance(value, (int, float)) else str(real)), True

    head = rows[0]
    if sum(1 for v in head if fix(v)[1]) >= 2:          # "classe | 2421 | 2422 | 2423"
        for c, v in enumerate(head):
            head[c], hit = fix(v)
            changed = changed or hit
    for c, title in enumerate(head):
        if isinstance(title, str) and _CAL_HEADER.search(title):
            for row in rows[1:]:
                if c < len(row):
                    row[c], hit = fix(row[c])
                    changed = changed or hit
    return changed


def _to_restore(text: str) -> bool:
    """Vero se nel testo c'e' qualcosa da ricondurre: segnaposto, pseudonimi o date traslate."""
    return bool(PLACEHOLDER.search(text) or (_DAYS and re.search(_Y, text)))


def restore(text: str, seg: Dict[str, str], pseudo: Dict[str, str]) -> str:
    """Un'unica passata per segnaposto e pseudonimi: nessun valore ripristinato viene riletto."""
    from clin_text import restore_text
    merged = dict(pseudo or {})
    merged.update(seg or {})
    if _DAYS:  # prima le date: quelle dentro i valori reali rimessi dopo non vanno toccate
        text = unshift_dates(text, _DAYS)
    return restore_text(text, merged) if merged else text


def candidates(root: Path, out_dir: Path) -> List[Path]:
    """File dell'agente: formati testuali e fogli, fuori da risultati e copie generate."""
    found = []
    out_dir = out_dir.resolve()
    for folder, dirs, files in os.walk(root, followlinks=False):
        here = Path(folder)
        dirs[:] = [d for d in dirs if d.casefold() not in _SKIP_DIRS and not d.startswith(".")
                   and not (here / d).is_symlink()
                   and (here / d).resolve() != out_dir]
        for name in files:
            p = here / name
            if (p.is_symlink() or p.suffix.lower() not in TEXT_EXT | SHEET_EXT | OOXML_EXT
                    or "_anonimizzato" in p.stem.casefold()):
                continue
            try:
                if p.stat().st_size <= MAX_BYTES:
                    found.append(p)
            except OSError:
                continue
    return found


def _ensure_private_dir(out_dir: Path) -> None:
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    marker = out_dir / RESULTS_MARKER
    if not marker.exists() and not marker.is_symlink():
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("Cartella di risultati reali generata da Clin (accesso negato agli agenti).\n")


def _safe_dst(dst: Path, out_dir: Path) -> bool:
    """Rifiuta link simbolici nella destinazione o nelle sue cartelle intermedie."""
    if dst.is_symlink():
        return False
    cur = dst.parent
    out_resolved = out_dir.resolve()
    while cur != cur.parent:
        if cur.is_symlink():
            return False
        if cur == out_dir or (cur.exists() and cur.resolve() == out_resolved):
            break
        cur = cur.parent
    return True


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


# testo di un run (<w:t> in Word, <a:t> in PowerPoint) e paragrafo che lo contiene
_OOXML_T = re.compile(r"(<(a:t|w:t)(?:\s[^>]*)?>)([^<]*)(</\2>)")
_OOXML_P = re.compile(r"<(a:p|w:p)[\s>].*?</\1>", re.S)


def restore_ooxml(xml: str, seg: Dict[str, str], pseudo: Dict[str, str]) -> str:
    """Rimette i dati reali nel testo di una parte XML di Word o PowerPoint, senza toccare il resto.

    Si lavora sul testo dell'XML e non su un albero: riscrivere l'albero cambierebbe i prefissi dei
    namespace e Word segnalerebbe il file come danneggiato."""
    import html
    from xml.sax.saxutils import escape

    def node(n, text):
        head = n.group(1)
        if n.group(2) == "w:t" and "xml:space" not in head:
            head = '<w:t xml:space="preserve">'  # il valore reale puo' iniziare o finire con uno spazio
        return head + escape(text) + n.group(4)

    def each(n):
        text = html.unescape(n.group(3))
        return node(n, restore(text, seg, pseudo)) if _to_restore(text) else n.group(0)

    def paragraph(pm):
        block = pm.group(0)
        joined = "".join(html.unescape(n.group(3)) for n in _OOXML_T.finditer(block))
        if not _to_restore(joined):
            return block
        full = restore(joined, seg, pseudo)
        done = _OOXML_T.sub(each, block)  # run per run: la formattazione resta com'e'
        if "".join(html.unescape(n.group(3)) for n in _OOXML_T.finditer(done)) == full:
            return done
        # un segnaposto spezzato tra due run ("[PAZIENTE" + "_1]"): tutto il testo nel primo run
        first = [True]

        def merged(n):
            text, first[0] = (full if first[0] else ""), False
            return node(n, text)
        return _OOXML_T.sub(merged, block)

    return _OOXML_T.sub(each, _OOXML_P.sub(paragraph, xml))  # ultimo passaggio: testo fuori dai paragrafi


def _restore_ooxml_file(src: Path, dst: Path, seg: Dict[str, str], pseudo: Dict[str, str]) -> bool:
    import zipfile
    folder = "word/" if src.suffix.lower() == ".docx" else "ppt/"
    changed = False
    dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    if tmp.is_symlink():
        return False
    try:
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item)
                if item.filename.startswith(folder) and item.filename.endswith(".xml"):
                    xml = data.decode("utf-8")
                    new = restore_ooxml(xml, seg, pseudo)
                    if new != xml:
                        data, changed = new.encode("utf-8"), True
                zout.writestr(item, data)
        if not changed:
            return False
        os.chmod(tmp, 0o600)
        os.replace(tmp, dst)
        return True
    finally:
        if tmp.exists() and not tmp.is_symlink():
            tmp.unlink()


def restore_file(src: Path, dst: Path, seg: Dict[str, str], pseudo: Dict[str, str]) -> bool:
    """Scrive in `dst` la versione con i dati reali; False se `src` non ha segnaposto."""
    if src.suffix.lower() in OOXML_EXT:
        return _restore_ooxml_file(src, dst, seg, pseudo)
    if src.suffix.lower() in SHEET_EXT:
        from openpyxl import load_workbook
        wb = load_workbook(src, keep_vba=src.suffix.lower() == ".xlsm")
        try:
            changed = False
            for ws in wb.worksheets:
                if _DAYS == CALENDAR_SHIFT:
                    grid = [[c.value for c in row] for row in ws.iter_rows()]
                    if _year_columns(grid):
                        changed = True
                        for row, values in zip(ws.iter_rows(), grid):
                            for cell, value in zip(row, values):
                                if cell.value != value:
                                    cell.value = value
                for row in ws.iter_rows():
                    for cell in row:
                        if isinstance(cell.value, str) and _to_restore(cell.value):
                            new = restore(cell.value, seg, pseudo)
                            if new != cell.value:
                                cell.value, changed = new, True
                        elif (_DAYS and hasattr(cell.value, "year") and not isinstance(cell.value, str)
                              and 2100 <= cell.value.year <= 2599):
                            from datetime import timedelta
                            cell.value, changed = cell.value - timedelta(days=_DAYS), True
            if not changed:
                return False
            dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            tmp = dst.with_suffix(dst.suffix + ".tmp")
            if tmp.is_symlink():
                return False
            wb.save(tmp)
            os.chmod(tmp, 0o600)
            os.replace(tmp, dst)
            return True
        finally:
            wb.close()
    raw = src.read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not _to_restore(text):
        return False
    original = text
    if _DAYS == CALENDAR_SHIFT and src.suffix.lower() in (".csv", ".tsv"):
        import csv
        import io
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            rows = list(csv.reader(io.StringIO(text), dialect))
            if _year_columns(rows):
                buf = io.StringIO()
                csv.writer(buf, dialect).writerows(rows)
                text = buf.getvalue()
        except csv.Error:
            pass  # non e' una tabella regolare: si procede sul testo
    new = restore(text, seg, pseudo)
    if _DAYS and (_LEFTOVER.search(new) or (src.suffix.lower() in (".csv", ".tsv") and _CAL_HEADER.search(
            new.split("\n", 1)[0]) and re.search(r"(?m)(?:^|[,;\t])" + _Y + r"(?:[,;\t]|$)", new))):
        UNRESOLVED.append(src)
    if new == original:
        return False
    _write_private(dst, new.encode("utf-8"))
    return True


def reidentify(root: Path, out_dir: Path = None) -> List[Path]:
    """Riconduce ai dati reali i risultati della cartella `root`. Restituisce i file scritti."""
    import clin_settings
    root = Path(root).resolve()
    out_dir = out_dir or clin_settings.results_dir(root)
    global _DAYS
    UNRESOLVED.clear()
    seg, pseudo = _tables()
    _DAYS = clin_settings.date_shift(create=False)
    if not seg and not pseudo and not _DAYS:
        return []
    written = []
    for src in candidates(root, out_dir):
        dst = out_dir / src.relative_to(root)
        try:
            if not _safe_dst(dst, out_dir):
                continue
            if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                continue
            _ensure_private_dir(out_dir)
            if restore_file(src, dst, seg, pseudo):
                written.append(dst)
        except Exception:
            continue  # un file illeggibile non ferma gli altri
    return written
