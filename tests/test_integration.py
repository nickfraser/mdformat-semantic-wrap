import copy
import os
import re
import subprocess
import sys

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin
import mdformat
import pytest

from mdformat_semantic_wrap.config import ConfigurationError
from mdformat_semantic_wrap.wrapping import display_width


def format_text(text, *, soft=40, hard=50, markers=",;:-–—", slw=None, extensions=None):
    return mdformat.text(
        text,
        options={"wrap": "keep", "plugin": {
            "semantic_wrap": {"soft_width": soft, "hard_width": hard, "preferred_markers": markers},
            "slw": {"lang": "en", **(slw or {})},
        }},
        extensions=extensions or ["semantic_wrap"],
    )


def normalized_html(text, *, gfm=False):
    parser = MarkdownIt("commonmark")
    if gfm:
        parser.enable(["table", "strikethrough"]).use(tasklists_plugin)
    # Exact code contents are checked separately below; prose soft breaks are
    # insignificant HTML whitespace.
    return re.sub(r"\s+", " ", parser.render(text)).strip()


def test_registered_entry_point():
    assert format_text("First sentence. Second sentence.") == "First sentence.\nSecond sentence.\n"


def test_softbreaks_are_rejoined_before_sentence_detection():
    assert format_text("One short\nsentence. Another\nshort sentence.") == (
        "One short sentence.\nAnother short sentence.\n"
    )


def test_english_abbreviations():
    assert format_text("Dr. Jones arrived. We left.") == "Dr. Jones arrived.\nWe left.\n"


def test_custom_abbreviations():
    assert format_text("Zyx. Jones arrived. We left.", slw={"abbreviations": "Zyx"}) == (
        "Zyx. Jones arrived.\nWe left.\n"
    )


def test_custom_sentence_markers_are_separate_from_preferred_markers():
    assert format_text("One; two. Three! Four?", slw={"slw_markers": "!?"}) == (
        "One; two. Three!\nFour?\n"
    )


@pytest.mark.parametrize("prefix", ["", "- ", "> ", "> - ", "10. ", "- - "])
def test_nested_indentation_and_width(prefix):
    source = prefix + "One two three four five six seven eight nine ten eleven twelve."
    result = format_text(source, soft=24, hard=30)
    assert all(display_width(line) <= 30 for line in result.splitlines())
    assert normalized_html(result) == normalized_html(source)
    assert format_text(result, soft=24, hard=30) == result


@pytest.mark.parametrize("span", [
    "`a  b. c, d`",
    "`` a ` b. c, d ``",
    '[a long, label. Yes](https://example.com/path "A title, with spaces")',
    "[a long, label. Yes](https://example.com/a_(b))",
    "![a long, alt. Yes](https://example.com/image.png)",
    "<https://example.com/really/long/path>",
    "<someone.long@example.com>",
    "[`a  b`](https://example.com)",
])
def test_atomic_inline_constructs(span):
    source = "Before " + span + " after with many more words to wrap. Next sentence."
    result = format_text(source, soft=20, hard=28)
    # mdformat itself may canonicalize delimiters, e.g. URL parentheses.
    canonical_span = mdformat.text(span).strip()
    assert canonical_span in result
    assert normalized_html(result) == normalized_html(source)
    assert format_text(result, soft=20, hard=28) == result


def test_code_whitespace_and_punctuation_are_preserved_exactly():
    source = "Before `a  b.  c` and `x   y` after. Next."
    result = format_text(source, soft=20, hard=30)
    parser = MarkdownIt()
    def code_contents(text):
        return [child.content for token in parser.parse(text)
                for child in token.children or [] if child.type == "code_inline"]
    assert code_contents(result) == code_contents(source) == ["a  b.  c", "x   y"]


@pytest.mark.parametrize("link", ["[a label][ref]", "[a label][]", "[a label]", "[a\nlabel][a label]"])
def test_reference_links_and_idempotence(link):
    source = f"Before {link} and more words afterwards. Next.\n\n[ref]: https://example.com\n[a label]: https://example.org\n"
    result = format_text(source, soft=20, hard=30)
    assert normalized_html(result) == normalized_html(source)
    assert format_text(result, soft=20, hard=30) == result


@pytest.mark.parametrize("break_marker", ["\\\n", "  \n"])
def test_explicit_hardbreaks(break_marker):
    source = "Some words here" + break_marker + "other words here. Next sentence."
    result = format_text(source, soft=15, hard=20)
    assert result.count("\\\n") == 1
    assert normalized_html(result) == normalized_html(source)
    assert format_text(result, soft=15, hard=20) == result


@pytest.mark.parametrize("before", ["One two three a", "One two three ", "One two three `a b`"])
def test_hardbreak_backslash_counts_toward_width(before):
    source = before + "\\\nNext line."
    result = format_text(source, soft=15, hard=15)
    assert all(display_width(line) <= 15 for line in result.splitlines())
    assert normalized_html(result) == normalized_html(source)
    assert format_text(result, soft=15, hard=15) == result


@pytest.mark.parametrize("source", [
    "```text\nDo not wrap. Leave this long code line alone, please.\n```\n",
    "    Indented code. More code, with spaces.\n",
    "<div>\nDo not wrap. Keep this long HTML line alone.\n</div>\n",
    "Text <span title='a b'>with inline HTML. More words here.</span> trailing.\n",
    "| First long column | Second long column |\n| More words here | More words there |\n",
])
def test_protected_blocks_and_html_match_plain_mdformat(source):
    assert format_text(source, soft=10, hard=15) == mdformat.text(source)


def test_gfm_tables_task_lists_and_strikethrough():
    source = """| Header one | Header two |
| --- | --- |
| Some long words. More words. | Other long words, please. |

- [x] A completed task, with many words that need wrapping. Another sentence.
- [ ] An unfinished ~~old task~~ with more words that need wrapping.
"""
    extensions = ["gfm", "semantic_wrap"]
    result = format_text(source, soft=30, hard=40, extensions=extensions)
    table = result.split("\n\n")[0]
    assert table == mdformat.text(source, extensions=["gfm"]).split("\n\n")[0]
    assert "- [x] " in result and "- [ ] " in result
    assert normalized_html(result, gfm=True) == normalized_html(source, gfm=True)
    assert format_text(result, soft=30, hard=40, extensions=extensions) == result


@pytest.mark.parametrize("extensions", [["gfm", "semantic_wrap"], ["semantic_wrap", "gfm"]])
def test_task_checkbox_counts_toward_first_line_width(extensions):
    source = "- [x] One two three four five six seven eight nine ten eleven twelve."
    result = format_text(source, soft=24, hard=24, extensions=extensions)
    assert all(display_width(line) <= 24 for line in result.splitlines())
    assert normalized_html(result, gfm=True) == normalized_html(source, gfm=True)
    assert format_text(result, soft=24, hard=24, extensions=extensions) == result


@pytest.mark.parametrize("source", [
    "A long paragraph with *emphasis, some more words* and **strong, more words**. Next sentence.",
    "First sentence. # This stays prose and should never turn into a heading.",
    "Some words then 1. this stays prose and should never become a list.",
    "Some words then > this stays prose and should never become a quote.",
    r"Literal \` backticks, and escaped \[brackets\] and backslashes \\ remain intact.",
    "中文 中文 中文 中文 中文。 More words, and still more words.",
    "A nonbreaking\u00a0space and more words, and still more words.",
    "Private use \ue0000\ue001 and `protected code` with more words, and more.",
    "Before [link](https://example.com/\ue0000\ue001) with more words afterwards.",
    "First sentence. --- another sentence with a spaced dash and extra words.",
    "Some words here with literal backslash \\\\ and extra words after it.",
    "Some words then 1234567890. this stays prose and has stable escapes.",
    "Some words then ~~~ this stays prose and should never become a fence.",
])
def test_markdown_preservation_and_idempotence(source):
    result = format_text(source, soft=20, hard=30)
    assert normalized_html(result) == normalized_html(source)
    assert format_text(result, soft=20, hard=30) == result


def test_caller_options_are_not_mutated():
    options = {"wrap": "keep", "plugin": {"slw": {"slw_wrap": 5, "no_wrap_sentences": True}}}
    original = copy.deepcopy(options)
    assert mdformat.text("First sentence. Next sentence.", options=options,
                         extensions=["semantic_wrap"]) == "First sentence.\nNext sentence.\n"
    assert options == original


def test_reject_concurrent_slw():
    with pytest.raises(ConfigurationError, match="without slw"):
        mdformat.text("Some text.", extensions=["semantic_wrap", "slw"])


def test_reject_mdformat_generic_wrap():
    with pytest.raises(ConfigurationError, match='wrap = "keep"'):
        mdformat.text("Some text.", options={"wrap": 80}, extensions=["semantic_wrap"])


def run_cli(directory, *args):
    return subprocess.run([sys.executable, "-m", "mdformat", *args], cwd=directory,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, check=False)


def test_cli_toml_precedence_and_check(tmp_path):
    config = tmp_path / ".mdformat.toml"
    config.write_text('''wrap = "keep"
extensions = ["semantic_wrap"]
[plugin.semantic_wrap]
soft_width = 15
hard_width = 25
preferred_markers = ","
[plugin.slw]
lang = "en"
''')
    path = tmp_path / "sample.md"
    source = "One, two three four five six seven. Next sentence.\n"
    path.write_text(source)
    check = run_cli(tmp_path, "--check", str(path))
    assert check.returncode == 1, check.stderr
    assert path.read_text() == source
    result = run_cli(tmp_path, "--semantic-wrap-soft-width", "80",
                     "--semantic-wrap-hard-width", "100", str(path))
    assert result.returncode == 0, result.stderr
    assert path.read_text() == "One, two three four five six seven.\nNext sentence.\n"
    assert run_cli(tmp_path, "--semantic-wrap-soft-width", "80",
                   "--semantic-wrap-hard-width", "100", "--check", str(path)).returncode == 0


def test_cli_custom_markers_and_stdin(tmp_path):
    command = [sys.executable, "-m", "mdformat", "--extensions", "semantic_wrap",
               "--semantic-wrap-soft-width", "20", "--semantic-wrap-hard-width", "26",
               "--semantic-wrap-preferred-markers", "|", "-"]
    result = subprocess.run(command, input="One | two three four five six.\n",
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "One |\ntwo three four five\nsix.\n"


def test_readme_sentence_still_wraps_at_current_soft_target():
    source = (
        "The companion calls that plugin's sentence callback itself and rejects enabling\n"
        "both extensions together."
    )
    assert len(source.replace("\n", " ")) == 105
    assert len(source.splitlines()[0]) == 79
    assert format_text(source, soft=80, hard=100) == source + "\n"
    assert format_text(source.replace("\n", " "), soft=80, hard=100) == source + "\n"
