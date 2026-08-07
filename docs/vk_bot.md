# `chutils.vk.callback`: VK Callback API Webhook Router для FastAPI

Класс `VKCallbackRouter` обеспечивает обработку входящих сообщений и событий от **ВКонтакте Callback API (Webhook)** в FastAPI приложениях.

---

## 🚀 Основные возможности

1. **Автоматическое подтверждение сервера**: При отправке типа события `confirmation` мгновенно возвращает заданный `confirmation_code`.
2. **Проверка подлинности (Secret Key)**: Автоматически проверяет наличие `secret` ключа во входящих Webhook событиях. При расхождении отклоняет запрос (HTTP 403).
3. **Декораторы подписки на события**:
   - `@router.on_event("message_new")`
   - `@router.on_message_new`
   - `@router.on_wall_post_new`
   - `@router.on_unhandled_event` (для логирования необработанных типов событий)
4. **Интеграция с FastAPI**: Роутер легко подключается через `app.include_router(vk_router.get_fastapi_router())`.

---

## 💻 Пример использования

```python
from fastapi import FastAPI
from chutils.vk.callback import VKCallbackRouter

app = FastAPI()

# Инициализируем роутер (confirmation_code и secret_key подтягиваются автоматически из env / secret_manager)
vk_router = VKCallbackRouter(
    confirmation_code="a1b2c3d4",
    secret_key="my_secret_group_key",
    path="/vk-webhook"
)

@vk_router.on_message_new
async def handle_new_message(event: dict):
    user_id = event["object"]["message"]["from_id"]
    text = event["object"]["message"]["text"]
    print(f"Новое сообщение от {user_id}: {text}")

# Подключаем вебхук в FastAPI
app.include_router(vk_router.get_fastapi_router())
```
