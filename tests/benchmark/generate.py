"""
Generatore di referti sintetici italiani con etichette esatte degli span.

Tutti i dati sono inventati e generati al momento a partire da un seme fisso:
nessun dato reale. I valori strutturati sono validi (CF con carattere di
controllo, tessera TEAM con Luhn, IBAN con mod-97), cosi' il benchmark misura
il riconoscimento e non la validazione.

I nominativi sono scritti a mano qui, in molte lingue (italiani, rumeni,
albanesi, arabi, cinesi, ucraini, indiani, filippini, africani, sudamericani...).

Etichette (`label`): PERSONA, ID_UFFICIALE, NASCITA_ETA, CONTATTO, IBAN,
ID_CLINICO, DATA, STRUTTURA. Il campo `sub` dettaglia il caso (es. PERSONA
etichettata, nel testo libero, familiare). Gli hard negative clinici sono
registrati in `negatives`: non vanno oscurati.
"""

from __future__ import annotations

import random
import string
from typing import Dict, List, Tuple

# (nome, cognome, sesso, origine)
PEOPLE: List[Tuple[str, str, str, str]] = [
    ("Mario", "Rossi", "M", "it"), ("Giulia", "Bianchi", "F", "it"), ("Paolo", "Neri", "M", "it"),
    ("Anna", "Esposito", "F", "it"), ("Luca", "Romano", "M", "it"), ("Francesca", "Colombo", "F", "it"),
    ("Giuseppe", "Ricci", "M", "it"), ("Chiara", "Marino", "F", "it"), ("Antonio", "Greco", "M", "it"),
    ("Elena", "Bruno", "F", "it"), ("Marco", "Gallo", "M", "it"), ("Sara", "Conti", "F", "it"),
    ("Roberto", "De Luca", "M", "it"), ("Lucia", "Mancini", "F", "it"), ("Stefano", "Costa", "M", "it"),
    ("Laura", "Giordano", "F", "it"), ("Davide", "Rizzo", "M", "it"), ("Martina", "Lombardi", "F", "it"),
    ("Alessandro", "Moretti", "M", "it"), ("Valentina", "Barbieri", "F", "it"),
    ("Gennaro", "Capuozzo", "M", "it"), ("Assunta", "Pirozzi", "F", "it"), ("Salvatore", "Lo Iacono", "M", "it"),
    ("Ionuț", "Popescu", "M", "ro"), ("Mihaela", "Ionescu", "F", "ro"), ("Andrei", "Dumitrescu", "M", "ro"),
    ("Arben", "Hoxha", "M", "sq"), ("Elira", "Shehu", "F", "sq"), ("Besnik", "Krasniqi", "M", "sq"),
    ("Mohamed", "El Amrani", "M", "ar"), ("Fatima", "Benali", "F", "ar"), ("Youssef", "Ait Benhaddou", "M", "ar"),
    ("Khadija", "Ouali", "F", "ar"), ("Ahmed", "Abdelrahman", "M", "ar"),
    ("Wei", "Wang", "M", "zh"), ("Xiaoling", "Zhang", "F", "zh"), ("Jie", "Chen", "M", "zh"), ("Mingyu", "Hu", "M", "zh"),
    ("Oleksandr", "Kovalenko", "M", "uk"), ("Olena", "Shevchuk", "F", "uk"), ("Iryna", "Bondarenko", "F", "uk"),
    ("Rajesh", "Kumar", "M", "in"), ("Priya", "Sharma", "F", "in"), ("Gurpreet", "Singh", "M", "in"),
    ("Muhammad", "Asif", "M", "pk"), ("Fahmida", "Akter", "F", "bd"), ("Rakibul", "Rahman", "M", "bd"),
    ("Maricel", "Dela Cruz", "F", "ph"), ("Jose", "Reyes", "M", "ph"),
    ("Chinedu", "Okafor", "M", "ng"), ("Ngozi", "Adeyemi", "F", "ng"), ("Blessing", "Eze", "F", "ng"),
    ("Mamadou", "Diop", "M", "sn"), ("Aminata", "Ndiaye", "F", "sn"),
    ("Luis", "Quispe", "M", "pe"), ("Rosa", "Huamán", "F", "pe"),
    ("Katarzyna", "Wiśniewska", "F", "pl"), ("Piotr", "Nowak", "M", "pl"), ("Jürgen", "Müller", "M", "de"),
    ("Nuwan", "Perera", "M", "lk"), ("Dilani", "Fernando", "F", "lk"), ("Natalia", "Smirnova", "F", "ru"),
    ("Thi Lan", "Nguyen", "F", "vn"), ("Kwame", "Mensah", "M", "gh"), ("Siddharth", "Iyer", "M", "in"),
]

KIN_M = ["marito", "figlio", "fratello", "padre", "nipote", "genero", "compagno", "cognato"]
KIN_F = ["moglie", "figlia", "sorella", "madre", "nipote", "nuora", "compagna", "cognata", "badante"]

CITIES = [("Roma", "H501", "00185"), ("Milano", "F205", "20121"), ("Napoli", "F839", "80134"),
          ("Torino", "L219", "10121"), ("Bologna", "A944", "40121"), ("Palermo", "G273", "90133"),
          ("Ancona", "A271", "60121"), ("Bari", "A662", "70121")]
STREETS = ["Via Garibaldi", "Via Roma", "Viale Mazzini", "Piazza Cavour", "Corso Vittorio Emanuele",
           "Via dei Mille", "Via Nazionale", "Largo Augusto"]
HOSPITALS = ["Ospedale San Camillo", "Policlinico Umberto I", "Azienda Ospedaliera Sant'Andrea",
             "Ospedale Maggiore", "Policlinico San Matteo"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
          "settembre", "ottobre", "novembre", "dicembre"]

# Hard negative clinici: (tipo, testo). Eponimi con cognomi reali inclusi apposta.
NEGATIVES: List[Tuple[str, str]] = [
    ("laboratorio", "Hb 12,4 g/dL"), ("laboratorio", "PCR 3,2 mg/L"), ("laboratorio", "creatinina 1,1 mg/dL"),
    ("laboratorio", "INR 2,5"), ("laboratorio", "GB 7.8 x10^3/uL (v.n. 4.0-10.0)"), ("laboratorio", "glicemia 105 mg/dL"),
    ("laboratorio", "Na 138 mEq/L, K 4.1 mEq/L"), ("laboratorio", "PLT 245.000/mm3"),
    ("parametri", "PA 135/80 mmHg"), ("parametri", "FC 78 bpm"), ("parametri", "SpO2 97% in aria ambiente"),
    ("parametri", "TC 37,8 °C"),
    ("durata", "febbre da 3 giorni"), ("durata", "dolore da 2 settimane"), ("durata", "storia di 10 anni di diabete"),
    ("durata", "follow-up a 6 mesi"), ("durata", "terapia per 10 giorni"),
    ("posologia", "amoxicillina/clavulanato 1 g x 3/die"), ("posologia", "enoxaparina 4000 UI sc 1 fl/die"),
    ("posologia", "Tachipirina 1000 mg al bisogno, max 3/die"), ("posologia", "ramipril 5 mg 1 cp ore 8"),
    ("posologia", "furosemide 25 mg 1/2 cp"),
    ("icd", "ICD-10 I21.4"), ("icd", "ICD-9-CM 410.71"), ("icd", "ICD-10 J18.9"), ("icd", "DRG 127"),
    ("protocollo", "protocollo FOLFOX-4 ciclo 3/12"), ("protocollo", "schema R-CHOP ogni 21 giorni"),
    ("eponimo", "manovra di Giordano negativa"), ("eponimo", "segno di Murphy negativo"),
    ("eponimo", "prove di Mingazzini nella norma"), ("eponimo", "Romberg negativo"),
    ("eponimo", "morbo di Parkinson"), ("eponimo", "malattia di Crohn"), ("eponimo", "scala di Glasgow 15/15"),
    ("eponimo", "manovra di Valsalva"), ("eponimo", "classificazione di Fontaine stadio IIb"),
    ("eponimo", "segno di Blumberg negativo"), ("eponimo", "Lasègue negativo bilateralmente"),
    ("maiuscola", "Addome trattabile, non dolente."), ("maiuscola", "Dolore lieve."),
    ("maiuscola", "Vigile, orientato, collaborante."), ("maiuscola", "Ferro sierico 40 ug/dL."),
    ("maiuscola", "Sereno il decorso post-operatorio."), ("maiuscola", "Rosa dei sintomi invariata."),
    ("maiuscola", "Mare e montagna sconsigliati per 30 giorni."), ("maiuscola", "Gloria del Pronto Soccorso: nessuna."),
]

_ODD = dict(zip(string.digits + string.ascii_uppercase,
                [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3,
                 6, 8, 12, 14, 16, 10, 22, 25, 24, 23]))


def cf_check(cf15: str) -> str:
    total = 0
    for i, ch in enumerate(cf15):
        if i % 2 == 0:  # posizioni dispari (1-based)
            total += _ODD[ch]
        else:
            total += int(ch) if ch.isdigit() else ord(ch) - 65
    return chr(65 + total % 26)


def _cf_part(word: str, is_name: bool) -> str:
    w = "".join(c for c in word.upper() if c.isalpha() and c.isascii())
    cons = [c for c in w if c not in "AEIOU"]
    vow = [c for c in w if c in "AEIOU"]
    if is_name and len(cons) >= 4:
        cons = [cons[0], cons[2], cons[3]]
    return ("".join(cons + vow) + "XXX")[:3]


def make_cf(first: str, last: str, sex: str, y: int, m: int, d: int, belfiore: str) -> str:
    day = d + (40 if sex == "F" else 0)
    s = _cf_part(last, False) + _cf_part(first, True) + f"{y % 100:02d}" + "ABCDEHLMPRST"[m - 1] \
        + f"{day:02d}" + belfiore
    return s + cf_check(s)


def luhn_digit(body: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(body)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            n -= 9 if n > 9 else 0
        total += n
    return str((10 - total % 10) % 10)


def make_team(rng: random.Random) -> str:
    body = "80380" + "".join(rng.choice(string.digits) for _ in range(14))
    return body + luhn_digit(body)


def make_iban(rng: random.Random) -> str:
    # CIN casuale: il motore verifica solo il mod-97
    bban = rng.choice(string.ascii_uppercase) + "".join(rng.choice(string.digits) for _ in range(10)) \
        + "".join(rng.choice(string.digits) for _ in range(12))
    num = "".join(str(int(c, 36)) for c in bban + "IT00")
    check = 98 - int(num) % 97
    raw = f"IT{check:02d}{bban}"
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4)) if rng.random() < 0.5 else raw


def make_phone(rng: random.Random) -> str:
    a, b, c = f"3{rng.randint(20, 99)}", f"{rng.randint(100, 999)}", f"{rng.randint(1000, 9999)}"
    p = rng.choice([f"{a} {b} {c}", f"{a}.{b}.{c}", f"{a}{b}{c}", f"{a}-{b}{c}", f"{a} {b}{c}"])
    if rng.random() < 0.6:
        return rng.choice(["+39 ", "0039 ", ""]) + p
    pre = f"0{rng.randint(2, 99)}"
    num = f"{rng.randint(100000, 9999999)}"
    return rng.choice([f"{pre}/{num}", f"{pre} {num}", f"{pre}-{num}", f"{pre}{num}",
                       f"+39 {pre} {num[:3]} {num[3:]}"])


def fmt_date(rng: random.Random, y: int, m: int, d: int) -> str:
    return f"{d:02d}/{m:02d}/{y}" if rng.random() < 0.6 else f"{d} {MONTHS[m - 1]} {y}"


class Doc:
    """Costruisce un testo registrando gli span esatti di ogni valore."""

    def __init__(self):
        self.parts: List[str] = []
        self.size = 0
        self.spans: List[Dict] = []
        self.negatives: List[Dict] = []

    def t(self, s: str) -> "Doc":
        self.parts.append(s)
        self.size += len(s)
        return self

    def v(self, s: str, label: str, sub: str) -> "Doc":
        self.spans.append({"start": self.size, "end": self.size + len(s), "label": label, "sub": sub, "text": s})
        return self.t(s)

    def neg(self, kind: str, s: str) -> "Doc":
        self.negatives.append({"start": self.size, "end": self.size + len(s), "kind": kind, "text": s})
        return self.t(s)

    def build(self, doc_id: str, kind: str) -> Dict:
        return {"id": doc_id, "kind": kind, "text": "".join(self.parts),
                "spans": self.spans, "negatives": self.negatives}


def _person(rng, sex=None, exclude=()):
    pool = [p for p in PEOPLE if (sex is None or p[2] == sex) and p not in exclude]
    return rng.choice(pool)


def _negs(rng: random.Random, doc: Doc, n: int, kinds=None) -> None:
    pool = [x for x in NEGATIVES if kinds is None or x[0] in kinds]
    for kind, s in rng.sample(pool, n):
        doc.neg(kind, s).t(". " if not s.endswith(".") else " ")


def _header(rng, doc: Doc, pat, birth, city) -> None:
    first, last, sex, _ = pat
    y, m, d = birth
    doc.v(rng.choice(HOSPITALS), "STRUTTURA", "intestazione").t("\nU.O.C. Medicina Interna\n\n")
    upper = rng.random() < 0.5
    doc.t("Paziente: ").v(f"{last.upper()} {first.upper()}" if upper else f"{first} {last}", "PERSONA", "etichettata")
    doc.t("\nData di nascita: ").v(fmt_date(rng, y, m, d), "NASCITA_ETA", "data_nascita")
    doc.t("\nCodice fiscale: ").v(make_cf(first, last, sex, y, m, d, city[1]), "ID_UFFICIALE", "cf")
    if rng.random() < 0.6:
        doc.t("\nTessera sanitaria: ").v(make_team(rng), "ID_UFFICIALE", "team")
    doc.t("\n" + rng.choice(["Residenza: ", "Indirizzo: ", "Residente in ", ""]))
    doc.v(f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {city[2]} {city[0]}", "CONTATTO", "indirizzo")
    doc.t("\n" + rng.choice(["Tel. ", "Cell. ", "Recapito: ", "Telefono ", ""]))
    doc.v(make_phone(rng), "CONTATTO", "telefono").t("\n")
    if rng.random() < 0.7:
        label = rng.choice(["Nosologico: ", "N. nosologico ", "Nosografico n. ", "N° ricovero: ",
                            "Cod. ricovero ", "Episodio n. "])
        doc.t(label).v(f"{rng.randint(2020, 2025)}{rng.choice(['', '/', '-'])}{rng.randint(100000, 999999)}",
                       "ID_CLINICO", "nosologico").t("\n")
    if rng.random() < 0.4:
        label = rng.choice(["Documento: C.I. n. ", "Carta d'identità ", "Doc. identità n. ", "Passaporto n. "])
        value = (f"{rng.choice('CA CB CD AY'.split())}{rng.randint(10000, 99999)}{rng.choice('AB CD EF'.split())}"
                 if "Passaporto" not in label else f"Y{rng.choice('ABC')}{rng.randint(1000000, 9999999)}")
        doc.t(label).v(value, "ID_CLINICO", "documento").t("\n")
    doc.t("\n")


def _kin_sentence(rng, doc: Doc, pat) -> Tuple[str, str]:
    """Familiare senza etichetta. Restituisce (nome usato, parentela) per le ripetizioni."""
    rel = _person(rng, exclude=(pat,))
    kin = rng.choice(KIN_M if rel[2] == "M" else KIN_F)
    art = {"M": "il", "F": "la"}[rel[2]]
    full = rng.random() < 0.5
    name = f"{rel[0]} {rel[1]}" if full else rel[0]
    form = rng.randrange(4)
    if form == 0:
        doc.t(f"Anamnesi raccolta dal{'la' if rel[2] == 'F' else ''} {kin} ").v(name, "PERSONA", "familiare").t(". ")
    elif form == 1:
        doc.t(f"Riferisce {art} {kin} ").v(name, "PERSONA", "familiare").t(" che il paziente ")
        doc.t("da alcuni giorni appare meno reattivo. ")
    elif form == 2:
        doc.t(f"Accompagnat{'a' if pat[2] == 'F' else 'o'} dal{'la' if rel[2] == 'F' else ''} {kin} ")
        doc.v(name, "PERSONA", "familiare").t(". ")
    else:
        doc.t(f"Caregiver di riferimento: {art} {kin}, ").v(name, "PERSONA", "familiare").t(", reperibile al ")
        doc.v(make_phone(rng), "CONTATTO", "telefono").t(". ")
    return rel[0], kin


def _signature(rng, doc: Doc, exclude) -> None:
    d = _person(rng, exclude=exclude)
    name = f"{d[0]} {d[1]}" if rng.random() < 0.5 else f"{d[1].upper()} {d[0].upper()}"
    form = rng.randrange(3)
    if form == 0:
        doc.t("\nDocumento firmato digitalmente ai sensi del D.Lgs. 82/2005 da: ").v(name, "PERSONA", "firma")
    elif form == 1:
        doc.t("\nFirmato digitalmente da ").v(name, "PERSONA", "firma").t(" il ")
        doc.v(fmt_date(rng, 2024, rng.randint(1, 12), rng.randint(1, 28)), "DATA", "firma")
    else:
        doc.t("\nFirmato digitalmente\n").v(name, "PERSONA", "firma")
    doc.t("\n")


def _doctor(rng, doc: Doc, exclude) -> None:
    d = _person(rng, exclude=exclude)
    title = rng.choice(["Dott.", "Dr.", "Dott.ssa" if d[2] == "F" else "Prof."])
    doc.t(f"{title} ").v(f"{d[0]} {d[1]}", "PERSONA", "medico")


def dimissione(rng: random.Random, i: int) -> Dict:
    doc = Doc()
    pat = _person(rng)
    birth = (rng.randint(1930, 2005), rng.randint(1, 12), rng.randint(1, 28))
    city = rng.choice(CITIES)
    _header(rng, doc, pat, birth, city)
    adm = (2024, rng.randint(1, 12), rng.randint(1, 28))
    doc.t("LETTERA DI DIMISSIONE\n\nRicoverat" + ("a" if pat[2] == "F" else "o") + " il ")
    doc.v(fmt_date(rng, *adm), "DATA", "ricovero").t(" per dolore toracico. ")
    age = 2024 - birth[0]
    doc.t("Paziente di ").v(f"{age} anni", "NASCITA_ETA", "eta").t(", ")
    _negs(rng, doc, 1, {"durata"})
    rel_name, _ = _kin_sentence(rng, doc, pat)
    doc.t("\n\nEsame obiettivo: ")
    _negs(rng, doc, 3, {"eponimo", "maiuscola", "parametri"})
    doc.t("\nEsami: ")
    _negs(rng, doc, 3, {"laboratorio"})
    doc.t("\nDiagnosi: ")
    _negs(rng, doc, 1, {"icd"})
    doc.t("\nTerapia: ")
    _negs(rng, doc, 2, {"posologia"})
    if rng.random() < 0.5:
        doc.t("\n").v(rel_name, "PERSONA", "familiare_ripetuto").t(" ha ricevuto il piano terapeutico. ")
    doc.t("\nControllo ambulatoriale il ").v(fmt_date(rng, 2025, rng.randint(1, 12), rng.randint(1, 28)), "DATA", "controllo")
    doc.t(".\n\nIl medico: ")
    _doctor(rng, doc, (pat,))
    if rng.random() < 0.6:
        _signature(rng, doc, (pat,))
    doc.t("\nProt. n. ").v(f"{2024}/{rng.randint(1000, 999999):07d}", "ID_CLINICO", "protocollo").t("\n")
    return doc.build(f"dim-{i:03d}", "dimissione")


def referto(rng: random.Random, i: int) -> Dict:
    doc = Doc()
    pat = _person(rng)
    birth = (rng.randint(1940, 2010), rng.randint(1, 12), rng.randint(1, 28))
    city = rng.choice(CITIES)
    _header(rng, doc, pat, birth, city)
    doc.t("REFERTO ECOGRAFIA ADDOME\nData esame: ").v(fmt_date(rng, 2024, rng.randint(1, 12), rng.randint(1, 28)), "DATA", "esame")
    doc.t("\nQuesito: ")
    _negs(rng, doc, 1, {"durata"})
    doc.t("Richiedente: ")
    _doctor(rng, doc, (pat,))
    doc.t("\n\nFegato di dimensioni nei limiti. ")
    _negs(rng, doc, 2, {"maiuscola", "protocollo", "icd"})
    doc.t("\nRefertato da ")
    _doctor(rng, doc, (pat,))
    doc.t("\n")
    if rng.random() < 0.5:
        email = f"{pat[0]}.{pat[1]}".lower().replace(" ", "").encode("ascii", "ignore").decode()
        doc.t("Copia inviata a: ").v(email + "@example.it", "CONTATTO", "email").t("\n")
    if rng.random() < 0.6:
        _signature(rng, doc, (pat,))
    if rng.random() < 0.5:
        doc.t("Referto n. ").v(f"{rng.randint(100000, 9999999)}", "ID_CLINICO", "referto").t("\n")
    doc.t("\n")
    return doc.build(f"ref-{i:03d}", "referto")


def anamnesi(rng: random.Random, i: int) -> Dict:
    """Testo libero senza intestazione: il nominativo compare solo in prosa."""
    doc = Doc()
    pat = _person(rng)
    first, last, sex, _ = pat
    age = rng.randint(18, 95)
    form = rng.randrange(3)
    if form == 0:
        doc.v(f"{first} {last}", "PERSONA", "libero").t(", ").v(f"{age}enne", "NASCITA_ETA", "eta")
    elif form == 1:
        doc.t("Visito in data odierna ").v(f"{first} {last}", "PERSONA", "libero").t(", ")
        doc.t("di ").v(f"{age} anni", "NASCITA_ETA", "eta")
    else:
        doc.t(("La signora " if sex == "F" else "Il signor ")).v(f"{first} {last}", "PERSONA", "titolo")
        doc.t(", di ").v(f"{age} anni", "NASCITA_ETA", "eta")
    if rng.random() < 0.5:
        city = rng.choice(CITIES)
        doc.t(", vive in ").v(f"{rng.choice(STREETS)} {rng.randint(1, 200)}, {city[2]} {city[0]}", "CONTATTO", "indirizzo")
    doc.t(", giunge in ambulatorio per ")
    _negs(rng, doc, 1, {"durata"})
    doc.t("In anamnesi ")
    _negs(rng, doc, 2, {"eponimo", "durata"})
    _kin_sentence(rng, doc, pat)
    doc.t("\nTerapia domiciliare: ")
    _negs(rng, doc, 2, {"posologia"})
    doc.t("\nObiettivita': ")
    _negs(rng, doc, 2, {"maiuscola", "parametri"})
    if rng.random() < 0.6:
        col = _person(rng, exclude=(pat,))
        doc.t("\nIl caso e' discusso con ").v(f"{col[0]} {col[1]}", "PERSONA", "collega_libero").t(" (cardiologo).")
    if rng.random() < 0.5:
        doc.t("\nRiferimento: ").v(make_phone(rng), "CONTATTO", "telefono")
    if rng.random() < 0.3:
        doc.t("\nRimborso su IBAN ").v(make_iban(rng), "IBAN", "iban")
    doc.t("\n")
    if rng.random() < 0.5:
        doc.v(last, "PERSONA", "libero_ripetuto").t(" riferisce buona aderenza alla terapia.\n")
    return doc.build(f"ana-{i:03d}", "anamnesi")


def generate(n: int = 150, seed: int = 20261121) -> List[Dict]:
    rng = random.Random(seed)
    makers = [dimissione, referto, anamnesi]
    return [makers[i % 3](rng, i) for i in range(n)]


if __name__ == "__main__":
    import json
    import sys
    docs = generate(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
    print(json.dumps(docs, ensure_ascii=False, indent=1))
