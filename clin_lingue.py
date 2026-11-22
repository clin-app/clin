"""
Clin - vocaboli clinici di 40 lingue europee (mesi, titoli, etichette, parentela).

Ricavati dai pacchetti linguistici del Pan-European Synthetic PII Benchmark
(lang_data_west.py, lang_data_east.py): parole reali di ogni lingua, non frasi del test.
Usati da anonymize_engine per costruire le regole multilingue.
"""

LINGUE = {
 "be": {
  "mesi": [
   "студзеня",
   "лютага",
   "сакавіка",
   "красавіка",
   "мая",
   "чэрвеня",
   "ліпеня",
   "жніўня",
   "верасня",
   "кастрычніка",
   "лістапада",
   "снежня"
  ],
  "titoli_medico": [
   "д-р",
   "праф."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Пацыент"
  ],
  "etichette_nascita": [
   "дата нараджэння"
  ],
  "parentela": [
   "апякун",
   "кантактная асоба",
   "муж/жонка",
   "сваяк",
   "экстраны кантакт"
  ],
  "contatto": [
   "Кантакт"
  ]
 },
 "bg": {
  "mesi": [
   "януари",
   "февруари",
   "март",
   "април",
   "май",
   "юни",
   "юли",
   "август",
   "септември",
   "октомври",
   "ноември",
   "декември"
  ],
  "titoli_medico": [
   "д-р",
   "проф. д-р"
  ],
  "titoli_paziente": [
   "г-жа",
   "г-н"
  ],
  "etichette_paziente": [
   "Пациент"
  ],
  "etichette_nascita": [
   "дата на раждане",
   "роден/а на"
  ],
  "parentela": [
   "близък",
   "лице за контакт",
   "настойник",
   "спешен контакт",
   "съпруг/съпруга"
  ],
  "contatto": [
   "Контакт"
  ]
 },
 "bs": {
  "mesi": [
   "januara",
   "februara",
   "marta",
   "aprila",
   "maja",
   "juna",
   "jula",
   "augusta",
   "septembra",
   "oktobra",
   "novembra",
   "decembra"
  ],
  "titoli_medico": [
   "dr.",
   "prof. dr."
  ],
  "titoli_paziente": [
   "g.",
   "gđa"
  ],
  "etichette_paziente": [
   "Pacijent",
   "Pacijent/ica"
  ],
  "etichette_nascita": [
   "datum rođenja",
   "rođen/a"
  ],
  "parentela": [
   "hitni kontakt",
   "kontakt osoba",
   "staratelj",
   "supružnik",
   "član porodice"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "ca": {
  "mesi": [
   "gener",
   "febrer",
   "març",
   "abril",
   "maig",
   "juny",
   "juliol",
   "agost",
   "setembre",
   "octubre",
   "novembre",
   "desembre"
  ],
  "titoli_medico": [
   "Dr.",
   "Dra.",
   "Prof.",
   "Profa."
  ],
  "titoli_paziente": [
   "Sr.",
   "Sra."
  ],
  "etichette_paziente": [
   "Pacient"
  ],
  "etichette_nascita": [
   "data de naixement",
   "nascut/da el"
  ],
  "parentela": [
   "acompanyant",
   "contacte d'emergència",
   "cònjuge",
   "familiar de referència",
   "tutor legal"
  ],
  "contatto": [
   "Contacte"
  ]
 },
 "cs": {
  "mesi": [
   "ledna",
   "února",
   "března",
   "dubna",
   "května",
   "června",
   "července",
   "srpna",
   "září",
   "října",
   "listopadu",
   "prosince"
  ],
  "titoli_medico": [
   "MUDr.",
   "prim. MUDr.",
   "prof. MUDr."
  ],
  "titoli_paziente": [
   "pan",
   "paní"
  ],
  "etichette_paziente": [
   "Pacient",
   "Pacient/ka",
   "Týká se"
  ],
  "etichette_nascita": [
   "datum narození",
   "narozen/a"
  ],
  "parentela": [
   "blízká osoba",
   "kontaktní osoba",
   "manžel/manželka",
   "nouzový kontakt",
   "opatrovník"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "cy": {
  "mesi": [
   "Ionawr",
   "Chwefror",
   "Mawrth",
   "Ebrill",
   "Mai",
   "Mehefin",
   "Gorffennaf",
   "Awst",
   "Medi",
   "Hydref",
   "Tachwedd",
   "Rhagfyr"
  ],
  "titoli_medico": [
   "Athro",
   "Dr"
  ],
  "titoli_paziente": [
   "Mr",
   "Mrs",
   "Ms"
  ],
  "etichette_paziente": [
   "Claf"
  ],
  "etichette_nascita": [
   "Dyddiad geni",
   "a anwyd ar",
   "dyddiad geni"
  ],
  "parentela": [
   "cyswllt brys",
   "gofalwr",
   "gwarcheidwad cyfreithiol",
   "perthynas agosaf",
   "priod"
  ],
  "contatto": [
   "Cyswllt"
  ]
 },
 "da": {
  "mesi": [
   "januar",
   "februar",
   "marts",
   "april",
   "maj",
   "juni",
   "juli",
   "august",
   "september",
   "oktober",
   "november",
   "december"
  ],
  "titoli_medico": [
   "Dr.",
   "Overlæge dr."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Patient"
  ],
  "etichette_nascita": [
   "Født",
   "fødselsdato",
   "født"
  ],
  "parentela": [
   "kontaktperson",
   "nødkontakt",
   "pårørende",
   "værge",
   "ægtefælle"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "de": {
  "mesi": [
   "Januar",
   "Februar",
   "März",
   "April",
   "Mai",
   "Juni",
   "Juli",
   "August",
   "September",
   "Oktober",
   "November",
   "Dezember"
  ],
  "titoli_medico": [
   "Dr. med.",
   "OA Dr.",
   "OÄ Dr.",
   "Prof. Dr."
  ],
  "titoli_paziente": [
   "Frau",
   "Herr"
  ],
  "etichette_paziente": [
   "Patient/in"
  ],
  "etichette_nascita": [
   "Geburtsdatum",
   "am",
   "geboren am"
  ],
  "parentela": [
   "Angehörige/r",
   "Betreuer/in",
   "Ehepartner/in",
   "Kontaktperson",
   "Notfallkontakt"
  ],
  "contatto": [
   "Angehörige/Notfallkontakt"
  ]
 },
 "el": {
  "mesi": [
   "Ιανουαρίου",
   "Φεβρουαρίου",
   "Μαρτίου",
   "Απριλίου",
   "Μαΐου",
   "Ιουνίου",
   "Ιουλίου",
   "Αυγούστου",
   "Σεπτεμβρίου",
   "Οκτωβρίου",
   "Νοεμβρίου",
   "Δεκεμβρίου"
  ],
  "titoli_medico": [
   "Δρ.",
   "Καθ."
  ],
  "titoli_paziente": [
   "κ.",
   "κα"
  ],
  "etichette_paziente": [
   "Ασθενής"
  ],
  "etichette_nascita": [
   "γέννησης",
   "γεννηθείς/είσα",
   "γεννηθείς/είσα στις",
   "ημερομηνία γέννησης"
  ],
  "parentela": [
   "άτομο επικοινωνίας",
   "επαφή έκτακτης ανάγκης",
   "νόμιμος εκπρόσωπος",
   "συγγενής",
   "σύζυγος"
  ],
  "contatto": [
   "Επαφή"
  ]
 },
 "en": {
  "mesi": [
   "January",
   "February",
   "March",
   "April",
   "May",
   "June",
   "July",
   "August",
   "September",
   "October",
   "November",
   "December"
  ],
  "titoli_medico": [
   "Dr",
   "Prof."
  ],
  "titoli_paziente": [
   "Mr",
   "Mrs",
   "Ms"
  ],
  "etichette_paziente": [
   "Patient"
  ],
  "etichette_nascita": [
   "DOB",
   "born",
   "born on",
   "date of birth"
  ],
  "parentela": [
   "carer",
   "emergency contact",
   "legal guardian",
   "next of kin",
   "spouse"
  ],
  "contatto": [
   "Contact"
  ]
 },
 "es": {
  "mesi": [
   "enero",
   "febrero",
   "marzo",
   "abril",
   "mayo",
   "junio",
   "julio",
   "agosto",
   "septiembre",
   "octubre",
   "noviembre",
   "diciembre"
  ],
  "titoli_medico": [
   "Dr.",
   "Dra.",
   "Prof.",
   "Profa."
  ],
  "titoli_paziente": [
   "D.",
   "Dña.",
   "Sr.",
   "Sra."
  ],
  "etichette_paziente": [
   "Paciente"
  ],
  "etichette_nascita": [
   "con fecha de nacimiento",
   "nacido/a el"
  ],
  "parentela": [
   "acompañante",
   "contacto de emergencia",
   "cónyuge",
   "familiar de contacto",
   "tutor legal"
  ],
  "contatto": [
   "Contacto"
  ]
 },
 "et": {
  "mesi": [
   "jaanuar",
   "veebruar",
   "märts",
   "aprill",
   "mai",
   "juuni",
   "juuli",
   "august",
   "september",
   "oktoober",
   "november",
   "detsember"
  ],
  "titoli_medico": [
   "dr",
   "prof dr"
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Patsient"
  ],
  "etichette_nascita": [
   "sündinud",
   "sünniaeg"
  ],
  "parentela": [
   "abikaasa",
   "eestkostja",
   "hädaabikontakt",
   "kontaktisik",
   "lähedane"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "eu": {
  "mesi": [
   "urtarrilak",
   "otsailak",
   "martxoak",
   "apirilak",
   "maiatzak",
   "ekainak",
   "uztailak",
   "abuztuak",
   "irailak",
   "urriak",
   "azaroak",
   "abenduak"
  ],
  "titoli_medico": [
   "Dr.",
   "Dra.",
   "Med."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Pazientea"
  ],
  "etichette_nascita": [
   "a bideratzen da, jaiotze-data",
   "azientearentzat, jaiotze-data",
   "jaiotze-data",
   "pazientea"
  ],
  "parentela": [
   "ezkontidea",
   "laguntzailea",
   "larrialdi kontaktua",
   "legezko tutorea",
   "senide arduraduna"
  ],
  "contatto": [
   "Kontaktua"
  ]
 },
 "fi": {
  "mesi": [
   "tammikuuta",
   "helmikuuta",
   "maaliskuuta",
   "huhtikuuta",
   "toukokuuta",
   "kesäkuuta",
   "heinäkuuta",
   "elokuuta",
   "syyskuuta",
   "lokakuuta",
   "marraskuuta",
   "joulukuuta"
  ],
  "titoli_medico": [
   "LL",
   "LT",
   "Ylilääkäri"
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Potilas"
  ],
  "etichette_nascita": [
   "syntymäaika",
   "syntynyt"
  ],
  "parentela": [
   "edunvalvoja",
   "hätäyhteys",
   "lähiomainen",
   "puoliso",
   "yhteyshenkilö"
  ],
  "contatto": [
   "Yhteyshenkilö"
  ]
 },
 "fr": {
  "mesi": [
   "janvier",
   "février",
   "mars",
   "avril",
   "mai",
   "juin",
   "juillet",
   "août",
   "septembre",
   "octobre",
   "novembre",
   "décembre"
  ],
  "titoli_medico": [
   "Dr",
   "Pr"
  ],
  "titoli_paziente": [
   "M.",
   "Mme"
  ],
  "etichette_paziente": [
   "Identité"
  ],
  "etichette_nascita": [
   "DDN",
   "date de naissance",
   "le"
  ],
  "parentela": [
   "conjoint(e)",
   "contact d'urgence",
   "personne de confiance",
   "proche",
   "tuteur légal"
  ],
  "contatto": [
   "Personne à prévenir"
  ]
 },
 "ga": {
  "mesi": [
   "Eanáir",
   "Feabhra",
   "Márta",
   "Aibreán",
   "Bealtaine",
   "Meitheamh",
   "Iúil",
   "Lúnasa",
   "Meán Fómhair",
   "Deireadh Fómhair",
   "Samhain",
   "Nollaig"
  ],
  "titoli_medico": [
   "An Dr.",
   "Ollamh"
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Othar"
  ],
  "etichette_nascita": [
   "Dáta breithe",
   "a rugadh ar",
   "dáta breithe"
  ],
  "parentela": [
   "caomhnóir dlíthiúil",
   "céile",
   "cúramóir",
   "neasa gaoil",
   "teagmhálaí éigeandála"
  ],
  "contatto": [
   "Teagmhálaí"
  ]
 },
 "gd": {
  "mesi": [
   "Faoilleach",
   "Gearran",
   "Màrt",
   "Giblean",
   "Cèitean",
   "Ògmhios",
   "Iuchar",
   "Lùnastal",
   "Sultain",
   "Dàmhair",
   "Samhain",
   "Dùbhlachd"
  ],
  "titoli_medico": [
   "An Dr",
   "Ollamh"
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Euslainteach"
  ],
  "etichette_nascita": [
   "Ceann-latha breith",
   "a rugadh air",
   "ceann-latha breith"
  ],
  "parentela": [
   "cèile",
   "dàimheach as fhaisge",
   "neach-conaltraidh èiginn",
   "neach-cùraim",
   "neach-glèidhidh"
  ],
  "contatto": [
   "Neach-conaltraidh"
  ]
 },
 "gl": {
  "mesi": [
   "xaneiro",
   "febreiro",
   "marzo",
   "abril",
   "maio",
   "xuño",
   "xullo",
   "agosto",
   "setembro",
   "outubro",
   "novembro",
   "decembro"
  ],
  "titoli_medico": [
   "Dr.",
   "Dra.",
   "Prof.",
   "Profa."
  ],
  "titoli_paziente": [
   "Sr.",
   "Sra."
  ],
  "etichette_paziente": [
   "Doente"
  ],
  "etichette_nascita": [
   "con data de nacemento",
   "nado/a o"
  ],
  "parentela": [
   "acompañante",
   "contacto de emerxencia",
   "cónxuxe",
   "familiar de referencia",
   "titor legal"
  ],
  "contatto": [
   "Contacto"
  ]
 },
 "hr": {
  "mesi": [
   "siječnja",
   "veljače",
   "ožujka",
   "travnja",
   "svibnja",
   "lipnja",
   "srpnja",
   "kolovoza",
   "rujna",
   "listopada",
   "studenoga",
   "prosinca"
  ],
  "titoli_medico": [
   "dr. med.",
   "prof. dr. sc."
  ],
  "titoli_paziente": [
   "g.",
   "gđa"
  ],
  "etichette_paziente": [
   "Pacijent",
   "Pacijent/ica"
  ],
  "etichette_nascita": [
   "datum rođenja",
   "rođen/a"
  ],
  "parentela": [
   "hitni kontakt",
   "kontakt osoba",
   "supružnik",
   "zakonski skrbnik",
   "član obitelji"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "hu": {
  "mesi": [
   "január",
   "február",
   "március",
   "április",
   "május",
   "június",
   "július",
   "augusztus",
   "szeptember",
   "október",
   "november",
   "december"
  ],
  "titoli_medico": [
   "Dr.",
   "Prof. Dr."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Beteg",
   "Beteg neve"
  ],
  "etichette_nascita": [
   "született",
   "születési idő"
  ],
  "parentela": [
   "hozzátartozó",
   "házastárs",
   "kapcsolattartó",
   "törvényes képviselő",
   "értesítendő személy"
  ],
  "contatto": [
   "Értesítendő"
  ]
 },
 "is": {
  "mesi": [
   "janúar",
   "febrúar",
   "mars",
   "apríl",
   "maí",
   "júní",
   "júlí",
   "ágúst",
   "september",
   "október",
   "nóvember",
   "desember"
  ],
  "titoli_medico": [
   "Dr.",
   "Dr. med."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Sjúklingur"
  ],
  "etichette_nascita": [
   "fæddur/fædd",
   "fæðingardagur"
  ],
  "parentela": [
   "lögráðamaður",
   "maki",
   "neyðartengiliður",
   "nánasti aðstandandi",
   "tengiliður"
  ],
  "contatto": [
   "Aðstandandi"
  ]
 },
 "it": {
  "mesi": [
   "gennaio",
   "febbraio",
   "marzo",
   "aprile",
   "maggio",
   "giugno",
   "luglio",
   "agosto",
   "settembre",
   "ottobre",
   "novembre",
   "dicembre"
  ],
  "titoli_medico": [
   "Dott.",
   "Dott.ssa",
   "Dr.",
   "Dr.ssa",
   "Prof.",
   "Prof.ssa"
  ],
  "titoli_paziente": [
   "Sig.",
   "Sig.ra"
  ],
  "etichette_paziente": [
   "Paziente"
  ],
  "etichette_nascita": [
   "data di nascita",
   "nato/a il",
   "nato/a in data"
  ],
  "parentela": [
   "coniuge",
   "contatto d'emergenza",
   "familiare di riferimento",
   "figlio/a",
   "tutore legale"
  ],
  "contatto": [
   "Contatto"
  ]
 },
 "lb": {
  "mesi": [
   "Januar",
   "Februar",
   "Mäerz",
   "Abrëll",
   "Mee",
   "Juni",
   "Juli",
   "August",
   "September",
   "Oktober",
   "November",
   "Dezember"
  ],
  "titoli_medico": [
   "Dr.",
   "Prof. Dr."
  ],
  "titoli_paziente": [
   "Här",
   "Madamm"
  ],
  "etichette_paziente": [
   "Patient/in"
  ],
  "etichette_nascita": [
   "Gebuertsdatum",
   "gebuer den"
  ],
  "parentela": [
   "Familljemember",
   "Kontaktpersoun",
   "Noutfallkontakt",
   "Partner/in",
   "Tuteur"
  ],
  "contatto": [
   "Kontaktpersoun"
  ]
 },
 "lt": {
  "mesi": [
   "sausio",
   "vasario",
   "kovo",
   "balandžio",
   "gegužės",
   "birželio",
   "liepos",
   "rugpjūčio",
   "rugsėjo",
   "spalio",
   "lapkričio",
   "gruodžio"
  ],
  "titoli_medico": [
   "gyd.",
   "prof. dr."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Pacientas",
   "Pacientas/ė"
  ],
  "etichette_nascita": [
   "gimimo data",
   "gimęs/usi"
  ],
  "parentela": [
   "artimasis",
   "kontaktinis asmuo",
   "skubus kontaktas",
   "sutuoktinis",
   "teisėtas atstovas"
  ],
  "contatto": [
   "Kontaktas"
  ]
 },
 "lv": {
  "mesi": [
   "janvāris",
   "februāris",
   "marts",
   "aprīlis",
   "maijs",
   "jūnijs",
   "jūlijs",
   "augusts",
   "septembris",
   "oktobris",
   "novembris",
   "decembris"
  ],
  "titoli_medico": [
   "Dr.",
   "Prof. Dr."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Pacients"
  ],
  "etichette_nascita": [
   "dzimis/dzimusi",
   "dzimis/usi",
   "dzimšanas datums"
  ],
  "parentela": [
   "kontaktpersona",
   "laulātais",
   "likumiskais pārstāvis",
   "tuvinieks",
   "ārkārtas kontakts"
  ],
  "contatto": [
   "Kontakts"
  ]
 },
 "mk": {
  "mesi": [
   "јануари",
   "февруари",
   "март",
   "април",
   "мај",
   "јуни",
   "јули",
   "август",
   "септември",
   "октомври",
   "ноември",
   "декември"
  ],
  "titoli_medico": [
   "д-р",
   "проф. д-р"
  ],
  "titoli_paziente": [
   "г-ѓа",
   "г."
  ],
  "etichette_paziente": [
   "Пациент"
  ],
  "etichette_nascita": [
   "датум на раѓање",
   "роден/а",
   "роден/а на"
  ],
  "parentela": [
   "итен контакт",
   "лице за контакт",
   "сопружник",
   "старател",
   "член на семејство"
  ],
  "contatto": [
   "Контакт"
  ]
 },
 "mt": {
  "mesi": [
   "Jannar",
   "Frar",
   "Marzu",
   "April",
   "Mejju",
   "Ġunju",
   "Lulju",
   "Awwissu",
   "Settembru",
   "Ottubru",
   "Novembru",
   "Diċembru"
  ],
  "titoli_medico": [
   "Dr",
   "Prof."
  ],
  "titoli_paziente": [
   "Sinjorina",
   "Sinjura",
   "Sur"
  ],
  "etichette_paziente": [
   "Pazjent/a"
  ],
  "etichette_nascita": [
   "data tat-twelid",
   "imwieled/imwielda",
   "twieled/twieldet"
  ],
  "parentela": [
   "konjuġi",
   "kuntatt",
   "kuntatt ta' emerġenza",
   "kustodju legali",
   "qarib ewlieni"
  ],
  "contatto": [
   "Kuntatt"
  ]
 },
 "nl": {
  "mesi": [
   "januari",
   "februari",
   "maart",
   "april",
   "mei",
   "juni",
   "juli",
   "augustus",
   "september",
   "oktober",
   "november",
   "december"
  ],
  "titoli_medico": [
   "dr.",
   "prof. dr."
  ],
  "titoli_paziente": [
   "dhr.",
   "mevr."
  ],
  "etichette_paziente": [
   "Patiënt"
  ],
  "etichette_nascita": [
   "geboortedatum",
   "geboren",
   "geboren op"
  ],
  "parentela": [
   "contactpersoon",
   "mantelzorger",
   "noodcontact",
   "partner",
   "wettelijk vertegenwoordiger"
  ],
  "contatto": [
   "Contact"
  ]
 },
 "no": {
  "mesi": [
   "januar",
   "februar",
   "mars",
   "april",
   "mai",
   "juni",
   "juli",
   "august",
   "september",
   "oktober",
   "november",
   "desember"
  ],
  "titoli_medico": [
   "Dr.",
   "Overlege"
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Pasient"
  ],
  "etichette_nascita": [
   "Født",
   "fødselsdato",
   "født"
  ],
  "parentela": [
   "ektefelle",
   "kontaktperson",
   "nødkontakt",
   "pårørende",
   "verge"
  ],
  "contatto": [
   "Pårørende"
  ]
 },
 "pl": {
  "mesi": [
   "stycznia",
   "lutego",
   "marca",
   "kwietnia",
   "maja",
   "czerwca",
   "lipca",
   "sierpnia",
   "września",
   "października",
   "listopada",
   "grudnia"
  ],
  "titoli_medico": [
   "dr n. med.",
   "lek.",
   "prof. dr hab."
  ],
  "titoli_paziente": [
   "Pan",
   "Pani"
  ],
  "etichette_paziente": [
   "Dotyczy",
   "Pacjent",
   "Pacjent/ka"
  ],
  "etichette_nascita": [
   "data urodzenia",
   "urodzony/a"
  ],
  "parentela": [
   "bliski",
   "kontakt alarmowy",
   "małżonek/małżonka",
   "opiekun prawny",
   "osoba upoważniona"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "pt": {
  "mesi": [
   "janeiro",
   "fevereiro",
   "março",
   "abril",
   "maio",
   "junho",
   "julho",
   "agosto",
   "setembro",
   "outubro",
   "novembro",
   "dezembro"
  ],
  "titoli_medico": [
   "Dr.",
   "Dra.",
   "Prof. Dr.",
   "Profa. Dra."
  ],
  "titoli_paziente": [
   "Sr.",
   "Sra."
  ],
  "etichette_paziente": [
   "Utente"
  ],
  "etichette_nascita": [
   "data de nascimento",
   "nascido/a a",
   "nascido/a em"
  ],
  "parentela": [
   "acompanhante",
   "contacto de emergência",
   "cônjuge",
   "familiar de referência",
   "representante legal"
  ],
  "contatto": [
   "Contacto"
  ]
 },
 "ro": {
  "mesi": [
   "ianuarie",
   "februarie",
   "martie",
   "aprilie",
   "mai",
   "iunie",
   "iulie",
   "august",
   "septembrie",
   "octombrie",
   "noiembrie",
   "decembrie"
  ],
  "titoli_medico": [
   "Dr.",
   "Prof. Dr."
  ],
  "titoli_paziente": [
   "Dl.",
   "Dna."
  ],
  "etichette_paziente": [
   "Pacient",
   "Pacient/ă"
  ],
  "etichette_nascita": [
   "data nașterii",
   "născut/ă la"
  ],
  "parentela": [
   "aparținător",
   "contact de urgență",
   "persoană de contact",
   "soț/soție",
   "tutore legal"
  ],
  "contatto": [
   "Contact"
  ]
 },
 "ru": {
  "mesi": [
   "января",
   "февраля",
   "марта",
   "апреля",
   "мая",
   "июня",
   "июля",
   "августа",
   "сентября",
   "октября",
   "ноября",
   "декабря"
  ],
  "titoli_medico": [
   "д-р",
   "проф."
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Пациент"
  ],
  "etichette_nascita": [
   "дата рождения"
  ],
  "parentela": [
   "контактное лицо",
   "опекун",
   "родственник",
   "супруг/супруга",
   "экстренный контакт"
  ],
  "contatto": [
   "Контакт"
  ]
 },
 "sk": {
  "mesi": [
   "januára",
   "februára",
   "marca",
   "apríla",
   "mája",
   "júna",
   "júla",
   "augusta",
   "septembra",
   "októbra",
   "novembra",
   "decembra"
  ],
  "titoli_medico": [
   "MUDr.",
   "prof. MUDr."
  ],
  "titoli_paziente": [
   "pani",
   "pán"
  ],
  "etichette_paziente": [
   "Pacient",
   "Pacient/ka"
  ],
  "etichette_nascita": [
   "dátum narodenia",
   "narodený/á"
  ],
  "parentela": [
   "blízka osoba",
   "kontaktná osoba",
   "manžel/manželka",
   "núdzový kontakt",
   "zákonný zástupca"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "sl": {
  "mesi": [
   "januarja",
   "februarja",
   "marca",
   "aprila",
   "maja",
   "junija",
   "julija",
   "avgusta",
   "septembra",
   "oktobra",
   "novembra",
   "decembra"
  ],
  "titoli_medico": [
   "dr. med.",
   "prof. dr."
  ],
  "titoli_paziente": [
   "g.",
   "ga."
  ],
  "etichette_paziente": [
   "Pacient",
   "Pacient/ka"
  ],
  "etichette_nascita": [
   "datum rojstva",
   "rojen/a"
  ],
  "parentela": [
   "kontaktna oseba",
   "nujni kontakt",
   "svojec",
   "zakonec",
   "zakoniti zastopnik"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "sq": {
  "mesi": [
   "janar",
   "shkurt",
   "mars",
   "prill",
   "maj",
   "qershor",
   "korrik",
   "gusht",
   "shtator",
   "tetor",
   "nëntor",
   "dhjetor"
  ],
  "titoli_medico": [
   "Dr.",
   "Prof. Dr."
  ],
  "titoli_paziente": [
   "Z.",
   "Znj."
  ],
  "etichette_paziente": [
   "Pacienti",
   "Pacienti/ja"
  ],
  "etichette_nascita": [
   "datëlindja",
   "lindur më",
   "me datëlindje"
  ],
  "parentela": [
   "bashkëshort/e",
   "familjar",
   "kontakt emergjence",
   "kujdestar ligjor",
   "person kontakti"
  ],
  "contatto": [
   "Kontakti"
  ]
 },
 "sr": {
  "mesi": [
   "јануара",
   "фебруара",
   "марта",
   "априла",
   "маја",
   "јуна",
   "јула",
   "августа",
   "септембра",
   "октобра",
   "новембра",
   "децембра"
  ],
  "titoli_medico": [
   "др",
   "проф. др"
  ],
  "titoli_paziente": [
   "г.",
   "гђа"
  ],
  "etichette_paziente": [
   "Пацијент"
  ],
  "etichette_nascita": [
   "датум рођења",
   "рођен/а"
  ],
  "parentela": [
   "контакт особа",
   "старатељ",
   "супружник",
   "хитан контакт",
   "члан породице"
  ],
  "contatto": [
   "Контакт"
  ]
 },
 "sv": {
  "mesi": [
   "januari",
   "februari",
   "mars",
   "april",
   "maj",
   "juni",
   "juli",
   "augusti",
   "september",
   "oktober",
   "november",
   "december"
  ],
  "titoli_medico": [
   "Dr",
   "Överläkare"
  ],
  "titoli_paziente": [],
  "etichette_paziente": [
   "Patient"
  ],
  "etichette_nascita": [
   "Född",
   "född",
   "född den",
   "födelsedatum"
  ],
  "parentela": [
   "anhörig",
   "god man",
   "kontaktperson",
   "make/maka",
   "närmast anhörig"
  ],
  "contatto": [
   "Kontakt"
  ]
 },
 "tr": {
  "mesi": [
   "Ocak",
   "Şubat",
   "Mart",
   "Nisan",
   "Mayıs",
   "Haziran",
   "Temmuz",
   "Ağustos",
   "Eylül",
   "Ekim",
   "Kasım",
   "Aralık"
  ],
  "titoli_medico": [
   "Prof. Dr.",
   "Uzm. Dr."
  ],
  "titoli_paziente": [
   "Sayın"
  ],
  "etichette_paziente": [
   "Hasta"
  ],
  "etichette_nascita": [
   "doğum",
   "doğum tarihi"
  ],
  "parentela": [
   "acil durum kişisi",
   "eş",
   "hasta yakını",
   "irtibat kişisi",
   "yasal vasi"
  ],
  "contatto": [
   "İrtibat"
  ]
 },
 "uk": {
  "mesi": [
   "січня",
   "лютого",
   "березня",
   "квітня",
   "травня",
   "червня",
   "липня",
   "серпня",
   "вересня",
   "жовтня",
   "листопада",
   "грудня"
  ],
  "titoli_medico": [
   "д-р",
   "проф."
  ],
  "titoli_paziente": [
   "п."
  ],
  "etichette_paziente": [
   "Пацієнт"
  ],
  "etichette_nascita": [
   "дата народження"
  ],
  "parentela": [
   "екстрений контакт",
   "контактна особа",
   "опікун",
   "родич",
   "чоловік/дружина"
  ],
  "contatto": [
   "Контакт"
  ]
 }
}
