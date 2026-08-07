from __future__ import annotations

import json
import logging  # chutils: ignore[ChutilsIntegrationRule]
import time
import urllib.request
from typing import Any

from chutils.telegram.formatting import escape_html, smart_truncate


class TelegramLogHandler(logging.Handler):
    """Handler стандартного модуля logging для отправки критических логов в Telegram."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: int | str | None = None,
        level: int = logging.ERROR,
        rate_limit_per_min: int = 10,
    ) -> None:
        super().__init__(level=level)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.rate_limit_per_min = rate_limit_per_min
        self._sent_timestamps: list[float] = []

    def _resolve_credentials(self) -> tuple[str | None, int | str | None]:
        token = self.bot_token
        chat = self.chat_id

        if not token or not chat:
            try:
                from chutils.config import get_config_value

                token = token or get_config_value("Telegram", "bot_token", None)
                chat = chat or get_config_value("Telegram", "admin_chat_id", None) or get_config_value("Telegram", "chat_id", None)
            except Exception:
                pass

        return token, chat

    def _should_throttle(self) -> bool:
        now = time.time()
        # Очищаем метки старше 60 секунд
        self._sent_timestamps = [t for t in self._sent_timestamps if now - t < 60]
        if len(self._sent_timestamps) >= self.rate_limit_per_min:
            return True
        self._sent_timestamps.append(now)
        return False

    def emit(self, record: logging.LogRecord) -> None:
        """Отправляет отформатированную запись лога в Telegram.

        Args:
            record: Запись лога logging.LogRecord.
        """
        token, chat = self._resolve_credentials()
        if not token or not chat:
            return

        if self._should_throttle():
            return

        try:
            log_entry = self.format(record)
            level_name = record.levelname
            icon = "🚨" if record.levelno >= logging.CRITICAL else "⚠️"

            formatted_msg = (
                f"<b>{icon} Alert [{level_name}]</b>\n"
                f"<b>Module:</b> <code>{escape_html(record.module)}</code>\n"
                f"<b>Message:</b>\n<pre>{escape_html(smart_truncate(log_entry, max_length=3000))}</pre>"
            )

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat,
                "text": formatted_msg,
                "parse_mode": "HTML",
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            self.handleError(record)


def send_alert(
    title: str,
    message: str,
    bot_token: str | None = None,
    chat_id: int | str | None = None,
    level: str = "ERROR",
) -> bool:
    """Отправляет кастомное алерты-уведомление администраторам в Telegram.

    Args:
        title: Заголовок алерта.
        message: Текст сообщения.
        bot_token: Опциональный токен бота.
        chat_id: Опциональный ID чата администратора.
        level: Уровень алерта (INFO, WARNING, ERROR, CRITICAL).

    Returns:
        True при успешной отправке, иначе False.
    """
    token = bot_token
    chat = chat_id

    if not token or not chat:
        try:
            from chutils.config import get_config_value

            token = token or get_config_value("Telegram", "bot_token", None)
            chat = chat or get_config_value("Telegram", "admin_chat_id", None) or get_config_value("Telegram", "chat_id", None)
        except Exception:
            pass

    if not token or not chat:
        return False

    icons = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨",
    }
    icon = icons.get(level.upper(), "📢")

    formatted_msg = (
        f"<b>{icon} {escape_html(title)} [{level.upper()}]</b>\n\n"
        f"{escape_html(smart_truncate(message, max_length=3500))}"
    )

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat,
            "text": formatted_msg,
            "parse_mode": "HTML",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


class HealthCheckAlertBridge:
    """Мост отправки Telegram-уведомлений при изменении статусов здоровья chutils.diagnostics."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: int | str | None = None,
        notify_on_degraded: bool = True,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.notify_on_degraded = notify_on_degraded

    def on_health_check(self, service_name: str, status: str, details: dict[str, Any] | None = None) -> bool:
        """Обрабатывает событие проверки здоровья и отправляет алерт при проблемах.

        Args:
            service_name: Имя сервиса/компонента.
            status: Статус (HEALTHY, DEGRADED, UNHEALTHY).
            details: Подробности ошибки или метрики.

        Returns:
            True, если алерт был отправлен, иначе False.
        """
        status_upper = status.upper()
        if status_upper == "HEALTHY":
            return False

        if status_upper == "DEGRADED" and not self.notify_on_degraded:
            return False

        level = "CRITICAL" if status_upper == "UNHEALTHY" else "WARNING"
        details_str = json.dumps(details, ensure_ascii=False, indent=2) if details else "No details"

        title = f"Health Alert: {service_name}"
        msg = f"<b>Status:</b> <code>{status_upper}</code>\n<b>Details:</b>\n<pre>{details_str}</pre>"

        return send_alert(
            title=title,
            message=msg,
            bot_token=self.bot_token,
            chat_id=self.chat_id,
            level=level,
        )
