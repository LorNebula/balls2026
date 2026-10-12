"""Command-line completion candidates."""

from __future__ import annotations

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.models import GameState


def completion_candidates(state: GameState) -> list[str]:
    cmds = [
        "dock",
        "undock",
        "help",
        "travel ",
        "travel planet ",
        "travel station ",
        "jump ",
    ]
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    if sys:
        for p in sys.planets:
            cmds.append(f"travel planet {ascii_only(p.name)}")
        for st in sys.stations:
            cmds.append(f"travel station {ascii_only(st.name)}")
        for nid in sys.neighbors:
            other = state.galaxy.get_system(nid)
            if other:
                cmds.append(f"jump {ascii_only(other.name)}")
    for s in state.galaxy.systems.values():
        if sys and s.id == sys.id:
            continue
        cmds.append(f"jump {ascii_only(s.name)}")
    return cmds


def matching_completions(state: GameState, partial: str, limit: int = 5) -> list[str]:
    text = partial.strip()
    if not text:
        return completion_candidates(state)[:limit]
    key = text.casefold()
    hits = [c for c in completion_candidates(state) if c.casefold().startswith(key)]
    if hits:
        return hits[:limit]
    # Match any token prefix (e.g. "planet Kiv" -> travel planet Kivi...)
    hits = [c for c in completion_candidates(state) if key in c.casefold()]
    return hits[:limit]


def best_completion(state: GameState, partial: str) -> str | None:
    text = partial.strip()
    if not text:
        return None
    matches = matching_completions(state, text, limit=1)
    if not matches:
        return None
    candidate = matches[0]
    if candidate.casefold() == text.casefold():
        return None
    return candidate
