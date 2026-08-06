# Telegram Bot Access Control & Helpers (`chutils.telegram`)

Модуль `chutils.telegram` предоставляет универсальные механизмы разграничения прав доступа, проверки администраторских
привилегий и фильтрации для Telegram-ботов на Python (`aiogram 3.x`, `python-telegram-bot`, `telebot`).

---

## 1. Проверка прав администратора (`is_admin`)

Функция `is_admin` проверяет, является ли пользователь администратором по Telegram ID или username.

```python
from chutils.telegram import is_admin

# Проверка по явным спискам
if is_admin(user_id=12345678, admin_ids=[12345678, 87654321]):
    print("Доступ разрешен")

# Проверка по username (регистронезависимо, подгружает значки @)
if is_admin(username="alice", admin_usernames=["@alice", "bob"]):
    print("Привет, Алиса!")
```

### Автоматический Fallback на конфигурацию `chutils`

Если явные списки `admin_ids` / `admin_usernames` не переданы, `is_admin` автоматически считывает разрешенные ID и
юзернеймы из секции `[Telegram]` вашего конфигурационного файла (`pyproject.toml` / `ai-lint.toml` / `.env`):

```toml
[Telegram]
admin_ids = [12345678, 87654321]
admin_usernames = ["@admin", "owner"]
```

---

## 2. Декоратор `@admin_only`

Декоратор `@admin_only` поддерживает как синхронные, так и асинхронные функции-хэндлеры.

```python
from chutils.telegram import admin_only
from chutils.exceptions import TelegramAccessDeniedError


# Асинхронный хэндлер с кастомным сообщением об отказе
@admin_only(admin_ids=[12345678], refusal_text="⛔ Функция доступна только администраторам")
async def secret_command(event):
    await event.answer("Секретные данные")


# Тихий режим (запросы игнорируются без вывода ответа)
@admin_only(admin_usernames=["admin"], silent=True)
async def quiet_handler(event):
    await event.answer("Тихая команда")


# Режим генерации исключения для централизованной обработки в Middleware
@admin_only(raise_on_denied=True)
def sync_handler(user_id: int):
    return "OK"
```

---

## 3. Интеграция с aiogram 3.x (`AdminFilter`)

`AdminFilter` наследуется от `aiogram.filters.BaseFilter` и позволяет использовать проверку прав непосредственно в
роутерах и диспетчерах `aiogram`.

```python
from aiogram import Router, types
from chutils.telegram import AdminFilter

router = Router()


@router.message(AdminFilter(admin_ids=[12345678]))
async def admin_panel(message: types.Message):
    await message.answer("Добро пожаловать в админ-панель!")
```

---

## 4. Защита от спама и флуда (`@tg_rate_limit`)

Декоратор `@tg_rate_limit` ограничивает частоту вызова команд с динамическим расчетом оставшегося времени ожидания
`{wait_sec}`.

```python
from chutils.telegram import tg_rate_limit


# Разрешить не более 2 вызовов в 10 секунд
@tg_rate_limit(rate=2, per=10.0, warning_text="⏱ Замедлитесь! Подождите {wait_sec} сек.")
async def heavy_command(event):
    await event.answer("Тяжелый запрос выполнен!")
```

---

## 5. aiogram 3.x Middleware (`TelegramThrottlingMiddleware`)

Глобальное предотвращение спама на уровне роутеров/диспетчеров `aiogram`:

```python
from aiogram import Dispatcher
from chutils.telegram import TelegramThrottlingMiddleware

dp = Dispatcher()
# Подключение мидлваря для всех текстовых сообщений
dp.message.middleware(TelegramThrottlingMiddleware(rate=1, per=2.0))
```

---

## 6. Белые и черные списки пользователей (`AccessListManager` и `@allowed_only`)

Менеджер `AccessListManager` управляет списками разрешенных и заблокированных пользователей с поддержкой автосохранения
в JSON-файл (`atomic_write`):

```python
from chutils.telegram import AccessListManager, allowed_only

manager = AccessListManager(storage_path="allowed_users.json")

# Динамическое управление пользователями
manager.allow_user("trusted_user")
manager.block_user(999888)


# Использование в декораторе
@allowed_only(manager=manager, refusal_text="⛔ У вас нет доступа")
async def restricted_feature(event):
    await event.answer("Доступ ограниченной группе предоставлен!")
```

---

## 7. aiogram 3.x SecretUserFilter (`SecretUserFilter`)

```python
from aiogram import Router
from chutils.telegram import SecretUserFilter

router = Router()
# Фильтрация только разрешенных юзеров по ID
router.message.filter(SecretUserFilter(allowed_ids=[12345678, 87654321]))
```

---

## 8. Трейсинг и логирование апдейтов (`trace_telegram_update`)

Утилита `trace_telegram_update` замеряет точное время выполнения хэндлера (`execution_time_ms`) и автоматически логирует
входящие события:

```python
from chutils.telegram import trace_telegram_update


@trace_telegram_update()
async def process_user_request(event):
    # Код обработки запроса
    return "SUCCESS"
```

---

## 9. aiogram 3.x TelegramLoggingMiddleware (`TelegramLoggingMiddleware`)

Прозрачное сквозное логирование всех входящих событий через Middleware:

```python
from aiogram import Dispatcher
from chutils.telegram import TelegramLoggingMiddleware

dp = Dispatcher()
dp.update.outer_middleware(TelegramLoggingMiddleware())
```

---

## 10. Безопасное экранирование (`escape_markdown` и `escape_html`)

Защищает от ошибок парсинга `BadRequest: Can't parse entities`:

```python
from chutils.telegram import escape_markdown, escape_html

safe_mdv2 = escape_markdown("Цена: 100.00$ [link]", version=2)
safe_html = escape_html("<b>1 < 2 & 3 > 0</b>")
```

---

## 11. Обрезка и разбиение длинных сообщений (`smart_truncate` и `split_message`)

```python
from chutils.telegram import smart_truncate, split_message

# Безопасная обрезка с запечатыванием незавершенного кодового блока ```
short_text = smart_truncate(long_code_str, max_length=1000)

# Разбиение текста по различным стратегиям: 'line', 'paragraph', 'word', 'char'
chunks_paragraphs = split_message(article_text, max_length=4096, mode="paragraph")
chunks_lines = split_message(huge_log_report, max_length=4096, mode="line")

for chunk in chunks_paragraphs:
    await message.answer(chunk)
```

---

## 12. Лог-хэндлер алертов в Telegram (`TelegramLogHandler`)

Автоматическая отправка ошибок уровня `ERROR` / `CRITICAL` в Telegram с троттлингом:

```python
import logging
from chutils.telegram import TelegramLogHandler

logger = logging.getLogger("my_app")
handler = TelegramLogHandler(bot_token="TOKEN", chat_id=12345678, rate_limit_per_min=10)
logger.addHandler(handler)

logger.error("Критический сбой базы данных!")
```

---

## 13. Мост алертов диагностики (`HealthCheckAlertBridge` & `send_alert`)

```python
from chutils.telegram import send_alert, HealthCheckAlertBridge

# Прямая отправка алерта
send_alert(
    title="High CPU Usage",
    message="Загрузка процессора превысила 95%",
    level="WARNING"
)

# Мост алертов диагностики
bridge = HealthCheckAlertBridge()
bridge.on_health_check("PostgreSQL", "UNHEALTHY", {"error": "Connection timeout"})
```

---

## 14. Динамические Inline-клавиатуры (`build_inline_keyboard`)

Построение сетки кнопок из списков кортежей или словарей:

```python
from chutils.telegram import build_inline_keyboard

buttons = [
    ("Купить", "buy_item_1"),
    ("Подробнее", "info_item_1"),
    {"text": "Сайт", "url": "https://example.com"}
]

# Возвращает структуру {'inline_keyboard': [...]} или aiogram InlineKeyboardMarkup (при as_aiogram=True)
keyboard = build_inline_keyboard(buttons, buttons_per_row=2, as_aiogram=True)
```

---

## 15. Пагинатор списков и каталогов (`PaginatorKeyboard`)

Автоматическая генерация панели навигации (`«`, `1/5`, `»`) с прикреплением футеров:

```python
from chutils.telegram import PaginatorKeyboard

catalog_items = [f"Товар #{i}" for i in range(1, 50)]
paginator = PaginatorKeyboard(catalog_items, per_page=5, callback_prefix="catalog")

# Построение 2-й страницы с дополнительной кнопкой 'Закрыть'
kb = paginator.build_keyboard(
    page=2,
    footer_buttons=[("Закрыть", "close_catalog")],
    as_aiogram=True
)
```
