from __future__ import annotations

from datetime import date

import pytest

from kilodial.errors import BadInputError, RuleError, StateError
from kilodial.tamper.event import (
    Finding,
    Standing,
    TamperKind,
    confirmed_before,
    earliest_since,
    tamper_kind,
)


def finding(reference: str = "TF-1", kind: object = "seal cut", **over: object) -> Finding:
    args: dict[str, object] = {"found_on": "2025-06-30", "found_by": "R Ellis"}
    args.update(over)
    return Finding.raise_finding(reference, str(args.pop("point_code", "SP-1042")), kind, **args)


def confirmed(reference: str = "TF-1", **over: object) -> Finding:
    since = str(over.pop("since", "2024-01-01"))
    return finding(reference, **over).confirmed(
        on="2025-07-04", since=since, evidence="jumper on the load side"
    )


def test_kind_lookup() -> None:
    assert tamper_kind("bypass") is TamperKind.BYPASS
    assert tamper_kind("SEAL_CUT") is TamperKind.SEAL_CUT
    assert tamper_kind(TamperKind.REVERSED) is TamperKind.REVERSED


@pytest.mark.parametrize("bad", ["vandalism", "", None, 4])
def test_a_kind_nobody_finds(bad: object) -> None:
    with pytest.raises(BadInputError, match="not a tamper finding"):
        tamper_kind(bad)


def test_which_findings_stop_the_meter_measuring() -> None:
    assert not TamperKind.SEAL_CUT.unmeters
    assert TamperKind.BYPASS.unmeters
    assert TamperKind.METER_MISSING.unmeters
    assert str(TamperKind.DIALS_TURNED) == "dials turned"


def test_a_new_finding_is_only_a_suspicion() -> None:
    f = finding()
    assert f.standing is Standing.SUSPECTED
    assert f.is_open
    assert not f.standing.moves_money
    assert f.settled_on is None
    assert str(f) == "TF-1 SP-1042 seal cut (suspected)"


def test_confirming_needs_a_start_and_evidence() -> None:
    f = confirmed()
    assert f.standing is Standing.CONFIRMED
    assert f.standing.moves_money
    assert f.since == date(2024, 1, 1)
    assert f.settled_on == date(2025, 7, 4)
    assert f.evidence == "jumper on the load side"


def test_confirming_without_evidence() -> None:
    with pytest.raises(RuleError, match="evidence written down"):
        finding().confirmed(on="2025-07-04", since="2024-01-01", evidence="  ")


def test_interference_cannot_start_after_it_was_found() -> None:
    with pytest.raises(RuleError, match="started after it was found"):
        finding().confirmed(on="2025-07-04", since="2025-08-01", evidence="jumper")


def test_a_finding_cannot_be_settled_before_it_was_made() -> None:
    with pytest.raises(RuleError, match="settled before it was made"):
        finding().confirmed(on="2025-01-01", since="2024-01-01", evidence="jumper")
    with pytest.raises(RuleError, match="settled before it was made"):
        finding().cleared(on="2025-01-01", why="tree crew")


def test_clearing_needs_a_reason() -> None:
    f = finding().cleared(on="2025-07-04", why="  tree crew cut it ")
    assert f.standing is Standing.CLEARED
    assert not f.is_open
    assert not f.standing.moves_money
    assert f.evidence == "tree crew cut it"
    with pytest.raises(RuleError, match="needs a reason"):
        finding().cleared(on="2025-07-04", why="   ")


def test_clearing_keeps_what_was_already_written() -> None:
    f = finding(evidence="seal wire hanging").cleared(on="2025-07-04", why="tree crew")
    assert f.evidence == "seal wire hanging; tree crew"


def test_a_settled_finding_cannot_be_settled_again() -> None:
    f = confirmed()
    with pytest.raises(StateError, match="already confirmed"):
        f.confirmed(on="2025-08-01", since="2024-01-01", evidence="again")
    with pytest.raises(StateError):
        f.cleared(on="2025-08-01", why="never mind")


def test_the_period_a_confirmed_finding_covers() -> None:
    span = confirmed().span()
    assert span.start == date(2024, 1, 1)
    assert span.end == date(2025, 6, 30)


def test_a_suspicion_has_no_period() -> None:
    with pytest.raises(RuleError, match="has no period"):
        finding().span()


def test_only_confirmed_findings_count() -> None:
    findings = [
        finding("TF-1").cleared(on="2025-07-04", why="tree crew"),
        confirmed("TF-2", since="2024-01-01"),
        finding("TF-3"),
    ]
    assert [f.reference for f in confirmed_before(findings, "2025-12-31")] == ["TF-2"]
    assert earliest_since(findings, "2025-12-31") == date(2024, 1, 1)


def test_findings_after_the_day_do_not_count() -> None:
    findings = [confirmed("TF-2", since="2024-01-01")]
    assert confirmed_before(findings, "2025-01-01") == []
    assert earliest_since(findings, "2025-01-01") is None


def test_the_earliest_start_wins() -> None:
    findings = [
        confirmed("TF-2", since="2024-06-01"),
        confirmed("TF-3", since="2023-02-01"),
    ]
    assert earliest_since(findings, "2025-12-31") == date(2023, 2, 1)
    assert [f.reference for f in confirmed_before(findings, "2025-12-31")] == [
        "TF-3",
        "TF-2",
    ]
