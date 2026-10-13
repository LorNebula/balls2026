from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, Static

from eve_ascii.ascii_ui import ascii_only, box_line
from eve_ascii.command_completions import matching_completions
from eve_ascii.models import GameState
from eve_ascii.playfield import render_playfield
from eve_ascii.screens.status_bar import format_status
from eve_ascii.widgets.command_suggester import GameCommandSuggester


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

    def compose(self):
        yield Static("", id="title_bar")
        yield Static("", id="playfield", markup=True)
        yield Static("", id="status_line")
        with Horizontal(id="cmd_row"):
            yield Static("> ", id="cmd_prefix")
            yield Input(
                placeholder="travel station ... | jump ... | dock",
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

    def _refresh_chrome(self) -> None:
        w = self.TITLE_WIDTH
        view = self.game_state.map_view.upper()
        if view == self._chrome_view:
            return
        self._chrome_view = view
        self.query_one("#title_bar", Static).update(
            box_line(w, f" EVE ASCII | map={view} | space trading terminal ")
        )
        self.query_one("#footer_bar", Static).update(
            box_line(
                w,
                " : command  galaxy/system  zoom in/out  quit ",
            )
        )

    def _playfield_size(self) -> tuple[int, int]:
        pf = self.query_one("#playfield", Static)
        w = pf.size.width if pf.size.width else 100
        h = pf.size.height if pf.size.height else 24
        return max(60, w), max(14, h)

    def refresh_ui(self, *, refresh_command_line: bool = True) -> None:
        st = self.game_state
        if st.tutorial_force_galaxy:
            st.map_view = "galaxy"
        if st.map_view.upper() != self._chrome_view:
            self._refresh_chrome()
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
        from eve_ascii.commands import execute_command

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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd_input":
            return
        line = event.value.strip()
        event.input.value = ""
        if line:
            self.run_command(line)
        self._update_completion_hint("")
