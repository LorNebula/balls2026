from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.app import App, SystemCommand
from textual.screen import Screen

from eve_ascii.commands import execute_command, palette_suggestions
from eve_ascii.galaxy import load_galaxy
from eve_ascii.models import GameState, ShipStatus
from eve_ascii.screens.map_screen import MapScreen
from eve_ascii import travel


class EveApp(App):
    TITLE = "EVE ASCII"
    CSS_PATH = Path(__file__).with_name("app.tcss")
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+p", "command_palette", "Commands"),
    ]

    def __init__(self, game_state: GameState) -> None:
        super().__init__()
        self.game_state = game_state

    def on_mount(self) -> None:
        self.push_screen(MapScreen(self.game_state))
        self.set_interval(0.2, self.game_tick)
        self.refresh_sub_title()

    def game_tick(self) -> None:
        travel.tick(self.game_state, 0.2)
        screen = self.screen
        if isinstance(screen, MapScreen):
            screen.refresh_ui()
        self.refresh_sub_title()

    def refresh_sub_title(self) -> None:
        ship = self.game_state.player.ship
        sys = self.game_state.galaxy.get_system(ship.location.system_id)
        name = sys.name if sys else "?"
        extra = ""
        if ship.status in (ShipStatus.WARPING, ShipStatus.JUMPING) and ship.destination:
            extra = f" -> {ship.destination.label}"
        self.sub_title = f"{name} | {ship.status.value}{extra}"

    def run_game_command(self, line: str) -> None:
        err = execute_command(self.game_state, line)
        if err:
            self.game_state.log(f"ERR: {err}")
        screen = self.screen
        if isinstance(screen, MapScreen):
            screen.refresh_ui()
        self.refresh_sub_title()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        for title, cmd in palette_suggestions(self.game_state):
            yield SystemCommand(
                title,
                cmd,
                lambda command=cmd: self.run_game_command(command),
                discover=title in ("Dock", "Undock"),
            )


def run_app() -> None:
    galaxy = load_galaxy()
    state = travel.new_game(galaxy)
    EveApp(state).run()
