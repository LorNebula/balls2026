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
            return travel.jump_system(state, None)
        return travel.jump_system(state, " ".join(args))

    def completions(self, state: GameState) -> list[str]:
        cmds = ["jump"]
        ship = state.player.ship
        sys = state.galaxy.get_system(ship.location.system_id)
        neighbor_ids = set(sys.neighbors) if sys else set()
        neighbors: list[str] = []
        others: list[str] = []
        for system in state.galaxy.systems.values():
            line = f"jump {ascii_only(system.name)}"
            if system.id in neighbor_ids:
                neighbors.append(line)
            else:
                others.append(line)
        cmds.extend(sorted(neighbors, key=str.casefold))
        cmds.extend(sorted(others, key=str.casefold)[:12])
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
            return "Usage: travel <x> <y> | travel up|right|down|left <units> | travel planet|station <name>"
        if args[0].lower() == "planet":
            return "Planets removed from the map. Use travel station <name> instead."
        if args[0].lower() == "station":
            if len(args) < 2:
                return "Usage: travel station <name>"
            return travel.travel_station(state, " ".join(args[1:]))
        direction = args[0].lower()
        if direction in ("up", "right", "down", "left"):
            if len(args) != 2:
                return "Usage: travel up|right|down|left <units>"
            try:
                units = float(args[1])
            except ValueError:
                return "Travel distance must be a number."
            return travel.travel_direction(state, direction, units)
        if len(args) == 2:
            try:
                x, y = float(args[0]), float(args[1])
            except ValueError:
                return "Coordinates must be numbers."
            return travel.travel_coords(state, x, y)
        return "Usage: travel <x> <y> | travel up|right|down|left <units> | travel planet|station <name>"

    def completions(self, state: GameState) -> list[str]:
        cmds = [
            "travel ",
            "travel up ",
            "travel right ",
            "travel down ",
            "travel left ",
            "travel planet ",
            "travel station ",
        ]
        ship = state.player.ship
        sys = state.galaxy.get_system(ship.location.system_id)
        if sys:
            for p in sys.planets:
                cmds.append(f"travel planet {ascii_only(p.name)}")
            for st in sys.stations:
                cmds.append(f"travel station {ascii_only(st.name)}")
        return cmds
