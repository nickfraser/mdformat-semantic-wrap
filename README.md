# mdformat-semantic-wrap

A companion to [mdformat-slw](https://github.com/KyleKing/mdformat-slw) that
adds configurable soft-target punctuation wrapping to
[mdformat](https://github.com/hukkin/mdformat).
Each detected sentence starts on a new line.
Short sentences stay together;
long sentences prefer punctuation boundaries near a soft width,
with a separate hard limit.

## Install locally

Requires Python 3.10 or newer and `uv`.
From this checkout, create an environment and install the package:

```bash
UV_CACHE_DIR=.ocs/cache uv venv .ocs/venv
UV_CACHE_DIR=.ocs/cache uv pip install --python .ocs/venv/bin/python -e '.[test]'
```

The `test` extra includes pytest and `mdformat-gfm` for integration tests.
For an installation without test dependencies,
use `-e .` instead of `-e '.[test]'`.
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

**Select `semantic_wrap` explicitly and omit `slw` from `extensions`.** Mdformat
normally enables every installed plugin,
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
.ocs/venv/bin/python -m mdformat README.md
.ocs/venv/bin/python -m mdformat --check README.md
```

`--check` reports unformatted files with a nonzero exit status and does not edit
them.
Directories can be passed alongside individual files.

CLI options override values in `.mdformat.toml`:

```bash
.ocs/venv/bin/python -m mdformat \
  --semantic-wrap-soft-width 72 \
  --semantic-wrap-hard-width 88 \
  --semantic-wrap-preferred-markers ',;:' \
  README.md
```

Without a configuration file, select the extension explicitly:

```bash
.ocs/venv/bin/python -m mdformat --extensions semantic_wrap README.md
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

Package source lives in `src/mdformat_semantic_wrap/`:

- `plugin.py`: mdformat hooks and protected inline nodes.
- `config.py`: shared configuration validation.
- `upstream.py`: the public mdformat-slw paragraph-callback adapter.
- `wrapping.py`: punctuation selection and display-column measurement.

The adapter invokes `mdformat_slw.POSTPROCESSORS["paragraph"]` with a copied
context.
It uses no private upstream helpers or monkey-patching.
Mdformat's inline hooks protect code and links before sentence detection.

Run the pytest suite after installing the `test` extra:

```bash
PYTHONPYCACHEPREFIX=.ocs/pycache .ocs/venv/bin/python -m pytest
```

Tests cover marker selection, widths, abbreviations, protected content,
nested indentation, GFM integration, HTML equivalence, idempotence,
TOML/CLI precedence, and `--check` behavior.
Pytest caches and its default temporary directory live under `.ocs/`.

Build the wheel and source distribution with:

```bash
UV_CACHE_DIR=.ocs/cache uv build --python .ocs/venv/bin/python --out-dir .ocs/dist
```

Build artifacts are written to `.ocs/dist/`.
