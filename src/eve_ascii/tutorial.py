"""Scripted opening tutorial with pauses between beats."""

from __future__ import annotations

from eve_ascii import combat, travel
from eve_ascii.comms import push_message
from eve_ascii.models import GameMode, GameState, ShipStatus, TutorialStep
from eve_ascii.quests import unlock_quests

# Seconds to wait at each beat before the next event
PAUSE_HYPERSPACE = 5.0
PAUSE_WARNING = 5.0
PAUSE_AFTER_COMBAT = 4.0
PAUSE_AFTER_JUMP = 4.0
PAUSE_GALAXY = 5.0
PAUSE_QUESTS = 4.0


def _set_step(state: GameState, step: TutorialStep) -> None:
    state.tutorial_step = step
    state.tutorial_step_elapsed = 0.0


def init_tutorial(state: GameState) -> None:
    _set_step(state, TutorialStep.HYPERSPACE)
    state.tutorial_timer = 0.0
    state.tutorial_post_combat = False
    state.mode = GameMode.HYPERSPACE
    state.player.ship.status = ShipStatus.JUMPING
    state.player.ship.fuel = state.player.ship.max_fuel
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
        state.mode = GameMode.COMBAT
        state.player.ship.status = ShipStatus.IDLE
        state.log("INTERDICT: pulled from hyperspace!")
        combat.spawn_pirates(state, 1)
        _set_step(state, TutorialStep.COMBAT)
        state.combat_time = 0.0
        state.log("Hostile hull on scope. Components 01-04 on the hull. lock A / lock A 01")
        push_message(state, "CMDR Crosshair", "Engage hostiles. Weapons free.")

    elif step == TutorialStep.COMBAT:
        resolved = combat.all_hostiles_dead(state) or state.combat_time >= 18.0
        if resolved and not state.tutorial_post_combat:
            state.tutorial_post_combat = True
            state.tutorial_step_elapsed = 0.0
            state.player.ship.weapons_active = False
            state.log("Combat cleared.")
            push_message(
                state,
                "CMDR Crosshair",
                "Good work. Jump to the nearest station system.",
            )
        elif state.tutorial_post_combat and state.tutorial_step_elapsed >= PAUSE_AFTER_COMBAT:
            state.mode = GameMode.SPACE
            _set_step(state, TutorialStep.JUMP_STATION)
            _auto_jump_to_station_system(state)
            state.log("Plotting jump to station system...")

    elif step == TutorialStep.JUMP_STATION:
        ship = state.player.ship
        if ship.status not in (ShipStatus.JUMPING, ShipStatus.WARPING):
            if state.tutorial_step_elapsed >= PAUSE_AFTER_JUMP:
                _set_step(state, TutorialStep.GALAXY)
                state.tutorial_force_galaxy = True
                push_message(
                    state,
                    "CMDR Crosshair",
                    "Solid execution, pilot. The sector is yours. Find your destiny.",
                )

    elif step == TutorialStep.GALAXY and state.tutorial_step_elapsed >= PAUSE_GALAXY:
        _set_step(state, TutorialStep.QUESTS)
        unlock_quests(state)

    elif step == TutorialStep.QUESTS and state.tutorial_step_elapsed >= PAUSE_QUESTS:
        _set_step(state, TutorialStep.DONE)
        state.tutorial_force_galaxy = False
        state.log("Tutorial complete. Free play.")


def _auto_jump_to_station_system(state: GameState) -> None:
    sys = state.galaxy.get_system(state.player.system_id)
    if not sys:
        return
    for nid in sys.neighbors:
        other = state.galaxy.get_system(nid)
        if other and other.stations:
            travel.jump_system(state, other.name)
            state.player.ship.eta_seconds = min(state.player.ship.eta_seconds, 3.0)
            return
    if sys.neighbors:
        other = state.galaxy.get_system(sys.neighbors[0])
        if other:
            travel.jump_system(state, other.name)
            state.player.ship.eta_seconds = min(state.player.ship.eta_seconds, 3.0)
