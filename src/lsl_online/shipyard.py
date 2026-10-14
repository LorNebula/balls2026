"""Playable ship hulls and fleet ship construction."""

from __future__ import annotations

from dataclasses import dataclass

from lsl_online.models import COMPONENT_KINDS, Ship, ShipComponent, ShipLocation


@dataclass(frozen=True)
class ShipType:
    id: str
    name: str
    price: int
    cargo_capacity: int
    component_health: float
    max_shield: float
    max_power: float
    visual_size: int
    component_slots: int


SHIP_TYPES = (
    ShipType("venture", "Venture", 0, 100, 100.0, 100.0, 100.0, 1, 4),
    ShipType("pioneer", "Pioneer", 6000, 150, 125.0, 120.0, 115.0, 2, 5),
    ShipType("courier", "Courier", 14000, 220, 150.0, 145.0, 130.0, 3, 6),
    ShipType("bulwark", "Bulwark", 27500, 300, 180.0, 175.0, 150.0, 4, 7),
    ShipType("leviathan", "Leviathan", 52500, 400, 215.0, 210.0, 180.0, 5, 8),
    ShipType("titan", "Titan", 92500, 550, 260.0, 255.0, 220.0, 6, 10),
)
SHIP_TYPES_BY_ID = {ship_type.id: ship_type for ship_type in SHIP_TYPES}


def build_ship(hull_id: str, location: ShipLocation, ship_id: str) -> Ship:
    ship_type = SHIP_TYPES_BY_ID[hull_id]
    components = [
        ShipComponent(
            slot_id=f"{index + 1:02d}",
            kind=kind,
            max_health=ship_type.component_health,
            health=ship_type.component_health,
        )
        for index, kind in enumerate(COMPONENT_KINDS)
    ]
    return Ship(
        name=ship_type.name,
        location=location,
        hull_id=ship_type.id,
        ship_id=ship_id,
        purchase_price=ship_type.price,
        cargo_capacity=ship_type.cargo_capacity,
        visual_size=ship_type.visual_size,
        max_slots=ship_type.component_slots,
        components=components,
        power=ship_type.max_power,
        max_power=ship_type.max_power,
        shield=ship_type.max_shield,
        max_shield=ship_type.max_shield,
    )