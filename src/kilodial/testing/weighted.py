"""The weighted average, which is the number a meter is actually judged on.

No single load point decides anything. A meter is graded on a weighted average
of its load points, and the weights are not the same for every meter: they
follow the number of measuring elements, because a three element meter spends
far more of its life on unbalanced and lagging load than a residential single
element meter ever will.

The house rule, and it is a house rule rather than a law:

    one element        full load 4, light load 1
    two elements       full load 3, light load 1, power factor 1
    two and a half     full load 3, light load 1, power factor 1
    three elements     full load 2, light load 1, power factor 2

Every row divides by five, which keeps the arithmetic comparable across the
shop. The consequence that catches people is that a power factor point is
optional paperwork on a form 2S meter and a hard requirement on a form 16S, so
the same missing point is a shrug on one bench and a void run on the next.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError
from kilodial.model.run import BenchRun, PointKind
from kilodial.units.registration import Registration

# Element count to the weight each load point carries. A kind absent from a row
# contributes nothing and is not required to be present.
WEIGHTS: dict[Decimal, dict[PointKind, int]] = {
    Decimal("1"): {PointKind.FULL_LOAD: 4, PointKind.LIGHT_LOAD: 1},
    Decimal("2"): {PointKind.FULL_LOAD: 3, PointKind.LIGHT_LOAD: 1, PointKind.POWER_FACTOR: 1},
    Decimal("2.5"): {PointKind.FULL_LOAD: 3, PointKind.LIGHT_LOAD: 1, PointKind.POWER_FACTOR: 1},
    Decimal("3"): {PointKind.FULL_LOAD: 2, PointKind.LIGHT_LOAD: 1, PointKind.POWER_FACTOR: 2},
}

DIVISOR = 5


def weights_for(elements: Decimal) -> dict[PointKind, int]:
    """The weighting row for an element count, refusing anything unlisted."""
    if elements not in WEIGHTS:
        raise RuleError(f"no weighting is defined for a {elements} element meter")
    return dict(WEIGHTS[elements])


def required_kinds(elements: Decimal) -> frozenset[PointKind]:
    """The load points a run has to carry before it can be averaged."""
    return frozenset(weights_for(elements))


@dataclass(frozen=True)
class WeightedAverage:
    """The averaged figure, with the working kept.

    The working is not decoration. A registration that gets argued about at a
    hearing gets argued about point by point, and a shop that can only produce
    the answer is in a much worse position than one that can produce the sum.
    """

    elements: Decimal
    parts: tuple[tuple[PointKind, int, Registration], ...]
    value: Registration

    @property
    def divisor(self) -> int:
        return sum(weight for _, weight, _ in self.parts)

    def show(self) -> str:
        """One line of arithmetic, in the order the weights are applied."""
        terms = " + ".join(f"{weight}x{reading.rounded(2)}" for _, weight, reading in self.parts)
        return f"({terms}) / {self.divisor} = {self.value.rounded(2)}"

    def __str__(self) -> str:
        return str(self.value)


def weighted_average(run: BenchRun, elements: Decimal) -> WeightedAverage:
    """Average a run's load points for a meter with that many elements."""
    row = weights_for(elements)
    missing = sorted(k.name.lower() for k in row if not run.has(k))
    if missing:
        raise RuleError(
            f"run {run.reference} is missing the {', '.join(missing)} "
            f"point a {elements} element meter is averaged on"
        )
    total = Decimal(0)
    parts: list[tuple[PointKind, int, Registration]] = []
    for kind in (PointKind.FULL_LOAD, PointKind.LIGHT_LOAD, PointKind.POWER_FACTOR):
        weight = row.get(kind)
        if weight is None:
            continue
        reading = run.point(kind).percent
        total += reading.percent * weight
        parts.append((kind, weight, reading))
    divisor = sum(weight for _, weight, _ in parts)
    if divisor != DIVISOR:
        raise RuleError(f"the weighting for {elements} elements adds to {divisor}, not {DIVISOR}")
    return WeightedAverage(elements, tuple(parts), Registration(total / divisor))


__all__ = [
    "DIVISOR",
    "WEIGHTS",
    "WeightedAverage",
    "required_kinds",
    "weighted_average",
    "weights_for",
]
