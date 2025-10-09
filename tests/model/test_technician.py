from __future__ import annotations

from datetime import date

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.run import RunKind
from kilodial.model.technician import Grade, Technician, grade_named


def person(**over: object) -> Technician:
    args: dict[str, object] = {
        "grade": Grade.BENCH,
        "certified_on": "2023-01-01",
        "certificate_due": "2026-01-01",
    }
    args.update(over)
    badge = args.pop("badge", "T-441")
    name = args.pop("name", "R Ellis")
    return Technician.build(badge, name, **args)


def device(**over: object) -> DeviceType:
    args: dict[str, object] = {
        "form_code": "2S",
        "class_code": "200",
        "voltage": "240",
        "kh": "7.2",
        "technology": Technology.INDUCTION,
        "register_ratio": "100",
        "introduced": "2004-05-01",
    }
    args.update(over)
    return DeviceType.build("Halvern", "R4S", **args)  # type: ignore[arg-type]


def poly() -> DeviceType:
    return device(form_code="16S", class_code="320")


def test_grade_lookup() -> None:
    assert grade_named("polyphase") is Grade.POLYPHASE
    assert grade_named(Grade.SUPERVISOR) is Grade.SUPERVISOR
    with pytest.raises(BadInputError, match="certification grade"):
        grade_named("apprentice")


def test_the_grades_stack() -> None:
    assert not Grade.BENCH.signs_polyphase
    assert Grade.POLYPHASE.signs_polyphase
    assert Grade.SUPERVISOR.signs_polyphase
    assert not Grade.POLYPHASE.signs_referee
    assert Grade.SUPERVISOR.signs_referee
    assert str(Grade.BENCH) == "bench"


def test_a_certification_carries_its_window() -> None:
    tech = person()
    assert tech.badge == "T-441"
    assert tech.window.start == date(2023, 1, 1)
    assert tech.is_certified_on("2025-03-04")
    assert not tech.is_certified_on("2026-01-02")
    assert tech.is_certified_on("2026-01-01")
    assert str(tech) == "T-441 R Ellis (bench, to 2026-01-01)"


def test_days_left_goes_negative() -> None:
    assert person().days_left_on("2026-01-01") == 0
    assert person().days_left_on("2026-01-11") == -10


def test_a_certification_that_expires_before_it_starts() -> None:
    with pytest.raises(RuleError, match="run out after"):
        person(certified_on="2026-01-01", certificate_due="2023-01-01")


def test_a_bench_technician_signs_single_phase_work() -> None:
    tech = person()
    assert tech.may_sign(RunKind.AS_FOUND, device(), on="2025-03-04")
    assert tech.refusals(RunKind.AS_FOUND, device(), on="2025-03-04") == []


def test_a_bench_technician_cannot_sign_polyphase() -> None:
    tech = person()
    assert not tech.may_sign(RunKind.AS_FOUND, poly(), on="2025-03-04")
    assert "is polyphase" in tech.refusals(RunKind.AS_FOUND, poly(), on="2025-03-04")[0]


def test_a_polyphase_technician_can() -> None:
    tech = person(grade=Grade.POLYPHASE)
    assert tech.may_sign(RunKind.AS_FOUND, poly(), on="2025-03-04")


def test_only_a_supervisor_signs_a_referee_run() -> None:
    assert not person(grade=Grade.POLYPHASE).may_sign(RunKind.REFEREE, device(), on="2025-03-04")
    assert person(grade=Grade.SUPERVISOR).may_sign(RunKind.REFEREE, device(), on="2025-03-04")


def test_a_lapsed_certification_signs_nothing() -> None:
    tech = person(grade=Grade.SUPERVISOR)
    assert not tech.may_sign(RunKind.AS_FOUND, device(), on="2026-06-01")
    assert (
        "was not certified on 2026-06-01"
        in tech.refusals(RunKind.AS_FOUND, device(), on="2026-06-01")[0]
    )


def test_every_refusal_is_reported_at_once() -> None:
    tech = person(certified_on="2010-01-01", certificate_due="2012-01-01")
    refusals = tech.refusals(RunKind.REFEREE, poly(), on="2025-03-04")
    assert len(refusals) == 3


def test_notes_are_tidied() -> None:
    assert person(note="  recert  course ").note == "recert course"
    assert person(note="  ").note is None


@pytest.mark.parametrize("bad", ["", "   ", None, "x" * 60])
def test_bad_names(bad: object) -> None:
    with pytest.raises(BadInputError):
        person(name=bad)
