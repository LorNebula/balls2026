from __future__ import annotations

from eve_ascii.commands.base import Command
from eve_ascii.comms import list_messages
from eve_ascii.events import OPEN_SHIP_UI
from eve_ascii.models import GameState
from eve_ascii import quests


class ShipCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("ship", "fit")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        state.bus.emit(OPEN_SHIP_UI)
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["ship"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Ship", "ship")]


class CommsCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("comms", "messages")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        for msg_line in list_messages(state):
            state.log(msg_line)
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["comms", "messages"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Comms", "comms")]


class QuestsCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "quests"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return quests.list_quests(state)

    def completions(self, state: GameState) -> list[str]:
        return ["quests"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Quests", "quests")]


class QuestCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "quest"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return quests.quest_status(state)
        if args[0].lower() == "start" and len(args) >= 2:
            return quests.start_quest(state, " ".join(args[1:]))
        if args[0].lower() in ("status", "active"):
            return quests.quest_status(state)
        return quests.start_quest(state, " ".join(args))

    def completions(self, state: GameState) -> list[str]:
        cmds = ["quest start ", "quest status"]
        if state.quests_unlocked:
            for q in state.quests:
                cmds.append(f"quest start {q.id}")
        return cmds


class HelpCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "help"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        state.log(
            "travel, jump, dock, inventory, sell <item> <qty>, upgrade reactor|weapons, "
            "lock, mine, cease, fire, radar, ship, comms, quests"
        )
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["help"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Help", "help")]
