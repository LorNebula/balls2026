"""Open-space ASCII rendering with Rich color (not a dot grid)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from rich.style import Style
from rich.text import Text

from eve_ascii.galaxy import planet_position, station_position
from eve_ascii.models import GameMode, GameState, NpcShip, Ship

SPACE_BG = Style(color="#1a3a5c", bgcolor="#050d18")
STAR_STYLE = Style(color="#6a8aaa")
SUN_STYLE = Style(color="#ffcc33", bold=True)
PLANET_STYLE = Style(color="#44cc88")
STATION_STYLE = Style(color="#88aaff")
STATION_ACCENT = Style(color="#cce0ff", bold=True)
HULL_PLAYER = Style(color="#00e5ff", bold=True)
HULL_ENEMY = Style(color="#ff5566", bold=True)
COMP_STYLE = Style(color="#ffee00", bold=True, bgcolor="#223344")
COMP_HIT = Style(color="#ff4400", bold=True, bgcolor="#442200")
ID_STYLE = Style(color="#ffffff", bold=True)
LASER_STYLE = Style(color="#66ff66", bold=True)
EXPLOSION_STYLE = Style(color="#ffaa00", bold=True)
PARTICLE_STYLES = (
    Style(color="#446688"),
    Style(color="#6688aa"),
    Style(color="#8866cc"),
)

# 01=reactor 02=shield 03=hyperdrive 04=cargo (embedded in art)
PLAYER_SHIP = [
    "        ______        ",
    "       /  01  \\       ",
    "  >====|02||03|====>  ",
    "       \\  04  /       ",
    "        ------        ",
]

ENEMY_SHIP = [
    "        ______        ",
    "       /  01  \\       ",
    "  <====|02||03|====   ",
    "       \\  04  /       ",
    "        ------        ",
]

STATION_ART = [
    "   +----------------+   ",
    "   |   STATION      |   ",
    "   |  [01] dock     |   ",
    "   |  [02] services |   ",
    "   |  [03] market   |   ",
    "   +----------------+   ",
]

SUN_ART = [
    "    \\  |  /    ",
    "  --- (O) ---   ",
    "    /  |  \\    ",
]

PLANET_ART = [
    "    .---.     ",
    "  .(     ).   ",
    "    '---'     ",
]


@dataclass
class Cell:
    ch: str = " "
    style: Style = SPACE_BG


class SpaceCanvas:
    def __init__(self, width: int, height: int, anchor_x: int, anchor_y: int) -> None:
        self.width = width
        self.height = height
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y
        self.cells = [[Cell() for _ in range(width)] for _ in range(height)]

    def world_to_screen(self, wx: float, wy: float, ship_x: float, ship_y: float, scale: float) -> tuple[int, int]:
        px = self.anchor_x + int((wx - ship_x) / scale)
        py = self.anchor_y + int((wy - ship_y) / scale)
        return px, py

    def put(self, x: int, y: int, ch: str, style: Style) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = Cell(ch, style)

    def _style_at(self, line: str, col: int, hull: Style, ship: Ship | None, subtarget: str | None) -> Style:
        for tag, comp in (("01", "reactor"), ("02", "shield"), ("03", "hyperdrive"), ("04", "cargo")):
            idx = line.find(tag)
            if idx >= 0 and idx <= col < idx + len(tag):
                if subtarget == comp and ship:
                    return COMP_HIT
                return COMP_STYLE
        return hull

    def stamp_art(
        self,
        cx: int,
        cy: int,
        lines: list[str],
        hull: Style,
        *,
        ship: Ship | None = None,
        subtarget: str | None = None,
        id_letter: str = "",
    ) -> None:
        y0 = cy - len(lines) // 2
        for dy, row in enumerate(lines):
            y = y0 + dy
            x0 = cx - len(row) // 2
            if id_letter and dy == len(lines) // 2:
                self.put(x0 - 2, y, id_letter, ID_STYLE)
            for dx, ch in enumerate(row):
                if ch != " ":
                    st = self._style_at(row, dx, hull, ship, subtarget)
                    self.put(x0 + dx, y, ch, st)

    def to_text(self) -> Text:
        out = Text()
        for y, row in enumerate(self.cells):
            for cell in row:
                out.append(cell.ch, style=cell.style)
            if y < self.height - 1:
                out.append("\n")
        return out


def _scatter_stars(canvas: SpaceCanvas, seed: int, count: int) -> None:
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randint(0, canvas.width - 1)
        y = rng.randint(0, canvas.height - 1)
        ch = rng.choice(".+*")
        canvas.put(x, y, ch, STAR_STYLE)


def _draw_player(canvas: SpaceCanvas, ship: Ship) -> None:
    canvas.stamp_art(
        canvas.anchor_x,
        canvas.anchor_y,
        PLAYER_SHIP,
        HULL_PLAYER,
        ship=ship,
        subtarget=ship.subtarget,
    )


def _draw_npc(canvas: SpaceCanvas, npc: NpcShip, sx: int, sy: int, locked: bool) -> None:
    sub = None
    fake = Ship(name="", location=None)  # type: ignore[arg-type]
    if locked:
        from eve_ascii.models import ShipLocation, Vec3

        fake = Ship(name="x", location=ShipLocation("x", "space", Vec3(0, 0, 0)))
        fake.subtarget = None
    subtarget = None
    canvas.stamp_art(
        sx,
        sy,
        ENEMY_SHIP,
        HULL_ENEMY,
        subtarget=subtarget,
        id_letter=npc.letter,
    )


def render_open_space(
    state: GameState,
    width: int,
    height: int,
    scale: float,
    *,
    hyperspace: bool = False,
) -> Text:
    anchor_x = max(14, width // 6)
    anchor_y = height // 2
    canvas = SpaceCanvas(width, height, anchor_x, anchor_y)
    seed = state.galaxy.seed + hash(state.player.system_id)
    _scatter_stars(canvas, seed, max(12, width * height // 80))

    from eve_ascii.travel import current_ship_coords

    sc = current_ship_coords(state)
    ship_x, ship_y = sc.x, sc.y
    ship = state.player.ship

    if hyperspace:
        for p in state.hyperspace_particles:
            sx = anchor_x + int((p.x - 400) / 70)
            sy = anchor_y + int(p.y / 35)
            canvas.put(sx, sy, p.char, PARTICLE_STYLES[int(p.x) % len(PARTICLE_STYLES)])
        _draw_player(canvas, ship)
        header = Text(" HYPERSPACE  ", style=Style(color="#bb88ff", bold=True))
        header.append(f"fuel {ship.fuel:.0f}\n", style=Style(color="#aaccee"))
        header.append(" components 01-04 on hull\n", style=Style(color="#668899"))
        header.append(canvas.to_text())
        return header

    sys = state.galaxy.get_system(ship.location.system_id)
    if sys:
        sx, sy = canvas.world_to_screen(0, 0, ship_x, ship_y, scale)
        canvas.stamp_art(sx, sy, SUN_ART, SUN_STYLE)

        for planet in sys.planets:
            pos = planet_position(planet)
            px, py = canvas.world_to_screen(pos.x, pos.y, ship_x, ship_y, scale)
            canvas.stamp_art(px, py, PLANET_ART, PLANET_STYLE)

        for st in sys.stations:
            pos = station_position(sys, st)
            px, py = canvas.world_to_screen(pos.x, pos.y, ship_x, ship_y, scale)
            canvas.stamp_art(px, py, STATION_ART, STATION_STYLE)

    lock = ship.target_letter
    for npc in state.npc_ships:
        if not npc.alive:
            continue
        px, py = canvas.world_to_screen(npc.position.x, npc.position.y, ship_x, ship_y, scale)
        sub = ship.subtarget if lock == npc.letter else None
        canvas.stamp_art(
            px,
            py,
            ENEMY_SHIP,
            HULL_ENEMY,
            subtarget=sub,
            id_letter=npc.letter,
        )

    for proj in state.projectiles:
        px, py = canvas.world_to_screen(proj.x, proj.y, ship_x, ship_y, scale)
        canvas.put(px, py, "=", LASER_STYLE)
        canvas.put(px + 1, py, ">", LASER_STYLE)

    for ex in state.explosions:
        px, py = canvas.world_to_screen(ex.x, ex.y, ship_x, ship_y, scale)
        canvas.stamp_art(px, py, [" *!* ", "!***!", " *!* "], EXPLOSION_STYLE)

    if ship.destination and ship.destination.coords:
        dp = ship.destination.coords
        px, py = canvas.world_to_screen(dp.x, dp.y, ship_x, ship_y, scale)
        canvas.put(px, py, "X", Style(color="#ff66aa", bold=True))

    _draw_player(canvas, ship)

    wpn = "ON" if ship.weapons_active else "off"
    title = sys.name if sys else "?"
    header = Text(f" {title} ", style=Style(color="#e8b84a", bold=True))
    header.append(
        f"| {state.mode.value} lock={lock or '-'} wpn={wpn} ",
        style=Style(color="#aaccee"),
    )
    header.append("01-04 on ships ", style=Style(color="#ffee66"))
    if ship.eta_seconds > 0:
        header.append(f"eta {ship.eta_seconds:.1f}s ", style=Style(color="#88ccff"))
    header.append("\n", style=Style())
    header.append(canvas.to_text())
    return header


def render_galaxy_map(state: GameState, width: int, height: int) -> Text:
    canvas = SpaceCanvas(width, height, width // 2, height // 2)
    _scatter_stars(canvas, state.galaxy.seed, width // 3)
    cur = state.galaxy.get_system(state.player.ship.location.system_id)
    if not state.galaxy.systems:
        return Text("Empty galaxy.", style=Style(color="#aaccee"))

    xs = [s.position.x for s in state.galaxy.systems.values()]
    ys = [s.position.y for s in state.galaxy.systems.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    pad = 3

    for s in state.galaxy.systems.values():
        gx = pad + int((s.position.x - min_x) / span_x * (width - 2 * pad - 1))
        gy = pad + int((s.position.y - min_y) / span_y * (height - 2 * pad - 1))
        if cur and s.id == cur.id:
            canvas.put(gx, gy, "@", Style(color="#00e5ff", bold=True))
        elif s.neighbors:
            canvas.put(gx, gy, "+", Style(color="#88aaff"))
        else:
            canvas.put(gx, gy, "*", Style(color="#ffcc66"))

    header = Text(" GALAXY MAP ", style=Style(color="#e8b84a", bold=True))
    header.append("[g] system view\n", style=Style(color="#6688aa"))
    header.append(canvas.to_text())
    return header
