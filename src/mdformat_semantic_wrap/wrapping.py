"""Deterministic, display-column-aware wrapping of protected prose."""

from __future__ import annotations

import re

from wcwidth import wcswidth

from .config import WrapConfig
from .upstream import ProtectedText


def display_width(text: str) -> int:
    """Measure display columns, with a fallback for control characters."""
    width = wcswidth(text)
    return width if width >= 0 else len(text)


def _unsafe_start(text: str) -> bool:
    """Disallow continuation starts that could introduce Markdown blocks."""
    if text and not text.strip("\\"):
        return True
    return bool(
        re.match(
            r"(?:>|#{1,6}(?:\s|$)|[-+*](?:\s|$)|\d+[.)](?:\s|$)"
            r"|[-=]{2,}(?:\s|$)|_{3,}(?:\s|$)|~{3,}|(?:\*\s*){3,}$)",
            text,
        )
    )


def wrap_sentence(
    sentence: str,
    protected: ProtectedText,
    config: WrapConfig,
    indent: int = 0,
    *,
    first_line_extra: int = 0,
) -> str:
    """Wrap one sentence; placeholders remain opaque until final output."""
    soft = max(1, config.soft_width - indent - first_line_extra)
    hard = max(1, config.hard_width - indent - first_line_extra)
    lines = []
    remaining = sentence.strip(" \t")
    while display_width(protected.restore(remaining)) > soft:
        candidates = []
        # Only regular spaces/tabs are breakable, never a nonbreaking space.
        for match in re.finditer(r"[ \t]+", remaining):
            head = remaining[:match.start()]
            tail = remaining[match.end():]
            if not head or not tail or _unsafe_start(protected.restore(tail)):
                continue
            # An odd run of backslashes before whitespace must not become a
            # hard break. An existing hard-break suffix remains attached.
            backslashes = len(head) - len(head.rstrip("\\"))
            if backslashes % 2:
                continue
            width = display_width(protected.restore(head))
            marker = head[-1]
            preferred = marker in config.preferred_markers
            if marker in "-–—":
                preferred = preferred and (len(head) == 1 or head[-2].isspace())
            candidates.append((match.start(), match.end(), width, preferred))
            # Later candidates cannot fit. Keep the first overflow candidate
            # only as a fallback for an indivisible span or unsafe line start.
            if width > hard:
                break
        if not candidates:
            break
        before = [c for c in candidates if c[2] <= soft]
        preferred_before = [c for c in before if c[3]]
        preferred_after = [c for c in candidates if soft < c[2] <= hard and c[3]]
        if preferred_before:
            chosen = preferred_before[-1]
        elif preferred_after:
            chosen = preferred_after[0]
        elif before:
            chosen = before[-1]
        else:
            # The first indivisible word/span may overflow the hard limit.
            # Keep it intact and resume wrapping after it.
            chosen = candidates[0]
        lines.append(remaining[:chosen[0]])
        remaining = remaining[chosen[1]:]
        soft = max(1, config.soft_width - indent)
        hard = max(1, config.hard_width - indent)
    lines.append(remaining)
    return "\n".join(lines)
