# Валидация конфигурации (`chutils validate`)

Команда `chutils validate` предназначена для автоматической статической проверки корректности файлов конфигурации (
`config.yml`, `config.yaml`, `config.ini`, `.env`) на соответствие вашей Pydantic-модели до запуска приложения.

Она позволяет обнаружить опечатки, пропущенные обязательные параметры или неверные типы данных еще до деплоя или старта
сервиса.

> [!NOTE]  
> Для работы команды требуется опциональная зависимость Pydantic. Установите её командой:  
> `pip install chutils[pydantic]`

---

## Синтаксис

```bash
chutils validate [-h] [-m MODEL]
```

### Параметры и флаги:

| Флаг     | Полное имя    | Описание                                                                                                                                                                                                   | Обязательный |
|:---------|:--------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------|
| **`-m`** | **`--model`** | Путь к Pydantic-модели (например, `myapp.config:Settings`). Если флаг не передан, `chutils` автоматически попытается найти класс с именем `Settings` в файлах `context.py` или `config.py` вашего проекта. | Нет          |

---

## Принцип работы и методы

При вызове команды утилита выполняет следующие шаги:

1. **Многоуровневое слияние данных**: загружает и объединяет все конфигурационные источники в единое дерево с учетом
   приоритетов (`config.yml` -> `config.local.yml` -> переменные окружения).
2. **Динамический импорт модели**: загружает указанный класс Pydantic (или выполняет авто-поиск по путям
   `src.context:Settings`, `src.config:Settings`, `context:Settings`, `config.py:Settings`).
3. **Строгая валидация типов**: передает объединенный словарь в Pydantic-модель.
4. **Результат и коды ответа (Exit Codes)**:
    * **`0`** — Конфигурация полностью валидна.
    * **`1`** — Обнаружены ошибки типов/структуры (Pydantic `ValidationError`) или модель не найдена.

---

## Пример Pydantic-модели конфигурации

Для проверки структуры `config.yml` создайте класс `Settings` в `config.py`:

```python
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = Field(5432, ge=1, le=65535)
    username: str


class Settings(BaseModel):
    app_name: str
    debug: bool = False
    database: DatabaseConfig
```

---

## Примеры использования

### 1. Успешная валидация (автоопределение модели)

Если модель `Settings` расположена в `config.py` или `context.py`:

```bash
chutils validate
```

*Вывод в консоли (зеленым):*

```text
 [OK]  Конфигурация успешно прошла валидацию по модели 'src.config:Settings'.
```

### 2. Ошибка валидации (неверный тип данных или пропущенное поле)

Если в `config.yml` указано строковое значение для целочисленного порта или пропущен обязательный `username`:

```bash
chutils validate -m app.settings:AppConfig
```

*Вывод в консоли (красным):*

```text
ОШИБКИ ВАЛИДАЦИИ:
  - database -> port: Input should be a valid integer, unable to parse string as an integer [type=int_parsing, input_value='not_a_port', input_type=str]
  - database -> username: Field required [type=missing]
```

*(Exit code: 1)*

---

## Использование в CI/CD (GitHub Actions / GitLab CI)

Благодаря коду возврата `1` при ошибках, `chutils validate` идеально подходит для автоматической проверки конфигурации в
CI/CD пайплайнах до сборки релизных артефактов или деплоя.

**Пример в GitHub Actions (`.github/workflows/ci.yml`):**

```yaml
jobs:
  validate-config:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install chutils[pydantic]
      - name: Validate Production Config
        run: chutils validate -m myapp.config:Settings
```

---

## Связанные команды

* [**`config debug`**](./config.md#config-debug) — Посмотреть, из какого конкретно источника (файла или ENV) подтянулось
  неверное значение.
* [**`template schema`**](./template.md) — Сгенерировать JSON Schema на базе вашей Pydantic-модели для автодополнения в
  IDE.
