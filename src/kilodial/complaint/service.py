"""Opening a customer request and answering it off the book.

The fiddly part is not the fee, it is deciding what "inside tolerance" means for
this question. A customer asked about their bill, so the thing that has to be
inside tolerance is the installation as it billed them, not the meter on its
own. An installation whose meter is perfect and whose multiplier is doubled
overbilled the customer by a factor of two, and charging them a fee for asking
would be indefensible.

So the answer runs the referee run through the same installed accuracy path an
adjustment uses, and a multiplier error waives the fee exactly as a bad meter
would.

When the customer last asked is not stored on the request. It is derived from
the other requests on the book at the moment it is needed, because storing it
would freeze an answer that changes whenever an older request is entered late,
and requests do arrive late.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from kilodial.adjust.rules import STATE_TARIFF, Tariff, is_adjustable
from kilodial.complaint.request import Charge, Reason, Request, charge_for
from kilodial.errors import RuleError
from kilodial.install.multiplier import InstalledAccuracy
from kilodial.model.run import RunKind
from kilodial.store.complaints import Complaint
from kilodial.store.shop import Shop
from kilodial.units.electrical import PowerFactor
from kilodial.units.money import Money


@dataclass(frozen=True)
class Answer:
    """What answering a request decided, with the reading behind it."""

    complaint: Complaint
    accuracy: InstalledAccuracy
    charge: Charge
    fee: Money

    @property
    def within_tolerance(self) -> bool:
        return not self.charge.name.startswith("WAIVED_ACCURACY")

    def explain(self) -> str:
        return f"{self.complaint.reference}: {self.accuracy.overall} overall, fee {self.charge}"

    def __str__(self) -> str:
        return self.explain()


def log(
    shop: Shop,
    reference: str,
    point_code: str,
    *,
    on: object,
    by: str,
    reason: object = Reason.OTHER,
    note: object = None,
) -> Complaint:
    """Open a request, filling in when the customer last asked."""
    code = point_code.strip().upper()
    previous = shop.complaints.previous_for(code, on)
    request = Request.build(
        reference,
        code,
        requested_on=on,
        requested_by=by,
        reason=reason,
        note=note,
        previous_request_on=previous,
    )
    return shop.complaints.open_request(request)


def answer(
    shop: Shop,
    reference: str,
    *,
    run_reference: str,
    on: object,
    fee: Money | None = None,
    tariff: Tariff = STATE_TARIFF,
    power_factor: PowerFactor | None = None,
) -> Answer:
    """Answer an open request with a referee run and close it."""
    complaint = shop.complaints.get(reference)
    run = shop.runs.get(run_reference)
    if run.kind is not RunKind.REFEREE:
        raise RuleError(
            f"run {run.reference} is an {run.kind} run and a customer request "
            "is answered by a referee run"
        )
    meter_set = shop.installs.on_day(complaint.request.point_code, run.tested_on)
    if meter_set is None:
        raise RuleError(
            f"nothing was set at {complaint.request.point_code} on {run.tested_on.isoformat()}"
        )
    if meter_set.meter_serial != run.meter_serial:
        raise RuleError(
            f"run {run.reference} is on meter {run.meter_serial} and "
            f"{meter_set.meter_serial} was set at {complaint.request.point_code}"
        )
    request = replace(
        complaint.request,
        previous_request_on=shop.complaints.previous_for(
            complaint.request.point_code, complaint.request.requested_on
        ),
    )
    verdict = shop.judge_run(run)
    if verdict.registration is None or not verdict.outcome.is_usable:
        raise RuleError(f"run {run.reference} is {verdict.outcome} and answers nothing")
    accuracy = shop.accuracy_of_set(
        meter_set, reading=verdict.registration, power_factor=power_factor
    )
    inside = not is_adjustable(accuracy, tariff)
    decided, owed = charge_for(
        request,
        tested_on=run.tested_on,
        within_tolerance=inside,
        **({} if fee is None else {"fee": fee}),
    )
    closed = shop.complaints.close(
        complaint.reference,
        run_reference=run.reference,
        charge=decided,
        fee=owed,
        on=on,
    )
    return Answer(closed, accuracy, decided, owed)


def previous_free_window(shop: Shop, point_code: str, on: object) -> bool:
    """Whether a request made on a day would be the customer's free one."""
    previous = shop.complaints.previous_for(point_code, on)
    request = Request.build(
        "CR-PROBE",
        point_code,
        requested_on=on,
        requested_by="probe",
        previous_request_on=previous,
    )
    return request.in_free_window()


__all__ = ["Answer", "answer", "log", "previous_free_window"]
