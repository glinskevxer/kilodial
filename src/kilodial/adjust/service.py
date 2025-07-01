"""Raising an adjustment off the book, with every input resolved for you.

The pieces are all in place by now and the value of this module is that it wires
them together in the one order that is defensible. Getting any of these in the
wrong order produces a number that looks right:

The set has to be the one standing on the day of the run, not the one standing
today. A meter pulled last month and replaced would otherwise be adjusted with
the new meter's transformers and multiplier.

The clean test has to be looked for at the same service point as well as on the
same meter. A meter that passed a test in the shop before it was set here says
nothing about this installation, whose current transformer might be the thing
that is wrong.

The billed history has to be clipped to the period after the period has been
worked out, not before. Clipping first hides the case where nothing was billed
over the period at all, which is a real situation and needs its own answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from kilodial.adjust.compute import Adjustment, compute
from kilodial.adjust.period import Period, period_for
from kilodial.adjust.rules import STATE_TARIFF, Tariff, is_adjustable, lookback_months, why_not
from kilodial.errors import RuleError
from kilodial.install.multiplier import InstalledAccuracy, accuracy_of
from kilodial.install.point import MeterSet
from kilodial.model.run import BenchRun, RunKind
from kilodial.store.shop import Shop
from kilodial.units.electrical import PowerFactor


@dataclass(frozen=True)
class Refusal:
    """Why no adjustment was raised, in words a clerk can pass on."""

    point_code: str
    reason: str
    accuracy: InstalledAccuracy | None

    def __str__(self) -> str:
        return f"{self.point_code}: {self.reason}"


def finding_run(shop: Shop, serial: str) -> BenchRun:
    """The run that found the error: the latest usable as found or referee run."""
    for run in reversed(shop.runs.for_meter(serial)):
        if run.kind not in (RunKind.AS_FOUND, RunKind.REFEREE):
            continue
        verdict = shop.judge_run(run)
        if verdict.outcome.is_usable and verdict.registration is not None:
            return run
    raise RuleError(f"meter {serial.strip().upper()} has no usable as found run")


def last_clean_test(
    shop: Shop,
    meter_set: MeterSet,
    before: object,
    *,
    tariff: Tariff = STATE_TARIFF,
    power_factor: PowerFactor | None = None,
) -> str | None:
    """The most recent earlier run on this installation that was inside tolerance."""
    cutoff = str(before)
    for run in reversed(shop.runs.for_meter(meter_set.meter_serial)):
        if run.tested_on.isoformat() >= cutoff:
            continue
        if run.kind not in (RunKind.AS_FOUND, RunKind.REFEREE, RunKind.ACCEPTANCE):
            continue
        if not meter_set.was_set_on(run.tested_on):
            continue
        verdict = shop.judge_run(run)
        if verdict.registration is None or not verdict.outcome.is_usable:
            continue
        stood = accuracy_of(
            meter_set,
            verdict.registration,
            current=shop.transformers.find(meter_set.ct_serial),
            voltage=shop.transformers.find(meter_set.vt_serial),
            power_factor=power_factor,
        )
        if is_adjustable(stood, tariff):
            continue
        return run.tested_on.isoformat()
    return None


def raise_adjustment(
    shop: Shop,
    point_code: str,
    *,
    on: object,
    tariff: Tariff = STATE_TARIFF,
    power_factor: PowerFactor | None = None,
) -> Adjustment | Refusal:
    """Work an adjustment out for a service point, or say why there is not one."""
    code = point_code.strip().upper()
    standing = shop.installs.current(code)
    if standing is None:
        history = shop.installs.history(code)
        if not history:
            raise RuleError(f"nothing has ever been set at {code}")
        standing = history[-1]
    run = finding_run(shop, standing.meter_serial)
    meter_set = shop.installs.on_day(code, run.tested_on) or standing
    accuracy = shop.accuracy_of_set(meter_set, power_factor=power_factor)
    if not is_adjustable(accuracy, tariff):
        return Refusal(code, str(why_not(accuracy, tariff)), accuracy)
    period = period_for(
        found_on=run.tested_on,
        set_on=meter_set.set_on,
        cap_months=lookback_months(accuracy, tariff),
        pulled_on=meter_set.removed_on,
        last_clean_on=last_clean_test(
            shop,
            meter_set,
            run.tested_on.isoformat(),
            tariff=tariff,
            power_factor=power_factor,
        ),
    )
    billed = shop.billing.covering(code, period.span)
    if not billed:
        return Refusal(
            code,
            f"there is no billed history for {period.span}, so nothing can be worked out",
            accuracy,
        )
    return compute(
        point_code=code,
        meter_serial=meter_set.meter_serial,
        accuracy=accuracy,
        period=period,
        billed=billed,
        on=on,
        tariff=tariff,
    )


def period_of(
    shop: Shop,
    point_code: str,
    *,
    tariff: Tariff = STATE_TARIFF,
    power_factor: PowerFactor | None = None,
) -> Period:
    """The adjustment period alone, for a clerk checking a date."""
    raised = raise_adjustment(
        shop, point_code, on="2000-01-01", tariff=tariff, power_factor=power_factor
    )
    if isinstance(raised, Refusal):
        raise RuleError(raised.reason)
    return raised.period


__all__ = ["Refusal", "finding_run", "last_clean_test", "period_of", "raise_adjustment"]
