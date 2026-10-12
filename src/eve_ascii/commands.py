"""Parse and execute player commands."""

from __future__ import annotations

import shlex

from eve_ascii import combat, market, travel
from eve_ascii.comms import list_messages
from eve_ascii.models import GameState
from eve_ascii import quests


def execute_command(state: GameState, line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    try:
        parts = shlex.split(line)
    except ValueError as e:
        return str(e)
    if not parts:
        return None
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in ("dock",):
        return travel.dock(state)
    if cmd in ("undock",):
        state.station_view = "hangar"
        return travel.undock(state)
    if cmd in ("inventory", "inv", "market"):
        return market.show_inventory(state)
    if cmd == "hangar":
        return market.show_hangar(state)
    if cmd == "sell":
        if len(args) < 2:
            return "Usage: sell <item> <quantity>"
        try:
            qty = int(args[-1])
        except ValueError:
            return "Quantity must be an integer."
        item_ref = " ".join(args[:-1])
        return market.sell_item(state, item_ref, qty)
    if cmd == "upgrade":
        if not args:
            return "Usage: upgrade reactor|weapons"
        return market.upgrade_component(state, args[0])
    if cmd in ("jump", "gate"):
        if not args:
            return "Usage: jump <system>"
        return travel.jump_system(state, " ".join(args))
    if cmd == "travel":
        if not args:
            return "Usage: travel <x> <y> <z> | travel planet <name> | travel station <name>"
        if args[0].lower() == "planet":
            if len(args) < 2:
                return "Usage: travel planet <name>"
            return travel.travel_planet(state, " ".join(args[1:]))
        if args[0].lower() == "station":
            if len(args) < 2:
                return "Usage: travel station <name>"
            return travel.travel_station(state, " ".join(args[1:]))
        if len(args) >= 3:
            try:
                x, y, z = float(args[0]), float(args[1]), float(args[2])
            except ValueError:
                return "Coordinates must be numbers."
            return travel.travel_coords(state, x, y, z)
        return "Usage: travel <x> <y> <z> | travel planet <name> | travel station <name>"
    if cmd in ("ship", "fit"):
        return None
    if cmd == "lock":
        if not args:
            return "Usage: lock <A-Z> [reactor|thrusters|shields|weapons|01-04]"
        sub = args[1] if len(args) > 1 else None
        return combat.lock_target(state, args[0], sub)
    if cmd == "fire":
        return combat.start_fire(state)
    if cmd in ("cease", "stop") and args and args[0].lower() == "fire":
        return combat.cease_fire(state)
    if cmd == "cease":
        return combat.cease_fire(state)
    if cmd in ("comms", "messages"):
        for line in list_messages(state):
            state.log(line)
        return None
    if cmd == "quests":
        return quests.list_quests(state)
    if cmd == "quest":
        if not args:
            return quests.quest_status(state)
        if args[0].lower() == "start" and len(args) >= 2:
            return quests.start_quest(state, " ".join(args[1:]))
        if args[0].lower() in ("status", "active"):
            return quests.quest_status(state)
        return quests.start_quest(state, " ".join(args))
    if cmd == "help":
        state.log(
            "travel, jump, dock, inventory, sell <item> <qty>, upgrade reactor|weapons, "
            "lock, fire, cease, ship, comms, quests"
        )
        return None
    return f"Unknown command: {cmd}. Type help."


def palette_suggestions(state: GameState) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = [
        ("Help", "help"),
        ("Ship", "ship"),
        ("Fire", "fire"),
        ("Cease fire", "cease"),
        ("Comms", "comms"),
        ("Quests", "quests"),
    ]
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    for npc in state.npc_ships:
        if npc.alive:
            items.append((f"Lock {npc.letter}", f"lock {npc.letter}"))
    if sys:
        for nid in sys.neighbors:
            other = state.galaxy.get_system(nid)
            if other:
                items.append((f"Jump to {other.name}", f"jump {other.name}"))
    if ship.status.value == "docked":
        items.append(("Inventory", "inventory"))
        for stack in state.player.cargo:
            if stack.quantity > 0:
                items.append(
                    (f"Sell {stack.name}", f"sell {stack.item_id} {stack.quantity}"),
                )
        items.append(("Upgrade reactor", "upgrade reactor"))
        items.append(("Upgrade weapons", "upgrade weapons"))
    return items
