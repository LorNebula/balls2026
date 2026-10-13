"""Travel rules, ETA, dock/undock."""

from __future__ import annotations

from eve_ascii.galaxy import (
    find_planet,
    find_station,
    find_system_by_name,
    planet_position,
    station_position,
)
from eve_ascii.models import (
    GameState,
    ShipLocation,
    ShipStatus,
    TravelTarget,
    Vec3,
)


DOCK_RANGE = 120.0
ORBIT_OFFSET = 15.0


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
    ship.destination = target
    ship.eta_seconds = dist / ship.warp_speed
    ship.status = ShipStatus.WARPING
    state.log(f"Warping to {target.label} ({ship.eta_seconds:.1f}s)")
    return None


def travel_coords(state: GameState, x: float, y: float, z: float) -> str | None:
    ship = state.player.ship
    target = TravelTarget(
        kind="coords",
        system_id=ship.location.system_id,
        coords=Vec3(x, y, z),
        label=f"({x:.0f}, {y:.0f}, {z:.0f})",
    )
    return _set_warp(state, target, Vec3(x, y, z))


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


def jump_system(state: GameState, system_name: str) -> str | None:
    from eve_ascii.models import GameMode
    from eve_ascii.vfx import trigger_flash

    ship = state.player.ship
    if state.mode == GameMode.HYPERSPACE and ship.status != ShipStatus.IDLE:
        return "Cannot jump manually during hyperspace transit."
    if ship.status == ShipStatus.DOCKED:
        return "Undock first."
    if ship.status in (ShipStatus.WARPING, ShipStatus.JUMPING):
        return "Already in transit."
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        return "Unknown current system."
    dest = find_system_by_name(state.galaxy, system_name)
    if not dest:
        return f"System not found: {system_name}"
    if dest.id not in sys.neighbors:
        return f"No stargate link to {dest.name}."
    if ship.fuel < ship.fuel_per_jump:
        return f"Not enough fuel (need {ship.fuel_per_jump:.0f}, have {ship.fuel:.0f})."
    ship.fuel -= ship.fuel_per_jump
    dist = sys.position.distance_to(dest.position)
    target = TravelTarget(
        kind="system",
        system_id=dest.id,
        label=dest.name,
    )
    ship.destination = target
    ship.eta_seconds = dist / ship.jump_speed
    ship.status = ShipStatus.JUMPING
    state.mode = GameMode.HYPERSPACE
    state.hyperspace_particles.clear()
    trigger_flash(state)
    state.log(f"Jumping to {dest.name} ({ship.eta_seconds:.1f}s)")
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
    state.station_view = "hangar"
    state.log(f"Docked at {best.name}")
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
    from eve_ascii.models import GameMode

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
            from eve_ascii.combat import enter_system

            enter_system(state, dest_sys)
            for nebula in state.galaxy.nebulae:
                if dest_sys.id in nebula.system_ids:
                    state.log(f"Nebula {nebula.name} envelops this system.")
            state.hyperspace_particles.clear()
            from eve_ascii.events import ENTERED_SYSTEM

            state.bus.emit(
                ENTERED_SYSTEM,
                system_id=dest_sys.id,
                system_name=dest_sys.name,
            )
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
    from eve_ascii.models import Galaxy, Player, Ship
    from eve_ascii.space_render import init_background_stars
    from eve_ascii.tutorial import init_tutorial, skip_tutorial
    from eve_ascii.market import starter_cargo

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
    from eve_ascii.event_handlers import bootstrap_events

    bootstrap_events(state)
    if with_tutorial:
        init_tutorial(state)
    else:
        skip_tutorial(state)
    return state
