"""Command registry and dispatch."""

from __future__ import annotations

import shlex

from eve_ascii.commands.base import Command
from eve_ascii.commands.combat_cmds import CeaseCommand, FireCommand, LockCommand
from eve_ascii.commands.mining_cmds import MineCommand, RadarCommand
from eve_ascii.commands.map_cmds import GalaxyViewCommand, ZoomCommand
from eve_ascii.commands.market_cmds import (
    BuyCommand,
    HangarCommand,
    InventoryCommand,
    MarketCommand,
    SellCommand,
    SystemViewCommand,
    RepairCommand,
    UpgradeCommand,
)
from eve_ascii.commands.misc_cmds import (
    CommsCommand,
    HelpCommand,
    QuitCommand,
    QuestCommand,
    QuestsCommand,
    SkipTutorialCommand,
)
from eve_ascii.commands.travel_cmds import DockCommand, JumpCommand, TravelCommand, UndockCommand
from eve_ascii.models import GameState

# Order matters: more specific matchers before generic ones (e.g. cease fire before cease-only).
COMMANDS: list[Command] = [
    HelpCommand(),
    QuitCommand(),
    SkipTutorialCommand(),
    DockCommand(),
    UndockCommand(),
    InventoryCommand(),
    MarketCommand(),
    SystemViewCommand(),
    GalaxyViewCommand(),
    ZoomCommand(),
    BuyCommand(),
    HangarCommand(),
    SellCommand(),
    RepairCommand(),
    UpgradeCommand(),
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
