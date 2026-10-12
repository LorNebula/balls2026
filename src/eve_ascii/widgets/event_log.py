from textual.widgets import RichLog


class EventLog(RichLog):
    """Travel and status messages."""

    DEFAULT_CSS = """
    EventLog {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def append_line(self, text: str) -> None:
        self.write(text)
