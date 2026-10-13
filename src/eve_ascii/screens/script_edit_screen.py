from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static, TextArea

from eve_ascii.models import GameState


class ScriptEditScreen(Screen):
    """In-game editor for the sandboxed trade script."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game_state = state

    def compose(self) -> ComposeResult:
        yield Static(
            " Trade script — def trade(ctx): return orders | Ctrl+S save | Esc cancel ",
            id="script_edit_help",
        )
        yield TextArea(
            self.game_state.trade_script_source or automation_default_hint(),
            id="script_editor",
            language="python",
            show_line_numbers=True,
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def action_save(self) -> None:
        editor = self.query_one(TextArea)
        self.game_state.trade_script_source = editor.text
        self.game_state.log("Trade script saved.")
        self.app.pop_screen()
        screen = self.app.screen
        if hasattr(screen, "refresh_ui"):
            screen.refresh_ui()

    def action_cancel(self) -> None:
        self.app.pop_screen()


def automation_default_hint() -> str:
    from eve_ascii.automation import TUTORIAL_TRADE_TEMPLATE

    return TUTORIAL_TRADE_TEMPLATE
