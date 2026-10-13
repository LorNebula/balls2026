"""Finnish / Finnish-inspired name generator."""

from __future__ import annotations

import random

SYLLABLES = (
    "kai",
    "tuo",
    "jar",
    "valo",
    "kivi",
    "lumi",
    "meri",
    "suo",
    "metsa",
    "havu",
    "kuu",
    "tahti",
    "pohja",
    "ita",
    "lansi",
    "kesa",
    "talvi",
    "ranta",
    "niemi",
    "saari",
    "lahti",
    "vuori",
    "joki",
    "koski",
    "halla",
    "usva",
    "aamu",
    "yota",
    "paiva",
)

SUFFIXES = ("nen", "la", "jarvi", "maa", "asema", "kyla", "niemi", "ranta", "lahti", "vuori")

STATION_PREFIXES = ("Satama", "Telakka", "Kaivos", "Terminaali", "Telakointi", "Satelliitti")

FINNISH_CITIES = (
    "Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu", "Turku", "Jyvaskyla",
    "Lahti", "Kuopio", "Pori", "Kouvola", "Joensuu", "Lappeenranta", "Hameenlinna",
    "Vaasa", "Rovaniemi", "Seinajoki", "Mikkeli", "Kotka", "Salo", "Porvoo",
    "Kokkola", "Lohja", "Hyvinkaa", "Nokia", "Jarvenpaa", "Rauma", "Kerava",
    "Kajaani", "Kemi", "Tornio", "Iisalmi", "Varkaus", "Savonlinna", "Imatra",
    "Riihimaki", "Ylivieska", "Kuusamo", "Heinola", "Naantali", "Kaarina",
    "Loviisa", "Hanko", "Uusikaarlepyy", "Kristiinankaupunki", "Pietarsaari",
    "Maarianhamina", "Kankaanpaa", "Forssa", "Orimattila", "Laitila", "Kiuruvesi",
)

FINNISH_WATERS = (
    "Saimaa", "Paijanne", "Inari", "Pielinen", "Oulujarvi", "Kallavesi",
    "Keitele", "Nasi", "Pyhajarvi", "Lappajarvi", "Lokan", "Porttipahdan",
    "Kemijoki", "Tornionjoki", "Oulujoki", "Kymijoki", "Kokemaenjoki",
    "Vuoksi", "Tenojoki", "Iijoki", "Paatsjoki", "Kitkajoki", "Koitajoki",
    "Porvoonjoki", "Aurajoki", "Vantaanjoki", "Muonionjoki", "Siikajoki",
    "Lestijoki", "Kalajoki", "Kyronselka", "Haukivesi", "Vesijarvi", "Lohjanjarvi",
)


def _capitalize(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


def system_name(rng: random.Random) -> str:
    return rng.choice(FINNISH_CITIES)


def water_name(rng: random.Random) -> str:
    return rng.choice(FINNISH_WATERS)


def planet_name(rng: random.Random, system_name_str: str) -> str:
    if rng.random() < 0.2:
        return f"{system_name_str} {rng.randint(1, 4)}"
    base = rng.choice(SYLLABLES)
    suffix = rng.choice(("", "nen", "la", "maa"))
    return _capitalize(base) + suffix


def station_name(rng: random.Random, index: int) -> str:
    prefix = rng.choice(STATION_PREFIXES)
    return f"{prefix}-{index}"
