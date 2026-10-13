"""System radar: contacts on map, minimal event log."""

from __future__ import annotations

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.galaxy import station_position
from eve_ascii.models import GameState, RadarContact
from eve_ascii.travel import current_ship_coords


def _in_nebula(state: GameState, system_id: str) -> bool:
    return any(system_id in nebula.system_ids for nebula in state.galaxy.nebulae)


def _radar_interval(state: GameState) -> float:
    sys_id = state.player.ship.location.system_id
    return 20.0 if _in_nebula(state, sys_id) else 10.0


def _display_label(state: GameState, label: str) -> str:
    if _in_nebula(state, state.player.ship.location.system_id):
        return "???"
    return ascii_only(label)


def refresh_radar_contacts(state: GameState) -> None:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        state.radar_contacts = []
        return
    coords = current_ship_coords(state)
    contacts: list[RadarContact] = []
    contacts.append(
        RadarContact(
            label=_display_label(state, "Sun"),
            x=0.0,
            y=0.0,
            kind="sun",
        )
    )
    for st in sys.stations:
        pos = station_position(sys, st)
        contacts.append(
            RadarContact(
                label=_display_label(state, f"St {st.name}"),
                x=pos.x,
                y=pos.y,
                kind="station",
            )
        )
    for ast in state.asteroids:
        if not ast.alive:
            continue
        contacts.append(
            RadarContact(
                label=_display_label(state, f"{ast.code}"),
                x=ast.position.x,
                y=ast.position.y,
                kind="asteroid",
            )
        )
    for npc in state.npc_ships:
        if not npc.alive:
            continue
        contacts.append(
            RadarContact(
                label=_display_label(state, f"Ship {npc.letter}"),
                x=npc.position.x,
                y=npc.position.y,
                kind="ship",
            )
        )
    state.radar_contacts = contacts
    _ = coords


def set_radar(state: GameState, active: bool) -> str | None:
    state.radar_active = active
    if active:
        state.radar_timer = 0.0
        refresh_radar_contacts(state)
        interval = _radar_interval(state)
        state.log(f"RADAR: ON ({interval:.0f}s refresh, contacts on map)")
    else:
        state.radar_contacts.clear()
        state.log("RADAR: OFF")
    return None


def toggle_radar(state: GameState) -> str | None:
    return set_radar(state, not state.radar_active)


def tick_radar(state: GameState, dt: float) -> None:
    if not state.radar_active:
        return
    state.radar_timer += dt
    if state.radar_timer >= _radar_interval(state):
        state.radar_timer = 0.0
        refresh_radar_contacts(state)
