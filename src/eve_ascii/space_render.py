"""Open-space ASCII rendering with Rich color (not a dot grid)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from rich.style import Style
from rich.text import Text

from eve_ascii.galaxy import planet_position, station_position
from eve_ascii.models import (
    BackgroundStar,
    Explosion,
    GameMode,
    GameState,
    NpcShip,
    Ship,
    TutorialStep,
)
from eve_ascii.models import GameMode, GameState, Ship, ShipComponent, TutorialStep
from eve_ascii.ship import BASE_SHIELD_GEN, is_powerless, shield_gen_per_sec, weapon_charge_seconds

SPACE_BG = Style(color="#1a3a5c", bgcolor="#050d18")
STAR_STYLE = Style(color="#6a8aaa")
SUN_STYLE = Style(color="#ffcc33", bold=True)
PLANET_STYLE = Style(color="#44cc88")
STATION_STYLE = Style(color="#88aaff")
HULL_PLAYER = Style(color="#00e5ff", bold=True)
HULL_ENEMY = Style(color="#ff5566", bold=True)
COMP_STYLE = Style(color="#ffee00", bold=True, bgcolor="#223344")
COMP_HIT = Style(color="#ff4400", bold=True, bgcolor="#442200")
COMP_DAMAGED = Style(color="#ffaa33", bold=True, bgcolor="#332200")
COMP_DEAD = Style(color="#664444", bgcolor="#221111")
COMP_DESTROYED = Style(color="#555555", bold=False)
ID_STYLE = Style(color="#ffffff", bold=True)
LASER_STYLE = Style(color="#66ff66", bold=True)
EXPLOSION_STYLE = Style(color="#ffaa00", bold=True)
EXPLOSION_LARGE = Style(color="#ff6622", bold=True)
PARTICLE_STYLES = (
    Style(color="#446688"),
    Style(color="#6688aa"),
    Style(color="#8866cc"),
)

# 01=reactor 02=thrusters 03=shields 04=weapons (embedded in art)
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

PLAYER_SHIP_ZOOM = [
    "              ______________              ",
    "             /              \\             ",
    "            /      01        \\            ",
    "           /    REACTOR       \\           ",
    "   >======|  02          03    |======>   ",
    "          | THRUST     SHIELD  |          ",
    "           \\      04          /           ",
    "            \\   WEAPONS      /            ",
    "             \\______________/             ",
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

EXPLOSION_SMALL = [" * ", "!*!"]
EXPLOSION_LARGE_ART = [
    "  *!!!*  ",
    " !*****! ",
    "*!!***!!*",
    " !*****! ",
    "  *!!!*  ",
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

    def _style_at(
        self,
        line: str,
        col: int,
        hull: Style,
        components: list[ShipComponent] | None,
        subtarget: str | None,
    ) -> Style:
        if components:
            for comp in components:
                idx = line.find(comp.slot_id)
                if idx >= 0 and idx <= col < idx + len(comp.slot_id):
                    if subtarget in (comp.slot_id, comp.kind):
                        return COMP_HIT
                    if comp.destroyed:
                        return COMP_DEAD
                    if comp.integrity < 0.5:
                        return COMP_DAMAGED
                    return COMP_STYLE
        return hull

    def stamp_art(
        self,
        cx: int,
        cy: int,
        lines: list[str],
        hull: Style,
        *,
        components: list[ShipComponent] | None = None,
        subtarget: str | None = None,
        id_letter: str = "",
        destroyed_components: set[str] | None = None,
    ) -> None:
        y0 = cy - len(lines) // 2
        for dy, row in enumerate(lines):
            y = y0 + dy
            x0 = cx - len(row) // 2
            if id_letter and dy == len(lines) // 2:
                self.put(x0 - 2, y, id_letter, ID_STYLE)
            for dx, ch in enumerate(row):
                if ch != " ":
                    st = self._style_at(row, dx, hull, components, subtarget, destroyed_components)
                    self.put(x0 + dx, y, ch, st)

    def to_text(self) -> Text:
        out = Text()
        for y, row in enumerate(self.cells):
            for cell in row:
                out.append(cell.ch, style=cell.style)
            if y < self.height - 1:
                out.append("\n")
        return out


def init_background_stars(state: GameState, count: int = 48) -> None:
    rng = random.Random(state.galaxy.seed + 991)
    state.background_stars = [
        BackgroundStar(
            x=rng.random(),
            y=rng.randint(0, 40),
            char=rng.choice(".+*"),
            parallax=rng.uniform(0.15, 0.55),
        )
        for _ in range(count)
    ]


def _draw_player(canvas: SpaceCanvas, ship: Ship) -> None:
    canvas.stamp_art(
        canvas.anchor_x,
        canvas.anchor_y,
        PLAYER_SHIP,
        HULL_PLAYER,
        components=ship.components,
        subtarget=ship.subtarget,
    )
def tick_star_scroll(state: GameState, dt: float) -> None:
    state.star_scroll += dt


def tutorial_arena(state: GameState) -> bool:
    """Tutorial combat: player + pirate only (no station / planets / sun)."""
    if state.mode == GameMode.HYPERSPACE:
        return True
    return state.mode == GameMode.COMBAT and state.tutorial_step != TutorialStep.DONE
def _draw_drifting_stars(canvas: SpaceCanvas, state: GameState, height: int) -> None:
    w = canvas.width
    for star in state.background_stars:
        drift = state.star_scroll * star.parallax
        x = int(star.x * w + drift) % w
        y = star.y % max(1, height)
        canvas.put(x, y, star.char, STAR_STYLE)


def _destroyed_components(components: dict[str, float]) -> set[str]:
    return {name for name, hp in components.items() if hp <= 0}


def _draw_explosion(canvas: SpaceCanvas, ex: Explosion, px: int, py: int) -> None:
    if ex.large:
        canvas.stamp_art(px, py, EXPLOSION_LARGE_ART, EXPLOSION_LARGE)
    else:
        canvas.stamp_art(px, py, EXPLOSION_SMALL, EXPLOSION_STYLE)


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
    inner_h = height

    from eve_ascii.travel import current_ship_coords

    sc = current_ship_coords(state)
    ship_x, ship_y = sc.x, sc.y
    ship = state.player.ship
    show_stations = state.tutorial_step == TutorialStep.DONE

    if hyperspace:
        _draw_drifting_stars(canvas, state, inner_h)
        for p in state.hyperspace_particles:
            sx = anchor_x + int((p.x - 400) / 70)
            sy = anchor_y + int(p.y / 35)
            canvas.put(sx, sy, p.char, PARTICLE_STYLES[int(p.x) % len(PARTICLE_STYLES)])
        canvas.stamp_art(
            canvas.anchor_x,
            canvas.anchor_y,
            PLAYER_SHIP,
            HULL_PLAYER,
            ship=ship,
            subtarget=ship.subtarget,
            destroyed_components=_destroyed_components(ship.components),
        )
        header = Text(" HYPERSPACE  ", style=Style(color="#bb88ff", bold=True))
        header.append(f"fuel {ship.fuel:.0f}\n", style=Style(color="#aaccee"))
        header.append(" hull 01 reactor  02 thrusters  03 shields  04 weapons\n", style=Style(color="#668899"))
        header.append(canvas.to_text())
        return header

    _draw_drifting_stars(canvas, state, inner_h)

    sys = state.galaxy.get_system(ship.location.system_id)
    if sys and not tutorial_arena(state):
        sx, sy = canvas.world_to_screen(0, 0, ship_x, ship_y, scale)
        canvas.stamp_art(sx, sy, SUN_ART, SUN_STYLE)

        for planet in sys.planets:
            pos = planet_position(planet)
            px, py = canvas.world_to_screen(pos.x, pos.y, ship_x, ship_y, scale)
            canvas.stamp_art(px, py, PLANET_ART, PLANET_STYLE)

        if show_stations:
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
            components=npc.components,
            subtarget=sub,
            id_letter=npc.letter,
            destroyed_components=_destroyed_components(npc.components),
        )

    for proj in state.projectiles:
        px, py = canvas.world_to_screen(proj.x, proj.y, ship_x, ship_y, scale)
        canvas.put(px, py, "=", LASER_STYLE)
        canvas.put(px + 1, py, ">", LASER_STYLE)

    for ex in state.explosions:
        px, py = canvas.world_to_screen(ex.x, ex.y, ship_x, ship_y, scale)
        _draw_explosion(canvas, ex, px, py)

    if ship.destination and ship.destination.coords:
        dp = ship.destination.coords
        px, py = canvas.world_to_screen(dp.x, dp.y, ship_x, ship_y, scale)
        canvas.put(px, py, "X", Style(color="#ff66aa", bold=True))

    canvas.stamp_art(
        canvas.anchor_x,
        canvas.anchor_y,
        PLAYER_SHIP,
        HULL_PLAYER,
        ship=ship,
        subtarget=ship.subtarget,
        destroyed_components=_destroyed_components(ship.components),
    )

    wpn = "ON" if ship.weapons_active else "off"
    title = sys.name if sys else "?"
    header = Text(f" {title} ", style=Style(color="#e8b84a", bold=True))
    header.append(
        f"| {state.mode.value} lock={lock or '-'} wpn={wpn} ",
        style=Style(color="#aaccee"),
    )
    header.append("01-04 components ", style=Style(color="#ffee66"))
    if ship.eta_seconds > 0:
        header.append(f"eta {ship.eta_seconds:.1f}s ", style=Style(color="#88ccff"))
    header.append("\n", style=Style())
    header.append(canvas.to_text())
    return header


def render_ship_inspect(state: GameState) -> Text:
    ship = state.player.ship
    width = 78
    height = 11
    canvas = SpaceCanvas(width, height, width // 2, height // 2)
    canvas.stamp_art(
        width // 2,
        height // 2,
        PLAYER_SHIP_ZOOM,
        HULL_PLAYER,
        components=ship.components,
    )
    out = Text(" SHIP ", style=Style(color="#e8b84a", bold=True))
    out.append(f"{ship.name}  fit {len(ship.components)}/{ship.max_slots}\n", style=Style(color="#aaccee"))
    out.append(canvas.to_text())
    out.append("\n")
    pwr_style = Style(color="#ff5566", bold=True) if is_powerless(ship) else Style(color="#88ffaa")
    out.append(
        f" POWER {ship.power:.0f}/{ship.max_power:.0f}   SHIELD {ship.shield:.0f}/{ship.max_shield:.0f}  "
        f"gen {shield_gen_per_sec(ship):.1f}/s\n",
        style=pwr_style,
    )
    if is_powerless(ship):
        out.append(" REACTOR DESTROYED - SHIP POWERLESS\n", style=Style(color="#ff3344", bold=True))
    for c in ship.components:
        mark = "X" if c.destroyed else ("!" if c.integrity < 0.5 else " ")
        extra = ""
        if c.kind == "reactor":
            extra = f"  power {c.integrity * 100:.0f}%"
        elif c.kind == "shields":
            extra = "  gen none" if c.destroyed else f"  gen {BASE_SHIELD_GEN * c.integrity:.1f}/s"
        elif c.kind == "weapons":
            extra = "  OFFLINE" if c.destroyed else f"  charge {weapon_charge_seconds(ship):.2f}s"
        elif c.kind == "thrusters":
            extra = "  (idle)"
        st = COMP_DEAD if c.destroyed else (COMP_DAMAGED if c.integrity < 0.5 else Style(color="#ddeeff"))
        out.append(
            f" {c.slot_id} {c.kind.upper():<10}  hp {c.health:5.0f}/{c.max_health:.0f}  {mark}{extra}\n",
            style=st,
        )
    out.append(" Esc close   command: ship\n", style=Style(color="#6688aa"))
    return out


def render_galaxy_map(state: GameState, width: int, height: int) -> Text:
    canvas = SpaceCanvas(width, height, width // 2, height // 2)
    rng = random.Random(state.galaxy.seed)
    for _ in range(width // 3):
        canvas.put(rng.randint(0, width - 1), rng.randint(0, height - 1), ".", STAR_STYLE)
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
