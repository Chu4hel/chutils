"""
Тесты для проверки безопасного импорта компонентов chutils.scraping.concurrency.
"""

from unittest.mock import patch

import pytest

from chutils.exceptions import OptionalDependencyError


def test_redis_task_queue_import_error() -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии библиотеки redis."""
    with patch.dict("sys.modules", {"redis": None}):
        with pytest.raises(OptionalDependencyError) as exc_info:
            from chutils.scraping.concurrency import RedisTaskQueue

            RedisTaskQueue()

        assert exc_info.value.context.get("dependency") == "redis"
