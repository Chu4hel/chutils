# Паттерн: Опциональные зависимости (v3.0.0+)

Этот кейс демонстрирует правила работы с опциональными зависимостями `chutils`.
В версии v3.0.0 произошло **ломающее изменение**: `RuntimeError` при отсутствии
зависимостей заменён на специализированный `OptionalDependencyError`.

---

## Что не так в `bad_pattern.py`?

1. **Перехват `RuntimeError` (устарело в v3.0.0):**
   ```python
   except RuntimeError as e:
       print(f"Ошибка: {e}")
   ```
   До v3.0.0 некоторые модули `chutils` бросали `RuntimeError`. В v3.0.0 это заменено
   на `OptionalDependencyError`. Старый код с `except RuntimeError` **не поймает** ошибку.

2. **Голый перехват `ImportError`:**
   ```python
   except ImportError:
       print("cryptography не установлен")
   ```
   Нет hint'а о том, как установить зависимость. Разработчик должен сам догадаться
   о команде установки.

3. **Прямой импорт внутренностей пакетов:**
   ```python
   from cryptography.fernet import Fernet
   ```
   Импорт напрямую из `cryptography` вместо `chutils.crypto` — теряется безопасный
   слой с `OptionalDependencyError` и подсказкой установки.

---

## Что сделано правильно в `good_pattern.py`?

1. **Перехват `OptionalDependencyError` (v3.0.0+):**
   ```python
   from chutils.exceptions import OptionalDependencyError
   ...
   except OptionalDependencyError as e:
       print(f"Hint: {e.hint}")  # "pip install chutils[crypto]"
   ```
   `OptionalDependencyError` содержит:
    - `e.message` — описание проблемы
    - `e.hint` — готовая команда установки (`pip install chutils[...]`)

2. **Использование модулей `chutils` вместо прямых зависимостей:**
   ```python
   from chutils.crypto import encrypt_portable
   ```
   `chutils.crypto` сам проверяет наличие `cryptography` и бросает `OptionalDependencyError`
   с правильным hint'ом.

3. **Разные стратегии для критичных и некритичных функций:**
    - **Некритичная** (трассировка, метрики): перехватываем, деградируем с предупреждением.
    - **Критичная** (шифрование данных): не перехватываем — пусть ошибка всплывёт выше.

---

## Миграция с v2.x на v3.0.0

```python
# ❌ Старый код (v2.x):
try:
    from chutils.crypto import encrypt_portable

    result = encrypt_portable(data, seed="seed")
except RuntimeError:
    result = data

# ✅ Новый код (v3.0.0+):
from chutils.exceptions import OptionalDependencyError

try:
    from chutils.crypto import encrypt_portable

    result = encrypt_portable(data, seed="seed")
except OptionalDependencyError as e:
    print(f"Установите зависимость: {e.hint}")
    result = data
```

---

## Ключевой совет для ИИ

> [!IMPORTANT]
> В v3.0.0+ все опциональные зависимости `chutils` (crypto, text, web, scraping, otel,
> metrics) при отсутствии бросают `OptionalDependencyError`, а не `RuntimeError`.
> Перехватывайте именно `OptionalDependencyError` и используйте `e.hint` для вывода
> пользователю команды установки.
