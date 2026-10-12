"""Parse and execute player commands."""

from __future__ import annotations

import shlex

from eve_ascii.models import GameState
from eve_ascii import travel


def execute_command(state: GameState, line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    try:
        parts = shlex.split(line)
    except ValueError as e:
        return str(e)
    if not parts:
        return None
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in ("dock",):
        return travel.dock(state)
    if cmd in ("undock",):
        return travel.undock(state)
    if cmd in ("jump", "gate"):
        if not args:
            return "Usage: jump <system>"
        return travel.jump_system(state, " ".join(args))
    if cmd == "travel":
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
    if cmd == "help":
        return None
    return f"Unknown command: {cmd}. Try dock, undock, travel, jump."


def palette_suggestions(state: GameState) -> list[tuple[str, str]]:
    """Return (label, command string) for command palette."""
    items: list[tuple[str, str]] = [
        ("Dock", "dock"),
        ("Undock", "undock"),
        ("Help", "help"),
    ]
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    if sys:
        for p in sys.planets:
            items.append((f"Orbit {p.name}", f"travel planet {p.name}"))
        for st in sys.stations:
            items.append((f"Warp to {st.name}", f"travel station {st.name}"))
        for nid in sys.neighbors:
            other = state.galaxy.get_system(nid)
            if other:
                items.append((f"Jump to {other.name}", f"jump {other.name}"))
    for s in state.galaxy.systems.values():
        if sys and s.id != sys.id:
            items.append((f"Jump to {s.name}", f"jump {s.name}"))
    return items
