from __future__ import annotations

from eve_ascii.commands.base import Command
from eve_ascii import market
from eve_ascii.models import GameState


class InventoryCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("inventory", "inv", "market")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return market.show_inventory(state)

    def completions(self, state: GameState) -> list[str]:
        return ["inventory"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.player.ship.status.value == "docked":
            return [("Inventory", "inventory")]
        return []


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
        try:
            qty = int(args[-1])
        except ValueError:
            return "Quantity must be an integer."
        item_ref = " ".join(args[:-1])
        return market.sell_item(state, item_ref, qty)

    def completions(self, state: GameState) -> list[str]:
        cmds = ["sell "]
        if state.player.ship.status.value == "docked":
            for stack in state.player.cargo:
                if stack.quantity > 0:
                    cmds.append(f"sell {stack.item_id} ")
                    cmds.append(f"sell {stack.name} ")
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
