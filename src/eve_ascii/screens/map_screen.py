from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from eve_ascii.models import GameState
from eve_ascii.screens.status_bar import format_status
from eve_ascii.widgets.event_log import EventLog
from eve_ascii.widgets.star_map import StarMap


class MapScreen(Screen):
    """Main play screen: map + log + command line."""

    BINDINGS = [
        ("h", "pan_left", "Pan L"),
        ("l", "pan_right", "Pan R"),
        ("k", "pan_up", "Pan U"),
        ("j", "pan_down", "Pan D"),
        ("plus", "zoom_in", "Zoom+"),
        ("minus", "zoom_out", "Zoom-"),
        ("g", "toggle_galaxy", "Galaxy"),
        ("colon", "focus_cmd", "Cmd"),
    ]

    def __init__(self, state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.game_state = state

    def compose(self):
        yield Header()
        yield Static("", id="status_line")
        with Horizontal():
            yield StarMap(id="star_map")
            with Vertical():
                yield Static(" Event log", classes="panel-title")
                yield EventLog(id="event_log", highlight=True, markup=False)
        yield Input(placeholder="Command (travel, dock, jump…)", id="cmd_input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#cmd_input", Input).display = False
        self.refresh_ui()

    def refresh_ui(self) -> None:
        st = self.game_state
        self.query_one("#status_line", Static).update(format_status(st))
        self.query_one("#star_map", StarMap).set_state(st)
        log = self.query_one("#event_log", EventLog)
        log.clear()
        for ev in st.events[-30:]:
            log.append_line(ev)

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
        self.query_one("#star_map", StarMap).toggle_galaxy_view()

    def action_focus_cmd(self) -> None:
        inp = self.query_one("#cmd_input", Input)
        inp.display = True
        inp.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cmd_input":
            return
        line = event.value
        event.input.value = ""
        event.input.display = False
        self.run_command(line)
