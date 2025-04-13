"""What a whole installation registers, and whether its multiplier is right.

Two different things can be wrong with a transformer rated installation and they
do not compose with each other, which is the point of keeping them apart here.

The first is measurement. The meter has an error, the current transformer has
one, the voltage transformer has one, and they multiply. A meter reading 100.30
behind a current transformer contributing 99.80 registers 100.0994 overall, and
whether that is acceptable is a tolerance question.

The second is arithmetic. The billing system multiplies the register reading by
a number somebody typed in. If that number is not the product of the transformer
ratios and the register multiplier, the bill is wrong by whatever the ratio of
the two is, and no tolerance in the world covers being billed at forty times
instead of eighty. That is not an error to be averaged in with the meter's half
percent; it is a separate finding that gets corrected in full.

So ``accuracy_of`` reports both and never folds one into the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError
from kilodial.install.point import MeterSet
from kilodial.units.electrical import PowerFactor
from kilodial.units.registration import Registration
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind

# How far a programmed multiplier may sit from the computed one before it is a
# finding. Multipliers are whole numbers in practice, so this is tight on
# purpose: it catches a rounded entry without firing on one.
MULTIPLIER_SLACK = Decimal("0.0001")


@dataclass(frozen=True)
class InstalledAccuracy:
    """Everything wrong with one installation, kept apart by kind."""

    meter: Registration
    current_transformer: Registration | None
    voltage_transformer: Registration | None
    overall: Registration
    expected_multiplier: Decimal
    programmed_multiplier: Decimal
    power_factor: PowerFactor

    @property
    def multiplier_ratio(self) -> Decimal:
        """Programmed over expected. One means the arithmetic is right."""
        return (self.programmed_multiplier / self.expected_multiplier).quantize(Decimal("0.000001"))

    @property
    def multiplier_is_right(self) -> bool:
        return abs(self.multiplier_ratio - 1) <= MULTIPLIER_SLACK

    @property
    def billed_registration(self) -> Registration:
        """What the customer's bill registers, multiplier error included.

        This is the only number in the package that folds the two kinds of error
        together, and it exists because a bill does not care which kind it was.
        """
        return Registration(self.overall.percent * self.multiplier_ratio)

    def faults(self) -> list[str]:
        found: list[str] = []
        if not self.multiplier_is_right:
            found.append(
                f"programmed multiplier {self.programmed_multiplier.normalize():f} against "
                f"a computed {self.expected_multiplier.normalize():f}"
            )
        return found

    def __str__(self) -> str:
        return f"{self.overall} overall at {self.power_factor}"


def expected_multiplier(
    meter_set: MeterSet,
    *,
    current: InstrumentTransformer | None = None,
    voltage: InstrumentTransformer | None = None,
) -> Decimal:
    """The multiplier the installation ought to be billed at."""
    total = meter_set.register_multiplier
    if current is not None:
        _expect(current, TransformerKind.CURRENT)
        total *= current.marked_ratio
    if voltage is not None:
        _expect(voltage, TransformerKind.VOLTAGE)
        total *= voltage.marked_ratio
    return total


def _expect(transformer: InstrumentTransformer, kind: TransformerKind) -> None:
    if transformer.kind is not kind:
        raise RuleError(
            f"transformer {transformer.serial} is a {transformer.kind} transformer "
            f"and was given as the {kind} one"
        )


def accuracy_of(
    meter_set: MeterSet,
    meter: Registration,
    *,
    current: InstrumentTransformer | None = None,
    voltage: InstrumentTransformer | None = None,
    power_factor: PowerFactor | None = None,
) -> InstalledAccuracy:
    """Compose the meter and its transformers into one installation reading."""
    pf = power_factor if power_factor is not None else PowerFactor.unity()
    if meter_set.ct_serial is not None and current is None:
        raise RuleError(
            f"set at {meter_set.point_code} names current transformer "
            f"{meter_set.ct_serial}, which was not supplied"
        )
    if meter_set.vt_serial is not None and voltage is None:
        raise RuleError(
            f"set at {meter_set.point_code} names voltage transformer "
            f"{meter_set.vt_serial}, which was not supplied"
        )
    overall = meter
    ct_share = None
    vt_share = None
    if current is not None:
        ct_share = current.contribution(pf)
        overall = overall.compose(ct_share)
    if voltage is not None:
        vt_share = voltage.contribution(pf)
        overall = overall.compose(vt_share)
    return InstalledAccuracy(
        meter=meter,
        current_transformer=ct_share,
        voltage_transformer=vt_share,
        overall=overall,
        expected_multiplier=expected_multiplier(meter_set, current=current, voltage=voltage),
        programmed_multiplier=meter_set.programmed_multiplier,
        power_factor=pf,
    )


__all__ = ["MULTIPLIER_SLACK", "InstalledAccuracy", "accuracy_of", "expected_multiplier"]
