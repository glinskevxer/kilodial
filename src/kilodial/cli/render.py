"""Turning rows into something readable in a terminal.

No dependency on a table library, because the output of this tool gets pasted
into emails and grepped by people who are not going to install anything. Columns
are padded to the widest cell, numbers go right, everything else goes left, and
that is the whole feature set.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from kilodial.errors import BadInputError

GAP = 2


def _is_number(text: str) -> bool:
    stripped = text.replace(",", "").replace("$", "").replace("%", "").strip()
    if stripped.startswith(("-", "+")):
        stripped = stripped[1:]
    return bool(stripped) and stripped.replace(".", "", 1).isdigit()


def table(headings: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    """Lay a table out, with a rule under the headings."""
    body = [[str(cell) for cell in row] for row in rows]
    for row in body:
        if len(row) != len(headings):
            raise BadInputError(f"a row of {len(row)} cells does not fit {len(headings)} headings")
    widths = [len(h) for h in headings]
    for row in body:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    right = [
        bool(body) and all(_is_number(row[index]) for row in body) for index in range(len(headings))
    ]
    lines = [_line(headings, widths, right)]
    lines.append(_line(["-" * w for w in widths], widths, [False] * len(widths)))
    lines.extend(_line(row, widths, right) for row in body)
    return lines


def _line(cells: Sequence[str], widths: Sequence[int], right: Sequence[bool]) -> str:
    parts = [
        cell.rjust(widths[i]) if right[i] else cell.ljust(widths[i]) for i, cell in enumerate(cells)
    ]
    return (" " * GAP).join(parts).rstrip()


def pairs(items: Iterable[tuple[str, str]]) -> list[str]:
    """A two column detail block, label left and value right after it."""
    rows = list(items)
    if not rows:
        return []
    width = max(len(label) for label, _ in rows)
    return [f"{label.ljust(width)}  {value}" for label, value in rows]


def yes_no(value: object) -> str:
    return "yes" if value else "no"


def or_dash(value: object) -> str:
    """Print a missing value as a dash rather than as the word None."""
    return "-" if value is None else str(value)


__all__ = ["GAP", "or_dash", "pairs", "table", "yes_no"]
