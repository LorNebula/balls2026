"""System radar scan to event log."""

from __future__ import annotations

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.galaxy import planet_position, station_position
from eve_ascii.models import GameState
from eve_ascii.travel import current_ship_coords


def scan_system(state: GameState) -> None:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        state.log("RADAR: no system data.")
        return
    coords = current_ship_coords(state)
    state.log(f"RADAR sweep {ascii_only(sys.name)} | you @ ({coords.x:.0f}, {coords.y:.0f})")
    for p in sys.planets:
        pos = planet_position(p)
        state.log(f"RADAR planet {ascii_only(p.name)} id={p.id} @ ({pos.x:.0f}, {pos.y:.0f})")
    for st in sys.stations:
        pos = station_position(sys, st)
        state.log(f"RADAR station {ascii_only(st.name)} id={st.id} @ ({pos.x:.0f}, {pos.y:.0f})")
    for ast in state.asteroids:
        if not ast.alive:
            continue
        state.log(
            f"RADAR {ast.code} {ast.material_id} @ ({ast.position.x:.0f}, {ast.position.y:.0f}) "
            f"yld {ast.yield_left}"
        )
    for npc in state.npc_ships:
        if not npc.alive:
            continue
        state.log(
            f"RADAR ship {npc.letter} {ascii_only(npc.name)} @ "
            f"({npc.position.x:.0f}, {npc.position.y:.0f})"
        )
    if not sys.planets and not sys.stations and not any(a.alive for a in state.asteroids):
        state.log("RADAR: no contacts besides stellar body.")


def set_radar(state: GameState, active: bool) -> str | None:
    state.radar_active = active
    if active:
        state.radar_timer = 0.0
        scan_system(state)
        state.log("RADAR: ON (10s refresh)")
    else:
        state.log("RADAR: OFF")
    return None


def toggle_radar(state: GameState) -> str | None:
    return set_radar(state, not state.radar_active)


def tick_radar(state: GameState, dt: float) -> None:
    if not state.radar_active:
        return
    state.radar_timer += dt
    if state.radar_timer >= 10.0:
        state.radar_timer = 0.0
        scan_system(state)
