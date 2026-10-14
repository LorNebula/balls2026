"""Scripted opening tutorial with pauses between beats."""

from __future__ import annotations

from lsl_online import combat
from lsl_online.comms import push_message
from lsl_online.galaxy import station_position
from lsl_online.models import GameMode, GameState, ShipStatus, TutorialStep, Vec3
from lsl_online.quests import unlock_quests
from lsl_online.vfx import trigger_flash

# Seconds to wait at each beat before the next event
PAUSE_HYPERSPACE = 5.0
PAUSE_AFTER_COMBAT = 4.0
TUTORIAL_MINE_UNITS = 3
PAUSE_AFTER_DOCK = 2.0
PAUSE_GALAXY = 5.0
PAUSE_QUESTS = 4.0


def _set_step(state: GameState, step: TutorialStep) -> None:
    state.tutorial_step = step
    state.tutorial_step_elapsed = 0.0


def log_tutorial(state: GameState, message: str) -> None:
    state.log(f"TUTORIAL: {message}")


def tutorial_awaiting_ready(state: GameState) -> bool:
    return state.tutorial_step in (TutorialStep.BRIEFING, TutorialStep.WARNING)


def ack_ready(state: GameState) -> str | None:
    step = state.tutorial_step
    if step == TutorialStep.BRIEFING:
        _begin_hyperspace_transit(state)
        return None
    if step == TutorialStep.WARNING:
        _begin_interdict(state)
        return None
    if step == TutorialStep.DONE:
        return "Tutorial is finished — nothing to confirm."
    return "No confirmation needed right now."


def _begin_hyperspace_transit(state: GameState) -> None:
    state.mode = GameMode.HYPERSPACE
    ship = state.player.ship
    ship.status = ShipStatus.JUMPING
    ship.fuel = ship.max_fuel
    trigger_flash(state)
    _set_step(state, TutorialStep.HYPERSPACE)
    log_tutorial(
        state,
        "Hyperspace transit started. Story continues in the event log — "
        "combat comes after the next briefing.",
    )


def _begin_interdict(state: GameState) -> None:
    trigger_flash(state)
    state.mode = GameMode.COMBAT
    state.player.ship.status = ShipStatus.IDLE
    state.log("INTERDICT: pulled from hyperspace!")
    combat.spawn_pirates(state, 2)
    _set_step(state, TutorialStep.COMBAT)
    state.combat_time = 0.0
    log_tutorial(
        state,
        "Combat: `lock A` then `fire`. Use `cease` to stop firing. "
        "`lock B` then `fire` for the second hostile.",
    )
    push_message(
        state,
        "CMDR Crosshair",
        "Hostiles on scope — letters match radar contacts. "
        "`lock <letter>` picks a target, `fire` shoots, `cease` stops. "
        "They hold fire ~9s; destroy both before your shields fail. "
        "Watch the log for HOSTILE HIT / shield status.",
    )


def _emit_opening_briefing(state: GameState) -> None:
    log_tutorial(
        state,
        "Welcome to LSL ONLINE — trade, mine, travel the galaxy, and take contracts.",
    )
    log_tutorial(
        state,
        "Type commands in the line at the bottom — it stays focused. "
        "The event log (right pane) shows combat, travel, and story text.",
    )
    log_tutorial(
        state,
        "Type `help` for commands, `comms` to re-read messages, `skip` for free play.",
    )
    log_tutorial(
        state,
        "Your current goal appears in the map header as obj: ...",
    )
    push_message(
        state,
        "CMDR Crosshair",
        "Pilot, this is Crosshair. You're hauling flagged cargo — "
        "pirates will come for it. I'll walk you through the basics first.",
    )
    log_tutorial(
        state,
        "COMBAT BASICS (read before we jump): hostiles show as letters on radar.",
    )
    log_tutorial(
        state,
        "`lock A` locks target A. `fire` enables weapons. `cease` stops firing "
        "(not the same as `cease mine` for asteroids).",
    )
    log_tutorial(
        state,
        "Hostiles wait ~9s before shooting — use that time to lock and fire. "
        "Shields absorb hits first; hull damage shows in the log.",
    )
    log_tutorial(
        state,
        "This tutorial WILL pull you into combat after hyperspace. "
        "When you've read the above, type `ready`.",
    )


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
    _set_step(state, TutorialStep.BRIEFING)
    state.tutorial_timer = 0.0
    state.tutorial_post_combat = False
    state.tutorial_jump_from_system = None
    state.tutorial_mined_units = 0
    state.tutorial_sell_done = False
    state.tutorial_upgraded_reactor = False
    state.tutorial_upgraded_weapons = False
    state.station_view = "hangar"
    state.mode = GameMode.SPACE
    state.player.ship.status = ShipStatus.IDLE
    state.player.ship.fuel = state.player.ship.max_fuel
    _emit_opening_briefing(state)


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
            "That cargo is flagged. Pirate cells are tracking your signature. "
            "Crosshair messages land in the event log — `comms` to review.",
        )
        log_tutorial(
            state,
            "Pirate interdict imminent. Re-read combat tips above if needed.",
        )
        log_tutorial(
            state,
            "When you're ready to be pulled out of hyperspace and fight, type `ready`.",
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
                log_tutorial(state, f"Next: `{cmd}`")
                push_message(
                    state,
                    "CMDR Crosshair",
                    f"Good work. Type `{cmd}`. "
                    "Jumps only work along stargate links to neighbor systems. "
                    "Use `path <system>` to plan a route; each jump costs fuel.",
                )
            else:
                log_tutorial(state, "Next: `jump <system>` (pick a linked system with a station)")
                push_message(
                    state,
                    "CMDR Crosshair",
                    "Good work. `jump <system>` to a linked neighbor with a station. "
                    "`path <system>` shows gate hops.",
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
            log_tutorial(
                state,
                "Next: `lock R1` then `mine` (`cease mine` stops the laser).",
            )
            push_message(
                state,
                "CMDR Crosshair",
                "Asteroids use codes like R1 on radar — `lock R1`, then `mine`. "
                "`cease mine` when switching targets. Cargo fills your hold; "
                f"pull at least {TUTORIAL_MINE_UNITS} units before we dock.",
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
                log_tutorial(state, f"Next: `{travel_cmd}` then `dock`")
                push_message(
                    state,
                    "CMDR Crosshair",
                    f"Good haul. `{travel_cmd}` burns you in; `dock` when within range. "
                    "Docked: `market`, `hangar`, `repair`, `undock`.",
                )
            else:
                log_tutorial(state, "Next: `travel station <name>` then `dock`")
                push_message(
                    state,
                    "CMDR Crosshair",
                    "`travel station <name>` then `dock`. Stations buy and sell cargo.",
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
            log_tutorial(
                state,
                "Next: `script` | set SELL_QTY=10 | Ctrl+S | `script run`",
            )
            push_message(
                state,
                "CMDR Crosshair",
                "Automation bay: `script` opens a Python trade bot. "
                "Set SELL_QTY=10, save (Ctrl+S), `script run` sells flagged cargo. "
                "`market` shows live prices; manual `sell` works too. "
                "Later: `script enable` runs every 60s; `script status` lists couriers.",
            )

    elif step == TutorialStep.SELL:
        if state.tutorial_sell_done:
            _set_step(state, TutorialStep.UPGRADE)
            log_tutorial(state, "Next: `upgrade reactor` then `upgrade weapons`")
            push_message(
                state,
                "CMDR Crosshair",
                "Credits on account. `market` lists stock and your cargo bids. "
                "`upgrade reactor` adds power hull; `upgrade weapons` adds damage. "
                "`repair` restores hull while docked if you took hits in combat.",
            )

    elif step == TutorialStep.UPGRADE:
        if state.tutorial_upgraded_reactor and state.tutorial_upgraded_weapons:
            _set_step(state, TutorialStep.GALAXY)
            state.tutorial_force_galaxy = False
            push_message(
                state,
                "CMDR Crosshair",
                "`galaxy` opens the star chart; `system` returns to local space. "
                "`zoom in` / `zoom out` adjust view. Green lines show your `path` route.",
            )
            log_tutorial(state, "Next: `galaxy` for the star chart, then `system` to return.")

    elif step == TutorialStep.GALAXY and state.tutorial_step_elapsed >= PAUSE_GALAXY:
        _set_step(state, TutorialStep.QUESTS)
        unlock_quests(state)
        log_tutorial(state, "Type `quests` — `quest start <id>` to take a contract.")
        push_message(
            state,
            "CMDR Crosshair",
            "Quest board unlocked. `quests` lists jobs; `quest start <id>` accepts one. "
            "Complete objectives for credits — kill, mine, trade, and travel contracts.",
        )

    elif step == TutorialStep.QUESTS and state.tutorial_step_elapsed >= PAUSE_QUESTS:
        _set_step(state, TutorialStep.DONE)
        state.tutorial_force_galaxy = False
        log_tutorial(
            state,
            "Tutorial complete. `help` = all commands. `script enable` = auto-trade every 60s.",
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
    log_tutorial(state, f"{st.name} on scope — `{f'travel station {st.name}'}` to approach.")


def tutorial_objective(state: GameState) -> str:
    step = state.tutorial_step
    if step == TutorialStep.BRIEFING:
        return "Read briefing in event log, then type ready"
    if step == TutorialStep.HYPERSPACE:
        return "Hyperspace transit (automatic)"
    if step == TutorialStep.WARNING:
        return "Read warning, then type ready for combat"
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
