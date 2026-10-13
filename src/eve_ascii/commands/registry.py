"""Command registry and dispatch."""

from __future__ import annotations

import shlex

from eve_ascii.commands.base import Command
from eve_ascii.commands.combat_cmds import CeaseCommand, FireCommand, LockCommand
from eve_ascii.commands.market_cmds import (
    HangarCommand,
    InventoryCommand,
    SellCommand,
    UpgradeCommand,
)
from eve_ascii.commands.misc_cmds import (
    CommsCommand,
    HelpCommand,
    QuestCommand,
    QuestsCommand,
    ShipCommand,
)
from eve_ascii.commands.travel_cmds import DockCommand, JumpCommand, TravelCommand, UndockCommand
from eve_ascii.models import GameState

# Order matters: more specific matchers before generic ones (e.g. cease fire before cease-only).
COMMANDS: list[Command] = [
    HelpCommand(),
    ShipCommand(),
    DockCommand(),
    UndockCommand(),
    InventoryCommand(),
    HangarCommand(),
    SellCommand(),
    UpgradeCommand(),
    JumpCommand(),
    TravelCommand(),
    LockCommand(),
    FireCommand(),
    CeaseCommand(),
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
