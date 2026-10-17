import pytest

from mdformat_semantic_wrap.config import ConfigurationError, WrapConfig


def options(**settings):
    return {"mdformat": {"plugin": {"semantic_wrap": settings}}}


def test_defaults():
    assert WrapConfig.from_options({}) == WrapConfig(80, 100, ",;:-–—")


def test_custom_markers_and_equal_widths():
    assert WrapConfig.from_options(options(
        soft_width=30, hard_width=30, preferred_markers="|/"
    )) == WrapConfig(30, 30, "|/")


def test_disable_preference():
    assert WrapConfig.from_options(options(preferred_markers="")).preferred_markers == ""


@pytest.mark.parametrize("key", ["soft_width", "hard_width"])
@pytest.mark.parametrize("value", [True, False, 0, -1, 1.5, "80", None])
def test_invalid_width(key, value):
    with pytest.raises(ConfigurationError, match=key):
        WrapConfig.from_options(options(**{key: value}))


def test_soft_above_hard():
    with pytest.raises(ConfigurationError, match="must not exceed"):
        WrapConfig.from_options(options(soft_width=101))


@pytest.mark.parametrize("value", [None, [], 123, "a b", "\n", "\x00"])
def test_invalid_markers(value):
    with pytest.raises(ConfigurationError, match="preferred_markers"):
        WrapConfig.from_options(options(preferred_markers=value))
