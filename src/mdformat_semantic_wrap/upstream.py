"""Keep the pinned mdformat-slw integration in one place.

Only sentence_breaks invokes the public paragraph callback. No private
mdformat-slw helpers are imported.
"""

from __future__ import annotations

from dataclasses import dataclass

import mdformat_slw
from mdformat.renderer import RenderContext, RenderTreeNode


@dataclass
class ProtectedText:
    """Opaque placeholders prevent reflow inside Markdown inline constructs."""

    text: str
    replacements: dict[str, str]

    def restore(self, text: str) -> str:
        # Outer links/images may contain already-protected inline code.
        for key, value in reversed(self.replacements.items()):
            text = text.replace(key, value)
        return text


def sentence_breaks(text: str, node: RenderTreeNode, context: RenderContext) -> str:
    """Use upstream abbreviations and markers without its width restrictions."""
    core = dict(context.options.get("mdformat", {}))
    # The flat keys have upstream API precedence over [plugin.slw]. Copy rather
    # than mutate shared options or cached configuration.
    core.update(no_wrap_sentences=False, slw_min_line=0, slw_wrap=0)
    local = context._replace(options={**context.options, "mdformat": core})
    return mdformat_slw.POSTPROCESSORS["paragraph"](text, node, local)
