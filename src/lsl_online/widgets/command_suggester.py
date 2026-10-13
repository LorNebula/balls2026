from __future__ import annotations

from typing import Callable

from textual.suggester import Suggester

from lsl_online.models import GameState


class GameCommandSuggester(Suggester):
    """Prefix completion for game commands."""

    def __init__(self, get_state: Callable[[], GameState]) -> None:
        super().__init__(case_sensitive=False)
        self._get_state = get_state

    async def get_suggestion(self, value: str) -> str | None:
        from lsl_online.command_completions import best_completion

        return best_completion(self._get_state(), value)
