from __future__ import annotations

from eve_ascii.commands.base import Command
from eve_ascii import combat, mining
from eve_ascii.models import GameState


class LockCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "lock"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return "Usage: lock <A-Z> [reactor|thrusters|shields|weapons|01-04]"
        sub = args[1] if len(args) > 1 else None
        return mining.lock_target_unified(state, args[0], sub)

    def completions(self, state: GameState) -> list[str]:
        cmds = ["lock "]
        for npc in state.npc_ships:
            if npc.alive:
                cmds.append(f"lock {npc.letter}")
                for comp in npc.components:
                    cmds.append(f"lock {npc.letter} {comp.kind}")
                    cmds.append(f"lock {npc.letter} {comp.slot_id}")
        for ast in state.asteroids:
            if ast.alive:
                cmds.append(f"lock {ast.code}")
        return cmds

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for npc in state.npc_ships:
            if npc.alive:
                items.append((f"Lock {npc.letter}", f"lock {npc.letter}"))
        for ast in state.asteroids:
            if ast.alive:
                items.append((f"Lock {ast.code}", f"lock {ast.code}"))
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
        if cmd == "stop" and len(parts) > 1 and parts[1].lower() in ("fire", "mine"):
            return True
        return False

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        mining.cease_mining(state)
        return combat.cease_fire(state)

    def completions(self, state: GameState) -> list[str]:
        return ["cease"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Cease fire", "cease")]
