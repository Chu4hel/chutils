# `chutils.vkma`: Валидация launchParams / initData VK Mini Apps

Подмодуль `chutils.vkma` предоставляет высокопроизводительные и безопасные утилиты для проверки HMAC-SHA256 подписи
`launchParams` / `initData` в VK Mini Apps, их парсинга в строго типизированные `Pydantic`-модели и автоматической
защиты API на фреймворках **FastAPI**, **Flask** и **Aiohttp**.

---

## 🚀 Основные возможности

1. **HMAC-SHA256 Validation**: Валидация подписи по официальному алгоритму VK с защитой от тайминг-атак (
   `hmac.compare_digest`).
2. **Time-Expiration Control**: Настройка допустимого возраста подписи (`max_age_seconds`) по параметру `vk_ts`.
3. **Automatic Secret Resolution**: Автоматический поиск `client_secret` VK через `chutils.secret_manager` /
   `chutils.config` (`Secrets.vk_client_secret` -> `Secrets.vk_secret_key` -> `CH_VK_CLIENT_SECRET`).
4. **Typed Pydantic Models**: Парсинг в `VKMALaunchParams` с готовыми свойствами (`user_id`, `app_id`, `is_app_user`,
   `platform`, `language`).
5. **Framework Middleware & Decorators**:
    - **FastAPI / Starlette**: `VKMAAuthMiddleware`, `Depends(get_current_vkma_params)`.
    - **Flask**: Декоратор `@require_vkma_auth(...)`.
    - **Aiohttp**: `@web.middleware` фабрика `vkma_auth_middleware(...)`.

---

## 📦 Установка

```bash
pip install "chutils[vkma]"
# или при использовании uv
uv add "chutils[vkma]"
```

### Развертывание готового шаблона VK Mini App через CLI

```bash
# Развернуть готовый каркас (FastAPI + React VKUI + VKMAAuthMiddleware)
chutils init --template vk-miniapp
```

---

## 💻 Быстрый старт

### 1. Прямая проверка и парсинг

```python
from chutils.vkma import validate_vkma_launch_params, parse_vkma_launch_params

raw_init_data = "vk_user_id=123456&vk_app_id=7890&vk_is_app_user=1&vk_ts=1750000000&sign=..."

# Валидация подписи (возвращает True или выбрасывает VKMAValidationError)
try:
    validate_vkma_launch_params(raw_init_data, client_secret="your_vk_app_secret", max_age_seconds=86400)
    print("Подпись валидна!")
except VKMAValidationError as e:
    print(f"Ошибка валидации: {e}")

# Парсинг в Pydantic-модель
params = parse_vkma_launch_params(raw_init_data, client_secret="your_vk_app_secret")
print(f"User ID: {params.user_id}, Platform: {params.platform}")
```

### 2. Интеграция с FastAPI

```python
from fastapi import FastAPI, Depends
from chutils.vkma import VKMALaunchParams
from chutils.vkma.integrations.fastapi import VKMAAuthMiddleware, get_current_vkma_params

app = FastAPI()

# Добавляем middleware для проверки заголовка Authorization: Bearer <initData> или query string
app.add_middleware(VKMAAuthMiddleware, client_secret="YOUR_SECRET", exclude_paths=["/docs", "/openapi.json"])


@app.get("/api/me")
def get_me(params: VKMALaunchParams = Depends(get_current_vkma_params)):
    return {
        "user_id": params.user_id,
        "app_id": params.app_id,
        "is_app_user": params.is_app_user
    }
```

### 3. Интеграция с Flask

```python
from flask import Flask, jsonify, g
from chutils.vkma.integrations.flask import require_vkma_auth

app = Flask(__name__)


@app.route("/api/profile")
@require_vkma_auth(client_secret="YOUR_SECRET")
def profile():
    params = g.vkma_params
    return jsonify({"user_id": params.user_id})
```

---

## 🧪 Тестирование (`chutils.vkma.testing` / `chutils.vk.testing`)

Модуль предоставляет готовые генераторы поддельных данных и `pytest` фикстуры для тестирования без вызова реального VK
API.

```python
from chutils.vkma.testing import generate_fake_launch_params, MockVKApi
from chutils.vkma import validate_vkma_launch_params

# Генерация валидной подписи для тестов
fake_query = generate_fake_launch_params(user_id=12345, secret_key="test_secret")
assert validate_vkma_launch_params(fake_query, client_secret="test_secret") is True


# Использование Pytest фикстур (vk_launch_params_factory, mock_vk_api)
def test_my_endpoint(test_client, vk_launch_params_factory):
    query = vk_launch_params_factory(user_id=999, secret_key="test_secret")
    response = test_client.get("/api/me", headers={"Authorization": f"Bearer {query}"})
    assert response.status_code == 200
```

---

## 🛠️ Ошибки и исключения

При любых ошибках проверки (невалидная подпись, истекший `vk_ts`, отсутствие `sign` или `client_secret`) выбрасывается
`VKMAValidationError` (наследник `ChutilsException`).
