from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.model.run import PointKind
from kilodial.tools import build_glossary as gate


def test_the_glossary_on_disk_matches_the_code() -> None:
    assert gate.differences() == []


def test_the_check_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--check"]) == 0
    assert "matches the" in capsys.readouterr().out


def test_the_domain_packages_are_in_and_the_plumbing_is_out() -> None:
    assert gate.is_domain("kilodial.model.device")
    assert gate.is_domain("kilodial.adjust.rules")
    assert not gate.is_domain("kilodial.store.shop")
    assert not gate.is_domain("kilodial.cli.main")
    assert not gate.is_domain("kilodial.tools.build_glossary")


def test_every_term_carries_a_summary() -> None:
    found = gate.terms()
    assert len(found) > 60
    for term in found:
        assert term.summary
        assert not term.name.startswith("_")


def test_the_terms_are_grouped_and_sorted() -> None:
    found = gate.terms()
    keys = [(t.area, t.name) for t in found]
    assert keys == sorted(keys)


def test_an_enum_carries_its_members() -> None:
    labels = gate.members_of(PointKind)
    assert "FL" in labels
    assert "CR" in labels


def test_a_class_that_is_not_an_enum_carries_none() -> None:
    from kilodial.units.money import Money

    assert gate.members_of(Money) == ()


def test_the_glossary_names_the_words_that_matter() -> None:
    text = gate.build()
    for word in ("Registration", "Outcome", "DueState", "TamperKind", "Basis"):
        assert f"### {word}" in text
    assert "void" in text
    assert "suspect" in text


def test_writing_and_reading_back(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "glossary.md"
    gate.write(path)
    assert gate.differences(path) == []


def test_a_missing_glossary(tmp_path: Path) -> None:
    assert "there is no glossary" in gate.differences(tmp_path / "nowhere.md")[0]


def test_a_stale_glossary(tmp_path: Path) -> None:
    path = tmp_path / "glossary.md"
    gate.write(path)
    path.write_text(path.read_text().replace("Registration", "Regisstration", 1))
    assert any("should be" in p for p in gate.differences(path))


def test_the_check_fails_on_a_stale_glossary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "glossary.md"
    path.write_text("nothing like it\n")
    assert gate.main(["--check", "--path", str(path)]) == 1
    assert "bring it up to date" in capsys.readouterr().out


def test_writing_from_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "glossary.md"
    assert gate.main(["--path", str(path)]) == 0
    assert "terms" in capsys.readouterr().out
