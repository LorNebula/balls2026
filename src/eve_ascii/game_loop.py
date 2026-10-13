"""Unity-style Start / Update game loop for tick systems."""

from __future__ import annotations

from abc import ABC, abstractmethod

from eve_ascii import automation, combat, market, mining, radar, ship as ship_sys, tutorial, travel, vfx
from eve_ascii.models import GameState
from eve_ascii.space_render import tick_star_scroll


class Behaviour(ABC):
    def start(self, state: GameState) -> None:
        pass

    @abstractmethod
    def update(self, state: GameState, dt: float) -> None:
        pass


class TutorialBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        tutorial.tick(state, dt)


class VfxBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        vfx.tick_flash(state, dt)
        tick_star_scroll(state, dt)
        combat.tick_hyperspace_vfx(state, dt)


class ShipBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        ship_sys.tick_all(state, dt)


class CombatBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        combat.tick(state, dt)


class TravelBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        travel.tick(state, dt)


class MiningBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        mining.tick(state, dt)


class RadarBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        radar.tick_radar(state, dt)


class MarketBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        market.tick(state, dt)


class AutomationBehaviour(Behaviour):
    def update(self, state: GameState, dt: float) -> None:
        automation.tick(state, dt)


def default_behaviours() -> list[Behaviour]:
    return [
        TutorialBehaviour(),
        VfxBehaviour(),
        ShipBehaviour(),
        CombatBehaviour(),
        TravelBehaviour(),
        MiningBehaviour(),
        RadarBehaviour(),
        MarketBehaviour(),
        AutomationBehaviour(),
    ]


class GameLoop:
    def __init__(self, state: GameState, behaviours: list[Behaviour] | None = None) -> None:
        self.state = state
        self.behaviours = behaviours if behaviours is not None else default_behaviours()
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        for behaviour in self.behaviours:
            behaviour.start(self.state)
        self._started = True

    def update(self, dt: float) -> None:
        if not self._started:
            self.start()
        if self.state.game_over:
            return
        for behaviour in self.behaviours:
            behaviour.update(self.state, dt)
