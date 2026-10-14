"""Register gameplay listeners on the event bus."""

from __future__ import annotations

import random

from lsl_online import combat, mining
from lsl_online.events import ENTERED_SYSTEM
from lsl_online.galaxy import system_rim_tier
from lsl_online.models import GameMode, GameState, ShipStatus, TutorialStep
from lsl_online.quests import bounty_kills_remaining_in_system


def _on_entered_system(state: GameState, *, system_id: str, system_name: str) -> None:
    if state.tutorial_step == TutorialStep.DONE:
        mining.fill_asteroid_field(state)
    if state.tutorial_step != TutorialStep.DONE:
        return
    ship = state.player.ship
    if ship.status == ShipStatus.DOCKED:
        return
    if state.mode in (GameMode.COMBAT, GameMode.HYPERSPACE):
        return
    if any(n.alive and n.hostile for n in state.npc_ships):
        return

    bounty_remaining = bounty_kills_remaining_in_system(state, system_id)
    if bounty_remaining > 0:
        spawn_count = min(bounty_remaining, 4)
        combat.spawn_pirates_for_system(state, system_id, min_count=spawn_count)
        state.mode = GameMode.COMBAT
        state.log(
            f"BOUNTY: {spawn_count} hostile(s) on scope in {system_name} "
            f"({bounty_remaining} kill(s) needed on contract)."
        )
        return

    rim = system_rim_tier(state.galaxy, system_id)
    encounter_chance = 0.25 + 0.40 * rim
    if random.random() >= encounter_chance:
        return
    combat.spawn_pirates_for_system(state, system_id)
    state.mode = GameMode.COMBAT
    state.log(f"WARNING: hostile contact in {system_name}.")


def bootstrap_events(state: GameState) -> None:
    state.bus.on(ENTERED_SYSTEM, lambda **kw: _on_entered_system(state, **kw))
