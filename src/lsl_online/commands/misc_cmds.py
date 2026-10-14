from __future__ import annotations

from lsl_online.commands.base import Command
from lsl_online.comms import list_messages
from lsl_online.events import QUIT_APP
from lsl_online.models import GameState
from lsl_online import quests
from lsl_online import tutorial


class QuitCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and (
            parts[0].lower() == "quit"
            or (parts[0].lower() == "exit" and len(parts) == 1)
        )

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        state.bus.emit(QUIT_APP)
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["quit"]


class ReadyCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("ready", "continue")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return tutorial.ack_ready(state)

    def completions(self, state: GameState) -> list[str]:
        if tutorial.tutorial_awaiting_ready(state):
            return ["ready", "continue"]
        return []

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if tutorial.tutorial_awaiting_ready(state):
            return [("I'm ready", "ready")]
        return []


class SkipTutorialCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "skip"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        if state.tutorial_step.value == "done":
            return "Tutorial is already complete."
        tutorial.skip_tutorial(state)
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["skip"] if state.tutorial_step.value != "done" else []

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        if state.tutorial_step.value != "done":
            return [("Skip tutorial", "skip")]
        return []


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
        lines = [
            "Keys: up/down = command history on the command line. "
            "Maps: galaxy, system, zoom in|out, path <system>, mark <system> <char> <color>. "
            "Travel: travel, jump (next hop if path set), dock, undock. "
            "Docked: market, hangar, cargo, repair, refuel, system, undock. "
            "Trade: buy <item> all, sell <item> all, upgrade, repair, refuel, "
            "script (edit), script run, script enable (60s cron), script status. "
            "Combat: lock, fire, cease. Mining: lock R#, mine, cease mine, radar. "
            "comms, quests, skip, quit",
        ]
        if tutorial.tutorial_awaiting_ready(state):
            lines.append("Tutorial: type ready (or continue) when you've read the briefing.")
        state.log(" ".join(lines))
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["help"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Help", "help")]
