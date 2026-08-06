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


def test_split_message_modes():
    """Проверяет стратегии разбиения сообщений: line, paragraph, word, char."""
    text = "Paragraph 1 line 1\nParagraph 1 line 2\n\nParagraph 2 line 1\nParagraph 2 line 2"

    # 1. Paragraph mode
    chunks_p = split_message(text, max_length=45, mode="paragraph")
    assert len(chunks_p) == 2
    assert "Paragraph 1" in chunks_p[0]
    assert "Paragraph 2" in chunks_p[1]

    # 2. Word mode
    short_words = "One two three four five six"
    chunks_w = split_message(short_words, max_length=15, mode="word")
    assert len(chunks_w) > 1
    for c in chunks_w:
        assert len(c) <= 15

    # 3. Char mode
    chunks_c = split_message("123456789012345", max_length=5, mode="char")
    assert chunks_c == ["12345", "67890", "12345"]
