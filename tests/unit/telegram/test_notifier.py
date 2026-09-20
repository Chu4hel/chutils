import logging
from unittest.mock import MagicMock, patch

from chutils.telegram.notifier import (
    HealthCheckAlertBridge,
    TelegramLogHandler,
    send_alert,
)


def test_telegram_log_handler_emit():
    """Проверяет отправку лог-записи через TelegramLogHandler."""
    handler = TelegramLogHandler(
        bot_token="TEST_TOKEN", chat_id=12345, rate_limit_per_min=5
    )
    logger = logging.getLogger("test_notifier")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = MagicMock()

        logger.error("Something went wrong!")
        assert mock_urlopen.called


def test_telegram_log_handler_throttling():
    """Проверяет троттлинг сообщений превышающих лимит в минуту."""
    handler = TelegramLogHandler(
        bot_token="TEST_TOKEN", chat_id=12345, rate_limit_per_min=2
    )
    logger = logging.getLogger("test_throttling")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = MagicMock()

        logger.error("Msg 1")
        logger.error("Msg 2")
        logger.error("Msg 3 (throttled)")

        assert mock_urlopen.call_count == 2


def test_send_alert():
    """Проверяет отправку кастомного алерта через send_alert."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = MagicMock()

        res = send_alert(
            "Test Alert",
            "Detail message",
            bot_token="TOKEN",
            chat_id=100,
            level="CRITICAL",
        )
        assert res is True
        assert mock_urlopen.called


def test_health_check_alert_bridge():
    """Проверяет мост алертов HealthCheckAlertBridge."""
    bridge = HealthCheckAlertBridge(
        bot_token="TOKEN", chat_id=100, notify_on_degraded=True
    )

    with patch("chutils.telegram.notifier.send_alert", return_value=True) as mock_send:
        # Healthy - не отправляем
        assert bridge.on_health_check("db", "HEALTHY") is False
        assert mock_send.call_count == 0

        # Degraded - отправляем
        assert bridge.on_health_check("redis", "DEGRADED", {"latency": "200ms"}) is True
        assert mock_send.call_count == 1


def test_telegram_log_handler_flapping_filter():
    """Проверяет работу подавления флаппинг-ошибок в TelegramLogHandler."""
    handler = TelegramLogHandler(
        bot_token="TEST_TOKEN",
        chat_id=12345,
        flapping_patterns=["Unable to make request to BotPolling"],
        flapping_threshold=3,
    )
    logger = logging.getLogger("test_flapping_telegram")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = MagicMock()

        # 1-я ошибка поллинга -> отсекается (нет сетевого запроса в Telegram)
        logger.error("Unable to make request to BotPolling, retrying...")
        assert mock_urlopen.call_count == 0

        # 2-я ошибка поллинга -> отсекается
        logger.error("Unable to make request to BotPolling, retrying...")
        assert mock_urlopen.call_count == 0

        # Другая несовпадающая ошибка -> сразу отправляется
        logger.error("Database connection lost")
        assert mock_urlopen.call_count == 1

        # 3-я ошибка поллинга -> достигла порога, отправляется с контекстом простоя!
        logger.error("Unable to make request to BotPolling, retrying...")
        assert mock_urlopen.call_count == 2
