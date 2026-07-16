# Руководство по проверке AI-готовности (ai-lint)

`chutils dev ai-lint` — это специализированный инструмент статического анализа (линтер), разработанный для оценки *
*AI-готовности** вашей кодовой базы.

Современные AI-ассистенты и автономные кодинг-агенты (такие как Antigravity, Gemini CLI, Claude, GitHub Copilot)
работают значительно эффективнее, если кодовая база хорошо структурирована, снабжена подробными манифестами, строгой
типизацией и стандартизированными docstrings. Инструмент `ai-lint` помогает автоматически проверять кодовую базу на
соответствие этим стандартам.

---

## Зачем нужен ai-lint?

При работе искусственного интеллекта с вашей кодовой базой возникают следующие проблемы:

1. **Отсутствие контекста**: ИИ не знает архитектурных ограничений проекта, принятых соглашений или используемых
   технологий, если они нигде не описаны.
2. **Плохая типизация**: Без аннотаций типов (`type hints`) ИИ часто делает ошибочные предположения о структурах данных,
   что ведет к багам.
3. **Неполная документация**: Если публичные методы не документированы по стандарту (например, Google Style), ИИ сложнее
   понять их контракты, параметры и возвращаемые типы.
4. **Утечка секретов**: AI-ассистенты отправляют части кода на внешние сервера. Наличие захардкоженных токенов и паролей
   в коде создает серьезную угрозу безопасности.
5. **Изобретение велосипедов**: Если в проекте уже есть готовые утилиты (например, логгер или менеджер секретов из
   `chutils`), ИИ может этого не знать и начать писать собственные аналоги.

`ai-lint` решает эти проблемы, выполняя статический аудит проекта по ряду специализированных правил.

---

## Использование существующих правил

### Базовый запуск

Для запуска проверки в текущей директории выполните:

```bash
poetry run python -m chutils dev ai-lint
```

или после установки библиотеки:

```bash
chutils dev ai-lint
```

### Параметры командной строки

Вы можете тонко настраивать поведение линтера с помощью флагов:

* `--strict` — строгий режим. Любые предупреждения (`warn`) будут трактоваться как ошибки (`error`), и линтер вернет
  ненулевой код выхода (1).
* `--soft-mode` — мягкий режим. Линтер выведет список всех найденных проблем, но всегда будет завершаться с успешным
  кодом выхода (0). Это полезно при первой интеграции в CI.
* `--ignore "<path1>,<path2>"` — дополнительные шаблоны путей для игнорирования (разделяются запятой). Эти шаблоны
  дополняют настройки из файлов конфигурации.
* `--rules "<Rule1>,<Rule2>"` — запуск только указанных правил (по умолчанию запускаются все встроенные и кастомные
  правила).
* `--custom-rules-path "<path_to_file>"` — путь к файлу с вашими собственными правилами.

Пример расширенного запуска:

```bash
chutils dev ai-lint --strict --ignore "build/,legacy_code.py" --rules "ManifestRule,SecurityHardcodeRule"
```

---

## Встроенные правила

В `ai-lint` встроено 5 основных правил:

### 1. ManifestRule (severity: `warn`)

Проверяет наличие файлов манифестов ИИ в корневом каталоге проекта и в основных пакетах (подкаталогах `src/`).

* **Используемые имена файлов**: `antigravity.md`, `agents.md`, `GEMINI.md` (в любом регистре), `.cursorrules`,
  `.windsurfrules`.
* **Зачем**: Файлы манифестов служат инструкцией для ИИ-агентов. В них описывается структура проекта, используемые
  библиотеки и глобальные правила кодирования.

### 2. DocstringQualityRule (severity: `error`)

Выполняет AST-анализ всех публичных классов, функций и методов (исключая тесты).

* **Что проверяет**:
    * Наличие docstring у публичных классов и функций.
    * Соответствие структуры docstring формату **Google Style** (наличие обязательных разделов `Args:` и `Returns:` при
      наличии параметров и возвращаемого значения).
    * Документированность каждого аргумента функции в разделе `Args:`.
    * Наличие аннотаций типов (`type hints`) у всех аргументов функции (кроме `self` и `cls`).
    * Наличие аннотации возвращаемого значения (кроме метода `__init__`).
* **Зачем**: Строгая типизация и структурированные docstrings критичны для генерации точного кода ИИ.

### 3. SecurityHardcodeRule (severity: `error`)

Сканирует текстовое содержимое файлов и строит AST-дерево для поиска секретов.

* **Что проверяет**:
    * Приватные ключи (заголовки `-----BEGIN PRIVATE KEY-----`).
    * Токены облачных провайдеров (AWS Access Key, Slack Token и др.).
    * Жестко заданные присвоения строк переменным, содержащим в имени `key`, `secret`, `password`, `token`, `pwd` (
      длиной более 8 символов, если они не похожи на плейсхолдеры).
* **Зачем**: Защита от случайной утечки учетных данных в контекст больших языковых моделей (LLM).

### 4. ChutilsIntegrationRule (severity: `warn`)

Проверяет интеграцию с экосистемой `chutils` в проекте.

* **Что проверяет**:
    * Использование стандартного модуля `logging` (рекомендует перейти на `chutils.setup_logger`).
    * Использование библиотеки `keyring` напрямую (рекомендует `chutils.SecretManager`).
    * Прямые обращения к `os.getenv` или `os.environ` (рекомендует использовать встроенные инструменты управления
      конфигурацией `chutils`).
    * Ручные вызовы метода `.mkdir(parents=True, exist_ok=True)` (рекомендует использовать `chutils.fs.ensure_dir`).
    * Ручные вызовы `.write_text()` / `.write_bytes()`, прямой вызов сериализаторов `json.dump` / `yaml.dump` или
      использование временных файлов `tempfile` с последующим перемещением/переименованием для записи файлов (
      рекомендует использовать безопасную атомарную запись `chutils.fs.atomic_write`).
* **Зачем**: Обеспечивает единообразие архитектуры проекта и направляет ИИ на переиспользование уже готовых библиотечных
  решений.

### 5. APIMapRule (severity: `error`)

Проверяет актуальность карты публичного API (`api_map.md`).

* **Что проверяет**:
    * Наличие файла `api_map.md` в корне.
    * Полное соответствие содержимого `api_map.md` реально экспортируемым публичным функциям, классам и константам
      библиотеки.
* **Зачем**: Карта API позволяет ИИ быстро ориентироваться в возможностях библиотеки без необходимости сканирования всех
  исходных файлов.

### 6. EnvSyncRule (severity: `warn`)

Проверяет соответствие состава ключей переменных окружения в файлах `.env` и `.env.example`.

* **Что проверяет**:
    * Одновременное существование файлов `.env` и `.env.example` (если один есть, а другого нет — выдает
      предупреждение).
    * Совпадение наборов ключей в обоих файлах.
* **Зачем**: Предотвращает ошибки запуска приложения из-за отсутствующих локальных переменных или забытых обновлений в
  файле-шаблоне.

---

## Настройка конфигурации

Вы можете настроить параметры `ai-lint` через стандартные файлы конфигурации проекта. Настройки объединяются в следующем
приоритете (от высшего к низшему):

1. Флаги CLI
2. Переменные окружения (`CH_DEV_AILINT_STRICT`, `CH_DEV_AILINT_IGNORE`, `CH_DEV_AILINT_RULES`,
   `CH_DEV_AILINT_CUSTOM_RULES_PATH`, `CH_DEV_AILINT_SOFT_MODE`)
3. Файл `config.yml` (секция `Dev.AI-Lint`)
4. Файл `pyproject.toml` (секция `[tool.chutils.ai-lint]`)
5. Значения по умолчанию

### Настройка в pyproject.toml

Рекомендуемый способ настройки проекта — добавление секции в `pyproject.toml`:

```toml
[tool.chutils.ai-lint]
strict = false
soft_mode = false
ignore = [
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "tests",
    "docs",
    "src/chutils/testing"
]
rules = ["ManifestRule", "DocstringQualityRule", "SecurityHardcodeRule"]
custom_rules_path = ".chutils/custom_rules.py"
env_path = ".env"
example_path = ".env.example"
```

### Файл .chutilsignore

В дополнение к секции `ignore` в конфигурации, линтер автоматически ищет файл `.chutilsignore` в корне проекта. Вы
можете указать там пути в формате glob (по аналогии с `.gitignore`):

```text
# Игнорировать автогенерированные файлы
src/chutils/dev/ast_indexer.py
*.tmp
temp/
```

---

## Создание собственных правил (Custom Rules)

Если вам необходимо внедрить специфичные для вашего проекта архитектурные правила, вы можете написать свои собственные
правила на Python.

### Базовые классы

Пользовательское правило должно быть классом, унаследованным от `chutils.dev.ai_lint.Rule`.
Интерфейс правила выглядит следующим образом:

```python
from typing import Optional


class LintResult:
    rule_name: str  # Имя правила, создавшего результат
    message: str  # Сообщение об ошибке/предупреждении
    severity: str  # Уровень критичности: "error" или "warn"
    file_path: Optional[str]  # Абсолютный путь к файлу с проблемой (опционально)
    line_number: Optional[int]  # Номер строки с проблемой (1-индексированный, опционально)
    fix_suggestion: Optional[str]  # Совет по исправлению проблемы (опционально)


class Rule:
    name: str = ""  # Уникальное имя правила
    description: str = ""  # Краткое описание правила
    severity: str = "error"  # Уровень критичности по умолчанию ("error" или "warn")

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """
        Выполняет проверку. Должен возвращать список LintResult.
        
        Args:
            base_dir: Абсолютный путь к корню проекта.
            files: Список абсолютных путей ко всем неигнорируемым файлам проекта.
        """
        raise NotImplementedError
```

### Шаг 1. Написание правила

Создайте файл `.chutils/custom_rules.py` в вашем проекте.
Например, напишем правило `NoAnyTypeRule`, которое запрещает использовать `Any` в аннотациях типов (согласно Zero-Any
Strategy):

```python
import ast
from pathlib import Path
from chutils.dev.ai_lint import Rule, LintResult


class AnyTypeVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, rule_name: str) -> None:
        self.file_path = file_path
        self.rule_name = rule_name
        self.issues: list[LintResult] = []

    def visit_Name(self, node: ast.Name) -> None:
        # Проверяем использование имени Any
        if node.id == "Any":
            self.issues.append(
                LintResult(
                    rule_name=self.rule_name,
                    message="Обнаружено использование типа 'Any' в аннотации.",
                    severity="error",
                    file_path=self.file_path,
                    line_number=node.lineno,
                    fix_suggestion="Используйте более конкретный тип или Union/Generic вместо Any."
                )
            )
        self.generic_visit(node)


class NoAnyTypeRule(Rule):
    name = "NoAnyTypeRule"
    description = "Запрещает использование типа 'Any' в кодовой базе для соблюдения строгой типизации."
    severity = "error"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        results: list[LintResult] = []
        for file_path in files:
            # Проверяем только Python-файлы и исключаем тесты
            if not file_path.endswith(".py"):
                continue
            if "tests" in Path(file_path).parts:
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Парсим файл в AST и обходим его
                tree = ast.parse(content)
                visitor = AnyTypeVisitor(file_path, self.name)
                visitor.visit(tree)
                results.extend(visitor.issues)
            except Exception as e:
                # В случае синтаксических ошибок пропускаем файл
                pass
        return results
```

### Шаг 2. Подключение правила

Чтобы подключить созданное правило, укажите путь к нему в вашем `pyproject.toml`:

```toml
[tool.chutils.ai-lint]
custom_rules_path = ".chutils/custom_rules.py"
```

Или передайте путь при запуске команды:

```bash
chutils dev ai-lint --custom-rules-path ".chutils/custom_rules.py"
```

При запуске линтер динамически импортирует ваш файл, найдет все классы, унаследованные от `Rule`, создаст их экземпляры
и выполнит проверку наряду со встроенными правилами.

---

## Интеграция в CI/CD

Автоматическая проверка AI-готовности кодовой базы при каждом коммите или Pull Request помогает поддерживать проект в
идеальном состоянии для работы AI-агентов.

### GitHub Actions

Создайте файл `.github/workflows/ai-lint.yml`:

```yaml
name: AI Readiness Lint

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install poetry
          poetry install

      - name: Run AI Linter
        run: |
          poetry run python -m chutils dev ai-lint --strict
```
