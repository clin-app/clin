"""
Costruisce l'estensione per Chrome/Edge in extension/dist e il pacchetto
extension/clin-estensione.zip da caricare sul Chrome Web Store.
Motore, pdf.js e OCR vengono presi dall'app web gia' compilata (web/build.py).

    python3 web/build.py && python3 extension/build.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

EXT = Path(__file__).resolve().parent
WEB = EXT.parent / "web" / "dist"
DIST = EXT / "dist"
FILES = ["manifest.json", "background.js", "content.js", "offscreen.html", "offscreen.js", "ner.js"]

import hashlib
import os
import urllib.request

# GLiNER nel browser: gliner.js (MIT), onnxruntime-web, tokenizer di transformers.js; verificati con SHA-256
NER_VENDOR = {
    "gliner.mjs": ("https://cdn.jsdelivr.net/npm/gliner@0.0.19/dist/index.mjs",
                   "c2e1c1daf47d0fe9dea51487adb23bac494b4141a3659803608cc99e85da8eed"),
    "transformers.min.js": ("https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js",
                            "bcf7cf304e51f470ed59409622b9d6ffbad80dfcf5baf6a40c919e4b9c4ff812"),
    "ort.wasm.min.mjs": ("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/ort.wasm.min.mjs",
                         "037db9f11eb741550e17ad5ace4e1401155c8ee0f6d8281c75bc6475d974881c"),
    "ort-wasm-simd-threaded.mjs": ("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/ort-wasm-simd-threaded.mjs",
                                   "d870a377322c3053fb97432d548423f165dd15e2af232947592fc07b0d2f3639"),
    "ort-wasm-simd-threaded.wasm": ("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/ort-wasm-simd-threaded.wasm",
                                    "1bf0b9ed7ad025cf9ca88ce6da29e54df3f128a169f8241d71823e81f078d578"),
}
CACHE = EXT / ".vendor-cache"
# modello esportato con tools/export_gliner_onnx.py (non nel repository: 581 MB)
MODEL = Path(os.path.expanduser(os.environ.get("CLIN_MODELLO_ONNX", "~/.clin/modelli/gliner-onnx")))


def fetch(name, url, sha):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        data = urllib.request.urlopen(url, timeout=120).read()
        if hashlib.sha256(data).hexdigest() != sha:
            sys.exit(f"Impronta SHA-256 errata per {url}")
        path.write_bytes(data)
    return path


if not (WEB / "vendor" / "pyodide").exists():
    sys.exit("Prima: python3 web/build.py")
shutil.rmtree(DIST, ignore_errors=True)
DIST.mkdir()
for f in FILES:
    shutil.copy2(EXT / f, DIST / f)
shutil.copytree(WEB / "vendor", DIST / "vendor")
shutil.copytree(WEB / "py", DIST / "py")
ner = DIST / "vendor" / "gliner"
ner.mkdir(parents=True)
for name, (url, sha) in NER_VENDOR.items():
    shutil.copy2(fetch(name, url, sha), ner / name)
g = (ner / "gliner.mjs").read_text(encoding="utf-8")  # import locali al posto dei nomi dei pacchetti
g = g.replace("from '@xenova/transformers'", "from './transformers.min.js'")
g = g.replace("import ort_CPU from 'onnxruntime-web';", "import ort_CPU from './ort.wasm.min.mjs';")
g = g.replace("import ort_WEBGPU from 'onnxruntime-web/webgpu';\n", "").replace("import ort_WEBGL from 'onnxruntime-web/webgl';\n", "")
g = g.replace("// src/lib/model.ts", "const ort_WEBGPU = ort_CPU, ort_WEBGL = ort_CPU;\n// src/lib/model.ts", 1)
assert "onnxruntime-web'" not in g and "@xenova" not in g
(ner / "gliner.mjs").write_text(g, encoding="utf-8")
if (MODEL / "model.onnx").exists():
    shutil.copytree(MODEL, ner / "model")
else:
    print(f"ATTENZIONE: modello GLiNER assente in {MODEL}: l'estensione usera' solo le regole. "
          "Esportarlo con tools/export_gliner_onnx.py")
(DIST / "icons").mkdir()
for size in (16, 48, 128):  # icone dal logo dell'app (sips su macOS, altrimenti copia)
    out = DIST / "icons" / f"{size}.png"
    try:
        subprocess.run(["sips", "-z", str(size), str(size), str(WEB / "icon-192.png"), "--out", str(out)],
                       check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        shutil.copy2(WEB / "icon-192.png", out)
zip_path = EXT / "clin-estensione.zip"
zip_path.unlink(missing_ok=True)
shutil.make_archive(str(zip_path.with_suffix("")), "zip", DIST)
size = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file()) / 1e6
print(f"Estensione in {DIST} ({size:.1f} MB), pacchetto: {zip_path.name}")
