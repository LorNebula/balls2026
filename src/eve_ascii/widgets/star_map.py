from __future__ import annotations

from textual.widgets import Static

from eve_ascii.models import GameMode, GameState
from eve_ascii.space_render import render_galaxy_map, render_open_space


class StarMap(Static):
    """Open-space ASCII view with colored ship shapes."""

    DEFAULT_CSS = """
    StarMap {
        width: 2fr;
        height: 1fr;
        border: none;
        padding: 0 1;
        background: #050d18;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", markup=True, **kwargs)
        self._state: GameState | None = None
        self._galaxy_view = False
        self._scale = 4.0

    def update_map(self, state: GameState, *, galaxy_view: bool) -> None:
        self._state = state
        if state.tutorial_force_galaxy:
            galaxy_view = True
        self._galaxy_view = galaxy_view
        self.refresh_map()

    @property
    def galaxy_view(self) -> bool:
        return self._galaxy_view

    def pan(self, dx: float, dy: float) -> None:
        self._scale = max(1.0, min(8.0, self._scale + dx * 0.01))

    def zoom(self, delta: float) -> None:
        self._scale = max(1.0, min(8.0, self._scale + delta))

    def _view_size(self) -> tuple[int, int]:
        w = self.size.width if self.size.width else 100
        h = self.size.height if self.size.height else 24
        return max(60, w - 2), max(18, h - 1)

    def refresh_map(self) -> None:
        if not self._state:
            self.update("No galaxy loaded.")
            return
        w, h = self._view_size()
        if self._galaxy_view:
            self.update(render_galaxy_map(self._state, w, h))
        elif self._state.mode == GameMode.HYPERSPACE:
            self.update(render_open_space(self._state, w, h, self._scale, hyperspace=True))
        else:
            self.update(render_open_space(self._state, w, h, self._scale, hyperspace=False))
