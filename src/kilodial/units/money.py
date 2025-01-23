"""Money, in whole cents, with a proration that does not lose a penny.

Bill adjustments get split across billing periods and across service points, so
the type that carries them has to divide a total into parts that add back to the
total exactly. Floating point cannot do that and neither can naive rounding of
each part, so amounts are held as an integer number of cents and split with the
largest remainder method.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering
from typing import Any

from kilodial.errors import BadInputError

CENTS = Decimal("0.01")


def _cents_from(value: object) -> int:
    if isinstance(value, Money):
        return value.cents
    if isinstance(value, int):
        return value * 100
    if isinstance(value, Decimal):
        return int(value.quantize(CENTS, rounding=ROUND_HALF_UP) * 100)
    if isinstance(value, float):
        return int(Decimal(repr(value)).quantize(CENTS, rounding=ROUND_HALF_UP) * 100)
    if isinstance(value, str):
        text = value.strip().replace("$", "").replace(",", "")
        negative = text.startswith("(") and text.endswith(")")
        if negative:
            text = text[1:-1]
        try:
            amount = Decimal(text)
        except InvalidOperation:
            raise BadInputError(f"{value!r} is not an amount of money") from None
        if negative:
            amount = -amount
        return int(amount.quantize(CENTS, rounding=ROUND_HALF_UP) * 100)
    raise BadInputError(f"cannot read money from {type(value).__name__}")


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Money:
    """A signed amount in whole cents.

    Negative is meaningful and is not an error: a refund to the customer and a
    back bill to the customer are the same calculation with opposite signs, and
    collapsing that into two code paths is how the sign gets lost.
    """

    cents: int

    def __init__(self, value: object = 0) -> None:
        object.__setattr__(self, "cents", _cents_from(value))

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_cents(cls, cents: int) -> Money:
        if not isinstance(cents, int):
            raise BadInputError("cents have to be a whole number")
        money = cls.__new__(cls)
        object.__setattr__(money, "cents", cents)
        return money

    @property
    def dollars(self) -> Decimal:
        return (Decimal(self.cents) / 100).quantize(CENTS)

    @property
    def is_zero(self) -> bool:
        return self.cents == 0

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money.from_cents(self.cents + other.cents)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money.from_cents(self.cents - other.cents)

    def __neg__(self) -> Money:
        return Money.from_cents(-self.cents)

    def __abs__(self) -> Money:
        return Money.from_cents(abs(self.cents))

    def scaled(self, factor: object) -> Money:
        """Multiply by a ratio, rounding half up at the cent."""
        if isinstance(factor, Money):
            raise BadInputError("money times money is not money")
        if isinstance(factor, str | int | Decimal | float):
            ratio = factor if isinstance(factor, Decimal) else Decimal(str(factor))
        else:
            raise BadInputError(f"cannot scale money by {type(factor).__name__}")
        exact = Decimal(self.cents) * ratio
        return Money.from_cents(int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP)))

    def split(self, weights: list[int]) -> list[Money]:
        """Divide across weights so the parts add back to the whole exactly.

        Every part gets the floor of its share and the leftover cents go one at
        a time to the largest remainders, ties broken by position. A zero weight
        gets nothing, and all zero weights is an error rather than a silent
        equal split, because a caller in that state has usually lost its data.
        """
        if not weights:
            raise BadInputError("nothing to split across")
        if any(w < 0 for w in weights):
            raise BadInputError("a split weight cannot be negative")
        total = sum(weights)
        if total == 0:
            raise BadInputError("cannot split across weights that are all zero")
        sign = -1 if self.cents < 0 else 1
        pot = abs(self.cents)
        base = [pot * w // total for w in weights]
        remainders = [(pot * w) % total for w in weights]
        left = pot - sum(base)
        order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
        for i in order[:left]:
            base[i] += 1
        return [Money.from_cents(sign * c) for c in base]

    def __str__(self) -> str:
        sign = "-" if self.cents < 0 else ""
        whole, part = divmod(abs(self.cents), 100)
        return f"{sign}${whole:,}.{part:02d}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return self.cents == other.cents
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Money", self.cents))

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Money):
            return bool(self.cents < other.cents)
        return NotImplemented


__all__ = ["CENTS", "Money"]
