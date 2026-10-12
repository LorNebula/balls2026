from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from eve_ascii.models import GameState
from eve_ascii.space_render import render_ship_inspect


class ShipScreen(ModalScreen):
    """Zoomed ship view: hull components, health, shield, power."""

    BINDINGS = [
        Binding("escape", "close_ship", "Close", priority=True),
    ]

    def __init__(self, state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game_state = state

    def compose(self):
        yield Static("", id="ship_inspect")

    def on_mount(self) -> None:
        self.refresh_view()

    def refresh_view(self) -> None:
        self.query_one("#ship_inspect", Static).update(render_ship_inspect(self.game_state))

    def action_close_ship(self) -> None:
        self.app.pop_screen()
