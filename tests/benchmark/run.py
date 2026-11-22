"""
Benchmark di Clin su referti sintetici. Un solo comando:

    python3 tests/benchmark/run.py            # regole + modello locale (se Ollama c'e')
    python3 tests/benchmark/run.py --regole   # solo regole (CLIN_LLM=0)
    python3 tests/benchmark/run.py --salva    # aggiorna tests/benchmark/baseline.json

Misura cio' che Clin sostituisce davvero con i segnaposto (`clin_text`):
* recall per etichetta e sottotipo: un valore conta come trovato solo se
  coperto per intero (nessun carattere alfanumerico lasciato leggibile);
  "parziale" conta anche le coperture incomplete;
* precisione per etichetta: ogni span oscurato che non tocca alcun valore
  vero e' un falso positivo, attribuito all'etichetta della sua categoria;
* falsi positivi per documento e per tipo di hard negative clinico.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

ENGINE_TO_LABEL = {
    "ID ufficiali": "ID_UFFICIALE", "Nome paziente": "PERSONA", "Ricorrenze nominativo": "PERSONA",
    "Persone": "PERSONA", "Medici": "PERSONA", "Personale sanitario": "PERSONA",
    "Personalizzati": "PERSONA", "Data di nascita": "NASCITA_ETA", "Contatti": "CONTATTO",
    "Provenienza": "CONTATTO", "Dati bancari": "IBAN", "Identificativi clinici": "ID_CLINICO",
    "Documenti": "ID_CLINICO", "Struttura sanitaria": "STRUTTURA", "Date": "DATA",
    "Scansione profonda": "DATA",
}


def predicted_spans(text: str, level: int):
    from anonymize_engine import collect_names
    import clin_text
    names = collect_names(text)
    if hasattr(clin_text, "find_spans"):
        return clin_text.find_spans(text, level, names=names)
    # versioni precedenti di Clin: stessa logica di `_replace`
    from anonymize_engine import find_matches
    spans = sorted(((m.start, m.end, m.category) for m in find_matches(
        text, level, keep_labels=True, derived_targets=names)), key=lambda t: (t[0], -(t[1] - t[0])))
    chosen = []
    for s, e, c in spans:
        while s < e and text[s] in " \t\n,;:.()":
            s += 1
        while e > s and text[e - 1] in " \t\n,;:()":
            e -= 1
        if e <= s:
            continue
        if chosen and s < chosen[-1][1]:
            if e > chosen[-1][1]:
                chosen[-1] = (chosen[-1][0], e, chosen[-1][2])
            continue
        chosen.append((s, e, c))
    return chosen


def evaluate(docs, level: int) -> dict:
    gold_n = defaultdict(int)
    full = defaultdict(int)
    partial = defaultdict(int)
    sub_n = defaultdict(int)
    sub_full = defaultdict(int)
    tp_pred = defaultdict(int)
    fp_pred = defaultdict(int)
    fp_neg = defaultdict(int)
    neg_n = defaultdict(int)
    missed = defaultdict(list)
    fps = []
    t0 = time.time()
    for d in docs:
        text = d["text"]
        pred = predicted_spans(text, level)
        covered = [False] * len(text)
        for s, e, _ in pred:
            for i in range(s, e):
                covered[i] = True
        for g in d["spans"]:
            chars = [i for i in range(g["start"], g["end"]) if text[i].isalnum()]
            hit = [covered[i] for i in chars]
            key = f'{g["label"]}/{g["sub"]}'
            gold_n[g["label"]] += 1
            sub_n[key] += 1
            if all(hit):
                full[g["label"]] += 1
                sub_full[key] += 1
            elif len(missed[key]) < 5:
                missed[key].append(g["text"])
            if any(hit):
                partial[g["label"]] += 1
        for s, e, cat in pred:
            overlap = [g for g in d["spans"] if g["start"] < e and s < g["end"]]
            if overlap:
                best = max(overlap, key=lambda g: min(e, g["end"]) - max(s, g["start"]))
                tp_pred[best["label"]] += 1
                continue
            label = ENGINE_TO_LABEL.get(cat, cat)
            fp_pred[label] += 1
            neg = next((n for n in d["negatives"] if n["start"] < e and s < n["end"]), None)
            if neg:
                fp_neg[neg["kind"]] += 1
            if len(fps) < 40:
                fps.append({"doc": d["id"], "categoria": cat, "testo": text[s:e]})
        for n in d["negatives"]:
            neg_n[n["kind"]] += 1

    def prf(label):
        r = full[label] / gold_n[label] if gold_n[label] else 0.0
        tp, fp = tp_pred[label], fp_pred[label]
        p = tp / (tp + fp) if tp + fp else 1.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        return {"n": gold_n[label], "precisione": round(p, 3), "recall": round(r, 3), "f1": round(f, 3),
                "recall_parziale": round(partial[label] / gold_n[label], 3) if gold_n[label] else 0.0,
                "falsi_positivi": fp}

    labels = sorted(set(gold_n) | set(fp_pred))
    total_gold = sum(gold_n.values())
    total_tp, total_fp = sum(tp_pred.values()), sum(fp_pred.values())
    micro_r = sum(full.values()) / total_gold
    micro_p = total_tp / (total_tp + total_fp) if total_tp + total_fp else 1.0
    return {
        "documenti": len(docs),
        "secondi_per_documento": round((time.time() - t0) / len(docs), 3),
        "complessivo": {"precisione": round(micro_p, 3), "recall": round(micro_r, 3),
                        "f1": round(2 * micro_p * micro_r / (micro_p + micro_r), 3) if micro_p + micro_r else 0.0,
                        "falsi_positivi_per_documento": round(total_fp / len(docs), 3)},
        "per_etichetta": {lb: prf(lb) for lb in labels},
        "recall_per_sottotipo": {k: round(sub_full[k] / sub_n[k], 3) for k in sorted(sub_n)},
        "falsi_positivi_su_hard_negative": {k: f"{fp_neg[k]}/{neg_n[k]}" for k in sorted(neg_n)},
        "esempi_mancati": dict(missed),
        "esempi_falsi_positivi": fps,
    }


def print_report(name: str, r: dict) -> None:
    c = r["complessivo"]
    print(f"\n== {name}: {r['documenti']} documenti, {r['secondi_per_documento']} s/doc ==")
    print(f"complessivo  P {c['precisione']:.3f}  R {c['recall']:.3f}  F1 {c['f1']:.3f}  "
          f"FP/doc {c['falsi_positivi_per_documento']}")
    print(f"{'etichetta':<14}{'n':>5}{'P':>8}{'R':>8}{'F1':>8}{'R parz.':>9}{'FP':>5}")
    for lb, m in r["per_etichetta"].items():
        print(f"{lb:<14}{m['n']:>5}{m['precisione']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}"
              f"{m['recall_parziale']:>9.3f}{m['falsi_positivi']:>5}")
    print("recall per sottotipo:", ", ".join(f"{k} {v:.2f}" for k, v in r["recall_per_sottotipo"].items()))
    print("FP su hard negative:", ", ".join(f"{k} {v}" for k, v in r["falsi_positivi_su_hard_negative"].items()))


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regole", action="store_true", help="solo regole, senza modello locale")
    ap.add_argument("--documenti", type=int, default=150)
    ap.add_argument("--livello", type=int, default=10, help=argparse.SUPPRESS)  # solo per versioni vecchie
    ap.add_argument("--salva", action="store_true", help="scrive il risultato in baseline.json")
    ap.add_argument("--nome", default=None, help="chiave sotto cui salvare (default: regole/regole+modello)")
    ap.add_argument("--json", action="store_true", help="stampa il risultato completo in JSON")
    a = ap.parse_args(argv)
    if a.regole:
        os.environ["CLIN_LLM"] = "0"
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(HERE))
    from generate import generate
    try:
        import clin_llm
        engine = clin_llm.status()
    except ImportError:
        engine = "solo regole (versione senza modello)"
    name = a.nome or ("regole" if a.regole or engine.startswith("solo") else "regole+modello")
    result = evaluate(generate(a.documenti), a.livello)
    result["motore"] = engine
    print_report(f"{name} — {engine}", result)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    if a.salva:
        path = HERE / "baseline.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        data[name] = result
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"salvato in {path} sotto '{name}'")
    return result


if __name__ == "__main__":
    main()
