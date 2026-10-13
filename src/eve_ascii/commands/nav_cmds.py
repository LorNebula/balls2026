from __future__ import annotations

from collections import deque

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.commands.base import Command
from eve_ascii.galaxy import find_system_by_name
from eve_ascii.models import GameState


MARK_COLORS = {
    "red": "#ff5566",
    "green": "#66ff88",
    "blue": "#88aaff",
    "yellow": "#ffee66",
    "cyan": "#00e5ff",
    "magenta": "#cc88ff",
    "white": "#ffffff",
}


def _bfs_path(state: GameState, goal_id: str) -> list[str] | None:
    start_id = state.player.ship.location.system_id
    if start_id == goal_id:
        return []
    prev: dict[str, str | None] = {start_id: None}
    queue: deque[str] = deque([start_id])
    while queue:
        current = queue.popleft()
        sys = state.galaxy.get_system(current)
        if not sys:
            continue
        for nid in sys.neighbors:
            if nid in prev:
                continue
            prev[nid] = current
            if nid == goal_id:
                hops: list[str] = []
                walk: str | None = goal_id
                while walk is not None:
                    hops.append(walk)
                    walk = prev[walk]
                hops.reverse()
                return hops[1:]
            queue.append(nid)
    return None


class PathCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "path"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return "Usage: path <system> | path clear"
        if args[0].lower() == "clear":
            state.nav_path.clear()
            state.nav_path_goal = None
            state.log("Navigation path cleared.")
            return None
        dest = find_system_by_name(state.galaxy, " ".join(args))
        if not dest:
            return f"System not found: {' '.join(args)}"
        hops = _bfs_path(state, dest.id)
        if hops is None:
            state.nav_path.clear()
            state.nav_path_goal = None
            return f"No stargate route to {dest.name}."
        state.nav_path = hops
        state.nav_path_goal = dest.id
        names = [
            ascii_only(state.galaxy.get_system(sid).name)
            for sid in hops
            if state.galaxy.get_system(sid)
        ]
        state.log(f"Path to {dest.name}: {' -> '.join(names)} ({len(hops)} jump(s)).")
        state.log("Type jump to jump to the next system on this path.")
        return None

    def completions(self, state: GameState) -> list[str]:
        cmds = ["path ", "path clear"]
        for system in state.galaxy.systems.values():
            cmds.append(f"path {ascii_only(system.name)}")
        return cmds

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Plot path", "path ")]


class MarkCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "mark"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = parts[1:]
        if not args:
            return "Usage: mark <system> <char> <color> | mark clear <system> | mark list"
        if args[0].lower() == "list":
            if not state.user_markers:
                state.log("No custom markers.")
                return None
            for sid, (ch, color) in state.user_markers.items():
                sys = state.galaxy.get_system(sid)
                name = ascii_only(sys.name) if sys else sid
                state.log(f"  {name}: '{ch}' ({color})")
            return None
        if args[0].lower() == "clear":
            if len(args) < 2:
                return "Usage: mark clear <system>"
            dest = find_system_by_name(state.galaxy, " ".join(args[1:]))
            if not dest:
                return f"System not found: {' '.join(args[1:])}"
            state.user_markers.pop(dest.id, None)
            state.log(f"Marker cleared for {dest.name}.")
            return None
        if len(args) < 3:
            return "Usage: mark <system> <char> <color>"
        color_key = args[-1].lower()
        char = args[-2]
        if len(char) != 1 or not char.isprintable():
            return "Marker char must be a single printable ASCII character."
        if color_key not in MARK_COLORS:
            return f"Unknown color. Use: {', '.join(sorted(MARK_COLORS))}"
        system_name = " ".join(args[:-2])
        dest = find_system_by_name(state.galaxy, system_name)
        if not dest:
            return f"System not found: {system_name}"
        state.user_markers[dest.id] = (char, color_key)
        state.log(f"Marked {dest.name} with '{char}' ({color_key}).")
        return None

    def completions(self, state: GameState) -> list[str]:
        cmds = ["mark list", "mark clear "]
        for color in sorted(MARK_COLORS):
            cmds.append(f"mark * {color}")
        return cmds

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [("Mark system", "mark ")]
