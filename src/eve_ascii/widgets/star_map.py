from __future__ import annotations

from textual.widgets import Static

from eve_ascii.models import GameMode, GameState, ShipStatus
from eve_ascii.market import render_inventory_view
from eve_ascii.space_render import render_docked_view, render_galaxy_map, render_open_space


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
        self._sync_ambient_classes(state)
        self.refresh_map()

    def _sync_ambient_classes(self, state: GameState) -> None:
        self.remove_class("-hyperspace", "-docked", "-flash", "-space")
        ship = state.player.ship
        if state.screen_flash > 0:
            self.add_class("-flash")
        elif ship.status == ShipStatus.DOCKED:
            self.add_class("-docked")
        elif state.mode == GameMode.HYPERSPACE:
            self.add_class("-hyperspace")
        else:
            self.add_class("-space")

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
        ship = self._state.player.ship
        if self._galaxy_view:
            self.update(render_galaxy_map(self._state, w, h))
        elif ship.status == ShipStatus.DOCKED:
            if self._state.station_view == "inventory":
                self.update(render_inventory_view(self._state, w, h))
            else:
                self.update(render_docked_view(self._state, w, h))
        elif self._state.mode == GameMode.HYPERSPACE:
            self.update(render_open_space(self._state, w, h, self._scale, hyperspace=True))
        else:
            self.update(render_open_space(self._state, w, h, self._scale, hyperspace=False))
