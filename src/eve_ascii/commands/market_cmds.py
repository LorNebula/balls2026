from __future__ import annotations

from eve_ascii.commands.base import Command
from eve_ascii import market
from eve_ascii.models import GameState


class InventoryCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("cargo", "inventory", "inv")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return market.show_cargo(state)

    def completions(self, state: GameState) -> list[str]:
        return ["cargo", "inventory"]

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
            return "Usage: buy <item|reactor|weapons> <quantity>"
        try:
            quantity = int(args[-1])
        except ValueError:
            return "Quantity must be an integer."
        return market.buy_item(state, " ".join(args[:-1]), quantity)

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
        return cmds


class HangarCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "hangar"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return market.show_hangar(state)

    def completions(self, state: GameState) -> list[str]:
        return ["hangar"]


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
