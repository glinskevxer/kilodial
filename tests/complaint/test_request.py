from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.complaint.request import (
    STANDARD_FEE,
    Charge,
    Reason,
    Request,
    charge_for,
    fee_share,
    reason_named,
)
from kilodial.errors import BadInputError, RuleError
from kilodial.units.money import Money


def request(**over: object) -> Request:
    args: dict[str, object] = {
        "requested_on": "2025-03-04",
        "requested_by": "M Okafor",
        "reason": Reason.HIGH_BILL,
    }
    args.update(over)
    return Request.build(
        str(args.pop("reference", "CR-2025-0044")),
        str(args.pop("point_code", "SP-1042")),
        **args,
    )


def test_a_request_is_tidied() -> None:
    r = request(reference=" cr-2025-0044 ", point_code="sp-1042")
    assert r.reference == "CR-2025-0044"
    assert r.point_code == "SP-1042"
    assert str(r) == "CR-2025-0044 SP-1042 2025-03-04 (high bill)"


def test_reason_lookup() -> None:
    assert reason_named("suspected tamper") is Reason.SUSPECTED_TAMPER
    assert reason_named("SUSPECTED_TAMPER") is Reason.SUSPECTED_TAMPER
    assert reason_named(Reason.OTHER) is Reason.OTHER


@pytest.mark.parametrize("bad", ["angry", "", None, 4])
def test_a_reason_nobody_files(bad: object) -> None:
    with pytest.raises(BadInputError):
        reason_named(bad)


def test_the_utility_has_thirty_days() -> None:
    r = request()
    assert r.due_by == date(2025, 4, 3)
    assert not r.was_late("2025-04-03")
    assert r.was_late("2025-04-04")
    assert r.days_taken("2025-03-14") == 10


def test_a_first_request_is_in_the_free_window() -> None:
    r = request()
    assert r.free_window_ends is None
    assert r.in_free_window()


def test_a_second_request_inside_two_years_is_not_free() -> None:
    r = request(previous_request_on="2024-01-01")
    assert r.free_window_ends == date(2026, 1, 1)
    assert not r.in_free_window()


def test_a_second_request_after_two_years_is_free_again() -> None:
    r = request(requested_on="2026-03-04", previous_request_on="2024-01-01")
    assert r.in_free_window()


def test_a_previous_request_cannot_be_in_the_future() -> None:
    with pytest.raises(RuleError, match="cannot be later"):
        request(previous_request_on="2026-01-01")


def test_a_bad_meter_waives_the_fee() -> None:
    charge, owed = charge_for(request(), tested_on="2025-03-14", within_tolerance=False)
    assert charge is Charge.WAIVED_ACCURACY
    assert owed.is_zero
    assert not charge.payable


def test_a_late_test_waives_the_fee_on_a_good_meter() -> None:
    r = request(previous_request_on="2024-01-01")
    charge, owed = charge_for(r, tested_on="2025-05-01", within_tolerance=True)
    assert charge is Charge.WAIVED_LATE
    assert owed.is_zero


def test_accuracy_is_checked_before_lateness() -> None:
    r = request(previous_request_on="2024-01-01")
    charge, _ = charge_for(r, tested_on="2025-05-01", within_tolerance=False)
    assert charge is Charge.WAIVED_ACCURACY


def test_the_free_test_is_not_charged() -> None:
    charge, owed = charge_for(request(), tested_on="2025-03-14", within_tolerance=True)
    assert charge is Charge.WAIVED_FREE
    assert owed.is_zero


def test_a_repeat_request_on_a_good_meter_is_charged() -> None:
    r = request(previous_request_on="2024-01-01")
    charge, owed = charge_for(r, tested_on="2025-03-14", within_tolerance=True)
    assert charge is Charge.CHARGED
    assert owed == STANDARD_FEE
    assert charge.payable
    assert str(charge) == "charged"


def test_the_fee_can_be_set() -> None:
    r = request(previous_request_on="2024-01-01")
    _, owed = charge_for(r, tested_on="2025-03-14", within_tolerance=True, fee=Money("40"))
    assert owed == Money("40.00")


def test_a_negative_fee() -> None:
    with pytest.raises(BadInputError, match="cannot be negative"):
        charge_for(request(), tested_on="2025-03-14", within_tolerance=True, fee=Money("-1"))


def test_the_fee_share() -> None:
    assert fee_share(STANDARD_FEE, Charge.CHARGED) == Decimal(1)
    assert fee_share(STANDARD_FEE, Charge.WAIVED_LATE) == Decimal(0)
    assert fee_share(Money.zero(), Charge.CHARGED) == Decimal(0)


def test_notes_are_tidied() -> None:
    assert request(note="  bill   doubled ").note == "bill doubled"
    assert request(note="   ").note is None
