"""Regression tests for an mdformat-slw 0.4.0 sentence-detection limitation.

WORKAROUND(mdformat-slw): upstream misses punctuation before Markdown closing
emphasis/strong/strikethrough delimiters. The upstream-only test deliberately
records the bug. When upgrading slw, remove that reproduction and the companion's
workaround_slw_closing_delimiters hooks if the behavior tests pass without them.
The behavior tests can then remain as ordinary sentence-formatting regressions.
"""

import re

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin
import mdformat
import pytest


def format_text(text, **slw):
    return mdformat.text(
        text,
        extensions=["gfm", "semantic_wrap"],
        options={"wrap": "keep", "plugin": {"slw": {"lang": "en", **slw}}},
    )


def html(text):
    parser = MarkdownIt().enable("strikethrough").use(tasklists_plugin)
    return re.sub(r"\s+", " ", parser.render(text)).strip()


def test_upstream_still_needs_closing_delimiter_workaround():
    # Remove this upstream-bug reproduction when the pinned slw is fixed.
    source = "**First sentence.** Second sentence."
    result = mdformat.text(
        source, extensions=["slw"],
        options={"wrap": "keep", "plugin": {"slw": {
            "slw_min_line": 0, "slw_wrap": 0, "lang": "en",
        }}},
    )
    assert result == source + "\n"


@pytest.mark.parametrize("first", [
    "*First sentence.*", "_First sentence._",
    "**First sentence.**", "__First sentence.__",
    "***First sentence.***", "**First *sentence.***",
    "*First **sentence.***", "~~First sentence.~~",
    '**First sentence.**"', "(**First sentence.**)",
    "**First sentence!**", "*First sentence?*",
])
def test_workaround_splits_after_formatted_sentence(first):
    # WORKAROUND regression: upstream cannot see the terminal punctuation.
    source = first + " Second sentence."
    result = format_text(source)
    assert result == mdformat.text(first).strip() + "\nSecond sentence.\n"
    assert html(result) == html(source)
    assert format_text(result) == result


@pytest.mark.parametrize("title", ["*Dr.*", "**Dr.**", "***Dr.***", "~~Dr.~~"])
def test_workaround_retains_upstream_abbreviation_rules(title):
    source = title + " Jones arrived. We left."
    result = format_text(source)
    assert result == title + " Jones arrived.\nWe left.\n"
    assert html(result) == html(source)
    assert format_text(result) == result


def test_workaround_retains_custom_abbreviations():
    assert format_text("**Zyx.** Jones arrived. We left.", abbreviations="Zyx") == (
        "**Zyx.** Jones arrived.\nWe left.\n"
    )


def test_workaround_retains_custom_sentence_markers():
    assert format_text("**First.** Next! Last?", slw_markers="!?") == (
        "**First.** Next!\nLast?\n"
    )


def test_workaround_handles_multiple_sentences_within_emphasis():
    assert format_text("**First. Second.** Third.") == "**First.\nSecond.**\nThird.\n"


def test_workaround_does_not_interpret_escaped_literal_delimiters():
    source = r"Literal punctuation.\*\* More words."
    result = format_text(source)
    assert result == source + "\n"
    assert html(result) == html(source)


@pytest.mark.parametrize("span", [
    "`a  b. c`", "[a. b](https://example.com)",
    "[a *label.* here](https://example.com)",
])
def test_workaround_keeps_inline_constructs_protected(span):
    source = f"**Before {span} after.** Next sentence."
    result = format_text(source)
    assert result == f"**Before {span} after.**\nNext sentence.\n"
    assert html(result) == html(source)
    assert format_text(result) == result


def test_workaround_tokens_do_not_collide_with_source_quotes():
    source = "Literal \")))\" and **first.** Then *second.* Finally ~~third.~~ Done."
    result = format_text(source)
    assert result == 'Literal ")))" and **first.**\nThen *second.*\nFinally ~~third.~~\nDone.\n'
    assert html(result) == html(source)
    assert format_text(result) == result
