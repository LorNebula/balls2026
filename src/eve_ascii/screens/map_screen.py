from textual.binding import Binding
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
        self._galaxy_zoom = 1.0
        self._scale = 4.0

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
        view = "GALAXY" if self._galaxy_view else "SYSTEM"
        self.query_one("#title_bar", Static).update(
            box_line(w, f" EVE ASCII | map={view} | space trading terminal ")
        )
        self.query_one("#footer_bar", Static).update(
            box_line(
                w,
                " Esc map keys  g toggle view  +/- zoom  system exits market  ? help  q quit ",
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
            self._galaxy_view = True
        pw, ph = self._playfield_size()
        self.query_one("#playfield", Static).update(
            render_playfield(
                st,
                pw,
                ph,
                galaxy_view=self._galaxy_view,
                scale=self._scale,
                galaxy_zoom=self._galaxy_zoom,
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
        command = line.strip().split(maxsplit=1)[0].casefold() if line.strip() else ""
        if command in ("system", "close", "exit", "map"):
            self._galaxy_view = False
            self._refresh_chrome()
        elif command in ("jump", "gate"):
            self._galaxy_view = False
            if self.game_state.player.ship.status.value == "docked":
                self.game_state.station_view = "system"
            self._refresh_chrome()
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
        self.game_state.log("dock, inventory, sell <item> <qty>, upgrade reactor|weapons")
        self.game_state.log("comms, quests, quest start q_scout, quest status")
        self.refresh_ui()

    def action_pan_left(self) -> None:
        self._scale = max(1.0, min(8.0, self._scale + 0.05))
        self.refresh_ui()

    def action_pan_right(self) -> None:
        self._scale = max(1.0, min(8.0, self._scale - 0.05))
        self.refresh_ui()

    def action_pan_up(self) -> None:
        pass

    def action_pan_down(self) -> None:
        pass

    def action_zoom_in(self) -> None:
        if self._galaxy_view or self.game_state.tutorial_force_galaxy:
            self._galaxy_zoom = min(8.0, self._galaxy_zoom * 1.5)
            self.refresh_ui()
            return
        self._scale = max(1.0, min(8.0, self._scale - 0.25))
        self.refresh_ui()

    def action_zoom_out(self) -> None:
        if self._galaxy_view or self.game_state.tutorial_force_galaxy:
            self._galaxy_zoom = max(0.05, self._galaxy_zoom / 1.5)
            self.refresh_ui()
            return
        self._scale = max(1.0, min(8.0, self._scale + 0.25))
        self.refresh_ui()

    def action_toggle_galaxy(self) -> None:
        self._galaxy_view = not self._galaxy_view
        if not self._galaxy_view and self.game_state.player.ship.status.value == "docked":
            self.game_state.station_view = "system"
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
