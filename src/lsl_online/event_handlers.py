"""Register gameplay listeners on the event bus."""

from __future__ import annotations

import random

from eve_ascii import combat, mining
from eve_ascii.events import ENTERED_SYSTEM
from eve_ascii.models import GameMode, GameState, ShipStatus, TutorialStep

PIRATE_ENCOUNTER_CHANCE = 0.25


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
    if any(n.alive for n in state.npc_ships):
        return
    if random.random() >= PIRATE_ENCOUNTER_CHANCE:
        return
    count = random.choice((1, 2))
    combat.spawn_pirates(state, count)
    state.mode = GameMode.COMBAT
    state.log(f"WARNING: hostile contact in {system_name}.")


def bootstrap_events(state: GameState) -> None:
    state.bus.on(ENTERED_SYSTEM, lambda **kw: _on_entered_system(state, **kw))
