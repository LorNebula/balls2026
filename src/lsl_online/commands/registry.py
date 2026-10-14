"""Command registry and dispatch."""

from __future__ import annotations

import shlex

from lsl_online.commands.base import Command
from lsl_online.commands.combat_cmds import CeaseCommand, FireCommand, LockCommand
from lsl_online.commands.mining_cmds import MineCommand, RadarCommand
from lsl_online.commands.map_cmds import GalaxyViewCommand, ZoomCommand
from lsl_online.commands.nav_cmds import MarkCommand, PathCommand
from lsl_online.commands.market_cmds import (
    BuyCommand,
    BuyShipCommand,
    HangarCommand,
    InventoryCommand,
    RoutesCommand,
    MarketCommand,
    SellCommand,
    SellShipCommand,
    SwitchShipCommand,
    SystemViewCommand,
    RepairCommand,
    RefuelCommand,
    UpgradeCommand,
)
from lsl_online.commands.misc_cmds import (
    CommsCommand,
    HelpCommand,
    QuitCommand,
    QuestCommand,
    QuestsCommand,
    ReadyCommand,
    SkipTutorialCommand,
)
from lsl_online.commands.script_cmds import ScriptCommand
from lsl_online.commands.travel_cmds import DockCommand, JumpCommand, TravelCommand, UndockCommand
from lsl_online.models import GameState

# Order matters: more specific matchers before generic ones (e.g. cease fire before cease-only).
COMMANDS: list[Command] = [
    HelpCommand(),
    QuitCommand(),
    ReadyCommand(),
    SkipTutorialCommand(),
    DockCommand(),
    UndockCommand(),
    InventoryCommand(),
    RoutesCommand(),
    MarketCommand(),
    BuyShipCommand(),
    SellShipCommand(),
    SwitchShipCommand(),
    SystemViewCommand(),
    GalaxyViewCommand(),
    ZoomCommand(),
    PathCommand(),
    MarkCommand(),
    BuyCommand(),
    HangarCommand(),
    SellCommand(),
    RepairCommand(),
    RefuelCommand(),
    UpgradeCommand(),
    ScriptCommand(),
    JumpCommand(),
    TravelCommand(),
    LockCommand(),
    MineCommand(),
    FireCommand(),
    CeaseCommand(),
    RadarCommand(),
    CommsCommand(),
    QuestsCommand(),
    QuestCommand(),
]


def execute_command(state: GameState, line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    try:
        parts = shlex.split(line)
    except ValueError as e:
        return str(e)
    if not parts:
        return None
    if state.game_over:
        allowed = {"quit", "exit", "help"}
        if parts[0].lower() not in allowed:
            return "Game over. Type quit to exit."
    for command in COMMANDS:
        if command.matches(parts):
            return command.execute(state, parts)
    cmd = parts[0].lower()
    return f"Unknown command: {cmd}. Type help."


def completion_candidates(state: GameState) -> list[str]:
    out: list[str] = []
    for command in COMMANDS:
        out.extend(command.completions(state))
    return out


def palette_suggestions(state: GameState) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for command in COMMANDS:
        items.extend(command.palette_items(state))
    return items
