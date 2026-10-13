"""Base class for player commands."""

from __future__ import annotations

from abc import ABC, abstractmethod

from eve_ascii.models import GameState


class Command(ABC):
    @abstractmethod
    def matches(self, parts: list[str]) -> bool:
        """Return True if this command should handle the parsed input."""

    @abstractmethod
    def execute(self, state: GameState, parts: list[str]) -> str | None:
        """Run the command; return an error message or None on success."""

    def completions(self, state: GameState) -> list[str]:
        return []

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return []
