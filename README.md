# mdformat-semantic-wrap

A companion to [mdformat-slw](https://github.com/KyleKing/mdformat-slw) that
adds configurable soft-target punctuation wrapping to
[mdformat](https://github.com/hukkin/mdformat).
Each detected sentence starts on a new line.
Short sentences stay together;
long sentences prefer punctuation boundaries near a soft width,
with a separate hard limit.

## Installation

Requires Python 3.10 or newer.
From this checkout, install the package into your chosen Python environment:

```bash
python -m pip install .
```

To install directly from GitHub, run:

```bash
python -m pip install git+https://github.com/nickfraser/mdformat-semantic-wrap.git
```

The commands below assume the package is installed in the default `python`
environment.
The runtime dependencies include mdformat 1.x, mdformat-slw 0.4.0, and wcwidth.
The upstream plugin is pinned to the release used by the integration tests.

## Configure

Place `.mdformat.toml` in the Markdown project's root.
This repository includes this configuration:

```toml
wrap = "keep"
extensions = ["semantic_wrap"]

[plugin.semantic_wrap]
soft_width = 80
hard_width = 100
preferred_markers = ",;:-–—"

[plugin.slw]
lang = "en"
slw_markers = ".!?"
```

**Select `semantic_wrap` explicitly and omit `slw` from `extensions`.**
Mdformat normally enables every installed plugin,
including the dependency's independent wrapping pass.
The companion calls that plugin's sentence callback itself and rejects enabling
both extensions together.
Keep `wrap = "keep"` so mdformat's generic wrapper does not compete with it.

For GitHub-Flavored Markdown, install `mdformat-gfm` and use:

```toml
extensions = ["gfm", "semantic_wrap"]
```

### Soft and hard widths

Both widths are positive integers,
and `soft_width` must not exceed `hard_width`.
Widths count display columns in the rendered Markdown source, including markup,
list and blockquote indentation, and explicit hard-break backslashes.
Wide characters and combining characters are measured using wcwidth.
GFM checkbox markers count toward the first line of their task item.

For each sentence exceeding the available soft width, the wrapper chooses:

1. The rightmost preferred punctuation boundary at or before the soft width.
1. Otherwise,
   the first preferred punctuation boundary after the soft width but at or
   before the hard width.
1. Otherwise,
   the rightmost safe whitespace boundary at or before the soft width.
1. If the first word or protected span already exceeds that width,
   the first safe whitespace boundary after it.

The same rules apply repeatedly to the remaining sentence.
An indivisible word or protected span can exceed the hard limit.
Markdown safety also takes precedence over width:
wrapping must not create an accidental heading, list, blockquote,
thematic break, or code fence.

For example, with `soft_width = 20` and `hard_width = 26`:

```text
One, two three, four five six seven.
```

becomes:

```text
One, two three,
four five six seven.
```

If the first available comma is just past the target,
the hard width leaves room to use it:

```text
One two three four five,
six seven eight.
```

### User-defined punctuation

`preferred_markers` is a string of individual characters,
all with equal priority.
Their order in the string has no effect.
Characters must be visible and cannot be whitespace.
For example:

```toml
[plugin.semantic_wrap]
preferred_markers = ",;:"  # Prefer only commas, semicolons, and colons.
```

A marker becomes a candidate only when followed by breakable whitespace.
Hyphens (`-`), en dashes (`–`),
and em dashes (`—`) additionally need preceding whitespace,
so hyphenated words are preserved.
Breaks retain the punctuation at the end of the preceding line.
An empty string disables punctuation preference and uses whitespace wrapping.

These markers are separate from `[plugin.slw].slw_markers`,
which identifies sentence endings regardless of soft width.
Sentence detection follows mdformat-slw's language and abbreviation rules.
Use its `abbreviations` and `abbreviations_only` options for project-specific abbreviations,
for example:

```toml
[plugin.slw]
lang = "en"
abbreviations = "Zyx,Acme"
```

The companion locally overrides `slw_min_line`, `slw_wrap`,
and `no_wrap_sentences` when invoking upstream:
it always splits recognized sentences and applies its own width rules.
It does not mutate the caller's options.

### Protected content

- Inline code, links, images, and autolinks stay atomic during reflow.
- Significant spaces inside code spans are preserved.
- Existing prose soft breaks are rejoined before wrapping;
  explicit hard breaks remain hard breaks.
- Nonbreaking spaces are never wrapping candidates.
- Headings and code blocks are left to mdformat's normal renderers.
- Tables and definition lists are excluded when their syntax extensions are enabled;
  pipe-prefixed table-like paragraphs are also excluded.
- HTML blocks and paragraphs containing inline HTML are left to mdformat's normal formatting,
  preserving newline-sensitive HTML.

## Format and check

```bash
python -m mdformat README.md
python -m mdformat --check README.md
```

`--check` reports unformatted files with a nonzero exit status and does not edit
them.
Directories can be passed alongside individual files.

CLI options override values in `.mdformat.toml`:

```bash
python -m mdformat \
  --semantic-wrap-soft-width 72 \
  --semantic-wrap-hard-width 88 \
  --semantic-wrap-preferred-markers ',;:' \
  README.md
```

Without a configuration file, select the extension explicitly:

```bash
python -m mdformat --extensions semantic_wrap README.md
```

To disable punctuation preference on the CLI,
pass `--semantic-wrap-preferred-markers ''`.
The dependency's `--slw-lang`, `--slw-markers`,
and abbreviation options are also available,
even though its independent extension is disabled.

## Python API

The Python API takes options explicitly; it does not read `.mdformat.toml`:

```python
import mdformat

formatted = mdformat.text(
    "One, two three, four five six seven. Another sentence.",
    extensions=["semantic_wrap"],
    options={
        "wrap": "keep",
        "plugin": {
            "semantic_wrap": {
                "soft_width": 20,
                "hard_width": 26,
                "preferred_markers": ",;:",
            },
            "slw": {"lang": "en"},
        },
    },
)
```

## Development

Install an editable checkout with the development dependencies:

```bash
python -m pip install -e '.[dev]'
```

The `dev` extra includes the test dependencies and pre-commit.
The `test` extra includes pytest, `mdformat-gfm`,
and the build backends used by the versioning integration tests.

Package source lives in `src/mdformat_semantic_wrap/`:

- `plugin.py`: mdformat hooks and protected inline nodes.
- `config.py`: shared configuration validation.
- `upstream.py`: the public mdformat-slw paragraph-callback adapter.
- `wrapping.py`: punctuation selection and display-column measurement.

The adapter invokes `mdformat_slw.POSTPROCESSORS["paragraph"]` with a copied
context.
It uses no private upstream helpers or monkey-patching.
Mdformat's inline hooks protect code and links before sentence detection.

### Upstream workarounds

mdformat-slw 0.4.0 misses sentence-ending punctuation before Markdown closing emphasis delimiters,
for example `**First sentence.** Second sentence.`.
The companion's `workaround_slw_closing_delimiters` hook temporarily represents
AST-confirmed closing emphasis, strong-emphasis,
and strikethrough delimiters as closing characters recognized by upstream,
then restores the original markup.
Abbreviation handling and configured sentence markers still come from upstream.

The hook, its registrations,
and its token prefix are explicitly marked `WORKAROUND(mdformat-slw)` in
`plugin.py`.
`tests/test_slw_workarounds.py` documents the upstream bug and tests the
companion-side correction.
When upgrading the pinned dependency to a release that fixes this behavior,
remove the upstream-only bug reproduction and the workaround hooks,
then verify that the behavior regressions still pass.

### Tests and pre-commit

Run the pytest suite after installing the `test` extra:

```bash
python -m pytest
```

Tests cover marker selection, widths, abbreviations, protected content,
nested indentation, GFM integration, HTML equivalence, idempotence,
TOML/CLI precedence, and `--check` behavior.
Pytest uses its standard cache and temporary-directory locations.

After installing the `dev` extra, configure the Git hook and run it manually:

```bash
python -m pre_commit install
python -m pre_commit run --all-files
```

The repository-local hook runs `python -m mdformat` on Markdown files,
using `.mdformat.toml` and the current editable plugin checkout.
It uses `python` on `PATH`,
which must have the development dependencies installed.
The hook formats files in place;
review and stage any formatting changes before committing again.

### Versioning and distributions

Versions come from Git through `hatch-vcs` and `setuptools_scm`.
There is no manually maintained version string in `pyproject.toml`.
Use tags such as `v1.2.3` for releases:

- A clean checkout at `v1.2.3` builds version `1.2.3`.
- Commits after that tag get a next-patch development version such as
  `1.2.4.dev1+g<commit>`.
- Dirty tracked files add a date to the local version identifier.
- Before the first release tag,
  builds receive an SCM-derived development version.

Editable-install version metadata reflects the Git state at installation time.
Refresh it after changing tags or commits by rerunning the editable installation
command above.
Formatting code changes themselves are picked up immediately by the editable
install.
To inspect the installed version:

```bash
python -c 'from importlib.metadata import version; print(version("mdformat-semantic-wrap"))'
```

The versioning tests use disposable repositories under pytest's temporary
directory to check clean tags, development commits, dirty checkouts,
untagged checkouts, and building a wheel from an sdist without Git metadata.

Build the wheel and source distribution with:

```bash
python -m hatchling build
```

Build artifacts are written to `dist/`.
Source distributions preserve their resolved version when built without Git.
