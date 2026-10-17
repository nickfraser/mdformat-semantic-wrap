"""mdformat parser-extension interface."""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping

from markdown_it import MarkdownIt
from mdformat.renderer import DEFAULT_RENDERERS, RenderContext, RenderTreeNode
from mdformat.renderer.typing import Postprocess, Render

from .config import ConfigurationError, WrapConfig
from .upstream import ProtectedText, sentence_breaks
from .wrapping import wrap_sentence


def add_cli_argument_group(group: argparse._ArgumentGroup) -> None:
    """Expose overrides without argparse defaults masking TOML settings."""
    group.add_argument(
        "--semantic-wrap-soft-width", type=int, dest="soft_width",
        help="Target width in display columns, including indentation (default: 80)",
    )
    group.add_argument(
        "--semantic-wrap-hard-width", type=int, dest="hard_width",
        help="Maximum breakable line width in display columns (default: 100)",
    )
    group.add_argument(
        "--semantic-wrap-preferred-markers", dest="preferred_markers",
        help="Preferred punctuation characters; an empty string disables preference",
    )


def update_mdit(mdit: MarkdownIt) -> None:
    """Validate options without introducing new Markdown syntax."""
    WrapConfig.from_options(mdit.options)
    core = mdit.options.get("mdformat", {})
    if core.get("wrap", "keep") != "keep":
        raise ConfigurationError('semantic_wrap requires mdformat wrap = "keep"')


def _paragraph(node: RenderTreeNode) -> RenderTreeNode | None:
    while node.parent:
        node = node.parent
        if node.type == "paragraph":
            return node
    return None


def softbreak(node: RenderTreeNode, context: RenderContext) -> str:
    """Rejoin prose input wrapping before inline constructs are rendered."""
    # Join source soft breaks before rendering links, so mdformat chooses the
    # final shortcut/reference spelling on the first pass too.
    paragraph = _paragraph(node)
    if paragraph is not None and not _skip(paragraph):
        return " "
    return DEFAULT_RENDERERS["softbreak"](node, context)


def protect_inline(text: str, node: RenderTreeNode, context: RenderContext) -> str:
    """Keep an inline construct atomic through sentence detection and wrapping."""
    paragraph = _paragraph(node)
    if paragraph is None or _skip(paragraph):
        return text
    state_key = "mdformat_semantic_wrap.protected"
    if state_key not in context.env:
        # Pick a prefix absent from all source tokens in this paragraph. The
        # placeholder alphabet is also disjoint from Markdown delimiters.
        prefix = "\ue000"
        contents = [
            child.content + str(child.attrs)
            for child in paragraph.walk(include_self=True)
        ]
        while any(prefix in content for content in contents):
            prefix += "\ue000"
        context.env[state_key] = (prefix, {})
    prefix, replacements = context.env[state_key]
    key = f"{prefix}{len(replacements)}\ue001"
    replacements[key] = text
    return key


def _skip(node: RenderTreeNode) -> bool:
    parent = node.parent
    while parent:
        if parent.type in {"table", "dl", "definition_list"}:
            return True
        parent = parent.parent
    source_lines = node.children[0].content.splitlines()
    if source_lines and all(
        line.lstrip().startswith("|") for line in source_lines if line.strip()
    ):
        return True
    # Inline HTML can depend on its exact newline placement. Be conservative
    # with the containing paragraph, as upstream protection doesn't cover it.
    return any(child.type == "html_inline" for child in node.walk(include_self=True))


def wrap_paragraph(text: str, node: RenderTreeNode, context: RenderContext) -> str:
    """Apply sentence boundaries, then soft-target punctuation wrapping."""
    import mdformat_slw

    if mdformat_slw in context.options.get("parser_extension", ()):
        raise ConfigurationError(
            'Enable semantic_wrap without slw: extensions = ["semantic_wrap"] '
            '(include other syntax extensions as needed)'
        )
    _, replacements = context.env.pop("mdformat_semantic_wrap.protected", ("", {}))
    protected = ProtectedText(text, replacements)
    if not text.strip() or _skip(node):
        return protected.restore(text)
    config = WrapConfig.from_options(context.options)
    # mdformat-gfm adds the checkbox after rendering the first paragraph. Its
    # four columns belong only to the first output line, not continuations.
    first_line_extra = 0
    if (
        node.previous_sibling is None
        and node.parent is not None
        and node.parent.type == "list_item"
        and "task-list-item" in node.parent.attrs.get("class", "").split()
    ):
        first_line_extra = 4
        text = re.sub(r"^(?:&#32;)+", "", text).lstrip()
        protected.text = text
    sentences = sentence_breaks(protected.text, node, context)
    indent = context.env.get("indent_width", 0)
    lines = []
    for sentence in sentences.split("\n"):
        # Keep the hard-break backslash attached and include it in the width.
        wrapped = wrap_sentence(
            sentence, protected, config, indent, first_line_extra=first_line_extra
        )
        lines.append(wrapped)
        first_line_extra = 0
    return protected.restore("\n".join(lines))


RENDERERS: Mapping[str, Render] = {"softbreak": softbreak}
POSTPROCESSORS: Mapping[str, Postprocess] = {
    "paragraph": wrap_paragraph,
    "code_inline": protect_inline,
    "link": protect_inline,
    "image": protect_inline,
}
