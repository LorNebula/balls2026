"""Open-space ASCII rendering with Rich color (not a dot grid)."""

from __future__ import annotations

import random
import textwrap
from dataclasses import dataclass

from rich.style import Style
from rich.text import Text

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.galaxy import planet_position, station_position
from eve_ascii.models import (
    BackgroundStar,
    Explosion,
    GameMode,
    GameState,
    Ship,
    ShipComponent,
    ShipStatus,
    TutorialStep,
)
from eve_ascii.ship import BASE_SHIELD_GEN, is_powerless, shield_gen_per_sec, weapon_charge_seconds

SPACE_BG = Style(color="#1a3a5c", bgcolor="#050d18")
HYPERSPACE_BG = Style(color="#5533aa", bgcolor="#120828")
DOCK_BG = Style(color="#6a7088", bgcolor="#141018")
STAR_STYLE = Style(color="#6a8aaa")
HYPERSPACE_STAR = Style(color="#9977cc")
DOCK_STAR = Style(color="#4a5566")
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

STATION_MARKER = [
    "  (S)  ",
    " /===\\ ",
]

ASTEROID_ART = [
    " (@) ",
    "/###\\",
]
ASTEROID_STYLE = Style(color="#cc8844", bold=True)

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
    def __init__(
        self,
        width: int,
        height: int,
        anchor_x: int,
        anchor_y: int,
        *,
        bg_style: Style | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y
        self.bg_style = bg_style or SPACE_BG
        self.cells = [
            [Cell(" ", self.bg_style) for _ in range(width)] for _ in range(height)
        ]

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
    ) -> None:
        y0 = cy - len(lines) // 2
        for dy, row in enumerate(lines):
            y = y0 + dy
            x0 = cx - len(row) // 2
            if id_letter and dy == len(lines) // 2:
                self.put(x0 - 2, y, id_letter, ID_STYLE)
            for dx, ch in enumerate(row):
                if ch != " ":
                    st = self._style_at(row, dx, hull, components, subtarget)
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


def _show_stations_on_map(state: GameState) -> bool:
    if tutorial_arena(state):
        return False
    if state.tutorial_step == TutorialStep.DONE:
        return True
    return state.tutorial_step in (TutorialStep.JUMP_STATION, TutorialStep.DOCK)


def _draw_drifting_stars(
    canvas: SpaceCanvas, state: GameState, height: int, *, star_style: Style | None = None
) -> None:
    w = canvas.width
    style = star_style or STAR_STYLE
    for star in state.background_stars:
        drift = state.star_scroll * star.parallax
        x = int(star.x * w + drift) % w
        y = star.y % max(1, height)
        canvas.put(x, y, star.char, style)


def _apply_screen_flash(canvas: SpaceCanvas, state: GameState) -> None:
    t = state.screen_flash
    if t <= 0:
        return
    peak = 0.32
    ship = state.player.ship
    in_hyperspace = state.mode == GameMode.HYPERSPACE or ship.status == ShipStatus.JUMPING
    if t >= peak:
        wash = Style(
            color="#ffffff",
            bgcolor="#ddd0ff" if in_hyperspace else "#fff4dd",
            bold=True,
        )
        fill = 0.5
    else:
        wash = Style(
            color="#bbaaff" if in_hyperspace else "#ffcc88",
            bgcolor="#2a1848" if in_hyperspace else "#2a2210",
        )
        fill = 0.22 * (t / peak)
    rng = random.Random(int(t * 800) + canvas.width)
    for y in range(canvas.height):
        for x in range(canvas.width):
            roll = rng.random()
            if roll < fill:
                canvas.put(x, y, " ", wash)
            elif roll < fill + 0.08:
                canvas.put(x, y, rng.choice("/\\|*"), wash)


def _draw_station_markers(
    canvas: SpaceCanvas,
    sys,
    ship_x: float,
    ship_y: float,
    scale: float,
) -> None:
    """One marker per screen cluster (systems often have two stations on one planet)."""
    placed: list[tuple[int, int]] = []
    min_dx, min_dy = 9, 4
    for st in sys.stations:
        pos = station_position(sys, st)
        px, py = canvas.world_to_screen(pos.x, pos.y, ship_x, ship_y, scale)
        if any(abs(px - qx) < min_dx and abs(py - qy) < min_dy for qx, qy in placed):
            continue
        placed.append((px, py))
        canvas.stamp_art(px, py, STATION_MARKER, STATION_STYLE)


def _draw_explosion(canvas: SpaceCanvas, ex: Explosion, px: int, py: int) -> None:
    if ex.large:
        canvas.stamp_art(px, py, EXPLOSION_LARGE_ART, EXPLOSION_LARGE)
    else:
        canvas.stamp_art(px, py, EXPLOSION_SMALL, EXPLOSION_STYLE)


def render_docked_view(state: GameState, width: int, height: int) -> Text:
    anchor_x = width // 2
    anchor_y = height // 2
    canvas = SpaceCanvas(width, height, anchor_x, anchor_y, bg_style=DOCK_BG)
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    st_name = "station"
    if sys and ship.location.station_id:
        st = next((s for s in sys.stations if s.id == ship.location.station_id), None)
        if st:
            st_name = st.name
    _draw_drifting_stars(canvas, state, height, star_style=DOCK_STAR)
    ring = [
        "    dock ring    ",
        "  ..========..  ",
        "   hangar open   ",
    ]
    canvas.stamp_art(anchor_x, anchor_y - 2, ring, Style(color="#88aacc", bold=True))
    canvas.stamp_art(
        anchor_x,
        anchor_y + 3,
        PLAYER_SHIP,
        Style(color="#66bbdd", bold=True),
        components=ship.components,
    )
    _apply_screen_flash(canvas, state)
    header = Text(f" DOCKED @ {st_name} ", style=Style(color="#c9a86a", bold=True))
    header.append("| type undock to leave\n", style=Style(color="#8899aa"))
    header.append(canvas.to_text())
    return header


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
    bg = HYPERSPACE_BG if hyperspace else SPACE_BG
    canvas = SpaceCanvas(width, height, anchor_x, anchor_y, bg_style=bg)
    inner_h = height

    from eve_ascii.travel import current_ship_coords

    sc = current_ship_coords(state)
    ship_x, ship_y = sc.x, sc.y
    ship = state.player.ship
    show_stations = _show_stations_on_map(state)

    if hyperspace:
        _draw_drifting_stars(canvas, state, inner_h, star_style=HYPERSPACE_STAR)
        for p in state.hyperspace_particles:
            sx = anchor_x + int((p.x - 400) / 70)
            sy = anchor_y + int(p.y / 35)
            canvas.put(sx, sy, p.char, PARTICLE_STYLES[int(p.x) % len(PARTICLE_STYLES)])
        canvas.stamp_art(
            canvas.anchor_x,
            canvas.anchor_y,
            PLAYER_SHIP,
            HULL_PLAYER,
            components=ship.components,
            subtarget=ship.subtarget,
        )
        _apply_screen_flash(canvas, state)
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
            _draw_station_markers(canvas, sys, ship_x, ship_y, scale)

        if not tutorial_arena(state):
            lock_ast = ship.target_letter or ""
            for ast in state.asteroids:
                if not ast.alive:
                    continue
                ax, ay = canvas.world_to_screen(
                    ast.position.x, ast.position.y, ship_x, ship_y, scale
                )
                highlight = lock_ast.upper() == ast.code.upper()
                style = Style(color="#ffcc66", bold=True) if highlight else ASTEROID_STYLE
                canvas.stamp_art(ax, ay, ASTEROID_ART, style, id_letter=ast.code)

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
        components=ship.components,
        subtarget=ship.subtarget,
    )

    wpn = "ON" if ship.weapons_active else "off"
    mine = "ON" if state.mining_active else "off"
    title = sys.name if sys else "?"
    header = Text(f" {title} ", style=Style(color="#e8b84a", bold=True))
    header.append(
        f"| {state.mode.value} lock={lock or '-'} wpn={wpn} mine={mine} ",
        style=Style(color="#aaccee"),
    )
    header.append("01-04 components ", style=Style(color="#ffee66"))
    if ship.eta_seconds > 0:
        header.append(f"eta {ship.eta_seconds:.1f}s ", style=Style(color="#88ccff"))
    header.append("\n", style=Style())
    _apply_screen_flash(canvas, state)
    header.append(canvas.to_text())
    return header


def render_ship_inspect(state: GameState) -> Text:
    from eve_ascii.ascii_ui import box_wrap

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
    inner = Text()
    inner.append(f"{ship.name}  fit {len(ship.components)}/{ship.max_slots}\n", style=Style(color="#aaccee"))
    inner.append(canvas.to_text())
    inner.append("\n")
    pwr_style = Style(color="#ff5566", bold=True) if is_powerless(ship) else Style(color="#88ffaa")
    inner.append(
        f" POWER {ship.power:.0f}/{ship.max_power:.0f}   SHIELD {ship.shield:.0f}/{ship.max_shield:.0f}  "
        f"gen {shield_gen_per_sec(ship):.1f}/s\n",
        style=pwr_style,
    )
    if is_powerless(ship):
        inner.append(" REACTOR DESTROYED - SHIP POWERLESS\n", style=Style(color="#ff3344", bold=True))
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
        inner.append(
            f" {c.slot_id} {c.kind.upper():<10}  hp {c.health:5.0f}/{c.max_health:.0f}  {mark}{extra}\n",
            style=st,
        )
    inner.append(" Esc close   command: ship\n", style=Style(color="#6688aa"))

    frame_style = Style(color="#e8b84a")
    body_style = Style(color="#c9d6e3")
    boxed_lines = box_wrap(width, "SHIP", inner.plain.splitlines()).split("\n")
    out = Text()
    for line in boxed_lines:
        if line.startswith("+"):
            out.append(line + "\n", style=frame_style)
        else:
            out.append(line + "\n", style=body_style)
    return out


def render_galaxy_map(state: GameState, width: int, height: int, zoom: float = 1.0) -> Text:
    width = max(1, width)
    height = max(5, height)
    if not state.galaxy.systems:
        return Text("Empty galaxy.", style=Style(color="#aaccee"))

    current = state.galaxy.get_system(state.player.ship.location.system_id)
    center = current.position if current else next(iter(state.galaxy.systems.values())).position
    current_name = ascii_only(current.name) if current else "unknown"
    hole_name = ascii_only(state.galaxy.black_hole.name) if state.galaxy.black_hole else "none"
    linked = [
        state.galaxy.get_system(system_id)
        for system_id in (current.neighbors if current else [])
    ]
    linked = [system for system in linked if system]
    link_names = ", ".join(ascii_only(system.name) for system in linked) or "none"
    link_lines = textwrap.wrap(f"LINKS: {link_names}", width=max(1, width), break_long_words=True)
    deltas = [(system.position.x - center.x, system.position.y - center.y) for system in linked]
    map_height = max(1, height - 2 - len(link_lines))
    available_x = max(1, width // 2 - 2)
    available_y = max(1, map_height // 2 - 1)
    reach_x = max((abs(dx) for dx, _ in deltas), default=1.0)
    reach_y = max((abs(dy) for _, dy in deltas), default=1.0)
    base_scale = min(available_x / reach_x, available_y / reach_y)
    scale = max(0.01, base_scale * max(0.05, zoom))
    canvas = SpaceCanvas(width, map_height, width // 2, map_height // 2)
    rng = random.Random(state.galaxy.seed)
    for _ in range(width // 3):
        canvas.put(rng.randint(0, width - 1), rng.randint(0, map_height - 1), ".", STAR_STYLE)

    screen_positions = {
        system.id: (
            canvas.anchor_x + round((system.position.x - center.x) * scale),
            canvas.anchor_y + round((system.position.y - center.y) * scale),
        )
        for system in state.galaxy.systems.values()
    }
    if current:
        x0, y0 = screen_positions[current.id]
        for system in linked:
            x1, y1 = screen_positions[system.id]
            steps = max(abs(x1 - x0), abs(y1 - y0))
            for step in range(1, steps):
                ratio = step / steps
                canvas.put(
                    round(x0 + (x1 - x0) * ratio),
                    round(y0 + (y1 - y0) * ratio),
                    ".",
                    Style(color="#6688aa"),
                )

    for system in state.galaxy.systems.values():
        gx, gy = screen_positions[system.id]
        if current and system.id == current.id:
            canvas.put(gx, gy, "@", Style(color="#00e5ff", bold=True))
        elif current and system.id in current.neighbors:
            canvas.put(gx, gy, "+", Style(color="#88ffaa", bold=True))
        elif any(system.id in nebula.system_ids for nebula in state.galaxy.nebulae):
            canvas.put(gx, gy, "N", Style(color="#cc88ff", bold=True))
        elif system.neighbors:
            canvas.put(gx, gy, "*", Style(color="#88aaff"))
        else:
            canvas.put(gx, gy, ".", Style(color="#667788"))

    if state.galaxy.black_hole:
        hole = state.galaxy.black_hole.position
        gx = canvas.anchor_x + round((hole.x - center.x) * scale)
        gy = canvas.anchor_y + round((hole.y - center.y) * scale)
        canvas.put(gx, gy, "O", Style(color="#ff6677", bold=True))

    header = Text(" GALAXY MAP ", style=Style(color="#e8b84a", bold=True))
    header.append(f"{current_name}  zoom {zoom:.2f}x\n", style=Style(color="#aaccee"))
    header.append(f"@=here +=linked *=other O={hole_name} N=nebula\n", style=Style(color="#668899"))
    for line in link_lines:
        header.append(line + "\n", style=Style(color="#88ffaa", bold=True))
    header.append(canvas.to_text())
    return header
