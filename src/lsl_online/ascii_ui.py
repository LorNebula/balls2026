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


def pad_line(line: str, width: int) -> str:
    text = ascii_only(line)
    if len(text) >= width:
        return text[:width]
    return text.ljust(width)


def frame_top(width: int, title: str = "") -> str:
    return box_top(width, title)


def frame_mid(width: int, content: str) -> str:
    return box_line(width, content)


def frame_bottom(width: int) -> str:
    return box_bottom(width)


def split_pane_top(left_w: int, right_w: int, left_title: str, right_title: str) -> str:
    """Two-pane header: +-- title --+ +-- title --+ joined at +."""
    left_inner = max(0, left_w - 2)
    right_inner = max(0, right_w - 2)
    lt = f" {ascii_only(left_title)} "
    if len(lt) >= left_inner:
        lt = lt[:left_inner]
    lp = left_inner - len(lt)
    left_top = "+" + "-" * (lp // 2) + lt + "-" * (lp - lp // 2) + "+"
    rt = f" {ascii_only(right_title)} "
    if len(rt) >= right_inner:
        rt = rt[:right_inner]
    rp = right_inner - len(rt)
    right_top = "+" + "-" * (rp // 2) + rt + "-" * (rp - rp // 2) + "+"
    return left_top + right_top


def split_pane_bottom(left_w: int, right_w: int) -> str:
    return frame_bottom(left_w) + frame_bottom(right_w)


def join_pane_row(left: str, right: str, left_w: int, right_w: int) -> str:
    return "|" + pad_line(left, left_w - 2) + "|" + pad_line(right, right_w - 2) + "|"
