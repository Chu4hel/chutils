# Integration Guide for AI Agents

Этот документ предназначен для LLM и AI-агентов, помогая им быстро интегрировать `chutils` в новые или существующие
проекты.

> [!TIP]
> При написании кода и решении задач всегда сверяйтесь
> с [Банком few-shot примеров](./ai_examples/README.md) (`docs/ai_examples/`), где
> содержатся примеры правильной реализации ("Как надо") и антипаттернов ("Как не надо") для ключевых задач.

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
- `chutils secrets get KEY`: Получение секрета из Keyring (с поддержкой `--fallback` и `--required`).
- `chutils validate -m my_app.models:Settings`: Валидация текущего конфига через Pydantic модель.
- `chutils config generate-schema --model my_app.models:Settings -o config.schema.json`: Генерация JSON Schema для
  автодополнения и Schema-First DX.

## 4. Схема конфигурации и Schema-First DX

Для обеспечения максимальной точности генерации конфигурации AI-агентами рекомендуется генерировать и предоставлять им
JSON Schema вашей модели настроек.

1. Сгенерируйте схему: `chutils config generate-schema --model my_app.models:Settings > schema.json`
2. Передайте содержимое `schema.json` в контекст AI-агента. Это позволит ему генерировать строго валидные YAML/JSON
   файлы.

## 5. Пример структуры (YAML)

```yaml
Logging:
  level: INFO
  format: standard
  file_enabled: true

Secrets:
  service_name: "my_custom_app"

```

## 6. Генерация AI-индекса проекта

Для ознакомления AI-агентов с API и структурой вашего проекта используйте команду генерации контекста. Вы можете
сканировать как саму библиотеку `chutils`, так и ваш целевой проект:

    * **Сгенерировать карту API текущего проекта в Markdown (по умолчанию):**
      ```bash
      chutils dev generate-context --project . -o api_map.md

  ```

*(Команда просканирует код, отфильтрует файлы по правилам `.gitignore` / `.chutilsignore` и создаст читаемую
Markdown-таблицу со всеми публичными классами, функциями и методами).*

* **Сгенерировать иерархический семантический JSON-индекс (дерево проекта):**
  ```bash
  chutils dev generate-context --project . --tree -o project_index.json
  ```

*(Этот файл идеален для передачи на вход LLM в качестве структурированной карты проекта).*

### 7. Метаданные и контроль актуальности индекса

Для борьбы с устареванием индекса при генерации контекста в `api_map.md` или `project_index.json` автоматически
записываются метаданные, включая детерминированный SHA-256 хэш проекта.

Встроенное правило `APIMapHashRule` в составе команды `chutils dev ai-lint` автоматически сверяет текущий хэш проекта с
хэшем из сохраненной карты API и выводит предупреждение при несовпадении. Перед коммитом рекомендуется обновлять карту
API, чтобы ИИ-агенты работали с актуальным контекстом проекта.

