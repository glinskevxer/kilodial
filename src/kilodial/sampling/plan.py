"""Sample plans: how many to test, and what the answer buys.

The whole point of periodic sample testing is that a utility with sixty thousand
meters cannot bench all of them, so it tests a sample of a homogeneous group and
lets the result decide when that group is next looked at. A group that comes
back tight gets a longer interval. A group that comes back loose gets a shorter
one, and a group that comes back badly enough gets pulled and mass tested.

Two things decide it and both have to pass:

The spread. The mean of the sample plus and minus two standard deviations has to
sit inside the in service band. A group can have a mean of exactly a hundred and
still fail this, and that is deliberate: a group whose meters are scattered half
a percent either side is a group that is about to start producing failures even
though its average is perfect.

The failures. No more than one meter in twenty may be outside the band on its
own. A tight mean cannot buy out a group with a real failure rate.

The interval ladder is in months and the steps are the ones the commission
recognises. Passing moves one step up, failing moves one step down, and the
bottom step failing is not a shorter interval, it is a mass test.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError
from kilodial.units.registration import Registration

# Lot size to the number that has to be tested. Small groups are tested whole,
# because a sample of a group of forty says nothing anybody would defend.
SAMPLE_SIZES: tuple[tuple[int, int], ...] = (
    (50, 0),
    (100, 25),
    (200, 30),
    (500, 40),
    (1200, 55),
    (3200, 75),
    (10000, 100),
)
LARGEST_SAMPLE = 125

INTERVAL_LADDER: tuple[int, ...] = (48, 72, 96, 120, 144, 192, 240, 300)

SPREAD_FACTOR = Decimal("2")
FAILURE_SHARE = Decimal("0.05")
DEFAULT_BAND = Decimal("2.0")


def sample_size(population: int) -> int:
    """How many of a population have to be tested. Zero means all of them."""
    if population < 0:
        raise RuleError("a population cannot be negative")
    for ceiling, size in SAMPLE_SIZES:
        if population <= ceiling:
            return population if size == 0 else size
    return LARGEST_SAMPLE


def required(population: int) -> int:
    """The same number, with the test everything case resolved."""
    size = sample_size(population)
    return min(size, population) if size else population


def step_interval(months: int, *, passed: bool) -> int | None:
    """Move one step along the ladder, or say the group has run out of ladder."""
    if months not in INTERVAL_LADDER:
        raise RuleError(f"{months} months is not a step on the test interval ladder")
    index = INTERVAL_LADDER.index(months)
    if passed:
        return INTERVAL_LADDER[min(index + 1, len(INTERVAL_LADDER) - 1)]
    if index == 0:
        return None
    return INTERVAL_LADDER[index - 1]


def mean_of(readings: list[Registration]) -> Decimal:
    if not readings:
        raise RuleError("there is nothing to average")
    total = sum((r.percent for r in readings), Decimal(0))
    return (total / len(readings)).quantize(Decimal("0.0001"))


def deviation_of(readings: list[Registration]) -> Decimal:
    """Sample standard deviation, with the n minus one divisor."""
    if len(readings) < 2:
        return Decimal(0)
    average = mean_of(readings)
    squares = sum(((r.percent - average) ** 2 for r in readings), Decimal(0))
    return (squares / (len(readings) - 1)).sqrt().quantize(Decimal("0.0001"))


@dataclass(frozen=True)
class SampleOutcome:
    """What a group's sample decided, and the working behind it."""

    population: int
    required: int
    tested: int
    mean: Decimal
    deviation: Decimal
    failures: int
    band: Decimal
    reasons: tuple[str, ...]

    @property
    def upper(self) -> Decimal:
        return (self.mean + SPREAD_FACTOR * self.deviation).quantize(Decimal("0.0001"))

    @property
    def lower(self) -> Decimal:
        return (self.mean - SPREAD_FACTOR * self.deviation).quantize(Decimal("0.0001"))

    @property
    def failure_share(self) -> Decimal:
        if self.tested == 0:
            return Decimal(0)
        return (Decimal(self.failures) / self.tested).quantize(Decimal("0.0001"))

    @property
    def passed(self) -> bool:
        return not self.reasons

    def show(self) -> str:
        return (
            f"{self.tested} of {self.population}, mean {self.mean}, "
            f"deviation {self.deviation}, spread {self.lower} to {self.upper}"
        )

    def __str__(self) -> str:
        return f"{'passed' if self.passed else 'failed'}: {self.show()}"


def assess(
    readings: list[Registration],
    *,
    population: int,
    band: Decimal = DEFAULT_BAND,
) -> SampleOutcome:
    """Judge a group's sample against the spread and the failure rules."""
    wanted = required(population)
    if population <= 0:
        raise RuleError("a group with no meters in it cannot be sampled")
    if len(readings) > population:
        raise RuleError(f"{len(readings)} readings were given for a population of {population}")
    reasons: list[str] = []
    if len(readings) < wanted:
        reasons.append(
            f"the sample is {len(readings)} and a population of {population} needs {wanted}"
        )
    average = mean_of(readings) if readings else Decimal(0)
    spread = deviation_of(readings)
    failures = sum(1 for r in readings if not r.within(band))
    outcome = SampleOutcome(
        population=population,
        required=wanted,
        tested=len(readings),
        mean=average,
        deviation=spread,
        failures=failures,
        band=band,
        reasons=tuple(reasons),
    )
    checked = list(reasons)
    high = outcome.upper - 100
    low = outcome.lower - 100
    if abs(high) > band or abs(low) > band:
        checked.append(
            f"the spread runs {outcome.lower} to {outcome.upper}, outside "
            f"the +/-{band} percent band"
        )
    if outcome.failure_share > FAILURE_SHARE:
        checked.append(
            f"{failures} of {len(readings)} are outside the band, over the "
            f"{FAILURE_SHARE * 100} percent allowed"
        )
    return SampleOutcome(
        population=population,
        required=wanted,
        tested=len(readings),
        mean=average,
        deviation=spread,
        failures=failures,
        band=band,
        reasons=tuple(checked),
    )


__all__ = [
    "DEFAULT_BAND",
    "FAILURE_SHARE",
    "INTERVAL_LADDER",
    "LARGEST_SAMPLE",
    "SAMPLE_SIZES",
    "SPREAD_FACTOR",
    "SampleOutcome",
    "assess",
    "deviation_of",
    "mean_of",
    "required",
    "sample_size",
    "step_interval",
]
