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
_SHIFT_ISO = re.compile(r"(?<!\d)(2[12]\d\d)-(\d{2})-(\d{2})(?!\d)")
_SHIFT_DMY = re.compile(r"(?<!\d)(\d{1,2})([/.\-])(\d{1,2})\2(2[12]\d\d)(?!\d)")


def unshift_dates(text: str, days: int) -> str:
    from datetime import date, timedelta

    def iso(m):
        try:
            return (date(int(m[1]), int(m[2]), int(m[3])) - timedelta(days=days)).isoformat()
        except ValueError:
            return m[0]

    def dmy(m):
        a, b = int(m[1]), int(m[3])
        us = b > 12 >= a
        try:
            d = (date(int(m[4]), a, b) if us else date(int(m[4]), b, a)) - timedelta(days=days)
        except ValueError:
            return m[0]
        first, second = (d.month, d.day) if us else (d.day, d.month)
        return f"{first:02d}{m[2]}{second:02d}{m[2]}{d.year}"

    return _SHIFT_DMY.sub(dmy, _SHIFT_ISO.sub(iso, text))


def _to_restore(text: str) -> bool:
    """Vero se nel testo c'e' qualcosa da ricondurre: segnaposto, pseudonimi o date traslate."""
    return bool(PLACEHOLDER.search(text) or (_DAYS and (_SHIFT_ISO.search(text) or _SHIFT_DMY.search(text))))


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
                for row in ws.iter_rows():
                    for cell in row:
                        if isinstance(cell.value, str) and _to_restore(cell.value):
                            new = restore(cell.value, seg, pseudo)
                            if new != cell.value:
                                cell.value, changed = new, True
                        elif (_DAYS and hasattr(cell.value, "year") and not isinstance(cell.value, str)
                              and 2100 <= cell.value.year <= 2299):
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
    new = restore(text, seg, pseudo)
    if new == text:
        return False
    _write_private(dst, new.encode("utf-8"))
    return True


def reidentify(root: Path, out_dir: Path = None) -> List[Path]:
    """Riconduce ai dati reali i risultati della cartella `root`. Restituisce i file scritti."""
    import clin_settings
    root = Path(root).resolve()
    out_dir = out_dir or clin_settings.results_dir(root)
    global _DAYS
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
