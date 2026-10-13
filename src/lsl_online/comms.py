"""Communications / inbox."""

from __future__ import annotations

from lsl_online.models import GameState, Message


def push_message(state: GameState, sender: str, body: str) -> None:
    msg = Message(sender=sender, body=body, tick=state.tutorial_timer)
    state.inbox.append(msg)
    state.log(f"COMMS [{sender}]: {body}")


def list_messages(state: GameState, limit: int = 10) -> list[str]:
    lines: list[str] = []
    for msg in state.inbox[-limit:]:
        lines.append(f"FROM {msg.sender}: {msg.body}")
    return lines
