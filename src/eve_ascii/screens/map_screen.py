from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Input, Static

from eve_ascii.ascii_ui import ascii_only, box_line
from eve_ascii.command_completions import matching_completions
from eve_ascii.models import GameState
from eve_ascii.screens.status_bar import format_status
from eve_ascii.widgets.command_suggester import GameCommandSuggester
from eve_ascii.widgets.event_log import EventLog
from eve_ascii.widgets.star_map import StarMap


class MapScreen(Screen):
    """Main play screen: ASCII map + log + command line."""

    BINDINGS = [
        ("h", "pan_left", "Pan L"),
        ("l", "pan_right", "Pan R"),
        ("k", "pan_up", "Pan U"),
        ("j", "pan_down", "Pan D"),
        ("plus", "zoom_in", "Zoom+"),
        ("minus", "zoom_out", "Zoom-"),
        Binding("g", "toggle_galaxy", "Galaxy", priority=True),
        ("colon", "focus_cmd", "Cmd"),
        ("?", "help", "Help"),
        ("escape", "map_focus", "Map"),
    ]

    TITLE_WIDTH = 78

    def __init__(self, state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game_state = state
        self._galaxy_view = False

    def compose(self):
        yield Static("", id="title_bar")
        yield Static("", id="status_line")
        with Horizontal(id="main_pane"):
            yield StarMap(id="star_map")
            with Vertical(id="log_pane"):
                yield EventLog(id="event_log")
        yield Static("", id="footer_bar")
        with Horizontal(id="cmd_row"):
            yield Static("> ", id="cmd_prefix")
            yield Input(
                placeholder="travel station ... | jump ... | dock",
                id="cmd_input",
                classes="-textual-compact",
            )
        yield Static("", id="cmd_completions")

    def on_mount(self) -> None:
        inp = self.query_one("#cmd_input", Input)
        inp.suggester = GameCommandSuggester(lambda: self.game_state)
        self._refresh_chrome()
        self.refresh_ui()
        inp.focus()

    def _refresh_chrome(self) -> None:
        w = self.TITLE_WIDTH
        view = "GALAXY" if self._galaxy_view else "SYSTEM"
        self.query_one("#title_bar", Static).update(
            box_line(w, f" EVE ASCII | map={view} | space trading terminal ")
        )
        self.query_one("#footer_bar", Static).update(
            box_line(
                w,
                " Esc map keys  g toggle view  : focus cmd  Tab/Right accept  ? help  q quit ",
            )
        )

    def refresh_ui(self, *, refresh_command_line: bool = True) -> None:
        st = self.game_state
        self.query_one("#status_line", Static).update(format_status(st))
        self.query_one("#star_map", StarMap).update_map(st, galaxy_view=self._galaxy_view)
        log = self.query_one("#event_log", EventLog)
        log.clear()
        for ev in st.events[-30:]:
            log.append_line(ascii_only(ev))
        log.refresh_log()
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
        w = self.TITLE_WIDTH
        self.query_one("#cmd_completions", Static).update(
            box_line(
                w,
                f" > {typed[:40]}  ||  complete: {hint[: w - 30]}",
            )
        )

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

    def action_help(self) -> None:
        self.game_state.log("travel, jump, lock A [reactor|thrusters|shields|weapons|01-04], fire, cease")
        self.game_state.log("ship - inspect hull components, power, shield")
        self.game_state.log("comms, quests, quest start q_scout, quest status")
        self.refresh_ui()

    def action_pan_left(self) -> None:
        self.query_one("#star_map", StarMap).pan(-5, 0)

    def action_pan_right(self) -> None:
        self.query_one("#star_map", StarMap).pan(5, 0)

    def action_pan_up(self) -> None:
        self.query_one("#star_map", StarMap).pan(0, -3)

    def action_pan_down(self) -> None:
        self.query_one("#star_map", StarMap).pan(0, 3)

    def action_zoom_in(self) -> None:
        self.query_one("#star_map", StarMap).zoom(-0.25)

    def action_zoom_out(self) -> None:
        self.query_one("#star_map", StarMap).zoom(0.25)

    def action_toggle_galaxy(self) -> None:
        self._galaxy_view = not self._galaxy_view
        mode = "galaxy" if self._galaxy_view else "system"
        self.game_state.log(f"Map view: {mode}")
        self._refresh_chrome()
        self.refresh_ui()

    def action_focus_cmd(self) -> None:
        self.query_one("#cmd_input", Input).focus()

    def action_map_focus(self) -> None:
        self.set_focus(None)
        self._refresh_chrome()

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
