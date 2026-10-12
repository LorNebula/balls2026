"""Command-line completion candidates."""

from __future__ import annotations

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.models import GameState


def completion_candidates(state: GameState) -> list[str]:
    cmds = [
        "help",
        "ship",
        "fire",
        "cease",
        "comms",
        "messages",
        "quests",
        "quest start ",
        "quest status",
        "lock ",
        "travel ",
        "travel planet ",
        "travel station ",
        "jump ",
    ]
    for npc in state.npc_ships:
        if npc.alive:
            cmds.append(f"lock {npc.letter}")
            for comp in npc.components:
                cmds.append(f"lock {npc.letter} {comp.kind}")
                cmds.append(f"lock {npc.letter} {comp.slot_id}")
    if state.quests_unlocked:
        for q in state.quests:
            cmds.append(f"quest start {q.id}")
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
    return cmds


def matching_completions(state: GameState, partial: str, limit: int = 5) -> list[str]:
    text = partial.strip()
    if not text:
        return completion_candidates(state)[:limit]
    key = text.casefold()
    hits = [c for c in completion_candidates(state) if c.casefold().startswith(key)]
    if hits:
        return hits[:limit]
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
