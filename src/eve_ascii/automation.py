"""Player automation hooks (stub for hackathon follow-up).

Later: sandboxed Python snippets, e.g. `if cargo > 500: dock()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from eve_ascii.models import GameState


@dataclass
class Rule:
    name: str
    source: str
    enabled: bool = True


def run_player_snippet(state: GameState, source: str) -> str | None:
    """Execute player code against game state. Not implemented in travel MVP."""
    _ = (state, source)
    return "Automation sandbox not enabled yet."


def list_rules() -> list[Rule]:
    return []


def register_tick_hook(_callback: Callable[[GameState], None]) -> None:
    """Register a hook to run each game tick."""
    pass
