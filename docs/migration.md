# Руководство по миграции: с версии v2 на v3

Это руководство содержит описание ключевых ломающих изменений (breaking changes) при переходе с версии `2.x` на версию
`3.0.0` библиотеки `chutils`, а также инструкции по обновлению вашего кода.

---

## 1. Повышение требований к версии Python и типизации

Минимальная поддерживаемая версия Python повышена:

- **Было:** `Python >= 3.9`
- **Стало:** `Python >= 3.10`

Если ваш проект использует Python 3.9, вам необходимо обновить среду выполнения до версии **3.10** или выше. В кодовой
базе библиотеки теперь активно используются новые синтаксические возможности Python 3.10 (например, объединенные типы
`int | str` вместо `Union[int, str]`).

### Отказ от `typing_extensions`:

- Пакет `typing-extensions` полностью удален из зависимостей `chutils`.
- Все импорты из `typing_extensions` (например, `TypeAlias`, `ParamSpec` и др.) в клиентском коде следует заменить на
  стандартные импорты из модуля `typing` стандартной библиотеки Python.

---

## 2. Унификация ошибок отсутствия зависимостей

При обращении к модулям, требующим неустановленные опциональные зависимости (extra-пакеты), тип выбрасываемого
исключения был изменен для повышения единообразия обработки ошибок.

- **Было:** Выбрасывалось стандартное исключение `RuntimeError` с сообщением о необходимости установки пакета.
- **Стало:** Выбрасывается специализированное исключение `OptionalDependencyError` (наследуемое от `ChutilsException`).

### Затронутые модули и функции:

- **`chutils.crypto`**: функции `encrypt_portable`, `decrypt_portable`, `encrypt_file`, `decrypt_file` (требуют
  `chutils[crypto]`).
- **`chutils.text`**: функция `is_significant_difference` (требует `chutils[text]`).
- **`chutils.config`**: функция `start_config_watcher` (требует `chutils[watch]`) и использование Pydantic-моделей в
  геттерах (требует `chutils[pydantic]`).
- **`chutils.secret_manager`**: провайдер `KeyringProvider` (требует `chutils[secrets]`).

### Что нужно изменить:

Если в вашем коде перехватывалось исключение `RuntimeError` для обработки отсутствующих библиотек, обновите его на
перехват `OptionalDependencyError` или базового `ChutilsException`:

```python
# Было (v2):
try:
    from chutils.crypto import encrypt_portable

    encrypt_portable("data", "seed")
except RuntimeError as e:
    print("Установите chutils[crypto]!")

# Стало (v3):
from chutils.exceptions import OptionalDependencyError

try:
    from chutils.crypto import encrypt_portable

    encrypt_portable("data", "seed")
except OptionalDependencyError as e:
    print(f"Ошибка: {e.message}")
    print(f"Совет: {e.hint}")
```

---

## 3. Удаление устаревших (Deprecated) переменных и функций в `chutils.config`

В рамках очистки публичного API перед релизом `3.0.0` были полностью удалены приватные глобальные переменные и функции
обратной совместимости, которые временно поддерживались с выдачей предупреждений `DeprecationWarning`.

### Удаленные приватные переменные модуля `config`:

- `config._BASE_DIR` — используйте публичную функцию `config.get_base_dir()`.
- `config._CONFIG_FILE_PATH` — используйте публичную функцию `config.get_config_file_path()`.
- `config._paths_initialized` — используйте публичную функцию `config.are_paths_initialized()`.
- `config._config_object` — используйте публичную функцию `config.get_config()`.
- `config._config_loaded` — используйте публичную функцию `config.is_config_loaded()`.
- `config._get_config_paths` — используйте публичные функции `config.get_config_paths()` или
  `config.get_all_config_paths()`.

### Удаленные функции:

- `config._initialize_paths()` — пути теперь инициализируются автоматически при первом вызове любого публичного геттера.
  Если в тестах или инфраструктурном коде вам необходимо вручную инициализировать пути, импортируйте внутренний менеджер
  конфигурации `_cm` и функцию поиска корня:
  ```python
  from chutils.config import _cm, find_project_root
  _cm.initialize_paths(find_project_root)
  ```
- `config._sync_legacy_state()` — синхронизация устаревшего глобального состояния больше не поддерживается.

При обращении к любым из этих удаленных атрибутов теперь будет выбрасываться стандартное исключение `AttributeError`.

---

## 4. Ограничение прямого доступа к внутреннему менеджеру `_cm`

Прямой импорт или доступ к менеджеру конфигурации `_cm` через `chutils.config._cm` теперь считается деталью внутренней
реализации.

- По возможности используйте только стабильный публичный API модуля `chutils.config` (`get_config_value`, `get_base_dir`
  и т.д.).
- Доступ к `_cm` сохранен для написания тестов и расширения возможностей библиотеки, однако при прямом использовании в
  бизнес-логике приложений рекомендуется мигрировать на официальный публичный интерфейс.

---

## 5. Перевод системного хранилища keyring в разряд опциональных зависимостей

Для предотвращения проблем сборки в изолированных окружениях (например, в Docker-контейнерах на Linux), библиотека
`keyring` была переведена в категорию дополнительных зависимостей.

### Что изменилось:

- Установка по умолчанию больше не включает пакет `keyring`. Для использования системного хранилища необходимо явно
  установить:
  `pip install chutils[secrets]` (или `pip install chutils[full]`).
- **Изящная деградация `SecretManager`:** Если пакет `keyring` отсутствует, класс `SecretManager` не падает с ошибкой, а
  автоматически отключает `KeyringProvider` и использует только Env и DotEnv провайдеры (переменные окружения и `.env`
  файлы).
- **Логирование и предупреждения:** При отсутствии `keyring` в логах будет выведено однократное предупреждение уровня
  `warning`. Его можно заглушить, если задать переменную окружения `CH_DISABLE_KEYRING_WARNING=true` или настроить
  соответствующее значение в конфигурации.
- **Изменение в CLI:** При отсутствии установленной зависимости `secrets` CLI-команды для управления секретами (
  `chutils secrets ...`) автоматически скрываются из справки `--help`. При попытке вызвать скрытую команду напрямую, CLI
  выбросит `CommandError` с сообщением о необходимости установки `chutils[keyring]`.

---

## 6. Унификация API SecretManager с Config API

Интерфейс получения секретов в `SecretManager` был унифицирован с поведением Config API для поддержки значений по
умолчанию (fallback) и принудительного выброса ошибок (fail-fast).

### Что изменилось:

- **Новые параметры `fallback` и `required`**: методы `get_secret` и `aget_secret` теперь принимают два новых
  необязательных параметра:
    - `fallback: Optional[str] = None` — значение, возвращаемое если секрет не найден.
    - `required: bool = False` — если установлено в `True`, отсутствие секрета приведет к генерации исключения
      `SecretNotFoundError` (наследуется от `SecretError`).
- **Новая CLI-подкоманда `secrets get`**:
  `chutils secrets get <key> [--service <name>] [--fallback <val>] [--required]`
  Позволяет получать значения секретов из командной строки. В случае отсутствия обязательного секрета (--required)
  команда завершается ошибкой (ненулевой код возврата).

### Пример использования API:

```python
from chutils.secret_manager import SecretManager
from chutils.exceptions import SecretNotFoundError

sm = SecretManager("my_app")

# 1. Поведение по умолчанию (совместимо с v2): возвращает None, если секрет не найден
val = sm.get_secret("MISSING_KEY")  # val is None

# 2. Использование fallback:
val = sm.get_secret("MISSING_KEY", fallback="default_value")  # val == "default_value"

# 3. Fail-fast режим (required=True):
try:
    val = sm.get_secret("MISSING_KEY", required=True)
except SecretNotFoundError:
    print("Критический секрет не найден в хранилище!")
```
