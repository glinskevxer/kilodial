"""What every command needs: a book, and a way to print.

Commands are handed one of these rather than reaching for a global. The reason
is testing more than purity: a command that opens its own book cannot be run
twice in one process against two books, and half the tests in this package do
exactly that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import click

from kilodial.errors import ConfigError
from kilodial.store.book import open_book
from kilodial.store.events import DEFAULT_ACTOR
from kilodial.store.shop import Shop, open_shop

DEFAULT_BOOK = "shop.sqlite3"


@dataclass
class Context:
    """The state one invocation carries."""

    book_path: Path
    quiet: bool = False
    actor: str = DEFAULT_ACTOR
    _shop: Shop | None = field(default=None, repr=False)

    def open(self, *, create: bool = False, migrate: bool = True) -> Shop:
        """Open the book once and hand the same handle back after that.

        ``migrate`` is off for the init command only, which wants to run the
        migrations itself so it can say which ones it ran.
        """
        if self._shop is None:
            if not create and not self.book_path.exists():
                raise ConfigError(
                    f"there is no book at {self.book_path}, run 'kilodial init' first"
                )
            if migrate:
                self._shop = open_shop(self.book_path, create=create)
            else:
                self._shop = Shop(open_book(self.book_path, create=create))
        return self._shop

    def close(self) -> None:
        if self._shop is not None:
            self._shop.close()
            self._shop = None

    def log(self, action: str, subject: str, detail: object = None) -> None:
        """Append a line to the book's event log under this invocation's actor.

        Called from inside the command's transaction, so a command that fails
        halfway leaves no line saying it happened. That is the whole reason the
        log lives on the book rather than in a file beside it.
        """
        if self._shop is None:
            raise ConfigError("nothing can be logged before the book is open")
        self._shop.events.record(action, subject, detail=detail, actor=self.actor)

    def say(self, message: str) -> None:
        if not self.quiet:
            click.echo(message)

    def warn(self, message: str) -> None:
        click.echo(message, err=True)


pass_context = click.make_pass_decorator(Context)


__all__ = ["DEFAULT_BOOK", "Context", "pass_context"]
