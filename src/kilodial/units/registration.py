"""Percent registration: what a watthour meter recorded against the truth.

A meter that records exactly the energy that passed through it registers 100
percent. Above that it is fast and the customer is being overbilled; below it
the meter is slow and the utility is losing revenue. Every accuracy number in
the shop is one of these, including the correction factors that instrument
transformers contribute, which is why they compose.

The type carries a ``Decimal`` quantised to four places. Four is not a taste
decision: bench standards report to 0.01 percent and the composition of three
factors in a transformer rated installation needs two more places before the
result is rounded back for the record.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import total_ordering
from typing import Any

from kilodial.errors import BadInputError

PLACES = Decimal("0.0001")
NOMINAL = Decimal("100")

# A meter this far off is not a meter that drifted, it is a wiring or a
# multiplier problem, and the shop wants it flagged rather than averaged in.
IMPLAUSIBLE_LOW = Decimal("10")
IMPLAUSIBLE_HIGH = Decimal("400")


def _to_decimal(value: object) -> Decimal:
    """Coerce a caller value to Decimal without letting float noise through."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            text = text[:-1].strip()
        try:
            return Decimal(text)
        except InvalidOperation:
            raise BadInputError(f"{value!r} is not a percentage") from None
    if isinstance(value, float):
        # Accepted, but pinned through repr so 99.87 does not arrive as
        # 99.8699999999999974 and quantise the wrong way at the boundary.
        return Decimal(repr(value))
    raise BadInputError(f"cannot read a percentage from {type(value).__name__}")


@total_ordering
@dataclass(frozen=True, init=False, eq=False)
class Registration:
    """Percent registration, quantised to four places.

    Construct from anything numeric or from a string, with or without a trailing
    percent sign. ``Registration("99.87")`` and ``Registration(Decimal("99.87"))``
    are equal and hash the same.
    """

    percent: Decimal

    def __init__(self, value: object) -> None:
        pct = _to_decimal(value).quantize(PLACES)
        if pct < 0:
            raise BadInputError("a registration cannot be negative")
        object.__setattr__(self, "percent", pct)

    @classmethod
    def nominal(cls) -> Registration:
        """The meter that is exactly right."""
        return cls(NOMINAL)

    @classmethod
    def from_readings(cls, indicated: object, actual: object) -> Registration:
        """Build from the two energy figures a bench run produces.

        ``indicated`` is what the meter under test recorded, ``actual`` what the
        reference standard says passed through it. Both are plain energy in the
        same unit; the unit cancels.
        """
        top = _to_decimal(indicated)
        bottom = _to_decimal(actual)
        if bottom <= 0:
            raise BadInputError("the reference reading has to be above zero")
        if top < 0:
            raise BadInputError("the meter reading cannot be negative")
        return cls(top / bottom * NOMINAL)

    @property
    def error(self) -> Decimal:
        """Percentage points away from nominal. Positive means fast."""
        return self.percent - NOMINAL

    @property
    def is_fast(self) -> bool:
        return self.percent > NOMINAL

    @property
    def is_slow(self) -> bool:
        return self.percent < NOMINAL

    @property
    def correction_factor(self) -> Decimal:
        """What a registered quantity must be multiplied by to get the truth."""
        if self.percent == 0:
            raise BadInputError("a meter registering nothing has no correction factor")
        return (NOMINAL / self.percent).quantize(PLACES)

    @property
    def is_plausible(self) -> bool:
        """False for the readings that mean something is wired wrong."""
        return IMPLAUSIBLE_LOW <= self.percent <= IMPLAUSIBLE_HIGH

    def within(self, band: object) -> bool:
        """True when the error is inside a symmetric tolerance band."""
        limit = _to_decimal(band)
        if limit < 0:
            raise BadInputError("a tolerance band cannot be negative")
        return abs(self.error) <= limit

    def compose(self, other: Registration) -> Registration:
        """Put two registrations in series.

        A meter reading 100.30 behind a current transformer whose own factor is
        99.80 registers 100.0994 overall. Composition is what makes a
        transformer rated installation's error different from its meter's.
        """
        return Registration(self.percent * other.percent / NOMINAL)

    def rounded(self, places: int = 2) -> Decimal:
        """The figure that goes on a record, rounded for print."""
        if places < 0 or places > 4:
            raise BadInputError("registrations are recorded to between 0 and 4 places")
        return self.percent.quantize(Decimal(1).scaleb(-places))

    def __str__(self) -> str:
        return f"{self.rounded(2)}%"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Registration):
            return self.percent == other.percent
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.percent)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Registration):
            return bool(self.percent < other.percent)
        return NotImplemented


__all__ = ["IMPLAUSIBLE_HIGH", "IMPLAUSIBLE_LOW", "NOMINAL", "PLACES", "Registration"]
