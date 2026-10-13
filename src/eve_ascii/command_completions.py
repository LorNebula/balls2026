"""Command-line completion candidates."""

from __future__ import annotations

from eve_ascii.commands.registry import completion_candidates as _completion_candidates
from eve_ascii.models import GameState


def completion_candidates(state: GameState) -> list[str]:
    return _completion_candidates(state)


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
