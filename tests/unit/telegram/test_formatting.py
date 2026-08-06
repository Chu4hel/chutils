import pytest

from chutils.telegram.formatting import (
    escape_markdown,
    escape_html,
    smart_truncate,
    split_message,
)


def test_escape_markdown_v2():
    """Проверяет экранирование спецсимволов для MarkdownV2."""
    raw = "Hello *world*! Price: $10.00 [link](http://test.com) #tag"
    escaped = escape_markdown(raw, version=2)
    assert r"\*world\*" in escaped
    assert r"\!" in escaped
    assert r"10\.00" in escaped
    assert r"\[link\]\(http://test\.com\)" in escaped
    assert r"\#tag" in escaped


def test_escape_markdown_v1():
    """Проверяет экранирование спецсимволов для MarkdownV1."""
    raw = "Hello *world*_code_ [link]"
    escaped = escape_markdown(raw, version=1)
    assert r"\*world\*" in escaped
    assert r"\_code\_" in escaped
    assert r"\[link]" in escaped


def test_escape_html():
    """Проверяет экранирование спецсимволов для HTML."""
    raw = "1 < 2 & 3 > 0 \"quote\""
    escaped = escape_html(raw)
    assert escaped == "1 &lt; 2 &amp; 3 &gt; 0 &quot;quote&quot;"


def test_smart_truncate():
    """Проверяет умную обрезку текста с закрытием блоков кода."""
    raw_code = "```python\nprint('hello world')\n```"
    truncated = smart_truncate(raw_code, max_length=20)
    assert truncated.endswith("\n```...")


def test_split_message():
    """Проверяет разбиение длинного текста на список чанков."""
    long_text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    chunks = split_message(long_text, max_length=15)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 15
