"""Current and voltage transformers, and the two errors they each carry.

A meter behind instrument transformers is only as accurate as they are, and they
carry two separate errors that have to be combined before either means anything.

The ratio correction factor is the easy one. A 200 to 5 current transformer
whose true ratio is 200.4 to 5 has an RCF of 1.002, and everything through it is
under measured by two parts in a thousand whatever the load is doing.

The phase angle error is the interesting one, and it is the reason this module
exists rather than a single multiplier on the installation. A transformer whose
secondary phasor sits a few minutes away from its primary introduces an error
that is exactly zero at unity power factor and grows with the tangent of the
load angle. So an installation that is dead right on a resistive load can be
half a percent out on a motor load, with nothing about the transformer having
changed. Any calculation that folds the two errors into one number before the
power factor is known has thrown that away.

The house formula, with the phase angle in minutes and positive when the
secondary phasor leads:

    PACF = 1 - (minutes x tan(theta)) / 3438
    TCF  = RCF x PACF

3438 is the number of minutes in a radian, near enough for angles this small,
and it is the number every burden table in the trade is built on.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.units.electrical import PowerFactor
from kilodial.units.registration import Registration
from kilodial.units.span import parse_date
from kilodial.units.text import key, number, positive, tidy

MINUTES_PER_RADIAN = Decimal("3438")
PLACES = Decimal("0.000001")

# Ratio correction factors outside this are a transformer nobody would install.
MIN_RCF = Decimal("0.9")
MAX_RCF = Decimal("1.1")
MAX_MINUTES = Decimal("240")


class TransformerKind(enum.Enum):
    """Which quantity the transformer steps down."""

    CURRENT = "current"
    VOLTAGE = "voltage"

    def __str__(self) -> str:
        return self.value


class AccuracyClass(enum.Enum):
    """How far the transformer correction factor may sit from one.

    The number is the allowance in percent, so a 0.3 class transformer has to
    hold its TCF between 0.997 and 1.003 across its burden range.
    """

    C03 = ("0.3", "0.3")
    C06 = ("0.6", "0.6")
    C12 = ("1.2", "1.2")

    def __init__(self, code: str, allowance: str) -> None:
        self.code = code
        self.allowance = Decimal(allowance)

    @property
    def limits(self) -> tuple[Decimal, Decimal]:
        share = self.allowance / 100
        return (Decimal(1) - share, Decimal(1) + share)

    def __str__(self) -> str:
        return self.code


def accuracy_class(code: object) -> AccuracyClass:
    """Read an accuracy class by its printed code, such as 0.3."""
    if isinstance(code, AccuracyClass):
        return code
    text = str(code).strip()
    for member in AccuracyClass:
        if member.code == text:
            return member
    raise BadInputError(f"{code!r} is not an instrument transformer accuracy class")


def tan_theta(power_factor: PowerFactor) -> Decimal:
    """The tangent of the load angle, signed by the sense.

    Lagging is positive and leading is negative, which is what makes the phase
    angle correction pull one way on a motor load and the other on a capacitive
    one. Unity is exactly zero, and that is not a rounding: it is why a
    transformer with a phase angle error passes a unity power factor test.
    """
    pf = power_factor.value
    if pf == 1:
        return Decimal(0)
    tangent = ((Decimal(1) - pf * pf).sqrt() / pf).quantize(PLACES)
    return -tangent if power_factor.sense.value == "leading" else tangent


@dataclass(frozen=True)
class InstrumentTransformer:
    """One current or voltage transformer, as tested."""

    serial: str
    kind: TransformerKind
    maker: str
    marked_ratio: Decimal
    accuracy: AccuracyClass
    rcf: Decimal
    phase_minutes: Decimal
    burden: str
    tested_on: date

    @classmethod
    def build(
        cls,
        serial: object,
        *,
        kind: TransformerKind,
        maker: object,
        marked_ratio: object,
        accuracy: object,
        rcf: object,
        phase_minutes: object = 0,
        burden: object = "B0.1",
        tested_on: object,
    ) -> InstrumentTransformer:
        if not isinstance(kind, TransformerKind):
            raise BadInputError("the kind has to be a TransformerKind")
        ratio = positive(marked_ratio, "marked ratio")
        factor = number(rcf, "ratio correction factor")
        if factor < MIN_RCF or factor > MAX_RCF:
            raise RuleError(f"a ratio correction factor of {factor} is not a transformer")
        minutes = number(phase_minutes, "phase angle")
        if abs(minutes) > MAX_MINUTES:
            raise RuleError(f"a phase angle of {minutes} minutes is not a transformer")
        return cls(
            serial=key(serial, "transformer serial", 24),
            kind=kind,
            maker=tidy(maker, "maker name", 40),
            marked_ratio=ratio,
            accuracy=accuracy_class(accuracy),
            rcf=factor,
            phase_minutes=minutes,
            burden=key(burden, "burden", 12),
            tested_on=parse_date(tested_on),
        )

    def pacf(self, power_factor: PowerFactor) -> Decimal:
        """The phase angle correction factor at a given load angle."""
        return (
            Decimal(1) - (self.phase_minutes * tan_theta(power_factor)) / MINUTES_PER_RADIAN
        ).quantize(PLACES)

    def tcf(self, power_factor: PowerFactor) -> Decimal:
        """The transformer correction factor: ratio and phase together."""
        return (self.rcf * self.pacf(power_factor)).quantize(PLACES)

    def contribution(self, power_factor: PowerFactor) -> Registration:
        """What this transformer does to the registration of the whole set.

        A correction factor above one means the true quantity is larger than the
        metered one, so the installation registers low. The contribution is the
        reciprocal expressed as a percentage, which composes straight onto the
        meter's own registration.
        """
        factor = self.tcf(power_factor)
        if factor <= 0:
            raise RuleError(f"transformer {self.serial} has a correction factor of {factor}")
        return Registration(Decimal(100) / factor)

    @property
    def true_ratio(self) -> Decimal:
        return (self.marked_ratio * self.rcf).quantize(Decimal("0.0001"))

    def within_class(self, power_factor: PowerFactor) -> bool:
        """Whether the transformer is holding the class it is stamped with."""
        low, high = self.accuracy.limits
        return low <= self.tcf(power_factor) <= high

    def __str__(self) -> str:
        return (
            f"{self.serial} {self.kind} {self.marked_ratio.normalize():f}:1 "
            f"class {self.accuracy} RCF {self.rcf}"
        )


__all__ = [
    "MAX_MINUTES",
    "MAX_RCF",
    "MINUTES_PER_RADIAN",
    "MIN_RCF",
    "PLACES",
    "AccuracyClass",
    "InstrumentTransformer",
    "TransformerKind",
    "accuracy_class",
    "tan_theta",
]
