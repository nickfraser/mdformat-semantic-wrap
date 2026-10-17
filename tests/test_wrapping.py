import pytest

from mdformat_semantic_wrap.config import WrapConfig
from mdformat_semantic_wrap.upstream import ProtectedText
from mdformat_semantic_wrap.wrapping import display_width, wrap_sentence


def wrap(text, soft=20, hard=26, markers=",;:-–—", indent=0):
    return wrap_sentence(text, ProtectedText(text, {}), WrapConfig(soft, hard, markers), indent)


@pytest.mark.parametrize("text", ["Short, sentence.", "Exactly twenty chars"])
def test_short_sentence_stays_intact(text):
    assert wrap(text) == text


def test_rightmost_preferred_boundary_before_soft():
    assert wrap("One, two three, four five six seven.") == (
        "One, two three,\nfour five six seven."
    )


def test_preferred_boundary_between_soft_and_hard():
    assert wrap("One two three four five, six seven eight.") == (
        "One two three four five,\nsix seven eight."
    )


def test_whitespace_fallback_targets_soft():
    assert wrap("One two three four five six seven.") == (
        "One two three four\nfive six seven."
    )


def test_empty_marker_set_uses_whitespace():
    assert wrap("One, two three, four five six seven.", markers="") == (
        "One, two three, four\nfive six seven."
    )


@pytest.mark.parametrize("marker", [",", ";", ":", "|", "/", "§"])
def test_user_defined_markers(marker):
    assert wrap(f"One{marker} two three four five six.", markers=marker).splitlines()[0] == f"One{marker}"


def test_marker_order_does_not_establish_priority():
    text = "One, two; three four five six seven."
    assert wrap(text, markers=",;") == wrap(text, markers=";,")
    assert wrap(text).splitlines()[0] == "One, two;"


@pytest.mark.parametrize("dash", ["-", "–", "—"])
def test_standalone_dashes(dash):
    assert wrap(f"One {dash} two three four five six seven.").splitlines()[0] == f"One {dash}"


def test_hyphenated_words_are_not_preferred_boundaries():
    assert wrap("A well-known-word- and more words to wrap.").splitlines()[0] == "A well-known-word-"
    # Same result as pure whitespace wrapping: the trailing hyphen isn't preferred.
    assert wrap("A well-known-word- and more words to wrap.") == wrap(
        "A well-known-word- and more words to wrap.", markers=""
    )


def test_punctuation_without_following_whitespace_is_not_a_boundary():
    assert wrap("One,two,three,four,five,six.") == "One,two,three,four,five,six."


def test_unbreakable_word_overflows_without_being_split():
    assert wrap("x" * 40 + " and more text.") == "x" * 40 + "\nand more text."


def test_nonbreaking_space_is_never_a_break_candidate():
    assert wrap("one\u00a0two\u00a0three and four five", soft=8, hard=12).startswith("one\u00a0two\u00a0three\n")


def test_indentation_counts_against_both_widths():
    assert wrap("One two three four five six.", soft=20, hard=24, indent=4) == (
        "One two three\nfour five six."
    )


@pytest.mark.parametrize("text,width", [("中文", 4), ("e\u0301", 1), ("🙂", 2)])
def test_display_columns(text, width):
    assert display_width(text) == width


def test_wide_text_wraps_by_display_columns():
    assert wrap("中文 中文 中文 中文", soft=9, hard=12) == "中文 中文\n中文 中文"


def test_protected_content_is_measured_at_its_real_width():
    protected = ProtectedText("One X and more words.", {"X": "`a long code span`"})
    result = wrap_sentence(protected.text, protected, WrapConfig(12, 18))
    assert protected.restore(result) == "One\n`a long code span`\nand more\nwords."


@pytest.mark.parametrize("start", ["# heading", "> quote", "- item", "1. item", "---", "==="])
def test_avoid_accidental_markdown_blocks(start):
    result = wrap("Some words " + start + " and more words.", soft=10, hard=20)
    assert all(not line.startswith(start) for line in result.splitlines()[1:])
