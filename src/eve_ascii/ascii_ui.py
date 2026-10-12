"""Pure ASCII helpers for TUI (printable chars only, no box-drawing Unicode)."""

from __future__ import annotations

import unicodedata


def ascii_only(text: str) -> str:
    """Strip to 7-bit ASCII for display (Finnish names -> ASCII transliteration)."""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def box_top(width: int, title: str = "") -> str:
    inner = max(0, width - 2)
    if not title:
        return "+" + "-" * inner + "+"
    label = f" {ascii_only(title)} "
    if len(label) >= inner:
        label = label[:inner]
    pad = inner - len(label)
    left = pad // 2
    right = pad - left
    return "+" + "-" * left + label + "-" * right + "+"


def box_bottom(width: int) -> str:
    return "+" + "-" * max(0, width - 2) + "+"


def box_line(width: int, content: str) -> str:
    inner = max(0, width - 2)
    text = ascii_only(content)[:inner]
    return "|" + text.ljust(inner) + "|"


def box_wrap(width: int, title: str, lines: list[str]) -> str:
    out = [box_top(width, title)]
    for line in lines:
        out.append(box_line(width, line))
    out.append(box_bottom(width))
    return "\n".join(out)
