"""Travel rules, ETA, dock/undock."""

from __future__ import annotations

from lsl_online.galaxy import (
    find_planet,
    find_station,
    find_system_by_name,
    planet_position,
    station_position,
)
from lsl_online.models import (
    GameState,
    ShipLocation,
    ShipStatus,
    TravelTarget,
    Vec3,
)


DOCK_RANGE = 200.0
ORBIT_OFFSET = 15.0


def _begin_transit(state: GameState, *, hyperspace: bool) -> None:
    from lsl_online import combat, mining
    from lsl_online.models import GameMode

    mining.cease_mining(state)
    combat.exit_combat_for_transit(state)
    if hyperspace:
        state.mode = GameMode.HYPERSPACE


def current_ship_coords(state: GameState) -> Vec3:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        return ship.location.coords
    if ship.location.kind == "docked" and ship.location.station_id:
        for st in sys.stations:
            if st.id == ship.location.station_id:
                return station_position(sys, st)
    if ship.location.kind == "orbit" and ship.location.planet_id:
        for p in sys.planets:
            if p.id == ship.location.planet_id:
                pos = planet_position(p)
                return Vec3(pos.x + ORBIT_OFFSET, pos.y, pos.z)
    return ship.location.coords


_current_coords = current_ship_coords


def _set_warp(state: GameState, target: TravelTarget, dest: Vec3) -> str | None:
    ship = state.player.ship
    if ship.status == ShipStatus.DOCKED:
        return "Undock first."
    if ship.status in (ShipStatus.WARPING, ShipStatus.JUMPING):
        return "Already in transit."
    start = _current_coords(state)
    dist = start.distance_to(dest)
    if dist < 1.0:
        _arrive_at_target(state, target, dest)
        return None
    from lsl_online.vfx import trigger_flash

    _begin_transit(state, hyperspace=False)
    ship.destination = target
    ship.eta_seconds = dist / ship.warp_speed
    ship.transit_total_seconds = ship.eta_seconds
    ship.status = ShipStatus.WARPING
    trigger_flash(state)
    state.log(f"Warping to {target.label} ({ship.eta_seconds:.1f}s)")
    from lsl_online.audio import request_sound

    request_sound(state, "warp")
    return None


def travel_coords(state: GameState, x: float, y: float) -> str | None:
    ship = state.player.ship
    target = TravelTarget(
        kind="coords",
        system_id=ship.location.system_id,
        coords=Vec3(x, y, 0.0),
        label=f"({x:.0f}, {y:.0f})",
    )
    return _set_warp(state, target, Vec3(x, y, 0.0))


def travel_direction(state: GameState, direction: str, units: float) -> str | None:
    if units <= 0:
        return "Travel distance must be greater than zero."
    start = current_ship_coords(state)
    offsets = {
        "up": (0.0, -units),
        "right": (units, 0.0),
        "down": (0.0, units),
        "left": (-units, 0.0),
    }
    if direction not in offsets:
        return "Direction must be up, right, down, or left."
    dx, dy = offsets[direction]
    return travel_coords(state, start.x + dx, start.y + dy)


def travel_planet(state: GameState, planet_name: str) -> str | None:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        return "Unknown system."
    planet = find_planet(sys, planet_name)
    if not planet:
        return f"Planet not found: {planet_name}"
    pos = planet_position(planet)
    orbit = Vec3(pos.x + ORBIT_OFFSET, pos.y, pos.z)
    target = TravelTarget(
        kind="planet",
        system_id=sys.id,
        planet_id=planet.id,
        coords=orbit,
        label=f"orbit {planet.name}",
    )
    return _set_warp(state, target, orbit)


def travel_station(state: GameState, station_name: str) -> str | None:
    ship = state.player.ship
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        return "Unknown system."
    st = find_station(sys, station_name)
    if not st:
        return f"Station not found: {station_name}"
    pos = station_position(sys, st)
    approach = Vec3(pos.x + 40, pos.y, pos.z)
    target = TravelTarget(
        kind="station",
        system_id=sys.id,
        station_id=st.id,
        coords=approach,
        label=st.name,
    )
    return _set_warp(state, target, approach)


def _sync_nav_path_after_jump(state: GameState, dest_id: str) -> None:
    if not state.nav_path:
        return
    if state.nav_path[0] == dest_id:
        state.nav_path.pop(0)
    elif dest_id in state.nav_path:
        idx = state.nav_path.index(dest_id)
        state.nav_path = state.nav_path[idx + 1 :]
    if not state.nav_path:
        state.nav_path_goal = None


def jump_system(state: GameState, system_name: str | None = None) -> str | None:
    from lsl_online.models import GameMode
    from lsl_online.vfx import trigger_flash

    ship = state.player.ship
    if state.mode == GameMode.HYPERSPACE and ship.status != ShipStatus.IDLE:
        return "Cannot jump manually during hyperspace transit."
    if ship.status == ShipStatus.DOCKED:
        err = undock(state)
        if err:
            return err
    if ship.status in (ShipStatus.WARPING, ShipStatus.JUMPING):
        return "Already in transit."
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        return "Unknown current system."
    if not system_name or not system_name.strip():
        if not state.nav_path:
            return "Usage: jump <system> (or path <system> then jump)"
        next_sys = state.galaxy.get_system(state.nav_path[0])
        if not next_sys:
            state.nav_path.clear()
            state.nav_path_goal = None
            return "Navigation path invalid — replot with path <system>."
        system_name = next_sys.name
    dest = find_system_by_name(state.galaxy, system_name)
    if not dest:
        return f"System not found: {system_name}"
    if dest.id not in sys.neighbors:
        return f"No stargate link to {dest.name}."
    if ship.fuel < ship.fuel_per_jump:
        return f"Not enough fuel (need {ship.fuel_per_jump:.0f}, have {ship.fuel:.0f})."
    _begin_transit(state, hyperspace=True)
    ship.fuel -= ship.fuel_per_jump
    state.pending_jump_from_id = sys.id
    _sync_nav_path_after_jump(state, dest.id)
    state.map_view = "system"
    state.station_view = "system"
    dist = sys.position.distance_to(dest.position)
    target = TravelTarget(
        kind="system",
        system_id=dest.id,
        label=dest.name,
    )
    ship.destination = target
    ship.eta_seconds = dist / ship.jump_speed
    ship.transit_total_seconds = max(ship.eta_seconds, 0.01)
    ship.status = ShipStatus.JUMPING
    state.hyperspace_particles.clear()
    trigger_flash(state)
    state.log(f"Jumping to {dest.name} ({ship.eta_seconds:.1f}s)")
    from lsl_online.audio import request_sound

    request_sound(state, "jump")
    return None


def dock(state: GameState) -> str | None:
    ship = state.player.ship
    if ship.status == ShipStatus.DOCKED:
        return "Already docked."
    if ship.status in (ShipStatus.WARPING, ShipStatus.JUMPING):
        return "Cannot dock while in transit."
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        return "Unknown system."
    here = _current_coords(state)
    best = None
    best_d = DOCK_RANGE
    for st in sys.stations:
        pos = station_position(sys, st)
        d = here.distance_to(pos)
        if d < best_d:
            best_d = d
            best = st
    if not best:
        return "No station in docking range."
    ship.location = ShipLocation(
        system_id=sys.id,
        kind="docked",
        coords=station_position(sys, best),
        station_id=best.id,
    )
    ship.status = ShipStatus.DOCKED
    ship.destination = None
    ship.eta_seconds = 0.0
    state.station_view = "market"
    state.log(f"Docked at {best.name}")
    from lsl_online.quests import note_docked

    note_docked(state)
    return None


def undock(state: GameState) -> str | None:
    ship = state.player.ship
    if ship.status != ShipStatus.DOCKED:
        return "Not docked."
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys or not ship.location.station_id:
        return "Cannot undock."
    st = next((x for x in sys.stations if x.id == ship.location.station_id), None)
    if not st:
        return "Station missing."
    pos = station_position(sys, st)
    ship.location = ShipLocation(
        system_id=sys.id,
        kind="space",
        coords=Vec3(pos.x + 60, pos.y, pos.z),
        station_id=None,
        planet_id=None,
    )
    ship.status = ShipStatus.IDLE
    state.log(f"Undocked from {st.name}")
    return None


def _arrive_at_target(state: GameState, target: TravelTarget, dest: Vec3) -> None:
    from lsl_online.models import GameMode

    ship = state.player.ship
    if target.kind == "system":
        dest_sys = state.galaxy.get_system(target.system_id)
        if dest_sys:
            ship.location = ShipLocation(
                system_id=dest_sys.id,
                kind="space",
                coords=Vec3(0.0, 0.0, 0.0),
            )
            state.player.system_id = dest_sys.id
            state.log(f"Arrived in {dest_sys.name}")
            from lsl_online.combat import enter_system

            enter_system(state, dest_sys)
            for nebula in state.galaxy.nebulae:
                if dest_sys.id in nebula.system_ids:
                    state.log(f"Nebula {nebula.name} envelops this system.")
            state.hyperspace_particles.clear()
            from lsl_online.vfx import trigger_flash

            trigger_flash(state)
            state.hyperspace_landing_timer = 0.45
            from lsl_online.events import ENTERED_SYSTEM

            state.bus.emit(
                ENTERED_SYSTEM,
                system_id=dest_sys.id,
                system_name=dest_sys.name,
            )
            from lsl_online.quests import note_jump_arrived

            note_jump_arrived(state, dest_sys.id, state.pending_jump_from_id)
            state.pending_jump_from_id = None
    elif target.kind == "planet" and target.planet_id:
        system = state.galaxy.get_system(target.system_id)
        planet = next(
            (item for item in system.planets if item.id == target.planet_id),
            None,
        ) if system else None
        ship.location = ShipLocation(
            system_id=target.system_id,
            kind="orbit",
            coords=dest,
            planet_id=target.planet_id,
        )
        details = ""
        if planet:
            moon = f", moon {planet.moon.name} ({planet.moon.size})" if planet.moon else ""
            details = f" [{planet.size} {planet.planet_type}{moon}]"
        state.log(f"In orbit: {target.label}{details}")
    elif target.kind == "station" and target.station_id:
        ship.location = ShipLocation(
            system_id=target.system_id,
            kind="space",
            coords=dest,
            station_id=target.station_id,
        )
        state.log(f"Near {target.label}")
    else:
        ship.location = ShipLocation(
            system_id=target.system_id,
            kind="space",
            coords=dest,
        )
        state.log(f"Arrived at {target.label}")
    ship.status = ShipStatus.IDLE
    ship.destination = None
    ship.eta_seconds = 0.0


def tick(state: GameState, dt: float) -> None:
    ship = state.player.ship
    if ship.status not in (ShipStatus.WARPING, ShipStatus.JUMPING):
        return
    if not ship.destination:
        ship.status = ShipStatus.IDLE
        return
    ship.eta_seconds -= dt
    if ship.eta_seconds > 0:
        return
    target = ship.destination
    if target.kind == "system":
        dest_sys = state.galaxy.get_system(target.system_id)
        if dest_sys:
            _arrive_at_target(
                state,
                target,
                Vec3(0.0, 0.0, 0.0),
            )
        return
    dest = target.coords or Vec3(0.0, 0.0, 0.0)
    _arrive_at_target(state, target, dest)


def new_game(galaxy, *, with_tutorial: bool = True) -> GameState:
    from lsl_online.models import Galaxy, Player, Ship
    from lsl_online.space_render import init_background_stars
    from lsl_online.tutorial import init_tutorial, skip_tutorial
    from lsl_online.market import starter_cargo

    assert isinstance(galaxy, Galaxy)
    start = next(iter(galaxy.systems.values()))
    ship = Ship(
        name="Venture",
        location=ShipLocation(
            system_id=start.id,
            kind="space",
            coords=Vec3(0.0, 0.0, 0.0),
        ),
        fuel=100.0,
        max_fuel=100.0,
        fuel_per_jump=1.0,
        cargo=starter_cargo(),
    )

    player = Player(ship=ship, system_id=start.id)
    state = GameState(galaxy=galaxy, player=player)
    init_background_stars(state)
    from lsl_online.event_handlers import bootstrap_events

    bootstrap_events(state)
    from lsl_online.market import ensure_station_wallets, ensure_tutorial_station_credits

    ensure_station_wallets(state)
    if with_tutorial:
        ensure_tutorial_station_credits(state)
        init_tutorial(state)
    else:
        skip_tutorial(state)
    return state
