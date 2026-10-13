from __future__ import annotations

from lsl_online.commands.base import Command
from lsl_online.models import GameState


class GalaxyViewCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "galaxy"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        state.map_view = "galaxy"
        state.log("Map view: galaxy")
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["galaxy"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Galaxy view", "galaxy")]


class ZoomCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "zoom"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        if len(parts) != 2 or parts[1].lower() not in ("in", "out"):
            return "Usage: zoom in|out"
        zoom_in = parts[1].lower() == "in"
        if state.map_view == "galaxy":
            if zoom_in:
                state.galaxy_zoom = min(8.0, state.galaxy_zoom * 1.5)
            else:
                state.galaxy_zoom = max(0.05, state.galaxy_zoom / 1.5)
        else:
            if zoom_in:
                state.system_zoom = max(1.0, state.system_zoom - 0.25)
            else:
                state.system_zoom = min(8.0, state.system_zoom + 0.25)
        return None

    def completions(self, state: GameState) -> list[str]:
        return ["zoom in", "zoom out"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Zoom in", "zoom in"), ("Zoom out", "zoom out")]