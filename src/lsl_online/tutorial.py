"""Scripted opening tutorial with pauses between beats."""

from __future__ import annotations

from lsl_online import combat
from lsl_online.comms import push_message
from lsl_online.galaxy import station_position
from lsl_online.market import TUTORIAL_CARGO_ID
from lsl_online.models import GameMode, GameState, ShipStatus, TutorialStep, Vec3
from lsl_online.quests import unlock_quests
from lsl_online.vfx import trigger_flash

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
    from lsl_online import mining

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
    state.log("TUTORIAL: entering hyperspace lane... (: = command line, help = commands)")


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
            "tracking your signature. Stay alert. Crosshair messages appear in the "
            "event log (right pane). Type comms to review.",
        )

    elif step == TutorialStep.WARNING and state.tutorial_step_elapsed >= PAUSE_WARNING:
        trigger_flash(state)
        state.mode = GameMode.COMBAT
        state.player.ship.status = ShipStatus.IDLE
        state.log("INTERDICT: pulled from hyperspace!")
        combat.spawn_pirates(state, 2)
        _set_step(state, TutorialStep.COMBAT)
        state.combat_time = 0.0
        state.log("Combat: lock A | fire | cease (stop firing) | lock B | fire")
        push_message(
            state,
            "CMDR Crosshair",
            "Engage hostiles. Press : for commands. lock <target>, fire to shoot, "
            "cease to stop. Hostiles hold fire ~9s — use that window.",
        )

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
                    f"Good work. Press : then type: {cmd}  "
                    "(jump only works to linked stargate systems).",
                )
            else:
                state.log("Next: jump <system>  (pick a linked system with a station)")
                push_message(
                    state,
                    "CMDR Crosshair",
                    "Good work. Press : then jump <system name> to a linked system with a station.",
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
            from lsl_online import mining

            _set_step(state, TutorialStep.MINE)
            mining.fill_tutorial_mining_field(state)
            state.log("Next: lock R1  then  mine  (cease mine to stop laser)")
            push_message(
                state,
                "CMDR Crosshair",
                "Local belt on scope. lock R1, then mine. cease mine when switching targets. "
                f"Pull at least {TUTORIAL_MINE_UNITS} units into your hold before we dock.",
            )

    elif step == TutorialStep.MINE:
        if state.tutorial_mined_units >= TUTORIAL_MINE_UNITS:
            from lsl_online import mining

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
                    f"Good haul. Burn to the station: {travel_cmd}  then {dock_cmd} when in range.",
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
            from lsl_online.automation import TUTORIAL_TRADE_TEMPLATE

            _set_step(state, TutorialStep.SELL)
            state.trade_script_source = TUTORIAL_TRADE_TEMPLATE
            state.trade_script_enabled = False
            state.log("Next: script | set SELL_QTY=10 | Ctrl+S | script run")
            push_message(
                state,
                "CMDR Crosshair",
                "Automation bay online. script opens your trade bot (Python). "
                "Set SELL_QTY from 0 to 10, Ctrl+S to save, script run to sell flagged cargo now. "
                "Later: script enable runs the bot every 60s; script status shows couriers.",
            )

    elif step == TutorialStep.SELL:
        if state.tutorial_sell_done:
            _set_step(state, TutorialStep.UPGRADE)
            state.log("Next: upgrade reactor  then  upgrade weapons")
            push_message(
                state,
                "CMDR Crosshair",
                "Credits on account. market shows prices. upgrade reactor  then  upgrade weapons. "
                "repair restores hull for credits if you took damage.",
            )

    elif step == TutorialStep.UPGRADE:
        if state.tutorial_upgraded_reactor and state.tutorial_upgraded_weapons:
            _set_step(state, TutorialStep.GALAXY)
            state.tutorial_force_galaxy = False
            push_message(
                state,
                "CMDR Crosshair",
                "Solid execution, pilot. Type galaxy for the star chart, "
                "system for local map, zoom in|out to adjust view.",
            )
            state.log("Next: type galaxy to open the star chart, then system to return.")

    elif step == TutorialStep.GALAXY and state.tutorial_step_elapsed >= PAUSE_GALAXY:
        _set_step(state, TutorialStep.QUESTS)
        unlock_quests(state)
        state.log("Type: quests  (quest <name> to start one)")

    elif step == TutorialStep.QUESTS and state.tutorial_step_elapsed >= PAUSE_QUESTS:
        _set_step(state, TutorialStep.DONE)
        state.tutorial_force_galaxy = False
        state.log(
            "Tutorial complete. help = all commands. script enable = auto-trade every 60s."
        )


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
        return "Hyperspace transit (automatic)"
    if step == TutorialStep.WARNING:
        return "Read Crosshair in event log (comms)"
    if step == TutorialStep.COMBAT:
        return "Destroy hostiles: lock, fire, cease"
    if step == TutorialStep.JUMP_STATION:
        return "Jump to a linked system with a station"
    if step == TutorialStep.MINE:
        return f"lock R1, mine ({state.tutorial_mined_units}/{TUTORIAL_MINE_UNITS} units)"
    if step == TutorialStep.DOCK:
        return "travel station, then dock"
    if step == TutorialStep.SELL:
        return "script: SELL_QTY=10, save, script run"
    if step == TutorialStep.UPGRADE:
        return "upgrade reactor and weapons"
    if step == TutorialStep.GALAXY:
        return "Type galaxy to open star chart (system to return)"
    if step == TutorialStep.QUESTS:
        return "Type: quests"
    return ""
