"""
Costruisce l'app web di Clin in `web/dist/`, pronta da pubblicare su un
qualunque hosting statico HTTPS.

Tutte le librerie vengono ospitate insieme all'app (nessuna CDN a runtime) e
verificate con SHA-256: il browser puo' cosi' vietare ogni connessione verso
altri siti (Content-Security-Policy `connect-src 'self'`).

    python3 web/build.py
    python3 -m http.server -d web/dist 8765     # prova locale
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
DIST = WEB / "dist"
CACHE = WEB / ".vendor-cache"

VENDOR = {
    # destinazione in dist/vendor: (url, sha256)
    # Excel nell'estensione: openpyxl (Python puro) caricato nel motore solo quando serve
    "wheels/openpyxl-3.1.5-py2.py3-none-any.whl": ("https://files.pythonhosted.org/packages/c0/da/977ded879c29cbd04de313843e76868e6e13408a94ed6b987245dc7c8506/openpyxl-3.1.5-py2.py3-none-any.whl",
                                                   "5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2"),
    "wheels/et_xmlfile-2.0.0-py3-none-any.whl": ("https://files.pythonhosted.org/packages/c1/8b/5fe2cc11fee489817272089c4203e679c63b570a5aaeb18d852ae3cbba6a/et_xmlfile-2.0.0-py3-none-any.whl",
                                                 "7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f536151b2caa"),
    "pyodide/pyodide.mjs": ("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs",
                            "04c052c815abb0bf2981fa38c2dfa58e3120ee5288c956df2b2a15e301782c5f"),
    "pyodide/pyodide.asm.js": ("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.asm.js",
                               "6b4c90de5b7172873f04f21884d0e9d2274e305fe32116558fe3e4fbe3618d51"),
    "pyodide/pyodide.asm.wasm": ("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.asm.wasm",
                                 "a50dd1843f805a0b7c45b61037ee0d7b26dfe85efe0e18ef95a34ad24e401f5f"),
    "pyodide/python_stdlib.zip": ("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/python_stdlib.zip",
                                  "16611534726e5d8ac2bd8f926410b2dcb8d6f49aa24913463533b457a2115c16"),
    "pyodide/pyodide-lock.json": ("https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide-lock.json",
                                  "9c45b916001a750f4102fc287494f3eab215909c7535c626a20db80fd6333e2c"),
    "pdfjs/pdf.min.mjs": ("https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs",
                          "27fc2a057a00f92a4334ad06e17dbd7259912954e9fb7f76400bcca5fd190a9c"),
    "pdfjs/pdf.worker.min.mjs": ("https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs",
                                 "1baa1844c89c80a5b2797c916e75ab29254be46d8e9cb53cb6364d7aad84be36"),
    "tess/tesseract.min.js": ("https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js",
                              "a8e29918d098b2b06e1012bdaeffb4aec0445c5d5654709023e0bd1f442a80e8"),
    "tess/worker.min.js": ("https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/worker.min.js",
                           "aca1229639fc9907d86f96e825955a2b7c5716d17f3bc3acd71f9c7ab66181fc"),
    "tess/tesseract-core-lstm.wasm.js": (
        "https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.1/tesseract-core-lstm.wasm.js",
        "8f04aa0cc81e7bde33f80e92fa01a7a665f0b4884d098acf5de9c7104a11dfaa"),
    "tess/tesseract-core-simd-lstm.wasm.js": (
        "https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.1/tesseract-core-simd-lstm.wasm.js",
        "ce20eda9533cbed1e6c2b4276fbae1e0adc61b6754b5513084be601787b457cf"),
    "tess/ita.traineddata.gz": (
        "https://cdn.jsdelivr.net/npm/@tesseract.js-data/ita/4.0.0_best_int/ita.traineddata.gz",
        "f702fcfad297ce028ede3626d1467b67939f23ff23595f9badd54681cf25a4d3"),
}

APP_FILES = ["index.html", "app.js", "style.css", "sw.js", "manifest.webmanifest", "clin_web.py", "dona.js", "dona.css", "ocr-orient.js"]
ENGINE_FILES = ["anonymize_engine.py", "clin_text.py", "tabular_engine.py", "clin_ocr.py", "clin_llm.py", "clin_lingue.py"]


def fetch(url: str, sha: str) -> bytes:
    cached = CACHE / sha
    if cached.exists():
        data = cached.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 - URL fissati sopra
            data = r.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha:
        sys.exit(f"Impronta SHA-256 non valida per {url}: {digest}")
    CACHE.mkdir(exist_ok=True)
    cached.write_bytes(data)
    return data


def render_icons(dest: Path) -> None:
    """Icone PNG dell'app (schermata Home), dal logo vettoriale."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    renderer = QSvgRenderer(str(ROOT / "assets" / "logo.svg"))
    for name, size, pad, bg in (("icon-192.png", 192, 0.0, None), ("icon-512.png", 512, 0.0, None),
                                ("icon-maskable-512.png", 512, 0.14, "#d4f06b"),
                                ("apple-touch-icon.png", 180, 0.06, "#ffffff")):
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(QColor(bg) if bg else Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        m = size * pad
        renderer.render(p, QRectF(m, m, size - 2 * m, size - 2 * m))
        p.end()
        img.save(str(dest / name))


def build() -> Path:
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "py").mkdir(parents=True)
    for f in APP_FILES:
        target = DIST / ("py" if f.endswith(".py") else "") / f
        shutil.copy2(WEB / f, target)
    for f in ENGINE_FILES:
        shutil.copy2(ROOT / f, DIST / "py" / f)
    (DIST / "fonts").mkdir()
    shutil.copy2(ROOT / "assets" / "AlbertSans.woff2", DIST / "fonts" / "AlbertSans.woff2")
    shutil.copy2(ROOT / "assets" / "OFL-AlbertSans.txt", DIST / "fonts" / "OFL-AlbertSans.txt")
    shutil.copy2(ROOT / "assets" / "logo.svg", DIST / "logo.svg")
    render_icons(DIST)
    for rel, (url, sha) in VENDOR.items():
        out = DIST / "vendor" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(fetch(url, sha))

    # versione della cache offline: cambia quando cambia un file
    h = hashlib.sha256()
    files = sorted(p for p in DIST.rglob("*") if p.is_file() and p.name != "sw.js")
    for p in files:
        h.update(p.relative_to(DIST).as_posix().encode())
        h.update(p.read_bytes())
    sw = DIST / "sw.js"
    sw.write_text(sw.read_text(encoding="utf-8")
                  .replace("__VERSION__", h.hexdigest()[:12])
                  .replace("__FILES__", json.dumps(["./"] + [p.relative_to(DIST).as_posix() for p in files])),
                  encoding="utf-8")
    (DIST / ".nojekyll").write_text("")
    return DIST


if __name__ == "__main__":
    out = build()
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) / 1e6
    print(f"App web pronta in {out} ({size:.1f} MB)")
