"""Configuration shared by the CLI, TOML files, and Python API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class ConfigurationError(ValueError):
    """An invalid semantic-wrap configuration."""


@dataclass(frozen=True)
class WrapConfig:
    """Validated widths and equal-priority preferred break characters."""

    soft_width: int = 80
    hard_width: int = 100
    preferred_markers: str = ",;:-–—"

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> WrapConfig:
        core = options.get("mdformat", {})
        settings = core.get("plugin", {}).get("semantic_wrap", {})
        defaults = cls()
        values = {}
        for name in ("soft_width", "hard_width"):
            value = settings.get(name, getattr(defaults, name))
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ConfigurationError(
                    f"semantic_wrap.{name} must be a positive integer"
                )
            values[name] = value
        if values["soft_width"] > values["hard_width"]:
            raise ConfigurationError(
                "semantic_wrap.soft_width must not exceed hard_width"
            )
        markers = settings.get("preferred_markers", defaults.preferred_markers)
        if not isinstance(markers, str) or any(
            c.isspace() or not c.isprintable() for c in markers
        ):
            raise ConfigurationError(
                "semantic_wrap.preferred_markers must be a string of visible characters"
            )
        return cls(**values, preferred_markers=markers)
