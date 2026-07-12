# Паттерн: Управление секретами (v3.0.0+)

Этот кейс демонстрирует правила безопасного получения секретов через `SecretManager`,
включая строгий режим (`required=True`) и поведение при отсутствии секрета.

---

## Что не так в `bad_pattern.py`?

1. **Прямое чтение из `os.getenv`:**
   ```python
   token = os.getenv("API_TOKEN")
   ```
   Переменные окружения могут логироваться в CI/CD системах, попадать в дампы процессов
   или утекать через `printenv`. `SecretManager` обеспечивает безопасный и аудируемый доступ.

2. **Нет проверки на отсутствие секрета:**
   `os.getenv` возвращает `None` без предупреждения. Ошибка проявится позже как
   `AttributeError: 'NoneType' object has no attribute...` без связи с реальной причиной.

3. **Захардкоженный fallback в production-коде:**
   ```python
   password = os.getenv("DB_PASSWORD", "admin123")
   ```
   Дефолтный пароль попадёт в репозиторий и будет использован в production если переменная
   не задана. `SecretManager` поддерживает явное разделение dev/production через `required`.

4. **Логирование секрета в открытом виде:**
   Передача токена в `print()` — прямая утечка в stdout/логи.

---

## Что сделано правильно в `good_pattern.py`?

1. **`required=True` для production:**
   ```python
   secret_mgr.get_secret("api_token", required=True)
   ```
   При отсутствии секрета возбуждается `SecretNotFoundError` с информативным сообщением
   и hint'ом о том, как установить секрет. Нет молчаливого возврата `None`.

2. **`fallback` только для dev/test:**
   ```python
   secret_mgr.get_secret("api_token", fallback="dev_token_local")
   ```
   Явно ограничиваем use-case: fallback допустим только вне production. Это читается в коде.

3. **`aget_secret` для async-кода:**
   ```python
   await secret_mgr.aget_secret("api_token", required=True)
   ```
   Неблокирующая версия для asyncio-приложений — не блокирует event loop.

4. **Иерархия хранилищ:**
   `SecretManager` автоматически ищет секрет в: `keyring` (системное хранилище) →
   `.env` файл → переменные окружения. На CI/CD keyring заменяется на секреты платформы.

---

## Ключевой совет для ИИ

> [!IMPORTANT]
> Никогда не читайте секреты через `os.getenv` в коде приложения. Всегда используйте
> `SecretManager`. В production-окружении всегда указывайте `required=True` — это
> гарантирует fail-fast при неправильной конфигурации вместо молчаливой работы с пустым
> или дефолтным значением.
