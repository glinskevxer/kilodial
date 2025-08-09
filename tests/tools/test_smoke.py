from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.store.shop import open_shop
from kilodial.tools import smoke as gate


def test_the_walk_gets_through_every_step() -> None:
    steps = gate.run_smoke()
    assert len(steps) == 7
    assert any("stood up" in s for s in steps)
    assert any("refund" in s for s in steps)
    assert steps[-1] == "book audits clean"


def test_standing_a_shop_up(tmp_path: Path) -> None:
    with open_shop(tmp_path / "smoke.sqlite3", create=True) as shop:
        gate.stand_up(shop)
        summary = shop.summary()
        assert summary["device types"] == 1
        assert summary["meter sets"] == 1
        assert summary["billed months"] == 6
        assert shop.audit() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    printed = capsys.readouterr().out
    assert "smoke passed in 7 steps" in printed
    assert "stood up" in printed


def test_quiet_prints_only_the_verdict(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--quiet"]) == 0
    printed = capsys.readouterr().out
    assert "smoke passed" in printed
    assert "stood up" not in printed


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> list[str]:
        raise AssertionError("the wheel is missing a module")

    monkeypatch.setattr(gate, "run_smoke", broken)
    assert gate.main([]) == 1
    assert "smoke failed: the wheel is missing a module" in capsys.readouterr().out


def test_expect_raises_on_a_false_condition() -> None:
    gate._expect(True, "fine")
    with pytest.raises(AssertionError, match="not fine"):
        gate._expect(False, "not fine")


def test_the_walk_leaves_no_book_behind(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())
    gate.run_smoke()
    assert set(tmp_path.iterdir()) == before
