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
