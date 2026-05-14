import asyncio
import json

import pytest

from chutils.logger import setup_logger, bind_context, unbind_context, clear_context


@pytest.mark.asyncio
async def test_context_isolation():
    """Проверяет изоляцию контекста между асинхронными корутинами."""
    logger = setup_logger(name="isolation_test", force_reconfigure=True)

    async def task(name, value, delay):
        token = bind_context(**{name: value})
        try:
            await asyncio.sleep(delay)
            # Проверяем, что в этой корутине контекст сохранился
            # и не был перезаписан другой корутиной
            from chutils.context import get_context
            ctx = get_context()
            assert ctx.get(name) == value
            assert len(ctx) == 1
        finally:
            unbind_context(token)

    # Запускаем две корутины параллельно
    await asyncio.gather(
        task("req_id", "AAA", 0.1),
        task("req_id", "BBB", 0.05)
    )


def test_bind_unbind_clear():
    """Проверяет базовые функции управления контекстом."""
    clear_context()
    from chutils.context import get_context

    assert get_context() == {}

    t1 = bind_context(user="alice")
    assert get_context() == {"user": "alice"}

    t2 = bind_context(request_id="123")
    assert get_context() == {"user": "alice", "request_id": "123"}

    unbind_context(t2)
    assert get_context() == {"user": "alice"}

    clear_context()
    assert get_context() == {}


def test_text_log_context_attribute(capsys):
    """Проверяет наличие %(context)s в текстовом логе."""
    clear_context()
    logger = setup_logger(name="text_ctx_test", json_format=False, force_reconfigure=True)

    # Без контекста %(context)s должен быть пустым
    logger.info("No context")
    captured = capsys.readouterr()
    # Мы ожидаем, что форматтер по умолчанию включает %(context)s
    # Если его нет в контексте, он должен быть ""
    assert "No context" in captured.err

    bind_context(request_id="REQ-1")
    logger.info("With context")
    captured = capsys.readouterr()
    assert "[request_id=REQ-1]" in captured.err
    assert "With context" in captured.err


def test_json_log_context_attribute(capsys):
    """Проверяет группировку контекста в JSON логе."""
    clear_context()
    logger = setup_logger(name="json_ctx_test", json_format=True, force_reconfigure=True)

    bind_context(user_id=42, trace="abc")
    logger.info("JSON with context")

    captured = capsys.readouterr()
    log_json = json.loads(captured.err.strip().split('\n')[-1])

    assert "context" in log_json
    assert log_json["context"]["user_id"] == 42
    assert log_json["context"]["trace"] == "abc"
    assert log_json["message"] == "JSON with context"
