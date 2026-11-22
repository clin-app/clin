"""
Clin - riconduce ai dati reali i risultati prodotti dall'agente IA.

L'agente lavora sulle copie anonimizzate e produce file (tabelle, relazioni,
elenchi) con segnaposto ([PAZIENTE_1]) e pseudonimi (PAZ-0001). Qui ogni file
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
TEXT_EXT = {".csv", ".tsv", ".txt", ".md", ".json", ".html", ".htm", ".tex", ".rtf"}
SHEET_EXT = {".xlsx", ".xlsm"}
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


def restore(text: str, seg: Dict[str, str], pseudo: Dict[str, str]) -> str:
    """Un'unica passata per segnaposto e pseudonimi: nessun valore ripristinato viene riletto."""
    from clin_text import restore_text
    merged = dict(pseudo or {})
    merged.update(seg or {})
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
            if (p.is_symlink() or p.suffix.lower() not in TEXT_EXT | SHEET_EXT
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


def restore_file(src: Path, dst: Path, seg: Dict[str, str], pseudo: Dict[str, str]) -> bool:
    """Scrive in `dst` la versione con i dati reali; False se `src` non ha segnaposto."""
    if src.suffix.lower() in SHEET_EXT:
        from openpyxl import load_workbook
        wb = load_workbook(src, keep_vba=src.suffix.lower() == ".xlsm")
        try:
            changed = False
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for cell in row:
                        if isinstance(cell.value, str) and PLACEHOLDER.search(cell.value):
                            new = restore(cell.value, seg, pseudo)
                            if new != cell.value:
                                cell.value, changed = new, True
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
    if not PLACEHOLDER.search(text):
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
    seg, pseudo = _tables()
    if not seg and not pseudo:
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
