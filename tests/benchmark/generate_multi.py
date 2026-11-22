"""
Referti sintetici in lingue europee e inglese (EN, FR, DE, ES, PT, NL, PL, RO) per
misurare Clin fuori dall'italiano. Stessa struttura di generate.py: testo, intervalli
da rimuovere (con lingua, etichetta e sottotipo) e termini clinici che devono restare.

    python3 tests/benchmark/run_multi.py
"""
import random

NAMES = [  # nomi di origini diverse, come in un reparto europeo
    ("Emily", "Clarke"), ("Oliver", "Hughes"), ("Camille", "Lefèvre"), ("Mathieu", "Garnier"),
    ("Lukas", "Schäfer"), ("Anna", "Großmann"), ("Lucía", "Fernández"), ("Javier", "Ortega"),
    ("João", "Gonçalves"), ("Inês", "Rodrigues"), ("Sanne", "de Vries"), ("Daan", "van der Berg"),
    ("Katarzyna", "Wiśniewska"), ("Piotr", "Zieliński"), ("Ioana", "Popescu"), ("Andrei", "Ionescu"),
    ("Aisha", "Rahman"), ("Mehmet", "Yılmaz"), ("Olena", "Kovalenko"), ("Kwame", "Mensah"),
    ("Wei", "Zhang"), ("Priya", "Nair"), ("Fatima", "El Amrani"), ("Sven", "Lindqvist"),
]

LANGS = {
    "en": dict(
        patient="Patient name:", dob="Date of birth:", sex="Sex: F",
        id=("NHS number:", lambda r: f"{r.randint(400,499)} {r.randint(100,999)} {r.randint(1000,9999)}"),
        phone=("Tel.", lambda r: f"+44 20 {r.randint(7000,7999)} {r.randint(1000,9999)}"),
        address=lambda r: f"{r.randint(2,180)} Baker Street, London NW1 6XE",
        months=["January", "March", "May", "July", "September", "November"],
        date=lambda d, m, y: f"{d} {m} {y}",
        admitted="Admitted on {date} with community-acquired pneumonia.",
        kin="Her daughter {name} (mobile {phone}) is the next of kin.",
        free="{name}, a {age}-year-old woman, presented to the emergency department with chest pain.",
        again="{surname} was started on amoxicillin 1 g three times daily.",
        doctor="Signed by Dr {name}, Consultant Cardiologist.",
        hospital="St Thomas' Hospital, Department of Medicine",
        record=("Hospital number:", lambda r: f"RJ{r.randint(100000,999999)}"),
        neg=["Parkinson's disease", "Cushing's syndrome", "amoxicillin 1 g", "Hb 12.4 g/dL", "BP 135/80 mmHg",
             "Murphy's sign", "Glasgow Coma Scale 15"],
    ),
    "fr": dict(
        patient="Nom du patient :", dob="Date de naissance :", sex="Sexe : F",
        id=("N° de sécurité sociale :", lambda r: f"2 {r.randint(40,99)} {r.randint(10,12):02d} 75 {r.randint(100,999)} {r.randint(100,999)} {r.randint(10,97)}"),
        phone=("Tél.", lambda r: f"06 {r.randint(10,99)} {r.randint(10,99)} {r.randint(10,99)} {r.randint(10,99)}"),
        address=lambda r: f"{r.randint(2,90)} rue de la Paix, 75002 Paris",
        months=["janvier", "mars", "mai", "juillet", "septembre", "novembre"],
        date=lambda d, m, y: f"{d} {m} {y}",
        admitted="Hospitalisée le {date} pour une pneumopathie communautaire.",
        kin="Sa fille {name} (portable {phone}) est la personne de confiance.",
        free="{name}, {age} ans, se présente aux urgences pour une douleur thoracique.",
        again="{surname} reçoit de l'amoxicilline 1 g trois fois par jour.",
        doctor="Compte rendu signé par le Dr {name}, cardiologue.",
        hospital="Hôpital Lariboisière, Service de Médecine Interne",
        record=("N° de dossier :", lambda r: f"{r.randint(10000000,99999999)}"),
        neg=["maladie de Parkinson", "signe de Murphy", "amoxicilline 1 g", "Hb 12,4 g/dL", "TA 135/80 mmHg",
             "syndrome de Cushing", "score de Glasgow 15"],
    ),
    "de": dict(
        patient="Name des Patienten:", dob="Geburtsdatum:", sex="Geschlecht: w",
        id=("Versichertennummer:", lambda r: f"A{r.randint(100000000,999999999)}"),
        phone=("Tel.", lambda r: f"+49 30 {r.randint(1000000,9999999)}"),
        address=lambda r: f"Hauptstraße {r.randint(2,120)}, 10115 Berlin",
        months=["Januar", "März", "Mai", "Juli", "September", "November"],
        date=lambda d, m, y: f"{d}. {m} {y}",
        admitted="Stationäre Aufnahme am {date} wegen ambulant erworbener Pneumonie.",
        kin="Die Tochter {name} (Handy {phone}) ist die Ansprechpartnerin.",
        free="{name}, {age} Jahre, stellt sich mit thorakalen Schmerzen in der Notaufnahme vor.",
        again="{surname} erhält Amoxicillin 1 g dreimal täglich.",
        doctor="Gezeichnet: Dr. med. {name}, Oberarzt Kardiologie.",
        hospital="Charité – Universitätsmedizin Berlin, Klinik für Innere Medizin",
        record=("Fallnummer:", lambda r: f"{r.randint(10000000,99999999)}"),
        neg=["Morbus Parkinson", "Murphy-Zeichen", "Amoxicillin 1 g", "Hb 12,4 g/dl", "RR 135/80 mmHg",
             "Cushing-Syndrom", "Glasgow-Koma-Skala 15"],
    ),
    "es": dict(
        patient="Nombre del paciente:", dob="Fecha de nacimiento:", sex="Sexo: M",
        id=("DNI:", lambda r: f"{r.randint(10000000,99999999)}{r.choice('TRWAGMYFPDXBNJZSQVHLCKE')}"),
        phone=("Tel.", lambda r: f"6{r.randint(10,99)} {r.randint(100,999)} {r.randint(100,999)}"),
        address=lambda r: f"Calle Mayor {r.randint(2,99)}, 28013 Madrid",
        months=["enero", "marzo", "mayo", "julio", "septiembre", "noviembre"],
        date=lambda d, m, y: f"{d} de {m} de {y}",
        admitted="Ingresa el {date} por neumonía adquirida en la comunidad.",
        kin="Su hija {name} (móvil {phone}) es la persona de contacto.",
        free="{name}, de {age} años, acude a urgencias por dolor torácico.",
        again="{surname} recibe amoxicilina 1 g cada 8 horas.",
        doctor="Firmado por el Dr. {name}, cardiólogo.",
        hospital="Hospital Universitario La Paz, Servicio de Medicina Interna",
        record=("Número de historia clínica:", lambda r: f"{r.randint(1000000,9999999)}"),
        neg=["enfermedad de Parkinson", "signo de Murphy", "amoxicilina 1 g", "Hb 12,4 g/dL", "TA 135/80 mmHg",
             "síndrome de Cushing", "escala de Glasgow 15"],
    ),
    "pt": dict(
        patient="Nome do doente:", dob="Data de nascimento:", sex="Sexo: F",
        id=("Nº de utente:", lambda r: f"{r.randint(100000000,999999999)}"),
        phone=("Telemóvel", lambda r: f"+351 91{r.randint(0,9)} {r.randint(100,999)} {r.randint(100,999)}"),
        address=lambda r: f"Rua Augusta {r.randint(2,200)}, 1100-053 Lisboa",
        months=["janeiro", "março", "maio", "julho", "setembro", "novembro"],
        date=lambda d, m, y: f"{d} de {m} de {y}",
        admitted="Internada a {date} por pneumonia adquirida na comunidade.",
        kin="A filha {name} (telemóvel {phone}) é a pessoa de contacto.",
        free="{name}, {age} anos, recorre à urgência por dor torácica.",
        again="{surname} iniciou amoxicilina 1 g de 8 em 8 horas.",
        doctor="Assinado pelo Dr. {name}, cardiologista.",
        hospital="Hospital de Santa Maria, Serviço de Medicina Interna",
        record=("Processo nº", lambda r: f"{r.randint(1000000,9999999)}"),
        neg=["doença de Parkinson", "sinal de Murphy", "amoxicilina 1 g", "Hb 12,4 g/dL", "TA 135/80 mmHg",
             "síndrome de Cushing", "escala de Glasgow 15"],
    ),
    "nl": dict(
        patient="Naam patiënt:", dob="Geboortedatum:", sex="Geslacht: V",
        id=("BSN:", lambda r: f"{r.randint(100000000,999999999)}"),
        phone=("Tel.", lambda r: f"06-{r.randint(10000000,99999999)}"),
        address=lambda r: f"Kerkstraat {r.randint(2,150)}, 1017 GB Amsterdam",
        months=["januari", "maart", "mei", "juli", "september", "november"],
        date=lambda d, m, y: f"{d} {m} {y}",
        admitted="Opgenomen op {date} met een buiten het ziekenhuis opgelopen pneumonie.",
        kin="Haar dochter {name} (mobiel {phone}) is de contactpersoon.",
        free="{name}, {age} jaar, meldt zich op de spoedeisende hulp met pijn op de borst.",
        again="{surname} krijgt amoxicilline 1 g driemaal daags.",
        doctor="Ondertekend door dr. {name}, cardioloog.",
        hospital="Amsterdam UMC, afdeling Interne Geneeskunde",
        record=("Patiëntnummer:", lambda r: f"{r.randint(1000000,9999999)}"),
        neg=["ziekte van Parkinson", "teken van Murphy", "amoxicilline 1 g", "Hb 7,7 mmol/l", "RR 135/80 mmHg",
             "syndroom van Cushing", "Glasgow Coma Scale 15"],
    ),
    "pl": dict(
        patient="Imię i nazwisko pacjenta:", dob="Data urodzenia:", sex="Płeć: K",
        id=("PESEL:", lambda r: f"{r.randint(40,99)}{r.randint(1,12):02d}{r.randint(1,28):02d}{r.randint(10000,99999)}"),
        phone=("Tel.", lambda r: f"+48 5{r.randint(10,99)} {r.randint(100,999)} {r.randint(100,999)}"),
        address=lambda r: f"ul. Marszałkowska {r.randint(2,140)}, 00-026 Warszawa",
        months=["stycznia", "marca", "maja", "lipca", "września", "listopada"],
        date=lambda d, m, y: f"{d} {m} {y}",
        admitted="Przyjęta {date} z powodu pozaszpitalnego zapalenia płuc.",
        kin="Córka {name} (tel. kom. {phone}) jest osobą do kontaktu.",
        free="{name}, lat {age}, zgłasza się na SOR z powodu bólu w klatce piersiowej.",
        again="{surname} otrzymuje amoksycylinę 1 g trzy razy dziennie.",
        doctor="Podpisał: lek. med. {name}, kardiolog.",
        hospital="Szpital Kliniczny Dzieciątka Jezus, Klinika Chorób Wewnętrznych",
        record=("Nr księgi głównej:", lambda r: f"{r.randint(10000,99999)}/{r.randint(2020,2026)}"),
        neg=["choroba Parkinsona", "objaw Murphy'ego", "amoksycylina 1 g", "Hb 12,4 g/dl", "RR 135/80 mmHg",
             "zespół Cushinga", "skala Glasgow 15"],
    ),
    "ro": dict(
        patient="Numele pacientului:", dob="Data nașterii:", sex="Sex: F",
        id=("CNP:", lambda r: f"2{r.randint(40,99)}{r.randint(1,12):02d}{r.randint(1,28):02d}{r.randint(100000,999999)}"),
        phone=("Tel.", lambda r: f"+40 7{r.randint(20,99)} {r.randint(100,999)} {r.randint(100,999)}"),
        address=lambda r: f"Strada Victoriei {r.randint(2,99)}, 010063 București",
        months=["ianuarie", "martie", "mai", "iulie", "septembrie", "noiembrie"],
        date=lambda d, m, y: f"{d} {m} {y}",
        admitted="Internată la {date} pentru pneumonie comunitară.",
        kin="Fiica sa, {name} (mobil {phone}), este persoana de contact.",
        free="{name}, în vârstă de {age} de ani, se prezintă la UPU pentru durere toracică.",
        again="{surname} primește amoxicilină 1 g de trei ori pe zi.",
        doctor="Semnat de Dr. {name}, medic cardiolog.",
        hospital="Spitalul Clinic de Urgență București, Secția Medicină Internă",
        record=("Nr. foaie de observație:", lambda r: f"{r.randint(10000,99999)}"),
        neg=["boala Parkinson", "semnul Murphy", "amoxicilină 1 g", "Hb 12,4 g/dL", "TA 135/80 mmHg",
             "sindromul Cushing", "scala Glasgow 15"],
    ),
}


def _doc(lang, r):
    L = LANGS[lang]
    pat, kin, doc, free = r.sample(NAMES, 4)
    d = lambda: L["date"](r.randint(1, 28), r.choice(L["months"]), r.randint(2023, 2026))
    dob = f"{r.randint(1, 28):02d}/{r.randint(1, 12):02d}/{r.randint(1935, 1990)}"
    parts, spans, negs = [], [], []

    def add(text, *fields):
        """fields: (valore, etichetta, sottotipo) inseriti con {0}, {1}... nel testo"""
        out = text
        pos = sum(len(p) + 1 for p in parts)
        for i, (val, lab, sub) in enumerate(fields):
            k = out.index("{%d}" % i)
            out = out[:k] + val + out[k + 3:]
            spans.append({"start": pos + k, "end": pos + k + len(val), "label": lab, "sub": sub, "text": val, "lang": lang})
        parts.append(out)

    add(L["hospital"].replace("{", "(").replace("}", ")"))
    spans.append({"start": 0, "end": len(L["hospital"]), "label": "STRUTTURA", "sub": "intestazione",
                  "text": L["hospital"].split(",")[0], "lang": lang})
    pname = f"{pat[1].upper()} {pat[0].upper()}"
    add(f"{L['patient']} {{0}}   {L['dob']} {{1}}   {L['sex']}", (pname, "PERSONA", "etichettata"), (dob, "NASCITA_ETA", "data_nascita"))
    add(f"{L['id'][0]} {{0}}   {L['record'][0]} {{1}}", (L["id"][1](r), "ID_UFFICIALE", "id"), (L["record"][1](r), "ID_CLINICO", "cartella"))
    add(f"{L['phone'][0]} {{0}}   {{1}}", (L["phone"][1](r), "CONTATTO", "telefono"), (L["address"](r), "CONTATTO", "indirizzo"))
    adm = L["admitted"]
    dt = d()
    k = adm.index("{date}")
    add(adm[:k] + "{0}" + adm[k + 6:], (dt, "DATA", "ricovero"))
    kn = L["kin"]
    a, b = kn.index("{name}"), kn.index("{phone}")
    add(kn[:a] + "{0}" + kn[a + 6:b] + "{1}" + kn[b + 7:], (f"{kin[0]} {kin[1]}", "PERSONA", "familiare"), (L["phone"][1](r), "CONTATTO", "telefono"))
    fr = L["free"].replace("{age}", str(r.randint(30, 88)))
    a = fr.index("{name}")
    add(fr[:a] + "{0}" + fr[a + 6:], (f"{free[0]} {free[1]}", "PERSONA", "libero"))
    ag = L["again"]
    a = ag.index("{surname}")
    add(ag[:a] + "{0}" + ag[a + 9:], (free[1], "PERSONA", "libero_ripetuto"))
    neg = r.sample(L["neg"], 3)
    parts.append(" ".join(f"{n}." for n in neg))
    negs += [{"text": n} for n in neg]
    dc = L["doctor"]
    a = dc.index("{name}")
    add(dc[:a] + "{0}" + dc[a + 6:], (f"{doc[0]} {doc[1]}", "PERSONA", "medico"))
    text = "\n".join(parts)
    for s in spans:  # verifica
        assert s["sub"] == "intestazione" or text[s["start"]:s["end"]] == s["text"], s
    return {"lang": lang, "text": text, "spans": spans, "negatives": negs}


def generate(per_lang=20, seed=11):
    r = random.Random(seed)
    return [_doc(lang, r) for lang in LANGS for _ in range(per_lang)]


if __name__ == "__main__":
    for d in generate(1)[:2]:
        print(d["text"], "\n")
