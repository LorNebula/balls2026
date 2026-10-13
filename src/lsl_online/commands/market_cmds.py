from __future__ import annotations

from lsl_online.commands.base import Command
from lsl_online import market
from lsl_online.models import GameState
from lsl_online.shipyard import SHIP_TYPES


class InventoryCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("cargo", "inventory", "inv")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return market.show_cargo(state)

    def completions(self, state: GameState) -> list[str]:
        return ["cargo"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Cargo", "cargo")]


class MarketCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "market"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return market.show_market(state)

    def completions(self, state: GameState) -> list[str]:
        return ["market"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.player.ship.status.value == "docked":
            return [("Market", "market")]
        return []


class BuyShipCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return len(parts) >= 2 and parts[0].lower() == "buy" and parts[1].lower() == "ship"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        if len(parts) < 3:
            return "Usage: buy ship <hull>"
        return market.buy_ship(state, " ".join(parts[2:]))

    def completions(self, state: GameState) -> list[str]:
        commands = ["buy ship "]
        if state.player.ship.status.value == "docked":
            system = state.galaxy.get_system(state.player.ship.location.system_id)
            station = next(
                (item for item in system.stations if item.id == state.player.ship.location.station_id),
                None,
            ) if system else None
            if station:
                commands.extend(
                    f"buy ship {hull_id}"
                    for hull_id, quantity in station.hangar_inventory.items()
                    if quantity > 0
                )
        return commands

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.player.ship.status.value != "docked":
            return []
        system = state.galaxy.get_system(state.player.ship.location.system_id)
        station = next(
            (item for item in system.stations if item.id == state.player.ship.location.station_id),
            None,
        ) if system else None
        if not station:
            return []
        return [
            (f"Buy {hull.name}", f"buy ship {hull.id}")
            for hull in SHIP_TYPES
            if station.hangar_inventory.get(hull.id, 0) > 0
        ]


class SellShipCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return len(parts) >= 2 and parts[0].lower() == "sell" and parts[1].lower() == "ship"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        if len(parts) < 3:
            return "Usage: sell ship <id>"
        return market.sell_ship(state, " ".join(parts[2:]))

    def completions(self, state: GameState) -> list[str]:
        return ["sell ship "] + [f"sell ship {ship.ship_id}" for ship in state.player.fleet]


class SwitchShipCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return len(parts) >= 2 and parts[0].lower() in ("switch", "change") and parts[1].lower() == "ship"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        if len(parts) < 3:
            return "Usage: switch ship <id>"
        return market.switch_ship(state, " ".join(parts[2:]))

    def completions(self, state: GameState) -> list[str]:
        return ["switch ship "] + [f"switch ship {ship.ship_id}" for ship in state.player.fleet]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.player.ship.status.value != "docked":
            return []
        return [
            (f"Switch to {ship.name} ({ship.ship_id})", f"switch ship {ship.ship_id}")
            for ship in state.player.fleet
            if ship is not state.player.ship
        ]


class SystemViewCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("system", "map", "close", "exit")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        state.map_view = "system"
        return market.show_system_view(state)

    def completions(self, state: GameState) -> list[str]:
        return ["system", "close"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("System view", "system")]


class BuyCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "buy"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if len(args) < 2:
            return "Usage: buy <item|reactor|weapons> <quantity|all>"
        quantity_arg = args[-1].lower()
        item_ref = " ".join(args[:-1])
        if quantity_arg == "all":
            station = market._current_station(state)
            if not station:
                return "No market at this station."
            key = item_ref.strip().casefold()
            item_id = next(
                (
                    item
                    for item, label in market.ITEM_NAMES.items()
                    if item == key or label.casefold() == key
                ),
                None,
            )
            if not item_id or item_id not in station.inventory:
                return f"Item not sold here: {item_ref}."
            used = sum(c.quantity for c in state.player.cargo)
            space = state.player.max_cargo - used
            quantity = market.max_affordable_quantity(
                state, station, item_id, station.inventory[item_id], space
            )
            if quantity <= 0:
                return "Cannot buy any (stock, cargo space, or credits)."
        else:
            try:
                quantity = int(quantity_arg)
            except ValueError:
                return "Quantity must be an integer or all."
        return market.buy_item(state, item_ref, quantity)

    def completions(self, state: GameState) -> list[str]:
        cmds = ["buy "]
        if state.player.ship.status.value != "docked":
            return cmds
        sys = state.galaxy.get_system(state.player.ship.location.system_id)
        station = None
        if sys and state.player.ship.location.station_id:
            station = next(
                (st for st in sys.stations if st.id == state.player.ship.location.station_id),
                None,
            )
        if station:
            for item_id, quantity in station.inventory.items():
                if quantity > 0:
                    cmds.append(f"buy {item_id} ")
                    cmds.append(f"buy {item_id} all")
        return cmds


class HangarCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "hangar"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return market.show_hangar(state)

    def completions(self, state: GameState) -> list[str]:
        return ["hangar"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.player.ship.status.value == "docked":
            return [("Open hangar", "hangar")]
        return []


class SellCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "sell"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if len(args) < 2:
            return "Usage: sell <item> <quantity>"
        quantity_arg = args[-1].lower()
        if quantity_arg != "all":
            try:
                quantity: int | str = int(quantity_arg)
            except ValueError:
                return "Quantity must be an integer or all."
        else:
            quantity = "all"
        item_ref = " ".join(args[:-1])
        return market.sell_item(state, item_ref, quantity)

    def completions(self, state: GameState) -> list[str]:
        cmds = ["sell "]
        if state.player.ship.status.value == "docked":
            for stack in state.player.cargo:
                if stack.quantity > 0:
                    cmds.append(f"sell {stack.item_id} ")
                    cmds.append(f"sell {stack.name} ")
                    cmds.append(f"sell {stack.item_id} all")
        return cmds

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        if state.player.ship.status.value == "docked":
            for stack in state.player.cargo:
                if stack.quantity > 0:
                    items.append(
                        (f"Sell {stack.name}", f"sell {stack.item_id} {stack.quantity}"),
                    )
        return items


class RepairCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "repair"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return market.repair_ship(state)

    def completions(self, state: GameState) -> list[str]:
        return ["repair"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.player.ship.status.value == "docked":
            return [("Repair hull", "repair")]
        return []


class UpgradeCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "upgrade"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return "Usage: upgrade reactor|weapons"
        return market.upgrade_component(state, args[0])

    def completions(self, state: GameState) -> list[str]:
        return ["upgrade reactor", "upgrade weapons"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.player.ship.status.value == "docked":
            return [
                ("Upgrade reactor", "upgrade reactor"),
                ("Upgrade weapons", "upgrade weapons"),
            ]
        return []
