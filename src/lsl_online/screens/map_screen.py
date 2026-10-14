from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Input, Static

from lsl_online.ascii_ui import ascii_only, box_line
from lsl_online.command_completions import matching_completions
from lsl_online.models import GameState
from lsl_online.playfield import render_playfield, _combat_border_active
from lsl_online.screens.status_bar import format_status
from lsl_online.widgets.command_suggester import GameCommandSuggester


class MapScreen(Screen):
    """Main play screen: ASCII map + log + command line."""

    BINDINGS = [
        ("colon", "focus_cmd", "Cmd"),
    ]

    TITLE_WIDTH = 78

    def __init__(self, state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game_state = state
        self._chrome_view: str | None = None
        self._last_title_text: str | None = None
        self._command_history: list[str] = []
        self._history_index: int | None = None
        self._history_draft = ""

    def compose(self):
        yield Static("", id="title_bar")
        yield Static("", id="playfield")
        yield Static("", id="status_line")
        with Horizontal(id="cmd_row"):
            yield Static("> ", id="cmd_prefix")
            yield Input(
                placeholder="help | galaxy | script | travel | jump | dock | ready",
                id="cmd_input",
                classes="-textual-compact",
            )
        yield Static("", id="cmd_completions")
        yield Static("", id="footer_bar")

    def on_mount(self) -> None:
        inp = self.query_one("#cmd_input", Input)
        inp.suggester = GameCommandSuggester(lambda: self.game_state)
        self._refresh_chrome()
        self.refresh_ui()
        inp.focus()

    def _title_bar_text(self) -> str:
        view = self.game_state.map_view.upper()
        if _combat_border_active(self.game_state):
            return f" LSL ONLINE | map={view} | IN DANGER "
        return f" LSL ONLINE | map={view} "

    def _refresh_chrome(self) -> None:
        w = self.TITLE_WIDTH
        view = self.game_state.map_view.upper()
        if view != self._chrome_view:
            self._chrome_view = view
            self.query_one("#footer_bar", Static).update(
                box_line(
                    w,
                    " type commands below  up/down history  galaxy|system  zoom in|out  script  help  quit ",
                )
            )
        self._update_title_bar()

    def _update_title_bar(self) -> None:
        text = self._title_bar_text()
        if text == self._last_title_text:
            return
        self._last_title_text = text
        w = self.TITLE_WIDTH
        self.query_one("#title_bar", Static).update(box_line(w, text))

    def _playfield_size(self) -> tuple[int, int]:
        pf = self.query_one("#playfield", Static)
        w = pf.size.width if pf.size.width else 100
        h = pf.size.height if pf.size.height else 24
        return max(60, w), max(14, h)

    def refresh_ui(self, *, refresh_command_line: bool = True) -> None:
        st = self.game_state
        self._refresh_chrome()
        self._update_title_bar()
        pw, ph = self._playfield_size()
        self.query_one("#playfield", Static).update(
            render_playfield(
                st,
                pw,
                ph,
                galaxy_view=st.map_view == "galaxy",
                scale=st.system_zoom,
                galaxy_zoom=st.galaxy_zoom,
            )
        )
        self.query_one("#status_line", Static).update(format_status(st))
        if refresh_command_line:
            inp = self.query_one("#cmd_input", Input)
            self._update_completion_hint(inp.value)

    def _update_completion_hint(self, partial: str) -> None:
        typed = partial if partial else "(empty)"
        matches = matching_completions(self.game_state, partial, limit=3)
        if matches:
            hint = " | ".join(matches)
        else:
            hint = "(no match)"
        line = f"> {typed[:40]}  ||  complete: {hint[:48]}"
        self.query_one("#cmd_completions", Static).update(ascii_only(line))

    def run_command(self, line: str) -> None:
        runner = getattr(self.app, "run_game_command", None)
        if callable(runner):
            runner(line)
            return
        from lsl_online.commands import execute_command

        err = execute_command(self.game_state, line)
        if err:
            self.game_state.log(f"ERR: {err}")
        self.refresh_ui()

    def action_focus_cmd(self) -> None:
        self.query_one("#cmd_input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "cmd_input":
            return
        self._update_completion_hint(event.value)
        event.input.refresh()

    def on_key(self, event: Key) -> None:
        if event.key not in ("up", "down"):
            return
        command_input = self.query_one("#cmd_input", Input)
        if self.focused is not command_input:
            return
        if event.key == "up":
            if not self._command_history:
                return
            if self._history_index is None:
                self._history_draft = command_input.value
                self._history_index = len(self._command_history) - 1
            else:
                self._history_index = max(0, self._history_index - 1)
            command_input.value = self._command_history[self._history_index]
        else:
            if self._history_index is None:
                return
            if self._history_index >= len(self._command_history) - 1:
                self._history_index = None
                command_input.value = self._history_draft
                self._history_draft = ""
            else:
                self._history_index += 1
                command_input.value = self._command_history[self._history_index]
        command_input.cursor_position = len(command_input.value)
        event.stop()
        event.prevent_default()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd_input":
            return
        line = event.value.strip()
        event.input.value = ""
        if line:
            if not self._command_history or self._command_history[-1] != line:
                self._command_history.append(line)
                self._command_history = self._command_history[-100:]
            self._history_index = None
            self._history_draft = ""
            from lsl_online.audio import request_sound

            request_sound(self.game_state, "blip")
            self.run_command(line)
        self._update_completion_hint("")
