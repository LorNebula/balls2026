from __future__ import annotations

from eve_ascii.commands.base import Command
from eve_ascii import combat
from eve_ascii.models import GameState


class LockCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "lock"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return "Usage: lock <A-Z> [reactor|thrusters|shields|weapons|01-04]"
        sub = args[1] if len(args) > 1 else None
        return combat.lock_target(state, args[0], sub)

    def completions(self, state: GameState) -> list[str]:
        cmds = ["lock "]
        for npc in state.npc_ships:
            if npc.alive:
                cmds.append(f"lock {npc.letter}")
                for comp in npc.components:
                    cmds.append(f"lock {npc.letter} {comp.kind}")
                    cmds.append(f"lock {npc.letter} {comp.slot_id}")
        return cmds

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for npc in state.npc_ships:
            if npc.alive:
                items.append((f"Lock {npc.letter}", f"lock {npc.letter}"))
        return items


class FireCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "fire"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return combat.start_fire(state)

    def completions(self, state: GameState) -> list[str]:
        return ["fire"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Fire", "fire")]


class CeaseCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        if not parts:
            return False
        cmd = parts[0].lower()
        if cmd == "cease":
            return True
        return cmd == "stop" and len(parts) > 1 and parts[1].lower() == "fire"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return combat.cease_fire(state)

    def completions(self, state: GameState) -> list[str]:
        return ["cease"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Cease fire", "cease")]
