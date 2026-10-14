"""Command-line completion candidates."""

from __future__ import annotations

from lsl_online.commands.registry import completion_candidates as _completion_candidates
from lsl_online.models import GameState, ShipStatus


def completion_candidates(state: GameState) -> list[str]:
    return _completion_candidates(state)


def _contextual_empty_completions(state: GameState, limit: int = 5) -> list[str]:
    ship = state.player.ship
    if ship.status == ShipStatus.DOCKED:
        return ["market", "hangar", "cargo", "repair", "system"][:limit]
    if state.map_view == "galaxy":
        return ["galaxy", "system", "path ", "mark ", "zoom in"][:limit]
    return ["travel", "radar", "lock", "mine", "jump"][:limit]


def _sort_jump_completions(state: GameState, hits: list[str]) -> list[str]:
    if not hits or not hits[0].casefold().startswith("jump "):
        return hits
    sys = state.galaxy.get_system(state.player.ship.location.system_id)
    neighbor_ids = set(sys.neighbors) if sys else set()
    neighbor_hits: list[str] = []
    other_hits: list[str] = []
    for hit in hits:
        name_part = hit[5:].strip().casefold()
        matched = False
        for system in state.galaxy.systems.values():
            if system.id in neighbor_ids and (
                system.name.casefold() == name_part
                or system.name.casefold().startswith(name_part)
            ):
                neighbor_hits.append(hit)
                matched = True
                break
        if not matched:
            other_hits.append(hit)
    return neighbor_hits + other_hits


def matching_completions(state: GameState, partial: str, limit: int = 5) -> list[str]:
    text = partial.strip()
    if not text:
        return _contextual_empty_completions(state, limit)
    key = text.casefold()
    hits = [c for c in completion_candidates(state) if c.casefold().startswith(key)]
    if hits:
        hits = _sort_jump_completions(state, hits)
        return hits[:limit]
    hits = [c for c in completion_candidates(state) if key in c.casefold()]
    hits = _sort_jump_completions(state, hits)
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
