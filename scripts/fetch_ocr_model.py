"""
Scarica il modello OCR italiano di Tesseract (tessdata_fast, ~2,6 MB) e ne
verifica l'impronta SHA-256. E' l'unico momento in cui Clin usa la rete:
l'OCR poi funziona offline.

    python3 scripts/fetch_ocr_model.py            # in models/tessdata/
    python3 scripts/fetch_ocr_model.py --dest DIR # altrove (poi CLIN_TESSDATA=DIR)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# commit fissato: il file non cambia sotto i piedi e l'impronta resta valida
COMMIT = "87416418657359cb625c412a48b6e1d6d41c29bd"
URL = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{COMMIT}/ita.traineddata"
SHA256 = "b8f89e1e785118dac4d51ae042c029a64edb5c3ee42ef73027a6d412748d8827"


def main() -> int:
    ap = argparse.ArgumentParser(description="Scarica il modello OCR italiano per Clin.")
    ap.add_argument("--dest", type=Path, default=ROOT / "models" / "tessdata")
    args = ap.parse_args()
    target = args.dest / "ita.traineddata"
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        print(f"Modello gia' presente e verificato: {target}")
        return 0
    print(f"Scarico {URL}")
    with urllib.request.urlopen(URL, timeout=60) as resp:
        data = resp.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        print(f"ERRORE: impronta SHA-256 inattesa ({digest}). File scartato.", file=sys.stderr)
        return 1
    args.dest.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    print(f"OK: {target} ({len(data) / 1e6:.1f} MB, SHA-256 verificata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
