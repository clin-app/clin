"""
Pubblicazione completa di Clin dall'unico repository clin-app/clin.

    python3 tools/pubblica.py            # compila, aggiorna docs/app e crea la release
    python3 tools/pubblica.py --solo-build

Cosa fa:
1. compila l'app web (web/build.py) e la copia in docs/app/, servita da GitHub Pages
   all'indirizzo https://clin-app.github.io/clin/app/;
2. compila l'estensione per il Chrome Web Store (extension/build.py --store, senza
   model.onnx, scaricato una sola volta al primo avvio con verifica SHA-256);
3. compila l'estensione completa (con GLiNER ONNX incluso, nessuna richiesta di rete);
4. se la versione di extension/manifest.json non ha ancora una release, crea la release
   vX.Y.Z su clin-app/clin con due allegati dal nome fisso:
     clin-estensione.zip           estensione completa da installare in modalita' sviluppatore
     clin-estensione-webstore.zip  pacchetto da caricare sul Chrome Web Store
   Il sito punta a .../releases/latest/download/clin-estensione.zip, quindi scarica
   sempre l'ultima versione senza modificare i link.

Dopo l'esecuzione: commit e push di docs/app (e delle altre modifiche) su main.
Il modello GLiNER ONNX va esportato una volta in ~/.clin/modelli/gliner-onnx
con tools/export_gliner_onnx.py.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "clin-app/clin"
EXT = ROOT / "extension"
OUT = ROOT / "release"


def run(*cmd, **kw):
    print("$", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, check=True, **kw)


def main():
    version = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))["version"]
    tag = f"v{version}"
    OUT.mkdir(exist_ok=True)

    # 1. app web -> docs/app
    run(sys.executable, "web/build.py")
    app = ROOT / "docs" / "app"
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(ROOT / "web" / "dist", app)
    print(f"App web copiata in {app}")

    # 2. estensione per il Chrome Web Store
    run(sys.executable, "extension/build.py", "--store")
    shutil.move(EXT / "clin-webstore.zip", OUT / "clin-estensione-webstore.zip")

    # 3. estensione completa (lascia extension/dist pronta per l'uso locale)
    run(sys.executable, "extension/build.py")
    shutil.move(EXT / "clin-estensione.zip", OUT / "clin-estensione.zip")
    if not (EXT / "dist" / "vendor" / "gliner" / "model" / "model.onnx").exists():
        sys.exit("Modello GLiNER assente: esportarlo con tools/export_gliner_onnx.py prima di pubblicare.")

    # plugin per Claude Code: ramo `plugin` con i soli file necessari (da inviare dopo il push di main)
    run(sys.executable, "tools/plugin_branch.py")

    for f in sorted(OUT.glob("*.zip")):
        print(f"  {f.name}: {f.stat().st_size / 1e6:.1f} MB")
    if "--solo-build" in sys.argv:
        return

    # 4. release su GitHub (solo se la versione e' nuova)
    exists = subprocess.run(["gh", "release", "view", tag, "--repo", REPO],
                            cwd=ROOT, capture_output=True).returncode == 0
    if exists:
        print(f"La release {tag} esiste gia': aggiornare \"version\" in extension/manifest.json per pubblicarne una nuova.")
        return
    notes = OUT / "note.md"
    notes.write_text(f"""Estensione **Clin {version}** per Chrome ed Edge.

### Download
- **`clin-estensione.zip`**: estensione completa, con motore Python locale (Pyodide), lettura PDF/OCR e modello **GLiNER ONNX** inclusi. Nessuna richiesta di rete.
- `clin-estensione-webstore.zip`: pacchetto per il Chrome Web Store (il modello GLiNER si scarica una sola volta al primo avvio, con verifica SHA-256).

### Installazione in modalita' sviluppatore
1. Scaricare `clin-estensione.zip` ed estrarlo in una cartella stabile (es. Documenti/Clin-estensione).
2. Aprire `chrome://extensions` (Chrome) o `edge://extensions` (Edge) e attivare **Modalita' sviluppatore**.
3. Cliccare **Carica estensione non pacchettizzata** e scegliere la cartella estratta.

### Aggiornamento
Sostituire il contenuto della cartella con quello del nuovo zip, poi premere **⟳ Ricarica** sulla scheda Clin in `chrome://extensions` e ricaricare le schede di ChatGPT, Claude o Gemini.
""", encoding="utf-8")
    run("gh", "release", "create", tag,
        OUT / "clin-estensione.zip", OUT / "clin-estensione-webstore.zip",
        "--repo", REPO, "--title", f"Clin {version}", "--notes-file", notes, "--latest")
    print(f"Pubblicata: https://github.com/{REPO}/releases/tag/{tag}")


if __name__ == "__main__":
    main()
