"""Ship fit: components, power, shields, weapon charge."""

from __future__ import annotations

from eve_ascii.models import (
    COMPONENT_ALIASES,
    GameState,
    NpcShip,
    Ship,
    ShipComponent,
)

BASE_WEAPON_CHARGE = 0.35
BASE_SHIELD_GEN = 12.0


def find_component(components: list[ShipComponent], ref: str) -> ShipComponent | None:
    key = ref.lower().strip()
    if key.isdigit():
        key = key.zfill(2)
    for c in components:
        if c.slot_id.lower() == key:
            return c
    kind = COMPONENT_ALIASES.get(key)
    if not kind:
        return None
    for c in components:
        if c.kind == kind:
            return c
    return None


def kind_integrity(components: list[ShipComponent], kind: str) -> float:
    parts = [c for c in components if c.kind == kind]
    if not parts:
        return 0.0
    return sum(c.integrity for c in parts) / len(parts)


def is_powerless(obj: Ship | NpcShip) -> bool:
    return kind_integrity(obj.components, "reactor") <= 0.0


def weapons_online(obj: Ship | NpcShip) -> bool:
    if is_powerless(obj):
        return False
    return kind_integrity(obj.components, "weapons") > 0.0


def weapon_charge_seconds(obj: Ship | NpcShip) -> float:
    integ = kind_integrity(obj.components, "weapons")
    if integ <= 0.0 or is_powerless(obj):
        return 999.0
    return BASE_WEAPON_CHARGE / integ


def shield_gen_per_sec(obj: Ship | NpcShip) -> float:
    if is_powerless(obj):
        return 0.0
    return BASE_SHIELD_GEN * kind_integrity(obj.components, "shields")


def tick_systems(obj: Ship | NpcShip, dt: float) -> None:
    obj.power = obj.max_power * kind_integrity(obj.components, "reactor")
    if kind_integrity(obj.components, "shields") <= 0.0:
        obj.shield = 0.0
        return
    gen = shield_gen_per_sec(obj)
    obj.shield = min(obj.max_shield, obj.shield + gen * dt)


def tick_all(state: GameState, dt: float) -> None:
    tick_systems(state.player.ship, dt)
    for npc in state.npc_ships:
        if npc.alive:
            tick_systems(npc, dt)


def pirate_components() -> list[ShipComponent]:
    return [
        ShipComponent("01", "reactor", health=45.0),
        ShipComponent("02", "thrusters", health=40.0),
        ShipComponent("03", "shields", health=40.0),
        ShipComponent("04", "weapons", health=35.0),
    ]
