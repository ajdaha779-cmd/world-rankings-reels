"""Каталог: страны, группы стран и темы рейтингов (индикаторы Всемирного банка)."""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))

# призыв в конце ролика (подпись, голос): в Instagram бот отвечает каждому, на YouTube — нет
CTA = (("Where does it rank?", "Comment your flag below!") if os.environ.get("REELS_PLATFORM") == "youtube"
       else ("We'll reply with its rank!", "Comment your flag. We'll reply with your rank!"))

# территории и спорные образования — не берём, чтобы не было претензий «это не страна»
EXCLUDE = set("AS AW BM VG KY CW FO PF GI GL GU HK IM MO MF NC MP PR SX TC VI JG XK PS KP".split())

SHORT = {"BS": "Bahamas", "BN": "Brunei", "CD": "DR Congo", "CG": "Congo", "EG": "Egypt", "FM": "Micronesia",
         "GM": "Gambia", "IR": "Iran", "KN": "St Kitts & Nevis", "KR": "South Korea", "RU": "Russia",
         "SO": "Somalia", "ST": "São Tomé", "SY": "Syria", "TT": "Trinidad & Tobago", "VC": "St Vincent",
         "VE": "Venezuela", "YE": "Yemen", "LA": "Laos", "KG": "Kyrgyzstan", "SK": "Slovakia", "CZ": "Czechia",
         "VN": "Vietnam", "TR": "Turkey", "CI": "Ivory Coast", "US": "USA", "GB": "UK", "AE": "UAE",
         "BA": "Bosnia", "CF": "Central Africa", "DO": "Dominican Rep.", "GQ": "Eq. Guinea",
         "PG": "Papua New Guinea", "AG": "Antigua & Barbuda", "MK": "North Macedonia", "SZ": "Eswatini",
         "TL": "Timor-Leste", "LC": "St Lucia", "MH": "Marshall Islands", "SB": "Solomon Islands"}


def _load_countries():
    raw = json.load(open(os.path.join(BASE, "data", "countries_raw.json")))[1]
    out = {}
    for c in raw:
        iso = c["iso2Code"]
        if c["region"]["value"] == "Aggregates" or iso in EXCLUDE:
            continue
        out[iso] = SHORT.get(iso, c["name"])
    return out


COUNTRIES = _load_countries()

_g = lambda s: [x for x in s.split() if x in COUNTRIES]
GROUPS = {
    "world": ("the world", list(COUNTRIES)),
    "europe": ("Europe", _g("AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT LV LI LT LU MT MD MC ME "
                            "NL MK NO PL PT RO RU SM RS SK SI ES SE CH UA GB")),
    "asia": ("Asia", _g("CN JP KR IN ID TH VN MY PH SG BD PK LK NP MM KH LA MN KZ UZ KG TJ TM AF IR IQ SA AE QA "
                        "KW BH OM YE JO LB SY IL TR AZ GE AM BT MV BN TL")),
    "americas": ("the Americas", _g("US CA MX GT BZ HN SV NI CR PA CU JM HT DO BS BB TT CO VE EC PE BO BR PY UY "
                                    "AR CL GY SR")),
    "africa": ("Africa", _g("DZ EG LY MA TN NG GH CI SN ML BF NE TD SD SS ET ER DJ SO KE UG RW BI TZ MZ MW ZM "
                            "ZW BW NA ZA LS SZ MG AO CD CG GA CM CF GQ BJ TG LR SL GN GW GM MR CV MU SC KM ST")),
    "mideast": ("the Middle East", _g("SA AE QA KW BH OM YE JO LB SY IQ IR IL TR EG")),
    "exussr": ("ex-USSR countries", _g("AM AZ BY EE GE KZ KG LV LT MD RU TJ TM UA UZ")),
    "g20": ("G20 countries", _g("AR AU BR CA CN FR DE IN ID IT JP KR MX RU SA ZA TR GB US")),
    "eu": ("the EU", _g("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE")),
}


# ---------- форматы чисел ----------
def _compact(v, prefix=""):
    a = abs(v)
    sign = "-" if v < 0 else ""
    for lim, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= lim:
            return f"{sign}{prefix}{a / lim:.1f}{suf}" if a / lim < 100 else f"{sign}{prefix}{a / lim:.0f}{suf}"
    return f"{sign}{prefix}{a:,.0f}"


FMT = {
    "money": lambda v: f"${v:,.0f}" if v < 1e6 else _compact(v, "$"),
    "pct": lambda v: f"{v:.1f}%",
    "years": lambda v: f"{v:.1f} yrs",
    "dec2": lambda v: f"{v:.2f}",
    "dec1": lambda v: f"{v:.1f}",
    "people": lambda v: _compact(v),
    "signed": lambda v: ("+" if v > 0 else "") + _compact(v),
    "density": lambda v: f"{v:,.0f}/km²",
    "tonnes": lambda v: f"{v:.1f} t",
}

# id, индикатор, порядок, хук (2 строки), подпись, формат, вопрос для заголовка, теги
TOPICS = [
    ("rich", "NY.GDP.PCAP.CD", "desc", ("RICHEST", "PER PERSON"), "GDP per person (USD)", "money",
     "Which countries are the richest per person {g}?", "money economy gdp"),
    ("poor", "NY.GDP.PCAP.CD", "asc", ("POOREST", "PER PERSON"), "GDP per person (USD)", "money",
     "Which countries are the poorest {g}?", "money economy poverty"),
    ("life", "SP.DYN.LE00.IN", "desc", ("WHERE PEOPLE", "LIVE LONGEST"), "Life expectancy at birth", "years",
     "Where do people live the longest {g}?", "health lifeexpectancy"),
    ("babies", "SP.DYN.TFRT.IN", "desc", ("MOST BABIES", "PER WOMAN"), "Births per woman", "dec2",
     "Where do women have the most babies {g}?", "population birthrate"),
    ("lowbirth", "SP.DYN.TFRT.IN", "asc", ("LOWEST", "BIRTH RATE"), "Births per woman", "dec2",
     "Which countries have the lowest birth rate {g}?", "population birthrate"),
    ("unemp", "SL.UEM.TOTL.ZS", "desc", ("HIGHEST", "UNEMPLOYMENT"), "Unemployment (% of workforce)", "pct",
     "Where is unemployment the highest {g}?", "jobs economy"),
    ("jobs", "SL.UEM.TOTL.ZS", "asc", ("LOWEST", "UNEMPLOYMENT"), "Unemployment (% of workforce)", "pct",
     "Where is it easiest to find a job {g}?", "jobs economy"),
    ("inflation", "FP.CPI.TOTL.ZG", "desc", ("WHERE PRICES", "RISE FASTEST"), "Inflation (yearly %)", "pct",
     "Where are prices rising the fastest {g}?", "inflation prices economy"),
    ("online", "IT.NET.USER.ZS", "desc", ("MOST", "ONLINE"), "Internet users (% of people)", "pct",
     "Which countries are the most online {g}?", "internet tech"),
    ("offline", "IT.NET.USER.ZS", "asc", ("LEAST", "ONLINE"), "Internet users (% of people)", "pct",
     "Which countries are the least online {g}?", "internet tech"),
    ("pop", "SP.POP.TOTL", "desc", ("MOST", "POPULATED"), "Total population", "people",
     "Which countries have the most people {g}?", "population"),
    ("health", "SH.XPD.CHEX.PC.CD", "desc", ("WHO SPENDS MOST", "ON HEALTH?"), "Health spending per person (USD)",
     "money", "Who spends the most on health {g}?", "health healthcare"),
    ("old", "SP.POP.65UP.TO.ZS", "desc", ("OLDEST", "COUNTRIES"), "People aged 65+ (% of population)", "pct",
     "Which countries are the oldest {g}?", "population aging"),
    ("doctors", "SH.MED.PHYS.ZS", "desc", ("MOST DOCTORS", "PER PERSON"), "Doctors per 1,000 people", "dec1",
     "Where are the most doctors {g}?", "health doctors"),
    ("crowded", "EN.POP.DNST", "desc", ("MOST", "CROWDED"), "People per km²", "density",
     "Which countries are the most crowded {g}?", "population density"),
    ("green", "AG.LND.FRST.ZS", "desc", ("GREENEST", "COUNTRIES"), "Forest area (% of land)", "pct",
     "Which countries are the greenest {g}?", "nature forest"),
    ("co2", "EN.GHG.CO2.PC.CE.AR5", "desc", ("BIGGEST POLLUTERS", "PER PERSON"), "CO2 per person (tonnes/year)",
     "tonnes", "Who pollutes the most per person {g}?", "climate environment"),
    ("women", "SL.TLF.CACT.FE.ZS", "desc", ("WHERE MOST", "WOMEN WORK"), "Women in the workforce (% of women 15+)",
     "pct", "Where do the most women work {g}?", "women jobs"),
    ("economy", "NY.GDP.MKTP.CD", "desc", ("BIGGEST", "ECONOMIES"), "GDP (USD)", "money",
     "What are the biggest economies {g}?", "economy gdp money"),
    ("growth", "NY.GDP.MKTP.KD.ZG", "desc", ("FASTEST GROWING", "ECONOMIES"), "GDP growth (yearly %)", "pct",
     "Which economies are growing the fastest {g}?", "economy growth"),
    ("movein", "SM.POP.NETM", "desc", ("WHERE EVERYONE", "IS MOVING"), "Net migration (people per year)", "signed",
     "Where is everyone moving to {g}?", "migration population"),
    ("moveout", "SM.POP.NETM", "asc", ("WHERE PEOPLE", "ARE LEAVING"), "Net migration (people per year)", "signed",
     "Which countries are people leaving {g}?", "migration population"),
]
TOPICS = [dict(zip(("id", "ind", "order", "hook", "sub", "fmt", "question", "tags"), t)) for t in TOPICS]

ACCENTS = [(255, 196, 46), (46, 204, 113), (64, 196, 255), (255, 92, 120), (190, 120, 255), (255, 140, 50)]

# ---------- гонка графиков во времени ----------
RACE_GROUPS = ["world", "europe", "asia", "americas", "africa", "exussr"]
RACE_TOPICS = [
    ("pop", "SP.POP.TOTL", ("MOST POPULATED", "COUNTRIES"), "Population", "people",
     "Most populated countries {g}, {y0} → {y1}", "population history"),
    ("economy", "NY.GDP.MKTP.CD", ("BIGGEST", "ECONOMIES"), "GDP (USD)", "money",
     "Biggest economies {g}, {y0} → {y1}", "economy gdp history"),
    ("rich", "NY.GDP.PCAP.CD", ("RICHEST", "PER PERSON"), "GDP per person (USD)", "money",
     "Richest countries per person {g}, {y0} → {y1}", "money economy history"),
    ("life", "SP.DYN.LE00.IN", ("LONGEST", "LIVES"), "Life expectancy (years)", "years",
     "Where people live longest {g}, {y0} → {y1}", "health lifeexpectancy history"),
    ("online", "IT.NET.USER.ZS", ("MOST", "ONLINE"), "Internet users (% of people)", "pct",
     "Most online countries {g}, {y0} → {y1}", "internet tech history"),
    ("old", "SP.POP.65UP.TO.ZS", ("OLDEST", "COUNTRIES"), "People aged 65+ (%)", "pct",
     "Oldest countries {g}, {y0} → {y1}", "population aging history"),
    ("co2", "EN.GHG.CO2.PC.CE.AR5", ("BIGGEST POLLUTERS", "PER PERSON"), "CO2 per person (tonnes)", "tonnes",
     "Biggest polluters per person {g}, {y0} → {y1}", "climate environment history"),
    # 20.11: «most dangerous» — хиты Instagram (Asia 1 704, Europe 1 509) → та же тема гонкой по годам
    ("danger", "VC.IHR.PSRC.P5", ("MOST DANGEROUS", "COUNTRIES"), "Murders per 100,000 people", "dec1",
     "Most dangerous countries {g}, {y0} → {y1}", "safety crime travel history"),
]
RACE_TOPICS = [dict(zip(("id", "ind", "hook", "sub", "fmt", "question", "tags"), t)) for t in RACE_TOPICS]

# ---------- дуэль двух стран ----------
# пары-соперники без активных войн и конфликтов между ними
DUEL_PAIRS = [("US", "CN"), ("DE", "FR"), ("GB", "FR"), ("JP", "KR"), ("BR", "AR"), ("ES", "PT"), ("IT", "ES"),
              ("CA", "AU"), ("US", "CA"), ("IN", "CN"), ("KZ", "UZ"), ("NO", "SE"), ("NL", "BE"), ("NG", "ZA"),
              ("ID", "PH"), ("VN", "TH"), ("SA", "AE"), ("EG", "MA"), ("PL", "CZ"), ("CH", "AT"), ("DK", "FI"),
              ("AZ", "GE"), ("AZ", "KZ"), ("TR", "AZ"), ("US", "GB"), ("DE", "JP"), ("MX", "BR"), ("IT", "FR"),
              ("CL", "PE"), ("CO", "VE"), ("IE", "GB"), ("NZ", "AU"), ("GR", "IT"), ("UA", "PL"), ("RU", "KZ"),
              ("TR", "GR"), ("QA", "AE"), ("SG", "MY"), ("KR", "CN"), ("PT", "BR")]
# индикатор, подпись, формат, побеждает большее значение?
DUEL_STATS = [("NY.GDP.PCAP.CD", "Richer per person", "money", True),
              ("SP.DYN.LE00.IN", "Longer lives", "years", True),
              ("SL.UEM.TOTL.ZS", "Lower unemployment", "pct", False),
              ("IT.NET.USER.ZS", "More online", "pct", True),
              ("SH.MED.PHYS.ZS", "More doctors (per 1,000)", "dec1", True),
              ("AG.LND.FRST.ZS", "Greener (forest %)", "pct", True),
              ("EN.GHG.CO2.PC.CE.AR5", "Less CO2 per person", "tonnes", False),
              ("SP.POP.TOTL", "Bigger population", "people", True),
              ("NY.GDP.MKTP.CD", "Bigger economy", "money", True),
              ("SH.XPD.CHEX.PC.CD", "More health spending", "money", True)]


def flag_emoji(iso):
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in iso)

# ---------- дополнительные темы рейтингов (6 роликов в день — нужен большой запас) ----------
_MORE = [
    ("urban", "SP.URB.TOTL.IN.ZS", "desc", ("MOST", "URBAN"), "People living in cities (%)", "pct",
     "Which countries are the most urban {g}?", "cities urbanization"),
    ("rural", "SP.URB.TOTL.IN.ZS", "asc", ("MOST", "RURAL"), "People living in cities (%)", "pct",
     "Which countries are the most rural {g}?", "village countryside"),
    ("flights", "IS.AIR.PSGR", "desc", ("BUSIEST", "SKIES"), "Air passengers per year", "people",
     "Which countries fly the most {g}?", "travel aviation"),
    ("renew", "EG.ELC.RNEW.ZS", "desc", ("CLEANEST", "ELECTRICITY"), "Renewable electricity (% of total)", "pct",
     "Who has the cleanest electricity {g}?", "energy renewable climate"),
    ("school", "SE.XPD.TOTL.GD.ZS", "desc", ("WHO INVESTS MOST", "IN EDUCATION?"), "Education spending (% of GDP)", "pct",
     "Who invests the most in education {g}?", "education school"),
    ("ppp", "NY.GNP.PCAP.PP.CD", "desc", ("REAL BUYING", "POWER"), "Income per person, adjusted for prices ($)",
     "money", "Where does money go the furthest {g}?", "money income"),
    ("young", "SP.POP.0014.TO.ZS", "desc", ("YOUNGEST", "COUNTRIES"), "Children under 15 (% of population)", "pct",
     "Which countries are the youngest {g}?", "population youth"),
    ("boom", "SP.POP.GROW", "desc", ("FASTEST GROWING", "POPULATION"), "Population growth (yearly %)", "pct",
     "Whose population is growing the fastest {g}?", "population growth"),
    ("shrink", "SP.POP.GROW", "asc", ("SHRINKING", "COUNTRIES"), "Population growth (yearly %)", "pct",
     "Which countries are shrinking the fastest {g}?", "population decline"),
]
# 11.11: острые темы — каждый ищет свою страну и спорит в комментариях (данные World Bank)
_MORE += [
    ("danger", "VC.IHR.PSRC.P5", "desc", ("MOST DANGEROUS", "COUNTRIES"), "Murders per 100,000 people", "dec1",
     "Which countries are the most dangerous {g}?", "safety crime travel"),
    ("safe", "VC.IHR.PSRC.P5", "asc", ("SAFEST", "COUNTRIES"), "Murders per 100,000 people", "dec1",
     "Which countries are the safest {g}?", "safety crime travel"),
    ("army", "MS.MIL.XPND.CD", "desc", ("BIGGEST", "MILITARY BUDGETS"), "Military spending (USD)", "money",
     "Who spends the most on the military {g}?", "military army defense"),
    ("soldiers", "MS.MIL.TOTL.P1", "desc", ("BIGGEST", "ARMIES"), "Armed forces personnel", "people",
     "Which countries have the biggest armies {g}?", "military army"),
    ("fat", "SH.STA.OWAD.ZS", "desc", ("MOST OVERWEIGHT", "COUNTRIES"), "Overweight adults (%)", "pct",
     "Which countries are the most overweight {g}?", "health obesity"),
    ("unequal", "SI.POV.GINI", "desc", ("MOST UNEQUAL", "COUNTRIES"), "Inequality (Gini index)", "dec1",
     "Where is the gap between rich and poor the biggest {g}?", "inequality money"),
    ("shortlife", "SP.DYN.LE00.IN", "asc", ("SHORTEST", "LIVES"), "Life expectancy at birth", "years",
     "Where do people die the youngest {g}?", "health lifeexpectancy"),
    # 23.11: темы с той же механикой, что «most dangerous» (моя страна + стыд/гордость + спор); свежие данные World Bank
    ("womendanger", "VC.IHR.PSRC.FE.P5", "desc", ("MOST DANGEROUS", "FOR WOMEN"), "Women murdered per 100,000", "dec1",
     "Where is it most dangerous to be a woman {g}?", "safety women travel"),
    ("womensafe", "VC.IHR.PSRC.FE.P5", "asc", ("SAFEST", "FOR WOMEN"), "Women murdered per 100,000", "dec1",
     "Where is it safest to be a woman {g}?", "safety women travel"),
    ("smokers", "SH.PRV.SMOK", "desc", ("BIGGEST", "SMOKERS"), "Adults who smoke (%)", "pct",
     "Which countries smoke the most {g}?", "health smoking"),
    ("youthjobs", "SL.UEM.1524.ZS", "desc", ("NO JOBS", "FOR YOUNG PEOPLE"), "Youth unemployment (%)", "pct",
     "Where can't young people find a job {g}?", "jobs youth economy"),
]
TOPICS += [dict(zip(("id", "ind", "order", "hook", "sub", "fmt", "question", "tags"), t)) for t in _MORE]
RACE_TOPICS += [dict(zip(("id", "ind", "hook", "sub", "fmt", "question", "tags"), t)) for t in [
    ("army", "MS.MIL.XPND.CD", ("BIGGEST", "MILITARY BUDGETS"), "Military spending (USD)", "money",
     "Biggest military budgets {g}, {y0} → {y1}", "military army history"),
]]

DUEL_PAIRS += [("US", "RU"), ("JP", "CN"), ("FR", "ES"), ("SE", "FI"), ("BR", "PT"), ("AR", "CL"), ("MX", "ES"),
               ("ID", "MY"), ("EG", "SA"), ("NG", "GH"), ("KE", "TZ"), ("ZA", "AU"), ("NL", "DE"), ("BE", "FR"),
               ("HU", "AT"), ("RO", "BG"), ("UZ", "KG"), ("GE", "TR"), ("KZ", "MN"), ("IE", "IS"), ("NO", "DK"),
               ("CA", "MX"), ("PH", "VN"), ("TH", "MY"), ("IN", "BD"), ("AE", "SG"), ("CH", "SG"), ("CN", "IN"),
               ("PL", "DE"), ("UA", "TR")]

# 14.11: иранская аудитория — самая активная в комментариях
DUEL_PAIRS += [("IR", "TR"), ("IR", "DE"), ("IR", "IT"), ("IR", "JP"), ("IR", "KR"), ("IR", "IN"), ("IR", "ES"),
               ("IR", "BR"), ("IR", "EG"), ("IR", "FR"), ("IR", "GB"), ("AZ", "TR"), ("MN", "KR"), ("AR", "GB")]
