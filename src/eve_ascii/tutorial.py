"""Scripted opening tutorial with pauses between beats."""

from __future__ import annotations

from eve_ascii import combat
from eve_ascii.comms import push_message
from eve_ascii.galaxy import station_position
from eve_ascii.market import TUTORIAL_CARGO_ID
from eve_ascii.models import GameMode, GameState, ShipStatus, TutorialStep, Vec3
from eve_ascii.quests import unlock_quests
from eve_ascii.vfx import trigger_flash

# Seconds to wait at each beat before the next event
PAUSE_HYPERSPACE = 5.0
PAUSE_WARNING = 5.0
PAUSE_AFTER_COMBAT = 4.0
TUTORIAL_MINE_UNITS = 3
PAUSE_AFTER_DOCK = 2.0
PAUSE_GALAXY = 5.0
PAUSE_QUESTS = 4.0


def _set_step(state: GameState, step: TutorialStep) -> None:
    state.tutorial_step = step
    state.tutorial_step_elapsed = 0.0


def skip_tutorial(state: GameState) -> None:
    """Free play: no scripted opening, quests available immediately."""
    _set_step(state, TutorialStep.DONE)
    state.tutorial_force_galaxy = False
    state.mode = GameMode.SPACE
    ship = state.player.ship
    ship.status = ShipStatus.IDLE
    ship.destination = None
    ship.eta_seconds = 0.0
    ship.weapons_active = False
    ship.target_letter = None
    ship.subtarget = None
    state.npc_ships.clear()
    state.projectiles.clear()
    state.explosions.clear()
    state.hyperspace_particles.clear()
    unlock_quests(state)
    from eve_ascii import mining

    mining.fill_asteroid_field(state)
    state.log("Tutorial skipped. Free play.")


def init_tutorial(state: GameState) -> None:
    _set_step(state, TutorialStep.HYPERSPACE)
    state.tutorial_timer = 0.0
    state.tutorial_post_combat = False
    state.tutorial_jump_from_system = None
    state.tutorial_mined_units = 0
    state.tutorial_sell_done = False
    state.tutorial_upgraded_reactor = False
    state.tutorial_upgraded_weapons = False
    state.station_view = "hangar"
    state.mode = GameMode.HYPERSPACE
    state.player.ship.status = ShipStatus.JUMPING
    state.player.ship.fuel = state.player.ship.max_fuel
    trigger_flash(state)
    state.log("TUTORIAL: entering hyperspace lane...")


def tick(state: GameState, dt: float) -> None:
    if state.tutorial_step == TutorialStep.DONE:
        return
    state.tutorial_timer += dt
    state.tutorial_step_elapsed += dt
    step = state.tutorial_step

    if step == TutorialStep.HYPERSPACE and state.tutorial_step_elapsed >= PAUSE_HYPERSPACE:
        _set_step(state, TutorialStep.WARNING)
        push_message(
            state,
            "CMDR Crosshair",
            "Pilot, this is Crosshair. That cargo is flagged. Pirate cells are "
            "tracking your signature. Stay alert. Acknowledge.",
        )

    elif step == TutorialStep.WARNING and state.tutorial_step_elapsed >= PAUSE_WARNING:
        trigger_flash(state)
        state.mode = GameMode.COMBAT
        state.player.ship.status = ShipStatus.IDLE
        state.log("INTERDICT: pulled from hyperspace!")
        combat.spawn_pirates(state, 2)
        _set_step(state, TutorialStep.COMBAT)
        state.combat_time = 0.0
        state.log("Two hostiles (A, B). lock A | lock A 01 | fire | lock B | fire")
        push_message(state, "CMDR Crosshair", "Engage hostiles. Weapons free.")

    elif step == TutorialStep.COMBAT:
        if combat.all_hostiles_dead(state) and not state.tutorial_post_combat:
            state.tutorial_post_combat = True
            state.tutorial_step_elapsed = 0.0
            state.player.ship.weapons_active = False
            state.log("Combat cleared.")
        elif state.tutorial_post_combat and state.tutorial_step_elapsed >= PAUSE_AFTER_COMBAT:
            state.mode = GameMode.SPACE
            _set_step(state, TutorialStep.JUMP_STATION)
            state.tutorial_jump_from_system = state.player.system_id
            jump_target = _station_jump_target_name(state)
            if jump_target:
                cmd = f"jump {jump_target}"
                state.log(f"Next: type  {cmd}")
                push_message(
                    state,
                    "CMDR Crosshair",
                    f"Good work. Jump to a station system. Open the command line and type: {cmd}",
                )
            else:
                state.log("Next: jump <system>  (pick a linked system with a station)")
                push_message(
                    state,
                    "CMDR Crosshair",
                    "Good work. Jump to a linked system with a station. Command: jump <system name>",
                )

    elif step == TutorialStep.JUMP_STATION:
        ship = state.player.ship
        origin = state.tutorial_jump_from_system
        jumped = (
            origin is not None
            and state.player.system_id != origin
            and ship.status == ShipStatus.IDLE
        )
        if jumped and state.tutorial_step_elapsed >= 1.0:
            from eve_ascii import mining

            _set_step(state, TutorialStep.MINE)
            mining.fill_tutorial_mining_field(state)
            state.log("Next: lock R1  then  mine  (cease mine when done)")
            push_message(
                state,
                "CMDR Crosshair",
                "Local belt on scope. Lock an asteroid (lock R1) and run the mining laser (mine). "
                f"Pull at least {TUTORIAL_MINE_UNITS} units before we sell at the station.",
            )

    elif step == TutorialStep.MINE:
        if state.tutorial_mined_units >= TUTORIAL_MINE_UNITS:
            from eve_ascii import mining

            mining.cease_mining(state)
            _set_step(state, TutorialStep.DOCK)
            _tutorial_place_near_station(state)
            station = _first_station_name(state)
            if station:
                travel_cmd = f"travel station {station}"
                dock_cmd = "dock"
                state.log(f"Next: {travel_cmd}  then  {dock_cmd}")
                push_message(
                    state,
                    "CMDR Crosshair",
                    f"Good haul. Dock and sell. Type: {travel_cmd}  then when in range: {dock_cmd}",
                )
            else:
                state.log("Next: travel station <name>  then  dock")
                push_message(
                    state,
                    "CMDR Crosshair",
                    "Dock at the station. travel station <name>  then  dock",
                )

    elif step == TutorialStep.DOCK:
        if (
            state.player.ship.status == ShipStatus.DOCKED
            and state.tutorial_step_elapsed >= PAUSE_AFTER_DOCK
        ):
            _set_step(state, TutorialStep.SELL)
            state.station_view = "inventory"
            sell_cmd = f"sell {TUTORIAL_CARGO_ID} 10"
            state.log(f"Next: inventory  then  {sell_cmd}")
            push_message(
                state,
                "CMDR Crosshair",
                f"Unload that flagged cargo. Type: inventory  then  {sell_cmd}",
            )

    elif step == TutorialStep.SELL:
        if state.tutorial_sell_done:
            _set_step(state, TutorialStep.UPGRADE)
            state.log("Next: upgrade reactor  then  upgrade weapons")
            push_message(
                state,
                "CMDR Crosshair",
                "Credits on account. Upgrade reactor and weapons: "
                "upgrade reactor  then  upgrade weapons",
            )

    elif step == TutorialStep.UPGRADE:
        if state.tutorial_upgraded_reactor and state.tutorial_upgraded_weapons:
            _set_step(state, TutorialStep.GALAXY)
            state.tutorial_force_galaxy = True
            push_message(
                state,
                "CMDR Crosshair",
                "Solid execution, pilot. The sector is yours. Find your destiny.",
            )
            state.log("Press g for galaxy map.")

    elif step == TutorialStep.GALAXY and state.tutorial_step_elapsed >= PAUSE_GALAXY:
        _set_step(state, TutorialStep.QUESTS)
        unlock_quests(state)
        state.log("Type: quests")

    elif step == TutorialStep.QUESTS and state.tutorial_step_elapsed >= PAUSE_QUESTS:
        _set_step(state, TutorialStep.DONE)
        state.tutorial_force_galaxy = False
        state.log("Tutorial complete. Free play.")


def _station_jump_target_name(state: GameState) -> str | None:
    sys = state.galaxy.get_system(state.player.system_id)
    if not sys:
        return None
    for nid in sys.neighbors:
        other = state.galaxy.get_system(nid)
        if other and other.stations:
            return other.name
    if sys.neighbors:
        other = state.galaxy.get_system(sys.neighbors[0])
        if other:
            return other.name
    return None


def _first_station_name(state: GameState) -> str | None:
    sys = state.galaxy.get_system(state.player.system_id)
    if sys and sys.stations:
        return sys.stations[0].name
    return None


def _tutorial_place_near_station(state: GameState) -> None:
    """After jump, spawn within docking range of the first station."""
    sys = state.galaxy.get_system(state.player.system_id)
    if not sys or not sys.stations:
        return
    st = sys.stations[0]
    pos = station_position(sys, st)
    state.player.ship.location.coords = Vec3(pos.x + 95.0, pos.y + 5.0, pos.z)
    state.log(f"{st.name} on scope - burn in with travel station {st.name}")


def tutorial_objective(state: GameState) -> str:
    step = state.tutorial_step
    if step == TutorialStep.HYPERSPACE:
        return "Hold course in hyperspace"
    if step == TutorialStep.WARNING:
        return "Read CMDR Crosshair comms"
    if step == TutorialStep.COMBAT:
        return "Destroy hostiles (lock, fire)"
    if step == TutorialStep.JUMP_STATION:
        return "Jump to a system with a station"
    if step == TutorialStep.MINE:
        return f"Mine ore into hold ({state.tutorial_mined_units}/{TUTORIAL_MINE_UNITS})"
    if step == TutorialStep.DOCK:
        return "Travel to station and dock"
    if step == TutorialStep.SELL:
        return f"Sell flagged cargo (sell {TUTORIAL_CARGO_ID})"
    if step == TutorialStep.UPGRADE:
        return "Upgrade reactor and weapons at station"
    if step == TutorialStep.GALAXY:
        return "Open galaxy map (g)"
    if step == TutorialStep.QUESTS:
        return "Type: quests"
    return ""
