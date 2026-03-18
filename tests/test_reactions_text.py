"""Tests for the _build_reaction_text helper."""

from discord_ferry.migrator.messages import _build_reaction_text
from discord_ferry.parser.models import DCEEmoji, DCEReaction


def _r(name: str, count: int, eid: str = "") -> DCEReaction:
    return DCEReaction(emoji=DCEEmoji(id=eid, name=name), count=count)


def test_basic_formatting() -> None:
    result = _build_reaction_text([_r("thumbsup", 12), _r("tada", 5)], 500)
    assert "thumbsup 12" in result and "tada 5" in result and "·" in result


def test_single_reaction() -> None:
    result = _build_reaction_text([_r("heart", 1)], 500)
    assert "heart 1" in result and "·" not in result


def test_empty_reactions() -> None:
    assert _build_reaction_text([], 500) == ""


def test_zero_count_excluded() -> None:
    result = _build_reaction_text([_r("thumbsup", 5), _r("ghost", 0)], 500)
    assert "thumbsup" in result and "ghost" not in result


def test_zero_budget() -> None:
    assert _build_reaction_text([_r("thumbsup", 5)], 0) == ""


def test_truncation_on_tight_budget() -> None:
    reactions = [_r(f"emoji{i}", i + 1) for i in range(20)]
    result = _build_reaction_text(reactions, 50)
    assert len(result) <= 50 and "..." in result


def test_all_included_with_large_budget() -> None:
    reactions = [_r(f"e{i}", i + 1) for i in range(25)]
    result = _build_reaction_text(reactions, 2000)
    for i in range(25):
        assert f"e{i}" in result


def test_custom_emoji_uses_name() -> None:
    result = _build_reaction_text([_r("pepe", 5, eid="12345")], 500)
    assert "pepe" in result and "12345" not in result
