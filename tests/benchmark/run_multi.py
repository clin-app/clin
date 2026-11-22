"""
Benchmark multilingue: quanti dati personali restano nel testo anonimizzato, per lingua.
Un dato conta come rimosso se il valore originale non compare piu' nel risultato.

    python3 tests/benchmark/run_multi.py            # regole + modello locale, se presente
    python3 tests/benchmark/run_multi.py --regole   # solo regole
"""
import argparse
import collections
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))

ap = argparse.ArgumentParser()
ap.add_argument("--regole", action="store_true")
ap.add_argument("--per-lingua", type=int, default=20)
ap.add_argument("--mancati", action="store_true", help="mostra i dati rimasti nel testo")
args = ap.parse_args()
if args.regole:
    os.environ["CLIN_LLM"] = "0"

import clin_llm  # noqa: E402
from clin_text import anonymize_text  # noqa: E402
from generate_multi import generate  # noqa: E402

docs = generate(args.per_lingua)
hit, tot = collections.Counter(), collections.Counter()
neg_ok, neg_tot = collections.Counter(), collections.Counter()
missed = collections.defaultdict(list)
t0 = time.time()
for d in docs:
    out = anonymize_text(d["text"], level=10).text
    for s in d["spans"]:
        k = (d["lang"], s["label"])
        tot[k] += 1
        if s["text"] not in out:
            hit[k] += 1
        else:
            missed[d["lang"]].append(f'{s["label"]}/{s["sub"]}: {s["text"]}')
    for n in d["negatives"]:
        neg_tot[d["lang"]] += 1
        neg_ok[d["lang"]] += n["text"] in out
        if n["text"] not in out:
            missed[d["lang"]].append(f'FALSO POSITIVO: {n["text"]}')

print(f"motore: {clin_llm.status()} · {len(docs)} documenti · {(time.time() - t0) / len(docs):.2f}s per documento")
labels = sorted({k[1] for k in tot})
print("lingua " + " ".join(f"{l[:10]:>11}" for l in labels) + "   clinici intatti")
for lang in sorted({k[0] for k in tot}):
    cells = []
    for l in labels:
        n = tot[(lang, l)]
        cells.append(f"{hit[(lang, l)] / n:>11.2f}" if n else f"{'-':>11}")
    print(f"{lang:<6} " + " ".join(cells) + f"   {neg_ok[lang]}/{neg_tot[lang]}")
all_hit, all_tot = sum(hit.values()), sum(tot.values())
print(f"complessivo: {all_hit}/{all_tot} = {all_hit / all_tot:.3f}; clinici intatti {sum(neg_ok.values())}/{sum(neg_tot.values())}")
if args.mancati:
    for lang, items in missed.items():
        print(f"\n[{lang}]", "; ".join(sorted(set(items))[:25]))
