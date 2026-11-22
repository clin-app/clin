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
FILES = ["manifest.json", "background.js", "content.js", "offscreen.html", "offscreen.js"]

if not (WEB / "vendor" / "pyodide").exists():
    sys.exit("Prima: python3 web/build.py")
shutil.rmtree(DIST, ignore_errors=True)
DIST.mkdir()
for f in FILES:
    shutil.copy2(EXT / f, DIST / f)
shutil.copytree(WEB / "vendor", DIST / "vendor")
shutil.copytree(WEB / "py", DIST / "py")
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
