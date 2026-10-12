from __future__ import annotations

from textual.widgets import Static

from eve_ascii.ascii_ui import box_wrap


class EventLog(Static):
    """Plain-text event feed inside an ASCII frame."""

    DEFAULT_CSS = """
    EventLog {
        height: 1fr;
        border: none;
        padding: 0 0;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._lines: list[str] = []
        self._width = 34

    def set_width(self, width: int) -> None:
        self._width = max(20, width)

    def clear(self) -> None:
        self._lines = []

    def append_line(self, text: str) -> None:
        self._lines.append(text)

    def refresh_log(self) -> None:
        inner_h = 18
        visible = self._lines[-inner_h:]
        while len(visible) < inner_h:
            visible.insert(0, "")
        self.update(box_wrap(self._width, "LOG", visible))
