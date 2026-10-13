from __future__ import annotations

from lsl_online.commands.base import Command
from lsl_online import mining
from lsl_online.models import GameState
from lsl_online import radar


class MineCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "mine"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return mining.start_mining(state)

    def completions(self, state: GameState) -> list[str]:
        return ["mine"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Mine", "mine")]


class RadarCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "radar"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return radar.toggle_radar(state)
        arg = args[0].lower()
        if arg in ("on", "start"):
            return radar.set_radar(state, True)
        if arg in ("off", "stop"):
            return radar.set_radar(state, False)
        return radar.toggle_radar(state)

    def completions(self, state: GameState) -> list[str]:
        return ["radar", "radar on", "radar off"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Radar", "radar")]
