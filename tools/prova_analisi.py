"""
Prova di andata e ritorno su uno studio simulato: le stesse analisi statistiche vengono eseguite
sui dati reali (verita') e sulle copie anonime create da Clin, come farebbe un agente; i risultati
dell'agente vengono poi ricondotti ai dati reali da Clin e confrontati con la verita', file per file.

    python3 tools/prova_analisi.py [--pazienti 400]

Lo studio: un registro Excel (anagrafica, date di nascita e di intervento, classe NYHA) e un
follow-up CSV (date di controllo e di decesso) collegati dall'ID di studio. Le analisi coprono cio'
che un ricercatore chiede davvero: eta', tempi di follow-up e di sopravvivenza, mortalita' per
classe, andamento per anno, mese, stagione e giorno della settimana, elenco dei deceduti, relazione.

Si provano le due modalita' delle date: numero segreto di giorni e 400 anni esatti (calendario).
Dati inventati; tutto avviene in una cartella temporanea, con una cartella dati di Clin separata.
Richiede pandas e openpyxl.
"""
import argparse
import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
COGNOMI = ["Rossi", "Bianchi", "Ferrari", "Russo", "Esposito", "Romano", "Colombo", "Ricci", "Marino", "Greco",
           "Bruno", "Gallo", "Conti", "De Luca", "Mancini", "Costa", "Giordano", "Rizzo", "Lombardi", "Moretti"]
NOMI = ["Mario", "Anna", "Luca", "Giulia", "Paolo", "Francesca", "Marco", "Elena", "Giovanni", "Sara",
        "Antonio", "Chiara", "Roberto", "Laura", "Stefano", "Martina", "Andrea", "Silvia", "Franco", "Paola"]


def simulate(folder: Path, n: int, seed: int = 7) -> None:
    import pandas as pd
    rnd = random.Random(seed)
    reg, fu = [], []
    for i in range(1, n + 1):
        birth = dt.date(1930, 1, 1) + dt.timedelta(days=rnd.randrange(0, 365 * 45))
        op = dt.date(2019, 1, 1) + dt.timedelta(days=rnd.randrange(0, 365 * 6))
        nyha = rnd.choice(["II", "III", "III", "IV"])
        dead = rnd.random() < {"II": .10, "III": .22, "IV": .45}[nyha]
        last = op + dt.timedelta(days=rnd.randrange(30, 900))
        sid = f"TAVI-{i:03d}"
        cf = "".join(rnd.choice("ABCDEFGHILMNOPRSTUVZ") for _ in range(6)) + f"{birth.year % 100:02d}A{birth.day:02d}H501X"
        reg.append({"ID studio": sid, "Cognome": rnd.choice(COGNOMI), "Nome": rnd.choice(NOMI), "Codice fiscale": cf,
                    "Data di nascita": pd.Timestamp(birth), "Data intervento": pd.Timestamp(op), "Classe NYHA": nyha,
                    "EuroSCORE II": round(rnd.uniform(1, 12), 1)})
        fu.append({"ID studio": sid, "Data follow-up": last.strftime("%d/%m/%Y"), "Stato": "deceduto" if dead else "vivo",
                   "Data decesso": last.strftime("%d/%m/%Y") if dead else ""})
    pd.DataFrame(reg).to_excel(folder / "registro_TAVI.xlsx", index=False)
    pd.DataFrame(fu).to_csv(folder / "follow_up.csv", index=False)


def analyse(reg_path: Path, fu_path: Path, out: Path) -> None:
    """L'analisi che scriverebbe un agente: legge i due file, li unisce e salva tabelle e relazione."""
    import pandas as pd
    out.mkdir(parents=True, exist_ok=True)
    reg = pd.read_excel(reg_path)
    fu = pd.read_csv(fu_path)
    for c in ("Data di nascita", "Data intervento"):
        reg[c] = pd.to_datetime(reg[c])
    for c in ("Data follow-up", "Data decesso"):
        fu[c] = pd.to_datetime(fu[c], format="%d/%m/%Y")
    d = reg.merge(fu, on="ID studio", validate="one_to_one")
    d["eta"] = ((d["Data intervento"] - d["Data di nascita"]).dt.days // 365.25).astype(int)
    d["giorni_fu"] = (d["Data follow-up"] - d["Data intervento"]).dt.days
    d["morto"] = d["Stato"].eq("deceduto")
    d["anno"] = d["Data intervento"].dt.year
    d["mese"] = d["Data intervento"].dt.strftime("%Y-%m")
    d["stagione"] = d["Data intervento"].dt.month.map(
        lambda m: "inverno" if m in (12, 1, 2) else "primavera" if m <= 5 else "estate" if m <= 8 else "autunno")
    d["giorno"] = d["Data intervento"].dt.dayofweek

    by = d.groupby("Classe NYHA").agg(pazienti=("morto", "size"), deceduti=("morto", "sum"),
                                      eta_media=("eta", "mean"), fu_mediano=("giorni_fu", "median"))
    by["mortalita_pct"] = (100 * by["deceduti"] / by["pazienti"]).round(1)
    by["eta_media"] = by["eta_media"].round(1)
    by.to_csv(out / "mortalita_per_nyha.csv")
    d.groupby("anno").agg(interventi=("morto", "size"), deceduti=("morto", "sum")).to_csv(out / "per_anno.csv")
    d.groupby("mese").size().rename("interventi").to_csv(out / "per_mese.csv")
    d.groupby("stagione").agg(interventi=("morto", "size"), deceduti=("morto", "sum")).to_csv(out / "per_stagione.csv")
    d.groupby("giorno").size().rename("interventi").to_csv(out / "per_giorno_settimana.csv")
    surv = d[d["morto"]].assign(giorni=lambda x: (x["Data decesso"] - x["Data intervento"]).dt.days)
    surv[["ID studio", "Cognome", "Classe NYHA", "eta", "Data intervento", "Data decesso", "giorni"]].to_excel(
        out / "deceduti.xlsx", index=False)

    first, last = d["Data intervento"].min(), d["Data intervento"].max()
    worst = surv.sort_values(["giorni", "ID studio"]).iloc[0]
    words = lambda t: f"{t.day} {MESI[t.month - 1]} {t.year}"
    top_year = d["anno"].value_counts().sort_index().idxmax()
    lines = [
        "# Relazione",
        f"Pazienti: {len(d)}. Eta' media all'intervento {d['eta'].mean():.1f} anni (min {d['eta'].min()}, max {d['eta'].max()}).",
        f"Follow-up mediano {d['giorni_fu'].median():.0f} giorni; deceduti {int(d['morto'].sum())} ({100 * d['morto'].mean():.1f}%).",
        f"Sopravvivenza mediana dei deceduti: {surv['giorni'].median():.0f} giorni.",
        f"Primo intervento il {words(first)}, ultimo il {last.strftime('%d/%m/%Y')} ({last.date().isoformat()}).",
        f"Periodo dello studio: {first.year}-{last.year}. L'anno con piu' interventi e' stato il {top_year}: nel {top_year} "
        f"sono stati eseguiti {int((d['anno'] == top_year).sum())} interventi.",
        f"Decesso piu' precoce: paziente {worst['ID studio']} ({worst['Cognome']}), operato il {words(worst['Data intervento'])} "
        f"e deceduto il {words(worst['Data decesso'])}, dopo {int(worst['giorni'])} giorni.",
        f"Interventi in inverno: {int((d['stagione'] == 'inverno').sum())}; di lunedi': {int((d['giorno'] == 0).sum())}.",
        # la stessa data in tutte le forme in cui un agente puo' scriverla
        "Formati: " + " | ".join([
            first.strftime("%Y-%m-%d"), first.strftime("%Y/%m/%d"), first.strftime("%d/%m/%Y"), first.strftime("%d.%m.%Y"),
            first.strftime("%d-%m-%Y"), first.strftime("%Y%m%d"), first.strftime("%Y-%m-%d %H:%M:%S"),
            f"{first.day} {MESI[first.month - 1][:3]} {first.year}", f"{first.day}-{MESI[first.month - 1][:3]}-{first.year}",
            f"{GIORNI[first.dayofweek]} {words(first)}", first.strftime("%B %d, %Y"), first.strftime("%A, %b %d, %Y"),
            f"{first.day} {first.strftime('%B')} {first.year}"]) + ".",
        f"Parziali: {MESI[first.month - 1]} {first.year} | {first.strftime('%Y-%m')} | Q{(first.month - 1) // 3 + 1} {first.year} "
        f"| dal {first.year} al {last.year} | ({first.year}) | {first.year}-{last.year}.",
    ]
    (out / "relazione.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load(path: Path):
    """Contenuto confrontabile di un file di risultati."""
    if path.suffix == ".xlsx":
        from openpyxl import load_workbook
        return [[str(c) for c in row] for row in load_workbook(path).active.iter_rows(values_only=True)]
    return path.read_text(encoding="utf-8").splitlines()


def same(name: str, truth, got) -> bool:
    if name not in ("deceduti.xlsx", "relazione.md"):
        return truth == got
    # il cognome torna come nominativo intero ("Rossi" nella verita', "Rossi Mario" nel risultato)
    flat = lambda rows: [" ".join(r) if isinstance(r, list) else r for r in rows]
    t, g = flat(truth), flat(got)
    if len(t) != len(g):
        return False
    for a, b in zip(t, g):
        if a == b:
            continue
        ta, tb = a.split(), b.split()
        i = 0
        for w in ta:   # ogni parola della verita' compare, nell'ordine, nel risultato
            while i < len(tb) and tb[i].strip("(),") != w.strip("(),"):
                i += 1
            if i == len(tb):
                return False
            i += 1
        if len(tb) - len(ta) > 3:
            return False
    return True


def run(mode: str, base: Path, n: int, seed: int = 7) -> dict:
    study, data = base / mode / "studio", base / mode / "dati"
    study.mkdir(parents=True)
    data.mkdir()
    simulate(study, n, seed)
    truth = base / mode / "verita"
    analyse(study / "registro_TAVI.xlsx", study / "follow_up.csv", truth)

    env = dict(os.environ, CLIN_DATI=str(data), CLIN_CARTELLE=str(study))
    clin = [sys.executable, str(ROOT / "clin.py")]
    (data / "impostazioni.json").write_text(json.dumps({"date_calendario": mode == "calendario", "modello_locale": False,
                                                       "motore": "ollama"}))
    out = subprocess.run(clin + ["avvia", str(study)], env=env, capture_output=True, text=True, check=True).stdout
    copies = study / "Clin_anonimizzati"
    reg = next(copies.glob("registro*.xlsx"))
    fu = next(copies.glob("follow_up*.csv"))
    leak = [w for w in COGNOMI + NOMI if w in reg.read_bytes().decode("latin-1") or w in fu.read_text()]
    analyse(reg, fu, study / "analisi")                      # l'agente: lavora solo sulle copie
    subprocess.run(clin + ["risultati", str(study)], env=env, capture_output=True, text=True, check=True)
    real = study / "Clin_risultati" / "analisi"
    report = {"_note": [l for l in out.splitlines() if l.startswith("Date dei fogli")][0][:110] + "…",
              "_dati personali nelle copie": "nessuno" if not leak else ", ".join(leak)}
    for f in sorted(truth.iterdir()):
        got = real / f.name
        report[f.name] = "uguale alla verita'" if got.exists() and same(f.name, load(f), load(got)) else (
            "DIVERSO" if got.exists() else "uguale (nulla da ricondurre)" if
            same(f.name, load(f), load(study / "analisi" / f.name)) else "DIVERSO (non ricondotto)")
    report["_esempio"] = (real / "relazione.md").read_text(encoding="utf-8").splitlines()[5] if (real / "relazione.md").exists() else ""
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pazienti", type=int, default=400)
    ap.add_argument("--seme", type=int, default=7, help="seme dei dati simulati")
    a = ap.parse_args()
    base = Path(tempfile.mkdtemp(prefix="clin-analisi-"))
    try:
        reports = {m: run(m, base, a.pazienti, a.seme) for m in ("segreto", "calendario")}
    finally:
        shutil.rmtree(base, ignore_errors=True)
    keys = [k for k in reports["segreto"] if not k.startswith("_")]
    print(f"{'risultato':<28}{'giorni segreti':<34}{'400 anni esatti'}")
    for k in keys:
        print(f"{k:<28}{reports['segreto'][k]:<34}{reports['calendario'][k]}")
    for m, r in reports.items():
        print(f"\n[{m}] {r['_note']}\n  dati personali nelle copie: {r['_dati personali nelle copie']}\n  relazione ricondotta: {r['_esempio']}")
    return 0 if all(reports["calendario"][k].startswith("uguale") for k in keys) else 1


if __name__ == "__main__":
    sys.exit(main())
