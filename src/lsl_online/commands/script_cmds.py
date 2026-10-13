from __future__ import annotations

from lsl_online import automation
from lsl_online.commands.base import Command
from lsl_online.events import OPEN_SCRIPT_EDITOR
from lsl_online.models import GameState


class ScriptCommand(Command):
    def matches(self, parts: list[str]) -> bool:
        return bool(parts) and parts[0].lower() == "script"

    def execute(self, state: GameState, parts: list[str]) -> str | None:
        args = [a.lower() for a in parts[1:]]
        if not args or args[0] in ("edit", "open"):
            state.bus.emit(OPEN_SCRIPT_EDITOR)
            return None
        if args[0] == "enable":
            if not state.trade_script_source.strip():
                return "No script saved. Use: script edit"
            state.trade_script_enabled = True
            state.trade_script_timer = 0.0
            state.log("Trade cron enabled (every 60s).")
            return None
        if args[0] == "disable":
            state.trade_script_enabled = False
            state.log("Trade cron disabled.")
            return None
        if args[0] == "run":
            return automation.execute_trade_script(state)
        if args[0] == "status":
            for line in automation.script_status_lines(state):
                state.log(line)
            return None
        return "Usage: script | script edit | script enable | script disable | script run | script status"

    def completions(self, state: GameState) -> list[str]:
        return [
            "script",
            "script edit",
            "script enable",
            "script disable",
            "script run",
            "script status",
        ]

    def palette_items(self, state: GameState) -> list[tuple[str, str]]:
        return [
            ("Edit trade script", "script edit"),
            ("Run trade script", "script run"),
            ("Trade script status", "script status"),
        ]
