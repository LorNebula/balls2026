"""Screen flash and ambient VFX timing."""

from __future__ import annotations

from lsl_online.models import GameState

FLASH_DURATION = 0.45


def trigger_flash(state: GameState, duration: float = FLASH_DURATION) -> None:
    state.screen_flash = max(state.screen_flash, duration)


def tick_flash(state: GameState, dt: float) -> None:
    if state.screen_flash > 0:
        state.screen_flash = max(0.0, state.screen_flash - dt)
