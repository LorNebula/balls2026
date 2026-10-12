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

CURATED_SYSTEMS = (
    "Aurinko",
    "Pohjantähti",
    "Valojärvi",
    "Kivijärvi",
    "Lumimaa",
    "Merenranta",
    "Havumetsä",
    "Usvalahti",
)


def _capitalize(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


def system_name(rng: random.Random) -> str:
    if rng.random() < 0.15:
        return rng.choice(CURATED_SYSTEMS)
    parts = rng.randint(1, 2)
    name = "".join(_capitalize(rng.choice(SYLLABLES)) for _ in range(parts))
    if rng.random() < 0.6:
        name += rng.choice(SUFFIXES)
    return name


def planet_name(rng: random.Random, system_name_str: str) -> str:
    if rng.random() < 0.2:
        return f"{system_name_str} {rng.randint(1, 4)}"
    base = rng.choice(SYLLABLES)
    suffix = rng.choice(("", "nen", "la", "maa"))
    return _capitalize(base) + suffix


def station_name(rng: random.Random, index: int) -> str:
    prefix = rng.choice(STATION_PREFIXES)
    return f"{prefix}-{index}"
