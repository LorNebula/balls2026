"""Mineable materials catalog (15 ores)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    id: str
    name: str
    base_price: float
    rarity: int  # 1=common .. 5=rare


MATERIALS: tuple[Material, ...] = (
    Material("veldspar", "Veldspar", 12.0, 1),
    Material("scordite", "Scordite", 18.0, 1),
    Material("pyroxeres", "Pyroxeres", 28.0, 2),
    Material("plagioclase", "Plagioclase", 32.0, 2),
    Material("omber", "Omber", 45.0, 2),
    Material("kernite", "Kernite", 58.0, 3),
    Material("jaspet", "Jaspet", 72.0, 3),
    Material("hemorphite", "Hemorphite", 88.0, 3),
    Material("hedbergite", "Hedbergite", 105.0, 4),
    Material("gneiss", "Gneiss", 120.0, 4),
    Material("dark_ochre", "Dark Ochre", 145.0, 4),
    Material("crokite", "Crokite", 175.0, 5),
    Material("bistot", "Bistot", 210.0, 5),
    Material("arkonor", "Arkonor", 260.0, 5),
    Material("mercoxit", "Mercoxit", 320.0, 5),
)

_BY_ID: dict[str, Material] = {m.id: m for m in MATERIALS}


def all_materials() -> tuple[Material, ...]:
    return MATERIALS


def material_by_id(material_id: str) -> Material | None:
    return _BY_ID.get(material_id)


def base_prices_map() -> dict[str, float]:
    return {m.id: m.base_price for m in MATERIALS}
