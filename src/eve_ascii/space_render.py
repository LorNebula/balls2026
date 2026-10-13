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
    NpcShip,
    Ship,
    ShipComponent,
    ShipStatus,
    TutorialStep,
)
from eve_ascii.ship import (
    BASE_SHIELD_GEN,
    hull_totals,
    is_powerless,
    meter,
    shield_gen_per_sec,
    weapon_charge_seconds,
)

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
ID_STYLE = Style(color="#ffffff", bold=True)
LASER_STYLE = Style(color="#66ff66", bold=True)
ENEMY_LASER_STYLE = Style(color="#ff4466", bold=True)
EXPLOSION_STYLE = Style(color="#ffaa00", bold=True)
EXPLOSION_LARGE = Style(color="#ff6622", bold=True)
PARTICLE_STYLES = (
    Style(color="#446688"),
    Style(color="#6688aa"),
    Style(color="#8866cc"),
)
HYPERLANE_ACTIVE = Style(color="#6688aa")
HYPERLANE_INACTIVE = Style(color="#50677f")

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

STATION_MARKER = [
    "  (S)  ",
    " /===\\ ",
]

ASTEROID_ART = [
    " (@) ",
    "/###\\",
]
ASTEROID_STYLE = Style(color="#cc8844", bold=True)

COMBAT_WARN = [
    " /\\ ",
    "/ !!\\",
]
WARN_STYLE = Style(color="#ff8800", bold=True)
NRG_BAR_STYLE = Style(color="#44ddff", bold=True)
NRG_LOW_STYLE = Style(color="#ff5555", bold=True)
HP_BAR_STYLE = Style(color="#66ff88", bold=True)
HP_LOW_STYLE = Style(color="#ff5555", bold=True)
HUD_LABEL_STYLE = Style(color="#aaccee", bold=True)

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
            start = 0
            while start < len(row):
                style = row[start].style
                end = start + 1
                while end < len(row) and row[end].style is style:
                    end += 1
                out.append("".join(cell.ch for cell in row[start:end]), style=style)
                start = end
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
    return state.tutorial_step == TutorialStep.JUMP


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


def _put_text(canvas: SpaceCanvas, x: int, y: int, text: str, style: Style) -> None:
    for i, ch in enumerate(text):
        canvas.put(x + i, y, ch, style)


def _put_text_right(canvas: SpaceCanvas, y: int, text: str, style: Style, right_x: int) -> None:
    x = max(0, right_x - len(text) + 1)
    _put_text(canvas, x, y, text, style)


def _resource_style(frac: float, *, energy: bool) -> Style:
    if frac < 0.3:
        return NRG_LOW_STYLE if energy else HP_LOW_STYLE
    return NRG_BAR_STYLE if energy else HP_BAR_STYLE


def _draw_combat_hud(canvas: SpaceCanvas, state: GameState) -> None:
    w, h = canvas.width, canvas.height
    cx = w // 2
    canvas.stamp_art(cx, 1, COMBAT_WARN, WARN_STYLE)

    ship = state.player.ship
    bar_w = min(12, max(8, w // 8))
    hp, hp_max = hull_totals(ship)
    nrg_frac = ship.power / ship.max_power if ship.max_power > 0 else 0.0
    hp_frac = hp / hp_max if hp_max > 0 else 0.0
    nrg_line = f"NRG{meter(ship.power, ship.max_power, bar_w)}"
    hp_line = f"HP {meter(hp, hp_max, bar_w)}"
    y_nrg = max(0, h - 2)
    y_hp = max(0, h - 1)
    _put_text(canvas, 1, y_nrg, nrg_line, _resource_style(nrg_frac, energy=True))
    _put_text(canvas, 1, y_hp, hp_line, _resource_style(hp_frac, energy=False))

    lock = ship.target_letter
    if not lock:
        return
    target: NpcShip | None = next(
        (n for n in state.npc_ships if n.alive and n.letter == lock.upper()),
        None,
    )
    if not target:
        return
    thp, thp_max = hull_totals(target)
    tnrg_frac = target.power / target.max_power if target.max_power > 0 else 0.0
    thp_frac = thp / thp_max if thp_max > 0 else 0.0
    tr_nrg = f"{target.letter} NRG{meter(target.power, target.max_power, bar_w)}"
    tr_hp = f"{target.letter} HP {meter(thp, thp_max, bar_w)}"
    right = w - 2
    _put_text_right(canvas, y_nrg, tr_nrg, _resource_style(tnrg_frac, energy=True), right)
    _put_text_right(canvas, y_hp, tr_hp, _resource_style(thp_frac, energy=False), right)


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
        if proj.friendly:
            canvas.put(px, py, "=", LASER_STYLE)
            canvas.put(px + 1, py, ">", LASER_STYLE)
        else:
            canvas.put(px - 1, py, "<", ENEMY_LASER_STYLE)
            canvas.put(px, py, "=", ENEMY_LASER_STYLE)

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
    if state.mode == GameMode.COMBAT:
        _draw_combat_hud(canvas, state)
    _apply_screen_flash(canvas, state)
    header.append(canvas.to_text())
    return header


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
    gate_prefix = "GATES: "
    separator_width = 2
    name_width = max(
        3,
        min(
            18,
            (width - len(gate_prefix) - separator_width * max(0, len(linked) - 1))
            // max(1, len(linked)),
        ),
    )
    gate_names = [
        ascii_only(system.name)
        if len(ascii_only(system.name)) <= name_width
        else ascii_only(system.name)[:name_width - 1] + "~"
        for system in linked
    ]
    gate_lines = textwrap.wrap(
        gate_prefix + ", ".join(gate_names or ["none"]),
        width=max(1, width),
        break_long_words=True,
    )
    deltas = [
        (system.position.x - center.x, system.position.y - center.y)
        for system in state.galaxy.systems.values()
    ]
    map_height = max(1, height - 2 - len(gate_lines))
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

    raw_positions = {
        system.id: (
            canvas.anchor_x + round((system.position.x - center.x) * scale),
            canvas.anchor_y + round((system.position.y - center.y) * scale),
        )
        for system in state.galaxy.systems.values()
    }
    screen_positions: dict[str, tuple[int, int]] = {}
    occupied: set[tuple[int, int]] = set()

    def lane_cells_between(
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> list[tuple[int, int]]:
        x0, y0 = first
        x1, y1 = second
        steps = max(abs(x1 - x0), abs(y1 - y0))
        if steps < 2:
            return []
        return [
            (
                round(x0 + (x1 - x0) * (step / steps)),
                round(y0 + (y1 - y0) * (step / steps)),
            )
            for step in range(1, steps)
        ]

    placement_order = sorted(
        state.galaxy.systems.values(),
        key=lambda system: (
            0 if current and system.id == current.id else
            1 if current and system.id in current.neighbors else 2,
            system.position.distance_to(center),
        ),
    )
    candidate_cells = [
        (x, y)
        for y in range(map_height)
        for x in range(width)
    ]
    for system in placement_order:
        target_x, target_y = raw_positions[system.id]
        candidate = None
        target_x = min(width - 1, max(0, target_x))
        target_y = min(map_height - 1, max(0, target_y))
        for radius in range(min(max(width, map_height), 5)):
            left, right = max(0, target_x - radius), min(width - 1, target_x + radius)
            top, bottom = max(0, target_y - radius), min(map_height - 1, target_y + radius)
            perimeter = (
                [(x, top) for x in range(left, right + 1)]
                + ([(x, bottom) for x in range(left, right + 1)] if bottom != top else [])
                + [(left, y) for y in range(top + 1, bottom)]
                + ([(right, y) for y in range(top + 1, bottom)] if right != left else [])
            )
            for x, y in perimeter:
                if (x, y) in occupied:
                    continue
                neighbor_positions = [
                    screen_positions[neighbor_id]
                    for neighbor_id in system.neighbors
                    if neighbor_id in screen_positions
                ]
                if any(max(abs(x - px), abs(y - py)) < 2 for px, py in neighbor_positions):
                    continue
                lane_cells = [
                    cell
                    for position in neighbor_positions
                    for cell in lane_cells_between((x, y), position)
                ]
                if any(cell in occupied for cell in lane_cells):
                    continue
                candidate = (x, y)
                break
            if candidate:
                break
        if candidate is None:
            for radius in range(max(width, map_height)):
                left, right = max(0, target_x - radius), min(width - 1, target_x + radius)
                top, bottom = max(0, target_y - radius), min(map_height - 1, target_y + radius)
                perimeter = (
                    [(x, top) for x in range(left, right + 1)]
                    + ([(x, bottom) for x in range(left, right + 1)] if bottom != top else [])
                    + [(left, y) for y in range(top + 1, bottom)]
                    + ([(right, y) for y in range(top + 1, bottom)] if right != left else [])
                )
                candidate = next((cell for cell in perimeter if cell not in occupied), None)
                if candidate:
                    break
        if candidate is None:
            candidate = next((cell for cell in candidate_cells if cell not in occupied), (target_x, target_y))
        screen_positions[system.id] = candidate
        occupied.add(candidate)
    lane_cells: dict[tuple[int, int], bool] = {}
    for system in state.galaxy.systems.values():
        x0, y0 = screen_positions[system.id]
        for neighbor_id in system.neighbors:
            if neighbor_id <= system.id:
                continue
            neighbor = state.galaxy.get_system(neighbor_id)
            if not neighbor:
                continue
            x1, y1 = screen_positions[neighbor.id]
            active = current and (system.id == current.id or neighbor.id == current.id)
            for cell in lane_cells_between((x0, y0), (x1, y1)):
                lane_cells[cell] = lane_cells.get(cell, False) or bool(active)

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

    for (x, y), active in lane_cells.items():
        existing = canvas.cells[y][x]
        if existing.ch != " ":
            if existing.ch != "@":
                canvas.put(
                    x,
                    y,
                    existing.ch,
                    HYPERLANE_ACTIVE if active else HYPERLANE_INACTIVE,
                )
        else:
            canvas.put(
                x,
                y,
                ".",
                HYPERLANE_ACTIVE if active else HYPERLANE_INACTIVE,
            )

    if state.galaxy.black_hole:
        hole = state.galaxy.black_hole.position
        target_x = canvas.anchor_x + round((hole.x - center.x) * scale)
        target_y = canvas.anchor_y + round((hole.y - center.y) * scale)
        open_cells = [
            cell
            for cell in candidate_cells
            if cell not in occupied and cell not in lane_cells
        ]
        gx, gy = min(
            open_cells or candidate_cells,
            key=lambda cell: (cell[0] - target_x) ** 2 + (cell[1] - target_y) ** 2,
        )
        canvas.put(gx, gy, "O", Style(color="#ff6677", bold=True))
        occupied.add((gx, gy))

    label_cells = set(occupied)
    for system in linked:
        marker_x, marker_y = screen_positions[system.id]
        slots: list[tuple[int, int, int]] = []
        for row in (marker_y, marker_y - 1, marker_y + 1):
            if not 0 <= row < map_height:
                continue
            for direction in (1, -1):
                available = 0
                x = marker_x + direction
                while 0 <= x < width and (x, row) not in label_cells:
                    available += 1
                    x += direction
                slots.append((available, direction, row))
        available, direction, label_y = max(slots, default=(0, 1, marker_y))
        label_width = min(10, available)
        if label_width < 3:
            continue
        name = ascii_only(system.name)
        if len(name) > label_width:
            name = name[:label_width - 1] + "~"
        start_x = marker_x + 1 if direction > 0 else marker_x - len(name)
        for offset, character in enumerate(name):
            x = start_x + offset
            canvas.put(x, label_y, character, Style(color="#aaddaa"))
            label_cells.add((x, label_y))

    header = Text(" GALAXY MAP ", style=Style(color="#e8b84a", bold=True))
    header.append(f"{current_name}  zoom {zoom:.2f}x\n", style=Style(color="#aaccee"))
    header.append(
        f"@=here +=open gate .=hyperlane O={hole_name} N=nebula\n",
        style=Style(color="#668899"),
    )
    for line in gate_lines:
        header.append(line + "\n", style=Style(color="#88ffaa", bold=True))
    header.append(canvas.to_text())
    return header
