"""
Converte una sessione di Claude Code registrata con
`claude -p ... --output-format stream-json --verbose` nel file docs/demo.json,
riprodotto nel sito da docs/demo.js con l'aspetto dell'interfaccia di Claude Code.
Solo dati sintetici; percorsi e nome utente vengono rimossi.

    python3 tools/demo_from_session.py CARTELLA_STUDIO "prompt 1" r1.jsonl "prompt 2" r2.jsonl ... > docs/demo.json
"""
import getpass
import json
import re
import sys

folder = sys.argv[1]
pairs = list(zip(sys.argv[2::2], sys.argv[3::2]))   # (prompt digitato, registrazione del turno)
ROOT = "~/Ricerca/Studio_TAVI"


def clean(s: str) -> str:
    s = s.replace(folder + "/", "").replace(folder, ROOT)
    s = s.replace(getpass.getuser(), "utente")             # nessun nome utente reale nel sito
    s = re.sub(r'"?/[^\s"]*/python3(\.\d+)?"?', "python3", s)
    s = re.sub(r'"?/[^\s"]*/clin\.py"?', "clin.py", s)
    s = re.sub(r"/private/tmp/\S*?/Studio_TAVI/?", "", s)
    return s


def cut(s: str, n: int) -> str:
    s = clean(s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


steps = []
for prompt, f in pairs:
    files = re.findall(r"@([\w.\-/]+?)(?=[\s,:;]|\.(?:\s|$)|$)", prompt)
    shown = re.sub(r"\s*@[\w.\-/]+?(?=[\s,:;]|\.(?:\s|$)|$)", "", prompt).replace(":.", ".").replace(" ,", ",")
    steps.append({"type": "user", "text": prompt, "shown": shown, "files": files})
    uses = {}
    for d in (json.loads(l) for l in open(f)):
        t = d.get("type")
        if t == "assistant":
            for c in d["message"]["content"]:
                if c["type"] == "text" and c["text"].strip():
                    steps.append({"type": "assistant", "text": cut(c["text"], 1400)})
                elif c["type"] == "tool_use":
                    inp, name = c["input"], c["name"]
                    if inp.get("description"):
                        steps.append({"type": "think", "text": cut(inp["description"], 90)})
                    if name == "Bash":
                        arg = (inp.get("command") or "").splitlines()[0] if inp.get("command") else ""
                    elif name in ("Read", "Write", "Edit"):
                        arg = clean(inp.get("file_path", ""))
                    elif name == "Glob":
                        arg = inp.get("pattern", "")
                    else:
                        arg = json.dumps(inp, ensure_ascii=False)
                    step = {"type": "tool", "name": name, "arg": cut(arg, 90), "out": [], "more": 0, "ok": True}
                    uses[c["id"]] = (step, inp)
                    steps.append(step)
        elif t == "user" and isinstance(d["message"]["content"], list):
            for c in d["message"]["content"]:
                if c.get("type") != "tool_result" or c.get("tool_use_id") not in uses:
                    continue
                step, inp = uses[c["tool_use_id"]]
                cont = c.get("content")
                txt = cont if isinstance(cont, str) else " ".join(x.get("text", "") for x in cont if isinstance(x, dict))
                if "Clin:" in txt and (c.get("is_error") or "nega" in txt):
                    step["ok"] = False
                    steps.append({"type": "clin", "text": cut(txt[txt.index("Clin:") + 5:], 220)})
                    continue
                lines = [l for l in clean(txt).splitlines() if l.strip()]
                if step["name"] == "Read":
                    path = inp.get("file_path", "")
                    step["out"] = [f"Read {max(1, len(lines))} lines"] if not txt.startswith("PDF") else ["Read PDF (1 pagina)"]
                    if "/Clin_anonimizzati/" not in path and "letture" not in path:
                        name = path.rsplit("/", 1)[-1]
                        steps.append({"type": "clin", "text": f"letta la copia anonimizzata di {name}: l'originale non entra nella conversazione"})
                elif step["name"] == "Write":
                    n = len((inp.get("content") or "").splitlines())
                    step["out"] = [f"Wrote {n} lines to {clean(inp.get('file_path', ''))}"]
                else:
                    step["out"] = [cut(l, 100) for l in lines[:3]] or ["(No content)"]
                    step["more"] = max(0, len(lines) - 3)
        elif t == "system" and d.get("subtype") == "informational" and "Clin:" in d.get("content", ""):
            steps.append({"type": "clin", "text": cut(d["content"].split("Clin:", 1)[1], 200)})

out = {"meta": "Ricostruzione dell'interfaccia di Claude Code con una sessione reale (Sonnet) su dati sintetici; percorsi abbreviati.",
       "cwd": ROOT, "steps": steps}
print(json.dumps(out, ensure_ascii=False, indent=1))
