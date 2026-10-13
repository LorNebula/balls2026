"""Scripted opening tutorial with pauses between beats."""

from __future__ import annotations

from eve_ascii import combat
from eve_ascii.comms import push_message
from eve_ascii.models import GameMode, GameState, ShipStatus, TutorialStep
from eve_ascii.quests import unlock_quests
from eve_ascii.vfx import trigger_flash

# Seconds to wait at each beat before the next event
PAUSE_HYPERSPACE = 5.0
PAUSE_WARNING = 5.0
PAUSE_AFTER_COMBAT = 4.0
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
            _set_step(state, TutorialStep.JUMP)
            state.tutorial_jump_from_system = state.player.system_id
            jump_target = _jump_target_name(state)
            if jump_target:
                cmd = f"jump {jump_target}"
                state.log(f"Next: type  {cmd}")
                push_message(
                    state,
                    "CMDR Crosshair",
                    f"Good work. Jump to a linked system. Open the command line and type: {cmd}",
                )
            else:
                state.log("Next: jump <system>  (pick a linked system)")
                push_message(
                    state,
                    "CMDR Crosshair",
                    "Good work. Jump to any linked system. Command: jump <system name>",
                )

    elif step == TutorialStep.JUMP:
        ship = state.player.ship
        origin = state.tutorial_jump_from_system
        jumped = (
            origin is not None
            and state.player.system_id != origin
            and ship.status == ShipStatus.IDLE
        )
        if jumped and state.tutorial_step_elapsed >= 1.0:
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


def _jump_target_name(state: GameState) -> str | None:
    sys = state.galaxy.get_system(state.player.system_id)
    if not sys or not sys.neighbors:
        return None
    other = state.galaxy.get_system(sys.neighbors[0])
    return other.name if other else None
