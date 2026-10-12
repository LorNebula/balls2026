from __future__ import annotations

from textual.widgets import Static

from eve_ascii.ascii_ui import ascii_only, box_wrap
from eve_ascii.galaxy import planet_position, station_position
from eve_ascii.models import GameState


class StarMap(Static):
    """ASCII map: system view or galaxy overview."""

    DEFAULT_CSS = """
    StarMap {
        width: 1fr;
        height: 1fr;
        border: none;
        padding: 0 0;
    }
    """

    MAP_WIDTH = 70

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._state: GameState | None = None
        self._galaxy_view = False
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._scale = 2.0

    def update_map(self, state: GameState, *, galaxy_view: bool) -> None:
        """Refresh map content (not Textual's Widget.render)."""
        self._state = state
        self._galaxy_view = galaxy_view
        self.refresh_map()

    @property
    def galaxy_view(self) -> bool:
        return self._galaxy_view

    def pan(self, dx: float, dy: float) -> None:
        self._pan_x += dx
        self._pan_y += dy
        self.refresh_map()

    def zoom(self, delta: float) -> None:
        self._scale = max(0.5, min(8.0, self._scale + delta))
        self.refresh_map()

    def refresh_map(self) -> None:
        if not self._state:
            self.update("No galaxy loaded.")
            return
        if self._galaxy_view:
            self.update(self._render_galaxy())
        else:
            self.update(self._render_system())

    def _project(self, x: float, y: float, width: int, height: int) -> tuple[int, int] | None:
        cx = width // 2 + int(self._pan_x)
        cy = height // 2 + int(self._pan_y)
        px = cx + int(x / self._scale)
        py = cy + int(y / self._scale)
        if 0 <= px < width and 0 <= py < height:
            return px, py
        return None

    def _blank_grid(self, w: int, h: int) -> list[list[str]]:
        return [["." for _ in range(w)] for _ in range(h)]

    def _plot(self, grid: list[list[str]], x: int, y: int, ch: str) -> None:
        if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
            grid[y][x] = ch

    def _render_system(self) -> str:
        state = self._state
        assert state
        ship = state.player.ship
        sys = state.galaxy.get_system(ship.location.system_id)
        if not sys:
            return "System missing."

        w, h = self.MAP_WIDTH - 2, 20
        grid = self._blank_grid(w, h)
        self._plot(grid, w // 2, h // 2, "*")

        for p in sys.planets:
            pos = planet_position(p)
            pt = self._project(pos.x, pos.y, w, h)
            if pt:
                self._plot(grid, pt[0], pt[1], "o")

        for st in sys.stations:
            pos = station_position(sys, st)
            pt = self._project(pos.x, pos.y, w, h)
            if pt:
                self._plot(grid, pt[0], pt[1], "S")

        from eve_ascii.travel import current_ship_coords

        sc = current_ship_coords(state)
        pt = self._project(sc.x, sc.y, w, h)
        if pt:
            self._plot(grid, pt[0], pt[1], "@")

        if ship.destination and ship.destination.coords:
            dp = ship.destination.coords
            pt = self._project(dp.x, dp.y, w, h)
            if pt:
                self._plot(grid, pt[0], pt[1], "X")

        lines = ["".join(row) for row in grid]
        title = ascii_only(sys.name)
        meta = f"ship={ship.status.value}"
        if ship.eta_seconds > 0:
            meta += f" eta={ship.eta_seconds:.1f}s"
        legend = "* sun  o planet  S station  @ you  X target"
        return box_wrap(self.MAP_WIDTH, f"SYSTEM {title} | {meta}", [legend, *lines])

    def _render_galaxy(self) -> str:
        state = self._state
        assert state
        ship = state.player.ship
        cur = state.galaxy.get_system(ship.location.system_id)
        w, h = self.MAP_WIDTH - 2, 20
        grid = self._blank_grid(w, h)

        if not state.galaxy.systems:
            return "Empty galaxy."

        xs = [s.position.x for s in state.galaxy.systems.values()]
        ys = [s.position.y for s in state.galaxy.systems.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        pad = 2

        def gal_pt(sx: float, sy: float) -> tuple[int, int]:
            gx = pad + int((sx - min_x) / span_x * (w - 2 * pad - 1))
            gy = pad + int((sy - min_y) / span_y * (h - 2 * pad - 1))
            return gx, gy

        for s in state.galaxy.systems.values():
            gx, gy = gal_pt(s.position.x, s.position.y)
            ch = "+" if s.neighbors else "*"
            if cur and s.id == cur.id:
                ch = "@"
            self._plot(grid, gx, gy, ch)

        lines = ["".join(row) for row in grid]
        legend = "GALAXY  + linked  * system  @ you  [g] system view"
        return box_wrap(self.MAP_WIDTH, "GALAXY", [legend, *lines])
