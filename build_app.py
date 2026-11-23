"""
Crea Clin.app (macOS) sulla Scrivania, con icona propria.

L'app usa l'interprete Python gia' installato e i file di questa cartella:
se la cartella del progetto viene spostata, rieseguire questo script.

    python3 build_app.py [cartella_destinazione]
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
APP_NAME = "Clin"
BUNDLE_ID = "local.clin.app"


def render_icns(svg: Path, out_icns: Path) -> None:
    """Disegna il logo vettoriale alle misure richieste da macOS e crea l'.icns."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841
    renderer = QSvgRenderer(str(svg))
    iconset = Path(tempfile.mkdtemp()) / "icon.iconset"
    iconset.mkdir()
    for base in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = base * scale
            # margine del 9%: le icone macOS non toccano i bordi del riquadro
            img = QImage(px, px, QImage.Format_ARGB32)
            img.fill(Qt.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing)
            m = px * 0.09
            renderer.render(painter, QRectF(m, m, px - 2 * m, px - 2 * m))
            painter.end()
            suffix = "" if scale == 1 else "@2x"
            img.save(str(iconset / f"icon_{base}x{base}{suffix}.png"))
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out_icns)], check=True)
    shutil.rmtree(iconset.parent, ignore_errors=True)


def framework_python() -> Path:
    """Eseguibile interno di Python.app: copiandolo nel bundle, nome e icona
    nel Dock e nella barra dei menu diventano quelli di Clin."""
    candidate = (Path(sys.base_prefix) / "Resources" / "Python.app" / "Contents"
                 / "MacOS" / "Python")
    return candidate if candidate.exists() else Path(sys.executable)


def build(dest_dir: Path) -> Path:
    app = dest_dir / f"{APP_NAME}.app"
    if app.exists():
        shutil.rmtree(app)
    macos = app / "Contents" / "MacOS"
    res = app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    res.mkdir(parents=True)

    render_icns(PROJECT / "assets" / "logo.svg", res / f"{APP_NAME}.icns")
    shutil.copy2(framework_python(), macos / "clin-python")

    launcher = macos / APP_NAME
    launcher.write_text(
        "#!/bin/bash\n"
        'HERE="$(cd "$(dirname "$0")" && pwd)"\n'
        f'cd "{PROJECT}"\n'
        f'exec "$HERE/clin-python" "{PROJECT / "clin_gui.py"}" \n'
    )
    launcher.chmod(0o755)

    with open(app / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump({
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleExecutable": APP_NAME,
            "CFBundleIconFile": APP_NAME,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "2.2",
            "CFBundleVersion": "2.2",
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.medical",
        }, fh)

    # firma ad hoc: senza firma macOS rifiuta il binario copiato nel bundle
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)],
                   check=False, capture_output=True)
    # aggiorna la cache delle icone del Finder
    os.utime(app, None)
    return app


if __name__ == "__main__":
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / "Desktop"
    print(f"Creata: {build(target)}")
