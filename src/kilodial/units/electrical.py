"""The electrical quantities a bench run is described in.

A test point is a load: so many amperes at so many volts at a stated power
factor. The bench holds that load while the meter under test and the reference
standard both accumulate energy, and the ratio of the two is the registration.
These types exist so that a power factor of 0.5 lagging and a power factor of
0.5 leading are different values, which matters because a two element meter can
be wired so that it is right on one and wrong on the other.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from kilodial.errors import BadInputError

MILLI = Decimal("0.001")
CENTI = Decimal("0.01")

# Nobody runs a shop bench above these, and a value past them is a typo in a
# bench export far more often than it is a real load.
MAX_AMPERES = Decimal("400")
MAX_VOLTS = Decimal("600")


def _decimal(value: object, what: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            raise BadInputError(f"{value!r} is not a {what}") from None
    raise BadInputError(f"cannot read a {what} from {type(value).__name__}")


class Sense(enum.Enum):
    """Which way the current sits against the voltage."""

    UNITY = "unity"
    LAGGING = "lagging"
    LEADING = "leading"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Amperes:
    """Test current, held to a milliamp."""

    value: Decimal

    def __init__(self, value: object) -> None:
        amps = _decimal(value, "current").quantize(MILLI, rounding=ROUND_HALF_UP)
        if amps < 0:
            raise BadInputError("a test current cannot be negative")
        if amps > MAX_AMPERES:
            raise BadInputError(f"{amps} A is past the bench limit of {MAX_AMPERES} A")
        object.__setattr__(self, "value", amps)

    def as_percent_of(self, test_amperes: Amperes) -> Decimal:
        """Where this current sits on the meter's own scale."""
        if test_amperes.value <= 0:
            raise BadInputError("the test ampere rating has to be above zero")
        return (self.value / test_amperes.value * 100).quantize(CENTI)

    def __str__(self) -> str:
        return f"{self.value.normalize():f} A"


@dataclass(frozen=True)
class Volts:
    """Test voltage, held to a centivolt."""

    value: Decimal

    def __init__(self, value: object) -> None:
        volts = _decimal(value, "voltage").quantize(CENTI, rounding=ROUND_HALF_UP)
        if volts <= 0:
            raise BadInputError("a test voltage has to be above zero")
        if volts > MAX_VOLTS:
            raise BadInputError(f"{volts} V is past the bench limit of {MAX_VOLTS} V")
        object.__setattr__(self, "value", volts)

    def __str__(self) -> str:
        return f"{self.value.normalize():f} V"


@dataclass(frozen=True)
class PowerFactor:
    """A power factor and the sense it was applied in.

    Unity is stored with a sense of ``UNITY`` whichever way it was asked for, so
    that two unity points compare equal instead of splitting into a leading and
    a lagging flavour that no bench can tell apart.
    """

    value: Decimal
    sense: Sense

    def __init__(self, value: object, sense: Sense = Sense.UNITY) -> None:
        pf = _decimal(value, "power factor").quantize(MILLI, rounding=ROUND_HALF_UP)
        if pf <= 0 or pf > 1:
            raise BadInputError("a power factor sits above zero and at or below one")
        if not isinstance(sense, Sense):
            raise BadInputError("the sense has to be one of the Sense values")
        if pf == 1:
            sense = Sense.UNITY
        elif sense is Sense.UNITY:
            raise BadInputError("a power factor below one has to lead or lag")
        object.__setattr__(self, "value", pf)
        object.__setattr__(self, "sense", sense)

    @classmethod
    def unity(cls) -> PowerFactor:
        return cls(1)

    @classmethod
    def lagging(cls, value: object) -> PowerFactor:
        return cls(value, Sense.LAGGING)

    @classmethod
    def leading(cls, value: object) -> PowerFactor:
        return cls(value, Sense.LEADING)

    @property
    def is_unity(self) -> bool:
        return self.sense is Sense.UNITY

    def __str__(self) -> str:
        if self.is_unity:
            return "1.0 PF"
        return f"{self.value.normalize():f} PF {self.sense}"


@dataclass(frozen=True)
class WattHours:
    """Energy, held to a milliwatthour because light load runs are small."""

    value: Decimal

    def __init__(self, value: object) -> None:
        wh = _decimal(value, "quantity of energy").quantize(MILLI, rounding=ROUND_HALF_UP)
        if wh < 0:
            raise BadInputError("energy registered cannot be negative")
        object.__setattr__(self, "value", wh)

    @classmethod
    def from_revolutions(cls, kh: object, revolutions: object) -> WattHours:
        """Energy from a disc count and the meter's watthour constant.

        ``Kh`` is watthours per revolution and is stamped on the nameplate of
        every induction meter. Solid state meters publish the same number as
        watthours per output pulse, so the call works for both.
        """
        constant = _decimal(kh, "watthour constant")
        revs = _decimal(revolutions, "revolution count")
        if constant <= 0:
            raise BadInputError("the watthour constant has to be above zero")
        if revs < 0:
            raise BadInputError("a revolution count cannot be negative")
        return cls(constant * revs)

    def __add__(self, other: object) -> WattHours:
        if not isinstance(other, WattHours):
            return NotImplemented
        return WattHours(self.value + other.value)

    def __str__(self) -> str:
        return f"{self.value.normalize():f} Wh"


__all__ = [
    "CENTI",
    "MAX_AMPERES",
    "MAX_VOLTS",
    "MILLI",
    "Amperes",
    "PowerFactor",
    "Sense",
    "Volts",
    "WattHours",
]
