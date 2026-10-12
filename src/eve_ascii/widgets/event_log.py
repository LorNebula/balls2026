from __future__ import annotations

from rich.style import Style
from rich.text import Text

from textual.widgets import Static


class EventLog(Static):
    """Colored event feed (1/3 of main pane width)."""

    DEFAULT_CSS = """
    EventLog {
        height: 1fr;
        width: 1fr;
        border: none;
        padding: 0 1;
        background: #0a1628;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", markup=True, **kwargs)
        self._lines: list[str] = []

    def clear(self) -> None:
        self._lines = []

    def append_line(self, text: str) -> None:
        self._lines.append(text)

    def refresh_log(self) -> None:
        h = max(12, (self.size.height if self.size.height else 20) - 2)
        visible = self._lines[-h:]
        out = Text()
        out.append(" EVENT LOG\n", style=Style(color="#e8b84a", bold=True))
        for line in visible:
            style = Style(color="#c9d6e3")
            if line.startswith("COMMS"):
                style = Style(color="#88ccff", bold=True)
            elif line.startswith("ERR"):
                style = Style(color="#ff6666", bold=True)
            elif line.startswith("HOSTILE") or "HIT" in line:
                style = Style(color="#ffaa44")
            elif line.startswith("TUTORIAL") or line.startswith("Quest"):
                style = Style(color="#aaffaa")
            out.append(line + "\n", style=style)
        self.update(out)
