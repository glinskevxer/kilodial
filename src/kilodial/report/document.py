"""A report as data, rendered afterwards.

Reports in this package are built as a document and rendered at the end, rather
than printed as they are computed. That costs a little and buys two things worth
more than it costs.

The same report goes to a terminal and to a file the commission wants as CSV,
and neither rendering is the "real" one. A report that printed as it went would
have the terminal format welded into the calculation, and the CSV would be a
second implementation that drifts.

And a report that exists as data can be checked. A test can assert that the
commission report has a row per group with the right count in it, without
parsing a page of aligned text and without the test breaking the first time a
column gets wider.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from kilodial.cli.render import pairs, table
from kilodial.errors import BadInputError


@dataclass(frozen=True)
class Grid:
    """A table of strings with headings."""

    headings: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @classmethod
    def of(cls, headings: list[str], rows: list[list[str]]) -> Grid:
        """Build a grid, refusing a row that does not fit the headings."""
        for row in rows:
            if len(row) != len(headings):
                raise BadInputError(
                    f"a row of {len(row)} cells does not fit {len(headings)} headings"
                )
        return cls(tuple(headings), tuple(tuple(r) for r in rows))

    @property
    def is_empty(self) -> bool:
        return not self.rows

    def lines(self) -> list[str]:
        return table(self.headings, self.rows)

    def dicts(self) -> list[dict[str, str]]:
        return [dict(zip(self.headings, row, strict=True)) for row in self.rows]


@dataclass
class Section:
    """One block of a report: a heading, some facts, and at most one grid."""

    title: str
    facts: list[tuple[str, str]] = field(default_factory=list)
    grid: Grid | None = None
    notes: list[str] = field(default_factory=list)

    def fact(self, label: str, value: object) -> Section:
        """Add a labelled figure, returning self so calls can be chained."""
        self.facts.append((label, str(value)))
        return self

    def note(self, text: str) -> Section:
        """Add a line of prose under the section."""
        self.notes.append(text)
        return self

    def lines(self) -> list[str]:
        out = [self.title, "=" * len(self.title)]
        if self.facts:
            out.extend(pairs(self.facts))
        if self.grid is not None and not self.grid.is_empty:
            if self.facts:
                out.append("")
            out.extend(self.grid.lines())
        if self.notes:
            out.append("")
            out.extend(self.notes)
        return out


@dataclass
class Document:
    """A whole report."""

    title: str
    sections: list[Section] = field(default_factory=list)

    def section(self, title: str, grid: Grid | None = None) -> Section:
        """Start a section and hand it back for filling in."""
        made = Section(title, grid=grid)
        self.sections.append(made)
        return made

    def render(self) -> str:
        """The report as text, the way it goes on a terminal."""
        out = [self.title, "=" * len(self.title), ""]
        for index, section in enumerate(self.sections):
            if index:
                out.append("")
            out.extend(section.lines())
        return "\n".join(out) + "\n"

    def as_json(self) -> str:
        """The report as json, for anything that is not a person."""
        payload: dict[str, Any] = {"title": self.title, "sections": []}
        for section in self.sections:
            block: dict[str, Any] = {
                "title": section.title,
                "facts": dict(section.facts),
                "notes": list(section.notes),
            }
            if section.grid is not None:
                block["rows"] = section.grid.dicts()
            payload["sections"].append(block)
        return json.dumps(payload, indent=2, sort_keys=True)

    def as_csv(self) -> str:
        """The first grid in the report as csv, which is what a regulator asks for."""
        for section in self.sections:
            if section.grid is not None and not section.grid.is_empty:
                out = StringIO()
                writer = csv.writer(out, lineterminator="\n")
                writer.writerow(section.grid.headings)
                writer.writerows(section.grid.rows)
                return out.getvalue()
        raise BadInputError(f"{self.title} has no table in it to write out")

    def __str__(self) -> str:
        return self.render()


__all__ = ["Document", "Grid", "Section"]
