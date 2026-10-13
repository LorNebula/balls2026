from __future__ import annotations

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.commands.base import Command
from eve_ascii import travel
from eve_ascii.models import GameState


class DockCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "dock"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        return travel.dock(state)

    def completions(self, state: GameState) -> list[str]:
        return ["dock"]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return []


class UndockCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "undock"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        state.station_view = "hangar"
        return travel.undock(state)


class JumpCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() in ("jump", "gate")

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return "Usage: jump <system>"
        return travel.jump_system(state, " ".join(args))

    def completions(self, state: GameState) -> list[str]:
        cmds = ["jump "]
        ship = state.player.ship
        sys = state.galaxy.get_system(ship.location.system_id)
        if sys:
            for nid in sys.neighbors:
                other = state.galaxy.get_system(nid)
                if other:
                    cmds.append(f"jump {ascii_only(other.name)}")
        return cmds

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        ship = state.player.ship
        sys = state.galaxy.get_system(ship.location.system_id)
        if sys:
            for nid in sys.neighbors:
                other = state.galaxy.get_system(nid)
                if other:
                    items.append((f"Jump to {other.name}", f"jump {other.name}"))
        return items


class TravelCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "travel"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
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

    def completions(self, state: GameState) -> list[str]:
        cmds = ["travel ", "travel planet ", "travel station "]
        ship = state.player.ship
        sys = state.galaxy.get_system(ship.location.system_id)
        if sys:
            for p in sys.planets:
                cmds.append(f"travel planet {ascii_only(p.name)}")
            for st in sys.stations:
                cmds.append(f"travel station {ascii_only(st.name)}")
        return cmds
