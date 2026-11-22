"""
Misura l'estensione (motore + GLiNER in WebAssembly) dentro Chromium, sullo stesso
formato JSONL di tests/benchmark/run_eu.py. Un dato conta come rimosso se il testo
originale non compare piu' nel risultato; i codici ICD devono restare.

    python3 extension/build.py
    python3 tools/bench_estensione.py DATASET.jsonl --per-lingua 10

Richiede Playwright con Chromium (pip install playwright; playwright install chromium).
"""
import argparse
import asyncio
import collections
import json
import random
import tempfile
import time
from pathlib import Path

from playwright.async_api import async_playwright

ap = argparse.ArgumentParser()
ap.add_argument("dataset")
ap.add_argument("--per-lingua", type=int, default=10)
ap.add_argument("--estensione", default=str(Path(__file__).resolve().parent.parent / "extension" / "dist"))
args = ap.parse_args()

rows = [json.loads(l) for l in open(args.dataset, encoding="utf-8")]
by = collections.defaultdict(list)
for r in rows:
    by[r["language"]].append(r)
rnd = random.Random(7)
docs = [r for lang in sorted(by) for r in rnd.sample(by[lang], min(args.per_lingua, len(by[lang])))]


async def launch(p):
    """Chromium con l'estensione, motore pronto, e una pagina da cui mandare i messaggi."""
    ext = args.estensione
    ctx = await p.chromium.launch_persistent_context(
        tempfile.mkdtemp(prefix="clin-bench-"), headless=True, channel="chromium",
        args=[f"--disable-extensions-except={ext}", f"--load-extension={ext}"])
    sw = ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event("serviceworker")
    await sw.evaluate("chrome.offscreen.createDocument({url: 'offscreen.html', reasons: ['WORKERS'], "
                      "justification: 'benchmark'}).catch(() => {})")
    await asyncio.sleep(15)  # motore e modello si caricano
    # i messaggi partono da una pagina dell'estensione: il service worker puo' essere chiuso da Chrome
    page = await ctx.new_page()
    await page.goto(sw.url.rsplit("/", 1)[0] + "/manifest.json")
    return ctx, page


async def main():
    async with async_playwright() as p:
        ctx, page = await launch(p)
        restarts = 0
        hit, tot, lh, lt = (collections.Counter() for _ in range(4))
        icd_ok = icd_tot = 0
        missed = []
        t0 = time.time()
        for d in docs:
            for attempt in range(2):
                try:
                    r = await page.evaluate("(t) => chrome.runtime.sendMessage({target: 'offscreen', op: 'anonymize', "
                                            "items: [{kind: 'testo incollato', text: t}], previous: {}})", d["text"])
                    break
                except Exception:  # browser chiuso (memoria): si riparte e si ripete il referto
                    restarts += 1
                    try:
                        await ctx.close()
                    except Exception:
                        pass
                    ctx, page = await launch(p)
            out = r["text"]
            for e in d["entities"]:
                if e["label"] == "ICD_CODE":
                    icd_tot += 1
                    icd_ok += e["text"] in out
                    continue
                tot[e["label"]] += 1
                lt[d["language"]] += 1
                if e["text"] not in out:
                    hit[e["label"]] += 1
                    lh[d["language"]] += 1
                else:
                    missed.append((d["language"], e["label"], e["text"]))
        print(f"{len(docs)} referti nel browser, {(time.time() - t0) / len(docs):.2f}s per referto, riavvii {restarts}")
        for k in sorted(tot):
            print(f"  {k:<18} {hit[k]}/{tot[k]} = {hit[k] / tot[k]:.3f}")
        print(f"  TOTALE {sum(hit.values())}/{sum(tot.values())} = {sum(hit.values()) / sum(tot.values()):.3f}; "
              f"ICD intatti {icd_ok}/{icd_tot}")
        print("  lingue peggiori:", sorted((round(lh[l] / lt[l], 2), l) for l in lt)[:6])
        print("  esempi mancati:", missed[:15])
        await ctx.close()


asyncio.run(main())
