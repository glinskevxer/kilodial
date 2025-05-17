from __future__ import annotations

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import MeterClass, Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.sampling.group import Group


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
    return DeviceType.build(
        str(args.pop("maker", "Halvern")),
        str(args.pop("model", "R4S")),
        **args,  # type: ignore[arg-type]
    )


def meter(serial: str = "84-119302", **over: object) -> Meter:
    args: dict[str, object] = {"acquired": "2019-04-02"}
    args.update(over)
    return Meter.receive(
        serial,
        str(args.pop("device_key", "Halvern/R4S")),
        **args,  # type: ignore[arg-type]
    )


def test_a_group_with_no_criteria_takes_everything() -> None:
    g = Group.build("ALL", "every meter")
    assert g.is_open
    assert g.takes(meter())
    assert g.criteria() == ["every meter"]


def test_a_group_by_device_key() -> None:
    g = Group.build("G1", "Halvern R4S", device_keys=["Halvern/R4S"])
    assert g.takes(meter())
    assert not g.takes(meter(device_key="Vantage/SM3"))
    assert not g.needs_device()
    assert g.criteria() == ["type Halvern/R4S"]


def test_device_keys_are_deduplicated_and_sorted() -> None:
    g = Group.build("G1", "two", device_keys=["Vantage/SM3", "Halvern/R4S", "Halvern/R4S"])
    assert g.device_keys == ("Halvern/R4S", "Vantage/SM3")


def test_a_group_by_class_needs_the_device_type() -> None:
    g = Group.build("G2", "class 200", class_code="200")
    assert g.needs_device()
    assert g.takes(meter(), device())
    assert not g.takes(meter(), device(class_code="320"))
    with pytest.raises(RuleError, match="judges on the device type"):
        g.takes(meter())


def test_a_group_by_technology() -> None:
    g = Group.build("G3", "solid state", technology=Technology.SOLID_STATE)
    assert not g.takes(meter(), device())
    assert g.takes(
        meter(),
        device(technology=Technology.SOLID_STATE, register_ratio=None),
    )


def test_a_technology_that_is_not_one() -> None:
    with pytest.raises(BadInputError, match="Technology"):
        Group.build("G3", "solid state", technology="solid state")  # type: ignore[arg-type]


def test_a_group_by_form() -> None:
    g = Group.build("G4", "polyphase", form_codes=["16s", "9S"])
    assert g.form_codes == ("16S", "9S")
    assert not g.takes(meter(), device())
    assert g.takes(meter(), device(form_code="16S", class_code="320"))


def test_a_group_by_acquisition_window() -> None:
    g = Group.build("G5", "the 2019 buy", acquired_from="2019-01-01", acquired_to="2019-12-31")
    assert g.takes(meter())
    assert not g.takes(meter(acquired="2021-04-02"))
    assert "acquired 2019-01-01 to 2019-12-31" in g.criteria()


def test_an_open_ended_acquisition_window() -> None:
    g = Group.build("G6", "everything since", acquired_from="2019-01-01")
    assert g.takes(meter(acquired="2099-01-01"))
    assert not g.takes(meter(acquired="2018-12-31"))


def test_a_window_that_ends_before_it_starts() -> None:
    with pytest.raises(RuleError, match="cannot end before"):
        Group.build("G5", "backwards", acquired_from="2020-01-01", acquired_to="2019-01-01")


def test_criteria_stack() -> None:
    g = Group.build(
        "G7",
        "induction class 200 2S",
        class_code="200",
        technology=Technology.INDUCTION,
        form_codes=["2S"],
        acquired_from="2015-01-01",
    )
    assert g.takes(meter(), device())
    assert not g.takes(meter(acquired="2010-01-01"), device())
    assert len(g.criteria()) == 4


def test_scrapped_and_lost_meters_are_out_of_the_population() -> None:
    g = Group.build("ALL", "every meter")
    scrapped = meter().moved_to(MeterState.STOCK).moved_to(MeterState.SCRAP, on="2025-01-01")
    assert not g.takes(scrapped)
    lost = meter().moved_to(MeterState.STOCK).moved_to(MeterState.SET).moved_to(MeterState.LOST)
    assert not g.takes(lost)


def test_a_set_meter_is_in_the_population() -> None:
    g = Group.build("ALL", "every meter")
    live = meter().moved_to(MeterState.STOCK).moved_to(MeterState.SET)
    assert g.takes(live)


@pytest.mark.parametrize("bad", ["", "   ", None, "x" * 80])
def test_bad_group_names(bad: object) -> None:
    with pytest.raises(BadInputError):
        Group.build("G1", bad)


def test_str_names_the_group() -> None:
    assert str(Group.build("g1", "Halvern R4S")) == "G1 Halvern R4S"
    assert Group.build("G2", "x", class_code=MeterClass.CL200).meter_class is MeterClass.CL200
