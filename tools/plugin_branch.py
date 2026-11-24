"""
Aggiorna il ramo `plugin`: il plugin di Clin per Claude Code con i soli file che gli servono.

    python3 tools/plugin_branch.py            # aggiorna il ramo locale
    python3 tools/plugin_branch.py --push     # e lo invia a origin

Il repository intero contiene anche il sito, l'app web (con file di diversi megabyte) e
l'applicazione desktop, che al plugin non servono: chi lo installa scaricherebbe tutto, e il
catalogo dei plugin trattiene per revisione i pacchetti con file grandi. Il ramo `plugin` contiene
solo la Skill, la guardia, il server MCP e il motore. Il marketplace in `main` e la richiesta al
catalogo puntano a quel ramo. Lo aggiorna da solo .github/workflows/plugin.yml a ogni push su
main; a mano serve solo per provarlo in locale.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANCH = "plugin"
FILES = [
    ".claude-plugin/plugin.json", ".claude-plugin/icon.png", "bin/clin", "skills/clin/SKILL.md", "scripts/fetch_ocr_model.py",
    "integrations/claude-code/clin/SKILL.md", "LICENSE",
    "anonymize_engine.py", "clin.py", "clin_guard.py", "clin_lingue.py", "clin_llm.py", "clin_mcp.py",
    "clin_ner.py", "clin_ocr.py", "clin_results.py", "clin_settings.py", "clin_text.py", "tabular_engine.py",
    "clin_api.py", "clin_sanitario.py",
]
README = "integrations/claude-code/PLUGIN.md"   # diventa il README del ramo
LIMIT = 256 * 1024                              # oltre, il catalogo trattiene il plugin per revisione
WHO = {"GIT_AUTHOR_NAME": "Clin", "GIT_AUTHOR_EMAIL": "clin-app@users.noreply.github.com",
       "GIT_COMMITTER_NAME": "Clin", "GIT_COMMITTER_EMAIL": "clin-app@users.noreply.github.com"}


def git(*args, env=None, check=True) -> str:
    res = subprocess.run(["git", *args], cwd=ROOT, env={**os.environ, **(env or {})},
                         capture_output=True, text=True)
    if check and res.returncode:
        sys.exit(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout.strip()


def build(dest: Path, version: str) -> None:
    """Copia i file del plugin in `dest`. In `main` plugin.json non ha versione; nel ramo la riceve qui,
    e cambia solo quando cambia il plugin: e' cio' che dice a Claude Code che c'e' un aggiornamento."""
    for rel in FILES:
        src = ROOT / rel
        if src.stat().st_size > LIMIT:
            sys.exit(f"{rel} supera 256 KiB: il catalogo tratterrebbe il plugin per revisione.")
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / rel)          # conserva i permessi: bin/clin resta eseguibile
    shutil.copy2(ROOT / README, dest / "README.md")
    manifest = dest / ".claude-plugin" / "plugin.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data = {"name": data.pop("name"), "version": version, **data}
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tree_for(version: str) -> str:
    with tempfile.TemporaryDirectory(prefix="clin-plugin-") as tmp:
        work = Path(tmp) / "tree"
        work.mkdir()
        build(work, version)
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index"), "GIT_WORK_TREE": str(work)}
        git("add", "-A", env=env)
        return git("write-tree", env=env)


def main() -> int:
    push = "--push" in sys.argv[1:]
    git("fetch", "-q", "origin", BRANCH, check=False)
    parent = git("rev-parse", "-q", "--verify", f"origin/{BRANCH}", check=False) or \
        git("rev-parse", "-q", "--verify", f"refs/heads/{BRANCH}", check=False)
    # con la versione del ramo attuale: se l'albero e' identico, il plugin non e' cambiato
    old = ""
    if parent:
        try:
            old = json.loads(git("show", f"{parent}:.claude-plugin/plugin.json")).get("version", "")
        except ValueError:
            pass
    if parent and old and git("rev-parse", f"{parent}^{{tree}}") == tree_for(old):
        print(f"Ramo {BRANCH} gia' aggiornato (versione {old}).")
        return 0   # niente da inviare (nel flusso di GitHub il ramo esiste solo come origin/plugin)
    else:
        # versione nuova: quella dell'estensione (maggiore.minore) e il numero di commit di main
        base = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))["version"].split(".")
        version = f"{base[0]}.{base[1]}.{git('rev-list', '--count', 'HEAD')}"
        tree = tree_for(version)
        source = git("log", "-1", "--format=%h %s")
        commit = git("commit-tree", tree, *(["-p", parent] if parent else []),
                     "-m", f"Plugin aggiornato da main: {source}", env=WHO)
        git("update-ref", f"refs/heads/{BRANCH}", commit)
        print(f"Ramo {BRANCH}: {commit[:7]}, versione {version} ({len(FILES) + 1} file)")
    if push:
        git("push", "-q", "origin", f"refs/heads/{BRANCH}:refs/heads/{BRANCH}")
        print(f"Inviato a origin/{BRANCH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
