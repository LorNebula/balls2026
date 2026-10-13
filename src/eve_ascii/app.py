from __future__ import annotations

from pathlib import Path
from textual.app import App

from eve_ascii.ascii_ui import ascii_only
from eve_ascii.commands import execute_command
from eve_ascii.events import OPEN_SCRIPT_EDITOR, QUIT_APP
from eve_ascii.game_loop import GameLoop
from eve_ascii.galaxy import load_galaxy
from eve_ascii.models import GameState, ShipStatus
from eve_ascii.screens.map_screen import MapScreen
from eve_ascii.screens.script_edit_screen import ScriptEditScreen
from eve_ascii import audio, travel


class EveApp(App):
    TITLE = "EVE ASCII"
    CSS_PATH = Path(__file__).with_name("app.tcss")
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = []

    def __init__(self, game_state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game_state = game_state
        self.game_loop = GameLoop(game_state)

    def on_mount(self) -> None:
        self.game_state.bus.on(QUIT_APP, self._quit_from_command)
        self.game_state.bus.on(OPEN_SCRIPT_EDITOR, self._open_script_editor)
        self.game_loop.start()
        self.push_screen(MapScreen(self.game_state))
        self.set_interval(0.2, self.game_tick)
        self.refresh_sub_title()

    def _quit_from_command(self, **_payload) -> None:
        self.exit()

    def _open_script_editor(self, **_payload) -> None:
        self.push_screen(ScriptEditScreen(self.game_state))

    def game_tick(self) -> None:
        dt = 0.2
        self.game_loop.update(dt)
        screen = self.screen
        if isinstance(screen, MapScreen):
            screen.refresh_ui(refresh_command_line=False)
        self.refresh_sub_title()

    def refresh_sub_title(self) -> None:
        ship = self.game_state.player.ship
        sys = self.game_state.galaxy.get_system(ship.location.system_id)
        name = ascii_only(sys.name) if sys else "?"
        extra = ""
        if ship.status in (ShipStatus.WARPING, ShipStatus.JUMPING) and ship.destination:
            extra = f" -> {ascii_only(ship.destination.label)}"
        self.sub_title = (
            f"{name} | {self.game_state.mode.value} | {ship.status.value}{extra}"
        )

    def run_game_command(self, line: str) -> None:
        err = execute_command(self.game_state, line)
        if err:
            self.game_state.log(f"ERR: {err}")
        screen = self.screen
        if isinstance(screen, MapScreen):
            screen.refresh_ui()
        self.refresh_sub_title()


def run_app(*, with_tutorial: bool = True, sound_enabled: bool = True) -> None:
    galaxy = load_galaxy()
    state = travel.new_game(galaxy, with_tutorial=with_tutorial)
    state.sound_enabled = sound_enabled
    try:
        EveApp(state).run()
    finally:
        audio.shutdown()
