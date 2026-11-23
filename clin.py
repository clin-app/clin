#!/usr/bin/env python3
"""
Clin - comando unico per l'uso con le IA.

    python3 clin.py                      apre l'applicazione grafica
    python3 clin.py testo FILE           stampa il testo anonimizzato (segnaposto)
    python3 clin.py appunti              anonimizza il testo copiato negli appunti
    python3 clin.py ripristina           rimette i dati originali nella risposta copiata
    python3 clin.py dimentica            cancella la tabella dei segnaposto salvata
    python3 clin.py mcp                  avvia il server MCP (per Claude, Cursor...)
    python3 clin.py collega claude-desktop   aggiunge Clin a Claude Desktop
    python3 clin.py collega claude-code      aggiunge server MCP e skill a Claude Code
    python3 clin.py copie CARTELLA       copie anonime di file/cartella (pseudonimi coerenti)
    python3 clin.py originale PAZ-0147   valore originale di uno pseudonimo, solo in locale
    python3 clin.py risultati [CARTELLA] risultati dell'agente ricondotti ai dati reali (Clin_risultati/)
    python3 clin.py impostazioni [K V]   impostazioni per Claude Code, Codex, Antigravity
    python3 clin.py installa             installazione una tantum: MCP, /clin, guardia dormiente
    python3 clin.py avvia [CARTELLA]     protegge la cartella e crea le copie anonime (lo fa /clin)
    python3 clin.py stato [CARTELLA]     diagnosi: agenti collegati, protezione, motori
    python3 clin.py escludi [PERCORSO]   file o cartelle senza dati di pazienti (articoli, linee guida)
    python3 clin.py attiva|disattiva     accende/spegne la guardia su una cartella
    python3 clin.py proteggi [CARTELLA]  guardia solo per un progetto (anche --agente tutti)

Flusso "appunti" (funziona con qualunque IA, anche dal browser):
  1. copiare il testo del referto (Cmd+C)
  2. eseguire `clin.py appunti` (o la scorciatoia da tastiera)
  3. incollare nella chat dell'IA: arrivano solo i segnaposto
  4. copiare la risposta dell'IA ed eseguire `clin.py ripristina` per
     rileggerla con i nomi veri, sul proprio computer.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MAP_DIR = Path(os.path.expanduser(os.environ.get("CLIN_DATI") or "~/.clin"))  # come clin_settings.DATA_DIR
MAP_FILE = MAP_DIR / "segnaposto.json"


# --------------------------------------------------------------------------
# Appunti di sistema (macOS, Windows, Linux) senza dipendenze
# --------------------------------------------------------------------------
def _linux_clipboard_cmd(read: bool) -> list:
    import shutil
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste") and shutil.which("wl-copy"):
        return ["wl-paste", "--no-newline"] if read else ["wl-copy"]
    if shutil.which("xclip"):
        return ["xclip", "-selection", "clipboard", "-o"] if read else ["xclip", "-selection", "clipboard"]
    if shutil.which("xsel"):
        return ["xsel", "--clipboard", "--output"] if read else ["xsel", "--clipboard", "--input"]
    raise ValueError("Utilità per gli appunti mancante: installare wl-clipboard (Wayland) oppure xclip/xsel (X11).")


def clipboard_get() -> str:
    system = platform.system()
    if system == "Darwin":
        return subprocess.run(["pbpaste"], capture_output=True, text=True, check=True).stdout
    if system == "Windows":
        return subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                              capture_output=True, text=True, check=True).stdout
    return subprocess.run(_linux_clipboard_cmd(True), capture_output=True, text=True, check=True).stdout


def clipboard_set(text: str) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
    elif system == "Windows":
        subprocess.run(["clip"], input=text, text=True, check=True)
    else:
        subprocess.run(_linux_clipboard_cmd(False), input=text, text=True, check=True)


def notify(message: str) -> None:
    """Notifica di sistema su macOS (utile quando il comando parte da una scorciatoia)."""
    if platform.system() == "Darwin" and not sys.stdout.isatty():
        subprocess.run(
            ["osascript", "-e", 'on run argv\ndisplay notification (item 1 of argv) with title "Clin"\nend run',
             "--", message],
            capture_output=True,
        )
    print(message)


# --------------------------------------------------------------------------
# Tabella segnaposto: solo in locale, leggibile solo dall'utente
# --------------------------------------------------------------------------
def save_mapping(mapping: dict) -> None:
    MAP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(MAP_DIR, 0o700)
    old = load_mapping()
    old.update(mapping)
    tmp = MAP_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(old, fh, ensure_ascii=False)
    os.replace(tmp, MAP_FILE)


def load_mapping() -> dict:
    try:
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------
# Comandi
# --------------------------------------------------------------------------
def cmd_testo(a) -> int:
    from clin_text import anonymize_file
    res = anonymize_file(Path(a.file))
    if a.salva_tabella:
        save_mapping(res.mapping)
    print(res.summary(), file=sys.stderr)
    for n in res.notes:
        print(n, file=sys.stderr)
    print(res.text)
    return 0


def clip_anonymize() -> str:
    """Anonimizza gli appunti in place; restituisce il messaggio per l'utente."""
    from clin_text import anonymize_text
    text = clipboard_get()
    if not text.strip():
        raise ValueError("Appunti vuoti: copiare prima il testo da anonimizzare.")
    # la numerazione prosegue dalla volta precedente: piu' incolla nella
    # stessa chat restano coerenti ([PAZIENTE_1] e' sempre la stessa persona)
    previous = load_mapping()
    res = anonymize_text(text, previous=previous,
                         names=[v for k, v in previous.items() if k.startswith("[PAZIENTE_")])
    save_mapping(res.mapping)
    clipboard_set(res.text)
    n = sum(res.counts.values())
    return f"Appunti anonimizzati: {n} dati sostituiti. Ora si puo' incollare nella chat."


def clip_restore() -> str:
    from clin_text import restore_text
    mapping = load_mapping()
    if not mapping:
        raise ValueError("Nessuna tabella segnaposto salvata: niente da ripristinare.")
    clipboard_set(restore_text(clipboard_get(), mapping))
    return "Risposta ripristinata con i dati originali (solo su questo computer)."


def cmd_appunti(a) -> int:
    notify(clip_anonymize())
    return 0


def cmd_ripristina(a) -> int:
    notify(clip_restore())
    return 0


def forget_mapping() -> str:
    """Cancella la tabella segnaposto e le copie di lettura della guardia che la usano."""
    import shutil
    try:
        MAP_FILE.unlink()
        msg = "Tabella segnaposto cancellata."
    except FileNotFoundError:
        msg = "Nessuna tabella segnaposto da cancellare."
    shutil.rmtree(MAP_DIR / "letture", ignore_errors=True)
    return msg


def cmd_dimentica(a) -> int:
    notify(forget_mapping())
    return 0


def cmd_originale(a) -> int:
    """Risale da uno pseudonimo dei fogli (PAZ-0147) al valore originale, in locale."""
    path = MAP_DIR / "pseudonimi.json"
    try:
        book = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("Nessuna tabella pseudonimi in ~/.clin: nessuna copia creata con /clin.")
    code = a.codice.strip().upper()
    originals = book.get("originali", {})
    codes = book.get("codici", book)
    hits = [originals.get(c) or value for table in codes.values() for value, c in table.items() if c == code]
    if not hits:
        raise ValueError(f"{code} non presente nella tabella pseudonimi.")
    print(f"{code}: {hits[0]}")
    return 0


def cmd_risultati(a) -> int:
    """Riconduce ai dati reali i risultati con segnaposto di una cartella."""
    import clin_results
    import clin_settings
    root = Path(a.cartella).expanduser().resolve()
    written = clin_results.reidentify(root)
    where = clin_settings.results_dir(root)
    notify(f"{len(written)} file ricondotti ai dati reali in {where}." if written
           else "Nessun nuovo risultato con segnaposto da ricondurre.")
    return 0


def cmd_impostazioni(a) -> int:
    import clin_settings
    if a.chiave == "categorie":
        from anonymize_engine import CONTROL_CATEGORIES
        excl = set(clin_settings.load()["categorie_escluse"])
        print("Categorie rimosse (si) o lasciate nel testo (no):")
        for c, desc in CONTROL_CATEGORIES.items():
            print(f"  {'no' if c in excl else 'si':<3} {c:<24} {desc}")
        print('\nPer lasciarne alcune: clin.py impostazioni categorie_escluse "Date, Struttura sanitaria"'
              '\nPer rimuovere di nuovo tutto: clin.py impostazioni categorie_escluse ""')
        return 0
    if a.chiave:
        if a.valore is None:
            raise ValueError("Indicare anche il valore, es.: clin.py impostazioni ripristino_automatico no")
        clin_settings.save({a.chiave: clin_settings.parse(a.chiave, a.valore)})
    values = clin_settings.load()
    for key, (_, desc) in clin_settings.OPTIONS.items():
        v = values[key]
        shown = ("si" if v else "no") if isinstance(v, bool) else (", ".join(v) or "nessuna") if isinstance(v, list) else v
        print(f"{key:<24} {shown}\n{'':<24} {desc}")
    return 0


def cmd_ner(a) -> int:
    import clin_ner
    if a.azione == "installa":
        notify("Installazione di GLiNER in corso (circa 2,4 GB, una volta sola)…")
        notify(clin_ner.install())
    else:
        import clin_llm
        notify(f"Motore attivo: {clin_llm.status()}")
    return 0


def cmd_copie(a) -> int:
    from clin_mcp import tool_crea_copie_anonime
    print(tool_crea_copie_anonime({"percorso": str(Path(a.percorso).expanduser().resolve())}))
    return 0


# --------------------------------------------------------------------------
# Guardia per agenti IA (hook): Claude Code, Codex, Google Antigravity
# --------------------------------------------------------------------------
def _guard_command() -> str:
    return f'"{python_path()}" "{HERE / "clin_guard.py"}"'


def _is_clin(entry) -> bool:
    return "clin_guard.py" in json.dumps(entry)


def _merge_event(hooks: dict, event: str, entry: dict) -> None:
    hooks[event] = [e for e in hooks.get(event, []) if not _is_clin(e)] + [entry]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text or "{}")
    except ValueError:
        raise ValueError(f"File non leggibile (JSON non valido): {path}")
    path.with_suffix(path.suffix + ".bak").write_text(text, encoding="utf-8")
    return data


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _install_skill(skill_dir: Path) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    template = (HERE / "integrations" / "claude-code" / "clin" / "SKILL.md").read_text(encoding="utf-8")
    text = template.replace("{PYTHON}", python_path()).replace("{CLIN_PATH}", str(HERE))
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")


def protect_claude_code(base: Optional[Path]) -> str:
    path = (base / ".claude" / "settings.json") if base else Path.home() / ".claude" / "settings.json"
    data = _load_json(path)
    hooks = data.setdefault("hooks", {})
    cmd = _guard_command()
    _merge_event(hooks, "PreToolUse", {"matcher": "Read|Bash|Grep",
                                       "hooks": [{"type": "command", "command": cmd, "timeout": 900}]})
    _merge_event(hooks, "PostToolUse", {"matcher": "Bash",
                                        "hooks": [{"type": "command", "command": cmd, "timeout": 120}]})
    _merge_event(hooks, "UserPromptSubmit", {"hooks": [{"type": "command", "command": cmd, "timeout": 60}]})
    # fine risposta: i risultati con segnaposto vengono ricondotti ai dati reali
    _merge_event(hooks, "Stop", {"hooks": [{"type": "command", "command": cmd + " stop", "timeout": 300}]})
    # i file citati con @ entrerebbero nel messaggio senza passare dagli hook
    data.setdefault("env", {})["CLAUDE_CODE_DISABLE_FILE_MENTIONS"] = "1"
    _save_json(path, data)
    _install_skill(Path.home() / ".claude" / "skills" / "clin")
    return f"Guardia installata in Claude Code ({path}). Comando /clin disponibile nelle nuove sessioni."


def protect_codex(base: Optional[Path]) -> str:
    path = (base / ".codex" / "hooks.json") if base else Path.home() / ".codex" / "hooks.json"
    data = _load_json(path)
    hooks = data.setdefault("hooks", {})
    cmd = _guard_command()
    _merge_event(hooks, "PreToolUse", {"matcher": "Bash|exec_command|shell",
                                       "hooks": [{"type": "command", "command": cmd, "timeout": 900}]})
    _merge_event(hooks, "UserPromptSubmit", {"hooks": [{"type": "command", "command": cmd, "timeout": 60}]})
    _merge_event(hooks, "Stop", {"hooks": [{"type": "command", "command": cmd + " stop", "timeout": 300}]})
    _save_json(path, data)
    _install_skill((base or Path.home()) / ".agents" / "skills" / "clin")
    return (f"Codex protetto ({path}). In Codex aprire /hooks e approvare l'hook di Clin "
            "(gli hook non approvati non vengono eseguiti).")


def protect_antigravity(base: Optional[Path]) -> str:
    path = (base / ".agents" / "hooks.json") if base else Path.home() / ".gemini" / "config" / "hooks.json"
    data = _load_json(path)
    data["clin"] = {"PreToolUse": [{
        "matcher": "view_file|view_file_outline|view_code_item|run_command|send_command_input|"
                   "grep_search|find_by_name|codebase_search",
        "hooks": [{"type": "command", "command": _guard_command(), "timeout": 900}]}],
        "Stop": [{"type": "command", "command": _guard_command() + " stop", "timeout": 300}]}
    _save_json(path, data)
    _install_skill((base / ".agents" / "skills" / "clin") if base
                   else Path.home() / ".gemini" / "config" / "skills" / "clin")
    return f"Antigravity protetto ({path}). Verificare in Customizations > Hooks che l'hook 'clin' sia attivo."


GUARD_FNS = {"claude-code": protect_claude_code, "codex": protect_codex, "antigravity": protect_antigravity}


def activate(folder: Path) -> str:
    """Attiva la guardia su una cartella (e sottocartelle): effetto immediato."""
    from datetime import date
    folder = folder.expanduser().resolve()
    marker = folder / ".clin-protetto"
    marker.write_text(f"Cartella protetta da Clin dal {date.today().isoformat()}.\n"
                      "Gli agenti IA leggono solo copie anonimizzate. Per disattivare: "
                      "/clin off oppure `clin.py disattiva`.\n", encoding="utf-8")
    return f"Protezione Clin attiva su {folder}."


def cmd_proteggi(a) -> int:
    base = None if a.globale else Path(a.cartella).expanduser().resolve()
    for name in (GUARD_FNS if a.agente == "tutti" else [a.agente]):
        notify(GUARD_FNS[name](base))
    if base:
        notify(activate(base))
    return 0


def detect_agents() -> list:
    """Agenti IA presenti sul computer."""
    import shutil
    home = Path.home()
    found = []
    if shutil.which("claude") or (home / ".local" / "bin" / "claude").exists():
        found.append("claude-code")
    if shutil.which("codex") or (home / ".codex").is_dir():
        found.append("codex")
    if (shutil.which("agy") or shutil.which("antigravity") or (home / ".gemini" / "antigravity").is_dir()
            or Path("/Applications/Antigravity.app").exists()):
        found.append("antigravity")
    return found


def cmd_installa(a) -> int:
    """Installazione una tantum: MCP, skill /clin e guardia dormiente."""
    agents = detect_agents() if a.agente == "auto" else list(GUARD_FNS) if a.agente == "tutti" else [a.agente]
    if not agents:
        raise ValueError("Nessun agente trovato (Claude Code, Codex, Antigravity): installarne uno e ripetere.")
    for name in agents:
        if name == "claude-code":
            notify(connect_claude_code())
        notify(GUARD_FNS[name](None))
    notify("Fatto. In una nuova sessione, dentro la cartella dei dati, scrivere /clin: "
           "la protezione si attiva su quella cartella.")
    return 0


def cmd_disinstalla(a) -> int:
    """Toglie hook, skill e server MCP di Clin; i dati in ~/.clin restano (salvo --tutto)."""
    import shutil
    home = Path.home()
    for path in (home / ".claude" / "settings.json", home / ".codex" / "hooks.json"):
        if path.exists():
            data = _load_json(path)
            hooks = data.get("hooks", {})
            for event in list(hooks):
                hooks[event] = [e for e in hooks[event] if not _is_clin(e)]
                if not hooks[event]:
                    del hooks[event]
            if path.parent.name == ".claude":
                data.get("env", {}).pop("CLAUDE_CODE_DISABLE_FILE_MENTIONS", None)
            _save_json(path, data)
    ag = home / ".gemini" / "config" / "hooks.json"
    if ag.exists():
        data = _load_json(ag)
        data.pop("clin", None)
        _save_json(ag, data)
    for d in (home / ".claude" / "skills" / "clin", home / ".agents" / "skills" / "clin",
              home / ".gemini" / "config" / "skills" / "clin"):
        shutil.rmtree(d, ignore_errors=True)
    claude = shutil.which("claude")
    if claude:
        subprocess.run([claude, "mcp", "remove", "--scope", "user", "clin"], capture_output=True)
    if a.tutto:
        shutil.rmtree(MAP_DIR, ignore_errors=True)
    notify("Clin disinstallato dagli agenti." + (" Dati locali cancellati." if a.tutto else
                                                 " Tabelle in ~/.clin conservate."))
    return 0


def cmd_attiva(a) -> int:
    notify(activate(Path(a.cartella)))
    return 0


def cmd_avvia(a) -> int:
    """Quello che fa /clin, in un solo comando: protegge la cartella e crea le copie anonime."""
    from clin_mcp import tool_crea_copie_anonime
    target = Path(a.percorso).expanduser().resolve()
    print(activate(target if target.is_dir() else target.parent))
    print(tool_crea_copie_anonime({"percorso": str(target)}))
    return 0


def cmd_stato(a) -> int:
    """Diagnosi: che cosa e' installato, per quali agenti, e se la cartella e' protetta."""
    import clin_llm
    import clin_ocr
    home = Path.home()
    here = Path(a.cartella).expanduser().resolve()
    root = next((f for f in [here, *here.parents] if (f / ".clin-protetto").is_file()), None)

    def has_hook(path: Path) -> bool:
        try:
            return "clin_guard.py" in path.read_text(encoding="utf-8")
        except OSError:
            return False

    agents = {  # nome: (file degli hook, cartella della skill)
        "Claude Code": (home / ".claude" / "settings.json", home / ".claude" / "skills" / "clin"),
        "Codex": (home / ".codex" / "hooks.json", home / ".agents" / "skills" / "clin"),
        "Antigravity": (home / ".gemini" / "config" / "hooks.json", home / ".gemini" / "config" / "skills" / "clin"),
    }
    found = detect_agents()
    print(f"Cartella: {here}")
    print("  protezione: " + (f"attiva (da {root})" if root else "non attiva: scrivere /clin nell'agente"))
    print("Agenti:")
    for (name, (hooks, skill)), ident in zip(agents.items(), GUARD_FNS):
        if ident not in found and not has_hook(hooks):
            print(f"  {name:<12} non presente su questo computer")
            continue
        ok = has_hook(hooks) and (skill / "SKILL.md").is_file()
        print(f"  {name:<12} {'pronto (guardia e /clin installati)' if ok else 'da collegare: clin.py installa'}")
    print(f"Nomi senza etichetta: {clin_llm.status()}")
    print(f"OCR per scansioni e foto: {'pronto' if clin_ocr.available() else 'assente (scripts/fetch_ocr_model.py)'}")
    return 0


def cmd_escludi(a) -> int:
    """File o cartelle senza dati di pazienti dentro una cartella protetta (lo decide solo l'utente)."""
    import clin_settings
    items = list(clin_settings.load()["percorsi_esclusi"])
    if a.percorso:
        target = str(Path(a.percorso).expanduser().resolve())
        if a.annulla:
            items = [i for i in items if i != target]
        elif not Path(target).exists():
            raise ValueError(f"Percorso inesistente: {target}")
        elif target not in items:
            items.append(target)
        clin_settings.save({"percorsi_esclusi": items})
    print("Percorsi esclusi dalla protezione (l'agente li legge cosi' come sono):" if items
          else "Nessun percorso escluso: nelle cartelle protette tutto viene anonimizzato.")
    for i in items:
        print(f"  {i}")
    return 0


def cmd_disattiva(a) -> int:
    folder = Path(a.cartella).expanduser().resolve()
    for f in [folder, *folder.parents]:
        if (f / ".clin-protetto").is_file():
            (f / ".clin-protetto").unlink()
            notify(f"Protezione Clin disattivata su {f}.")
            return 0
    notify("Nessuna cartella protetta da disattivare qui.")
    return 0


def python_path() -> str:
    """Interprete da usare nelle configurazioni dei client IA."""
    if sys.prefix != sys.base_prefix:  # ambiente virtuale (installer): ha i pacchetti di Clin
        return sys.executable
    candidate = Path(sys.base_prefix) / "bin" / "python3"
    return str(candidate if candidate.exists() else Path(sys.executable))


def claude_desktop_config() -> Path:
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if platform.system() == "Windows":
        return Path(os.environ.get("APPDATA", Path.home())) / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def connect_claude_desktop() -> str:
    """Aggiunge Clin ai server MCP di Claude Desktop (con copia di sicurezza)."""
    cfg = claude_desktop_config()
    data = {}
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8") or "{}")
        except ValueError:
            raise ValueError(f"Configurazione di Claude Desktop non leggibile: {cfg}")
        cfg.with_suffix(".json.bak").write_text(cfg.read_text(encoding="utf-8"), encoding="utf-8")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("mcpServers", {})["clin"] = {
        "command": python_path(), "args": [str(HERE / "clin.py"), "mcp"],
    }
    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return "Clin collegato a Claude Desktop. Riavviare Claude Desktop per attivarlo."


def connect_claude_code() -> str:
    """Registra il server MCP in Claude Code e installa la skill `clin`."""
    import shutil
    claude = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")
    if not Path(claude).exists():
        raise ValueError("Comando `claude` non trovato: installare prima Claude Code.")
    subprocess.run([claude, "mcp", "remove", "--scope", "user", "clin"], capture_output=True)
    subprocess.run([claude, "mcp", "add", "--scope", "user", "clin", "--",
                    python_path(), str(HERE / "clin.py"), "mcp"],
                   check=True, capture_output=True, text=True)
    _install_skill(Path.home() / ".claude" / "skills" / "clin")
    return "Clin collegato a Claude Code (server MCP e skill `clin`)."


def cmd_collega(a) -> int:
    fn = {"claude-desktop": connect_claude_desktop, "claude-code": connect_claude_code}[a.client]
    notify(fn())
    return 0


def cmd_mcp(a) -> int:
    from clin_mcp import serve
    serve()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="clin", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("testo", help="stampa il testo anonimizzato di un documento")
    p.add_argument("file")
    p.add_argument("--salva-tabella", action="store_true",
                   help="salva la tabella segnaposto per `ripristina`")
    p.set_defaults(fn=cmd_testo)

    sub.add_parser("appunti", help="anonimizza il testo negli appunti").set_defaults(fn=cmd_appunti)

    sub.add_parser("ripristina", help="rimette i dati originali negli appunti").set_defaults(fn=cmd_ripristina)
    p = sub.add_parser("risultati", help="riconduce ai dati reali i risultati con segnaposto (cartella invisibile all'agente)")
    p.add_argument("cartella", nargs="?", default=".")
    p.set_defaults(fn=cmd_risultati)
    p = sub.add_parser("impostazioni", help="mostra o modifica le impostazioni per gli agenti IA")
    p.add_argument("chiave", nargs="?")
    p.add_argument("valore", nargs="?")
    p.set_defaults(fn=cmd_impostazioni)
    p = sub.add_parser("ner", help="riconoscimento rapido dei nomi con GLiNER (installa | stato)")
    p.add_argument("azione", choices=["installa", "stato"])
    p.set_defaults(fn=cmd_ner)
    p = sub.add_parser("originale", help="valore originale di uno pseudonimo dei fogli (es. PAZ-0147), in locale")
    p.add_argument("codice")
    p.set_defaults(fn=cmd_originale)
    p = sub.add_parser("copie", help="crea copie anonime di un file o di una cartella (Clin_anonimizzati/)")
    p.add_argument("percorso")
    p.set_defaults(fn=cmd_copie)
    p = sub.add_parser("avvia", help="protegge la cartella e crea le copie anonime (cio' che fa /clin)")
    p.add_argument("percorso", nargs="?", default=".")
    p.set_defaults(fn=cmd_avvia)
    p = sub.add_parser("escludi", help="dichiara senza dati di pazienti un file o una cartella (articoli, linee guida)")
    p.add_argument("percorso", nargs="?")
    p.add_argument("--annulla", action="store_true", help="toglie il percorso dall'elenco")
    p.set_defaults(fn=cmd_escludi)
    p = sub.add_parser("stato", help="diagnosi: agenti collegati, protezione della cartella, motori")
    p.add_argument("cartella", nargs="?", default=".")
    p.set_defaults(fn=cmd_stato)
    p = sub.add_parser("installa", help="installazione una tantum: MCP, /clin e guardia (dormiente)")
    p.add_argument("--agente", choices=["auto", "claude-code", "codex", "antigravity", "tutti"], default="auto",
                   help="default: tutti gli agenti trovati sul computer")
    p.set_defaults(fn=cmd_installa)
    p = sub.add_parser("disinstalla", help="toglie hook, skill e MCP di Clin dagli agenti")
    p.add_argument("--tutto", action="store_true", help="cancella anche ~/.clin (segnaposto e pseudonimi)")
    p.set_defaults(fn=cmd_disinstalla)
    for name, fn, hlp in (("attiva", cmd_attiva, "attiva la guardia su una cartella"),
                          ("disattiva", cmd_disattiva, "disattiva la guardia su una cartella")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("cartella", nargs="?", default=".")
        p.set_defaults(fn=fn)
    p = sub.add_parser("proteggi", help="installa la guardia (hook) e il comando /clin negli agenti IA")
    p.add_argument("cartella", nargs="?", default=".", help="progetto da proteggere (default: cartella corrente)")
    p.add_argument("--agente", choices=["claude-code", "codex", "antigravity", "tutti"], default="claude-code")
    p.add_argument("--globale", action="store_true", help="tutti i progetti dell'utente")
    p.set_defaults(fn=cmd_proteggi)
    sub.add_parser("dimentica", help="cancella la tabella segnaposto").set_defaults(fn=cmd_dimentica)
    sub.add_parser("mcp", help="server MCP su stdio").set_defaults(fn=cmd_mcp)
    p = sub.add_parser("collega", help="collega Clin a un client IA")
    p.add_argument("client", choices=["claude-desktop", "claude-code"])
    p.set_defaults(fn=cmd_collega)

    a = parser.parse_args(argv)
    if not getattr(a, "fn", None):
        import clin_gui
        clin_gui.main()
        return 0
    try:
        return a.fn(a)
    except (ValueError, subprocess.CalledProcessError) as exc:
        notify(f"Errore: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
