"""Combined map + event log playfield with ASCII +---| frame."""

from __future__ import annotations

import textwrap

from rich.style import Style
from rich.text import Text

from lsl_online.ascii_ui import ascii_only, pad_line, split_pane_bottom, split_pane_top
from lsl_online.market import render_cargo_view, render_hangar_view, render_market_view
from lsl_online.models import GameMode, GameState, ShipStatus
from lsl_online.space_render import (
    render_docked_view,
    render_galaxy_map,
    render_open_space,
)

COMBAT_BORDER_ORANGE = Style(color="#ff8800", bold=True)
COMBAT_BORDER_RED = Style(color="#ff3333", bold=True)
DEFAULT_BORDER = Style(color="#8899aa")
DEFAULT_TITLE = Style(color="#e8b84a", bold=True)
COMBAT_BORDER_FLASH_PERIOD = 0.55
CMD_STYLE = Style(color="#ffe066", bold=True)


def _combat_border_active(state: GameState) -> bool:
    return state.mode == GameMode.COMBAT and any(
        npc.alive for npc in state.npc_ships
    )


def _combat_border_style(state: GameState) -> Style:
    phase = int(state.combat_time / COMBAT_BORDER_FLASH_PERIOD) % 2
    return COMBAT_BORDER_RED if phase else COMBAT_BORDER_ORANGE


def _log_style(line: str) -> Style:
    if line.startswith("COMMS"):
        return Style(color="#88ccff", bold=True)
    if line.startswith("ERR"):
        return Style(color="#ff6666", bold=True)
    if line.startswith("HOSTILE") or "HIT" in line:
        return Style(color="#ffaa44")
    if line.startswith("TUTORIAL") or line.startswith("Quest"):
        return Style(color="#aaffaa")
    return Style(color="#c9d6e3")


def _styled_log_line(plain: str, base_style: Style) -> Text:
    if "`" not in plain:
        return Text(plain, style=base_style)
    out = Text()
    for index, part in enumerate(plain.split("`")):
        if not part:
            continue
        out.append(part, style=CMD_STYLE if index % 2 == 1 else base_style)
    return out


def _styled_tokens(plain: str, base_style: Style) -> list[tuple[str, Style]]:
    tokens: list[tuple[str, Style]] = []
    for index, part in enumerate(plain.split("`")):
        if not part:
            continue
        style = CMD_STYLE if index % 2 == 1 else base_style
        words = part.split(" ")
        for word_index, word in enumerate(words):
            if not word:
                continue
            if word_index > 0:
                prefix = " "
            elif tokens and not tokens[-1][0].endswith(" "):
                prefix = " "
            else:
                prefix = ""
            tokens.append((prefix + word, style))
    return tokens


def _wrap_styled_event(plain: str, base_style: Style, width: int) -> list[Text]:
    if not plain:
        return [Text("")]
    if "`" not in plain:
        parts = textwrap.wrap(
            plain,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        )
        return [Text(part, style=base_style) for part in (parts or [plain[:width]])]

    tokens = _styled_tokens(plain, base_style)
    rows: list[Text] = []
    line = Text()
    line_len = 0

    def flush() -> None:
        nonlocal line, line_len
        if line.plain:
            rows.append(line)
        line = Text()
        line_len = 0

    for piece, style in tokens:
        while piece:
            if line_len == 0 and piece.startswith(" "):
                piece = piece[1:]
                if not piece:
                    break
            room = width - line_len
            if room <= 0:
                flush()
                continue
            if len(piece) <= room:
                line.append(piece, style=style)
                line_len += len(piece)
                piece = ""
            elif line_len > 0:
                flush()
            else:
                line.append(piece[:room], style=style)
                piece = piece[room:]
                flush()
    flush()
    return rows or [Text("")]


def _pad_rich_line(line: Text, width: int) -> Text:
    out = line.copy()
    plain_len = len(out.plain)
    if plain_len < width:
        out.append(" " * (width - plain_len), style=Style())
    return out


def _wrap_event_lines(events: list[str], width: int) -> list[Text]:
    rows: list[Text] = []
    for ev in events:
        plain = ascii_only(ev)
        base = _log_style(ev)
        if not plain:
            rows.append(Text(""))
            continue
        for line in _wrap_styled_event(plain, base, width):
            rows.append(_pad_rich_line(line, width))
    return rows


def render_log_pane(state: GameState, width: int, height: int) -> Text:
    inner_w = max(8, width - 2)
    inner_h = max(4, height - 2)
    wrapped = _wrap_event_lines(state.events, inner_w)
    visible = wrapped[-inner_h:]
    out = Text()
    for i in range(inner_h):
        if i < len(visible):
            out.append(_pad_rich_line(visible[i], inner_w))
            out.append("\n")
        else:
            out.append(" " * inner_w + "\n", style=Style(color="#c9d6e3"))
    return out


def _map_pane_title(state: GameState, *, galaxy_view: bool) -> str:
    ship = state.player.ship
    if galaxy_view:
        return "GALAXY MAP"
    if ship.status == ShipStatus.DOCKED and state.station_view != "system":
        if state.station_view == "market":
            return "STATION MARKET"
        if state.station_view == "hangar":
            return "STATION HANGAR"
        if state.station_view == "cargo":
            return "CARGO HOLD"
        return "DOCK / HANGAR"
    if state.station_view == "cargo":
        return "CARGO HOLD"
    if state.mode == GameMode.HYPERSPACE or ship.status == ShipStatus.JUMPING:
        return "HYPERSPACE"
    sys = state.galaxy.get_system(ship.location.system_id)
    if not sys:
        return "SYSTEM"
    in_nebula = any(sys.id in nebula.system_ids for nebula in state.galaxy.nebulae)
    return f"{ascii_only(sys.name)} / NEBULA" if in_nebula else ascii_only(sys.name)


def render_map_pane(
    state: GameState,
    width: int,
    height: int,
    *,
    galaxy_view: bool,
    scale: float,
    galaxy_zoom: float = 1.0,
) -> Text:
    w, h = max(20, width - 2), max(8, height - 2)
    ship = state.player.ship
    if galaxy_view:
        return render_galaxy_map(state, w, h, galaxy_zoom)
    if state.station_view == "cargo":
        return render_cargo_view(state, w, h)
    if ship.status == ShipStatus.DOCKED and state.station_view != "system":
        if state.station_view == "market":
            return render_market_view(state, w, h)
        if state.station_view == "hangar":
            return render_hangar_view(state, w, h)
        return render_docked_view(state, w, h)
    in_hyperspace = (
        state.mode == GameMode.HYPERSPACE
        or ship.status == ShipStatus.JUMPING
        or state.hyperspace_landing_timer > 0
    )
    if in_hyperspace:
        body = render_open_space(state, w, h, scale, hyperspace=True)
    else:
        body = render_open_space(state, w, h, scale, hyperspace=False)
    return body


def _as_text(line: Text | None) -> Text:
    if line is None:
        return Text("")
    return line


def _fit_rich_line(line: Text, width: int) -> Text:
    """Pad or clip a Rich line without stripping per-cell styles."""
    if len(line) > width:
        out = line.copy()
        out.truncate(width, pad=False)
        return out
    if len(line) == width:
        return line.copy()
    out = line.copy()
    out.append(" " * (width - len(line)))
    return out


def render_playfield(
    state: GameState,
    total_w: int,
    total_h: int,
    *,
    galaxy_view: bool,
    scale: float,
    galaxy_zoom: float = 1.0,
) -> Text:
    total_w = max(60, total_w)
    total_h = max(14, total_h)
    log_w = max(22, total_w // 3)
    map_w = total_w - log_w
    inner_h = total_h - 2

    map_body = render_map_pane(
        state,
        map_w,
        inner_h,
        galaxy_view=galaxy_view,
        scale=scale,
        galaxy_zoom=galaxy_zoom,
    )
    log_body = render_log_pane(state, log_w, inner_h)

    map_lines = map_body.split("\n")
    log_lines = log_body.split("\n")

    left_title = _map_pane_title(state, galaxy_view=galaxy_view)
    out = Text()
    in_combat = _combat_border_active(state)
    border_style = _combat_border_style(state) if in_combat else DEFAULT_BORDER
    title_style = border_style if in_combat else DEFAULT_TITLE
    out.append(split_pane_top(map_w, log_w, left_title, "EVENT LOG") + "\n", style=title_style)

    frame_style = border_style
    for i in range(inner_h):
        ml = _as_text(map_lines[i] if i < len(map_lines) else None)
        ll = _as_text(log_lines[i] if i < len(log_lines) else None)
        ml = _fit_rich_line(ml, map_w - 2)
        ll = _fit_rich_line(ll, log_w - 2)
        row = Text("|", style=frame_style)
        row.append_text(ml)
        row.append("|", style=frame_style)
        row.append_text(ll)
        row.append("|", style=frame_style)
        out.append_text(row)
        out.append("\n")

    out.append(split_pane_bottom(map_w, log_w) + "\n", style=frame_style)
    return out
