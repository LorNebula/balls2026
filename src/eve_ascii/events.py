"""Discrete game events (register listeners, emit from gameplay)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

ENTERED_SYSTEM = "entered_system"
OPEN_SHIP_UI = "open_ship_ui"
QUIT_APP = "quit_app"

Listener = Callable[..., None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Listener]] = defaultdict(list)

    def on(self, name: str, listener: Listener) -> None:
        if listener not in self._listeners[name]:
            self._listeners[name].append(listener)

    def off(self, name: str, listener: Listener) -> None:
        try:
            self._listeners[name].remove(listener)
        except ValueError:
            pass

    def emit(self, name: str, **payload: Any) -> None:
        for listener in list(self._listeners[name]):
            listener(**payload)
