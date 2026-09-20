"""
Тесты для модуля фильтров логирования chutils.logger.filters.
"""

from __future__ import annotations

import logging
import re
import threading
import time

from chutils.logger import FlappingFilter


def _make_record(
    msg: str,
    level: int = logging.ERROR,
    name: str = "test_logger",
) -> logging.LogRecord:
    """Создает тестовый объект LogRecord."""
    return logging.LogRecord(
        name=name,
        level=level,
        pathname="test_file.py",
        lineno=10,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_flapping_filter_non_matching_message() -> None:
    """Проверяет, что несовпадающие сообщения не модифицируются и проходят фильтр."""
    f = FlappingFilter(patterns="Connection lost", threshold=3)
    record = _make_record("Normal database query failed", level=logging.ERROR)

    assert f.filter(record) is True
    assert record.levelno == logging.ERROR
    assert record.levelname == "ERROR"
    assert f.consecutive_failures == 0


def test_flapping_filter_downgrade_action() -> None:
    """Проверяет понижение уровня (downgrade) при сбоях ниже порога."""
    f = FlappingFilter(
        patterns="Connection lost",
        threshold=3,
        action="downgrade",
        downgrade_level=logging.INFO,
    )

    rec1 = _make_record("Connection lost: retry 1", level=logging.ERROR)
    assert f.filter(rec1) is True
    assert rec1.levelno == logging.INFO
    assert rec1.levelname == "INFO"
    assert f.consecutive_failures == 1
    assert not f.is_escalated

    rec2 = _make_record("Connection lost: retry 2", level=logging.ERROR)
    assert f.filter(rec2) is True
    assert rec2.levelno == logging.INFO
    assert rec2.levelname == "INFO"
    assert f.consecutive_failures == 2
    assert not f.is_escalated

    # 3-я попытка достигает порога -> эскалация, уровень остается ERROR
    rec3 = _make_record("Connection lost: retry 3", level=logging.ERROR)
    assert f.filter(rec3) is True
    assert rec3.levelno == logging.ERROR
    assert rec3.levelname == "ERROR"
    assert f.consecutive_failures == 3
    assert f.is_escalated
    assert "[DOWNTIME THRESHOLD EXCEEDED" in str(rec3.msg)


def test_flapping_filter_drop_action() -> None:
    """Проверяет действие drop (полное отсечение записи до порога)."""
    f = FlappingFilter(patterns="Timeout occurred", threshold=2, action="drop")

    rec1 = _make_record("Timeout occurred: try 1")
    assert f.filter(rec1) is False
    assert f.consecutive_failures == 1

    rec2 = _make_record("Timeout occurred: try 2")
    assert f.filter(rec2) is True
    assert f.consecutive_failures == 2
    assert f.is_escalated


def test_flapping_filter_regex_pattern() -> None:
    """Проверяет работу фильтра с регулярными выражениями."""
    pattern = re.compile(r"Worker \d+ died")
    f = FlappingFilter(patterns=pattern, threshold=2, action="drop")

    rec1 = _make_record("Worker 42 died unexpectedly")
    assert f.filter(rec1) is False

    rec2 = _make_record("Worker 99 died unexpectedly")
    assert f.filter(rec2) is True
    assert f.consecutive_failures == 2


def test_flapping_filter_auto_reset_on_success() -> None:
    """Проверяет автоматический сброс счётчика при успешных записях (уровень < ERROR)."""
    recovered_calls: list[float] = []

    f = FlappingFilter(
        patterns="Flapping error",
        threshold=2,
        action="drop",
        auto_reset_on_success=True,
        on_recovered=lambda duration: recovered_calls.append(duration),
    )

    # 1 сбой
    f.filter(_make_record("Flapping error 1"))
    assert f.consecutive_failures == 1

    # Успешное событие (INFO)
    info_rec = _make_record("Service healthy", level=logging.INFO)
    assert f.filter(info_rec) is True
    assert f.consecutive_failures == 0

    # Эскалируем сбой
    f.filter(_make_record("Flapping error 1"))
    f.filter(_make_record("Flapping error 2"))
    assert f.is_escalated

    # Восстановление после эскалации
    f.filter(_make_record("Connection restored", level=logging.INFO))
    assert f.consecutive_failures == 0
    assert not f.is_escalated
    assert len(recovered_calls) == 1
    assert recovered_calls[0] >= 0.0


def test_flapping_filter_timeout_escalation() -> None:
    """Проверяет эскалацию по истечении failure_timeout даже если threshold не достигнут."""
    escalated_calls: list[tuple[logging.LogRecord, int, float]] = []

    f = FlappingFilter(
        patterns="Slow failure",
        threshold=100,  # высокий порог
        failure_timeout=0.01,  # минимальный таймаут
        action="drop",
        on_escalated=lambda rec, cnt, dur: escalated_calls.append((rec, cnt, dur)),
    )

    rec1 = _make_record("Slow failure attempt 1")
    assert f.filter(rec1) is False

    time.sleep(0.02)

    rec2 = _make_record("Slow failure attempt 2")
    assert f.filter(rec2) is True
    assert f.is_escalated
    assert len(escalated_calls) == 1


def test_flapping_filter_thread_safety() -> None:
    """Проверяет потокобезопасность счетчиков фильтра при параллельных вызовах."""
    f = FlappingFilter(patterns="Thread error", threshold=50, action="drop")
    threads: list[threading.Thread] = []

    def worker() -> None:
        for _ in range(10):
            f.filter(_make_record("Thread error occurred"))

    for _ in range(5):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert f.consecutive_failures == 50
    assert f.is_escalated
