"""Ship fit: components, power bar, shields, weapon charge."""

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
BASE_MAX_POWER = 100.0
BASE_POWER_GEN = 20.0
SHIELD_POWER_PER_SEC = 5.0
WEAPON_RECHARGE_POWER_PER_SEC = 6.0
WEAPON_FIRE_COST = 4.0


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


def reactor_factor(obj: Ship | NpcShip) -> float:
    return kind_integrity(obj.components, "reactor")


def is_powerless(obj: Ship | NpcShip) -> bool:
    return reactor_factor(obj) <= 0.0


def reactor_max_power(obj: Ship | NpcShip) -> float:
    return BASE_MAX_POWER * reactor_factor(obj)


def power_gen_per_sec(obj: Ship | NpcShip) -> float:
    return BASE_POWER_GEN * reactor_factor(obj)


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


def spend_power(obj: Ship | NpcShip, amount: float) -> bool:
    if amount <= 0:
        return True
    if obj.power + 1e-9 < amount:
        return False
    obj.power -= amount
    return True


def meter(current: float, maximum: float, width: int = 16) -> str:
    if maximum <= 0:
        return "[" + "-" * width + "]"
    frac = max(0.0, min(1.0, current / maximum))
    filled = int(round(frac * width))
    filled = min(width, max(0, filled))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def tick_systems(obj: Ship | NpcShip, dt: float) -> None:
    obj.max_power = reactor_max_power(obj)
    if obj.max_power <= 0:
        obj.power = 0.0
        if kind_integrity(obj.components, "shields") <= 0.0:
            obj.shield = 0.0
        return
    obj.power = min(obj.max_power, obj.power + power_gen_per_sec(obj) * dt)

    if kind_integrity(obj.components, "shields") <= 0.0:
        obj.shield = 0.0
        return
    if obj.shield >= obj.max_shield:
        return
    cost = SHIELD_POWER_PER_SEC * dt
    if spend_power(obj, cost):
        obj.shield = min(obj.max_shield, obj.shield + shield_gen_per_sec(obj) * dt)


def tick_weapon_recharge(obj: Ship, dt: float) -> bool:
    """Spend power to count down weapon charge. False if starved."""
    if obj.fire_cooldown <= 0:
        return True
    if not weapons_online(obj):
        return False
    cost = WEAPON_RECHARGE_POWER_PER_SEC * dt
    if not spend_power(obj, cost):
        return False
    obj.fire_cooldown = max(0.0, obj.fire_cooldown - dt)
    return True


def try_fire_shot(obj: Ship) -> bool:
    if not weapons_online(obj):
        return False
    if obj.fire_cooldown > 0:
        return False
    return spend_power(obj, WEAPON_FIRE_COST)


def tick_all(state: GameState, dt: float) -> None:
    tick_systems(state.player.ship, dt)
    for npc in state.npc_ships:
        if npc.alive:
            tick_systems(npc, dt)


def pirate_components() -> list[ShipComponent]:
    return [
        ShipComponent("01", "reactor", max_health=75.0, health=75.0),
        ShipComponent("02", "thrusters", max_health=70.0, health=70.0),
        ShipComponent("03", "shields", max_health=70.0, health=70.0),
        ShipComponent("04", "weapons", max_health=65.0, health=65.0),
    ]
