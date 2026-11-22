"""
Valutazione di Clin su un dataset esterno in formato JSONL con intervalli esatti
(es. il Pan-European Synthetic PII Benchmark: 40 lingue, latino, cirillico, greco).

Un dato conta come rimosso se almeno il 90% dei suoi caratteri e' coperto (alcuni
segnaposto lasciano fuori il titolo o la punteggiatura). I codici ICD sono contenuto
clinico: per Clin devono restare, e si contano a parte.

    python3 tests/benchmark/run_eu.py DATASET.jsonl                    # regole + modello locale
    python3 tests/benchmark/run_eu.py DATASET.jsonl --regole --per-lingua 250
    python3 tests/benchmark/run_eu.py DATASET.jsonl --mancati it,de
"""
import argparse
import collections
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

ap = argparse.ArgumentParser()
ap.add_argument("dataset")
ap.add_argument("--regole", action="store_true")
ap.add_argument("--per-lingua", type=int, default=50)
ap.add_argument("--mancati", default="", help="lingue di cui elencare i dati mancati e i falsi positivi")
args = ap.parse_args()
if args.regole:
    os.environ["CLIN_LLM"] = "0"

import clin_llm  # noqa: E402
from anonymize_engine import collect_names  # noqa: E402
from clin_text import find_spans  # noqa: E402

KEEP = {"ICD_CODE"}
rows = [json.loads(l) for l in open(args.dataset, encoding="utf-8")]
by_lang = collections.defaultdict(list)
for r in rows:
    by_lang[r["language"]].append(r)
rnd = random.Random(7)
sample = [r for lang in sorted(by_lang) for r in rnd.sample(by_lang[lang], min(args.per_lingua, len(by_lang[lang])))]

hit, tot = collections.Counter(), collections.Counter()
lang_hit, lang_tot = collections.Counter(), collections.Counter()
kept, kept_tot = collections.Counter(), collections.Counter()
fp_spans = collections.Counter()
details = collections.defaultdict(list)
show = set(filter(None, args.mancati.split(",")))
t0 = time.time()
for r in sample:
    text, lang = r["text"], r["language"]
    spans = find_spans(text, 10, names=collect_names(text))
    covered = bytearray(len(text))
    for s, e, _ in spans:
        covered[s:e] = b"\x01" * (e - s)
    for ent in r["entities"]:
        n = ent["end"] - ent["start"]
        frac = sum(covered[ent["start"]:ent["end"]]) / max(1, n)
        if ent["label"] in KEEP:
            kept_tot[lang] += 1
            kept[lang] += frac < 0.5
            if frac >= 0.5 and lang in show:
                details[lang].append(f"ICD COPERTO: {ent['text']}")
            continue
        tot[ent["label"]] += 1
        lang_tot[lang] += 1
        if frac >= 0.9:
            hit[ent["label"]] += 1
            lang_hit[lang] += 1
        elif lang in show:
            details[lang].append(f"{ent['label']}: {ent['text']}  [{frac:.0%}]")
    gold = [(e["start"], e["end"]) for e in r["entities"]]
    for s, e, cat in spans:  # coperto ma fuori da ogni dato del dataset
        if not any(s < ge and e > gs for gs, ge in gold):
            fp_spans[cat] += 1
            if lang in show:
                details[lang].append(f"COPERTO IN PIU' ({cat}): {text[s:e]}")

dt = (time.time() - t0) / len(sample)
print(f"motore: {clin_llm.status()} · {len(sample)} referti · {len(by_lang)} lingue · {dt:.2f}s per referto")
print("\nper etichetta (rimossi):")
for k in sorted(tot):
    print(f"  {k:<18} {hit[k]:>6}/{tot[k]:<6} {hit[k] / tot[k]:.3f}")
all_hit, all_tot = sum(hit.values()), sum(tot.values())
print(f"  {'TOTALE':<18} {all_hit:>6}/{all_tot:<6} {all_hit / all_tot:.3f}")
print(f"\ncodici ICD lasciati intatti: {sum(kept.values())}/{sum(kept_tot.values())}")
print(f"coperture fuori dai dati del dataset: {dict(fp_spans)}")
print("\nper lingua (rimossi):")
langs = sorted(lang_tot, key=lambda l: lang_hit[l] / lang_tot[l])
print("  " + "  ".join(f"{l} {lang_hit[l] / lang_tot[l]:.2f}" for l in langs))
for lang in show:
    print(f"\n[{lang}]")
    for line in sorted(set(details[lang]))[:40]:
        print("  " + line)
