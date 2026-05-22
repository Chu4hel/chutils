# Integration Guide for AI Agents

Этот документ предназначен для LLM и AI-агентов, помогая им быстро интегрировать `chutils` в новые или существующие
проекты.

## 1. Quick Start (Copy-Paste)

### Рекомендуемая инициализация приложения

Используйте этот сниппет для стандартного запуска приложения с поддержкой логирования и конфигурации.

```python
from chutils import setup_logger, get_config_value, bind_context

# 1. Настройка логгера (автоматически подхватит настройки из config.yml)
logger = setup_logger(name="my_app")

# 2. Использование контекста (полезно для трейсинга запросов)
with bind_context(request_id="unique-uuid"):
    logger.info("Приложение запущено")

    # 3. Получение настроек
    db_host = get_config_value("Database", "host", "localhost")
    logger.debug(f"Используется хост БД: {db_host}")
```

## 2. Ключевые возможности

- **Config**: Авто-поиск `config.yml` в корне проекта. Приоритет: `Environment Variables` > `config.local.yml` >
  `config.yml`.
- **Logger**: Форматированный вывод (Rich), ротация файлов, маскировка секретов.
- **Secrets**: Интеграция с системным хранилищем ключей (Keyring). Не храните пароли в конфигах!
- **Decorators**: `@retry`, `@timeout`, `@log_function_details`.

## 3. CLI Команды

- `chutils init -y`: Быстрая инициализация проекта (создает конфиг и .gitignore).
- `chutils secrets set KEY VALUE`: Сохранение секрета в Keyring.
- `chutils validate -m my_app.models:Settings`: Валидация текущего конфига через Pydantic модель.

## 4. Схема конфигурации (Пример)

```yaml
Logging:
  level: INFO
  format: standard
  file_enabled: true

Secrets:
  service_name: "my_custom_app"
```
