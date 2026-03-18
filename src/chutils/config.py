"""
Модуль для работы с конфигурацией.

Обеспечивает автоматический поиск файла `config.yml`, `config.yaml` или `config.ini`
в корне проекта и предоставляет удобные функции для чтения и сохранения настроек.
Поддерживает кастомные уровни логирования при условии, что модуль logger загружен.
"""

import asyncio
import configparser
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional, List, Dict, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .logger import ChutilsLogger

# Настраиваем логгер для этого модуля.
# Используем стандартный getLogger, чтобы избежать циклической рекурсии с logger.setup_logger.
# Если модуль logger уже загружен, logging вернет экземпляр ChutilsLogger.
logger = logging.getLogger(__name__)


def _get_logger() -> 'ChutilsLogger':
    """
    Вспомогательная функция для получения типизированного логгера.

    Returns:
        Экземпляр логгера (может быть ChutilsLogger, если инициализирован).
    """
    return logger  # type: ignore


# --- Глобальное состояние для "ленивой" инициализации ---
_BASE_DIR: Optional[str] = None
_CONFIG_FILE_PATH: Optional[str] = None
_paths_initialized = False

_config_object: Optional[Dict] = None
_config_loaded = False


def find_project_root(start_path: Path, markers: List[str]) -> Optional[Path]:
    """
    Ищет корень проекта, двигаясь вверх по дереву каталогов.

    Корень определяется по наличию одного из файлов-маркеров (например, .git или pyproject.toml).

    Args:
        start_path: Директория, с которой начинается поиск.
        markers: Список имен файлов или папок (маркеров), наличие которых
            в директории указывает на то, что это корень проекта.

    Returns:
        Объект Path, представляющий корневую директорию проекта, или None, если корень не найден.
    """
    current_path = start_path.resolve()
    # Идем вверх до тех пор, пока не достигнем корня файловой системы
    while current_path != current_path.parent:
        for marker in markers:
            if (current_path / marker).exists():
                _get_logger().debug("Найден маркер '%s' в директории: %s", marker, current_path)
                return current_path
        current_path = current_path.parent
    _get_logger().debug("Корень проекта не найден.")
    return None


def _merge_configs(main_config: Dict, local_config: Dict) -> Dict:
    """
    Рекурсивно объединяет два словаря конфигурации.

    Значения из `local_config` имеют приоритет и переопределяют значения из `main_config`.

    Args:
        main_config: Основной словарь конфигурации.
        local_config: Словарь с локальными переопределениями.

    Returns:
        Объединенный словарь конфигурации.
    """
    for key, value in local_config.items():
        if key in main_config and isinstance(main_config[key], dict) and isinstance(value, dict):
            main_config[key] = _merge_configs(main_config[key], value)
        else:
            main_config[key] = value
    return main_config


def _initialize_paths():
    """
    Автоматически находит и кэширует пути к корню проекта и файлу конфигурации.

    Инициализация происходит только один раз. Приоритет поиска файлов:
    YAML (.yml, .yaml) -> INI (.ini) -> Маркеры проекта (pyproject.toml).
    """
    global _BASE_DIR, _CONFIG_FILE_PATH, _paths_initialized
    if _paths_initialized:
        return

    # Приоритет поиска: сначала YAML, потом INI, потом общий маркер проекта.
    markers = ['config.yml', 'config.yaml', 'config.ini', 'config.local.yml', 'config.local.yaml', 'config.local.ini',
               'pyproject.toml']
    project_root = find_project_root(Path.cwd(), markers)

    if project_root:
        _BASE_DIR = str(project_root)
        # Находим, какой именно конфигурационный файл был найден
        for marker in markers:
            if (project_root / marker).is_file() and marker.startswith('config'):
                _CONFIG_FILE_PATH = str(project_root / marker)
                break
        _get_logger().debug("Корень проекта автоматически определен: %s", _BASE_DIR)
    else:
        _get_logger().warning("Не удалось автоматически найти корень проекта.")

    _paths_initialized = True


def _get_config_paths(cfg_file: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """
    Внутренняя функция для получения путей к основному и локальному файлам конфигурации.

    Если пути не инициализированы, запускает поиск. Также определяет путь к .local файлу
    на основе имени основного файла.

    Args:
        cfg_file: Явный путь к основному файлу (переопределяет автопоиск).

    Returns:
        Кортеж: (путь_к_основному, путь_к_локальному). Элементы могут быть None, если файлы не найдены.
    """
    main_config_path: Optional[str] = None
    local_config_path: Optional[str] = None

    if cfg_file:
        main_config_path = cfg_file
    elif not _paths_initialized:
        _initialize_paths()
        main_config_path = _CONFIG_FILE_PATH
    else:
        main_config_path = _CONFIG_FILE_PATH

    if main_config_path:
        main_path_obj = Path(main_config_path)
        file_ext = main_path_obj.suffix.lower()
        local_file_name = f"{main_path_obj.stem}.local{file_ext}"
        potential_local_path = main_path_obj.parent / local_file_name
        if potential_local_path.exists():
            local_config_path = str(potential_local_path)
            _get_logger().debug("Найден локальный файл конфигурации: %s", local_config_path)

    return main_config_path, local_config_path


def get_config() -> Dict:
    """
    Загружает и объединяет конфигурацию из всех доступных источников.

    Результат кэшируется. Повторные вызовы возвращают кэшированный объект,
    если он не был сброшен (например, при сохранении нового значения).

    Returns:
       _config_object: Словарь со всей конфигурацией проекта. Если файлы не найдены, возвращается пустой словарь.
    """
    global _config_object, _config_loaded
    if _config_loaded and _config_object is not None:
        return _config_object

    main_path, local_path = _get_config_paths()
    main_config: Dict = {}
    local_config: Dict = {}

    if main_path and Path(main_path).exists():
        file_ext = Path(main_path).suffix.lower()
        if file_ext in ['.yml', '.yaml']:
            main_config = _load_yaml(main_path)
            _get_logger().debug("Основная конфигурация успешно загружена из YAML: %s", main_path)
        elif file_ext == '.ini':
            main_config = _load_ini(main_path)
            _get_logger().debug("Основная конфигурация успешно загружена из INI: %s", main_path)
        else:
            _get_logger().warning("Неподдерживаемый формат основного файла конфигурации: %s", main_path)
    else:
        _get_logger().debug("Основной файл конфигурации не найден или не указан.")

    if local_path and Path(local_path).exists():
        file_ext = Path(local_path).suffix.lower()
        if file_ext in ['.yml', '.yaml']:
            local_config = _load_yaml(local_path)
            _get_logger().debug("Локальная конфигурация успешно загружена из YAML: %s", local_path)
        elif file_ext == '.ini':
            local_config = _load_ini(local_path)
            _get_logger().debug("Локальная конфигурация успешно загружена из INI: %s", local_path)
        else:
            _get_logger().warning("Неподдерживаемый формат локального файла конфигурации: %s", local_path)
    else:
        _get_logger().debug("Локальный файл конфигурации не найден или не указан.")

    _config_object = _merge_configs(main_config, local_config)
    _config_loaded = True
    return _config_object


async def aget_config() -> Dict:
    """
    Асинхронная версия get_config.

    Returns:
        Словарь конфигурации.
    """
    return await asyncio.to_thread(get_config)


def _load_yaml(path: str) -> Dict:
    """
    Загружает YAML файл и обрабатывает ошибки парсинга.

    Args:
        path: Путь к файлу.

    Returns:
        Словарь данных или пустой словарь при ошибке.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, FileNotFoundError) as e:
        _get_logger().critical("Ошибка чтения YAML файла конфигурации %s: %s", path, e)
        return {}


def _nest_ini_dict(flat_dict: Dict[str, Dict[str, Any]]) -> Dict:
    """
    Преобразует плоский словарь INI-секций во вложенную структуру.

    Разделяет имена секций по точкам (например, 'Logging.default' -> {'Logging': {'default': ...}}).

    Args:
        flat_dict: Словарь, где ключи - названия секций INI.

    Returns:
        Вложенный словарь.
    """
    nested_dict = {}
    for section_key, section_values in flat_dict.items():
        current_level = nested_dict
        parts = section_key.split('.')
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # Последняя часть - это название секции
                current_level[part] = section_values
            else:
                current_level = current_level.setdefault(part, {})
    return nested_dict


def _load_ini(path: str) -> Dict:
    """
    Загружает INI файл и преобразует его во вложенный словарь.

    Args:
        path: Путь к файлу.

    Returns:
        Словарь данных или пустой словарь при ошибке.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            parser = configparser.ConfigParser()
            parser.read_string(f.read())
            flat_ini_config = {s: dict(parser.items(s)) for s in parser.sections()}
            # Преобразуем плоскую структуру вложенных секций в иерархическую
            return _nest_ini_dict(flat_ini_config)
    except (configparser.Error, FileNotFoundError) as e:
        _get_logger().critical("Ошибка чтения INI файла конфигурации %s: %s", path, e)
        return {}


def save_config_value(
        section: str,
        key: str,
        value: Any,
        cfg_file: Optional[str] = None,
        save_to_local: bool = False
) -> bool:
    """
    Сохраняет или обновляет одно значение в файле конфигурации.

    Warning:
        Важно: При сохранении в `.yml` комментарии и форматирование будут утеряны.
        При сохранении в `.ini` - сохраняются.

    Args:
        section: Имя секции.
        key: Имя ключа в секции.
        value: Новое значение для ключа.
        cfg_file: Опциональный путь к файлу для сохранения. Если указан,
            имеет приоритет над `save_to_local`.
        save_to_local: Если True, и существует локальный файл конфигурации
            (например, `config.local.yml`), значение будет сохранено в него.
            По умолчанию False.

    Returns:
        True: Если значение было успешно обновлено и сохранено.
        False: Если файл не найден, или произошла ошибка.
    """
    global _config_object, _config_loaded

    path: Optional[str] = None

    # Явный путь в cfg_file имеет высший приоритет
    if cfg_file:
        path = cfg_file
    else:
        main_path, local_path = _get_config_paths()
        if save_to_local and local_path:
            path = local_path
            _get_logger().debug("Для сохранения выбран локальный файл конфигурации: %s", path)
        else:
            path = main_path

    if path is None:
        _get_logger().error("Невозможно сохранить значение: путь к файлу конфигурации не определен.")
        return False

    file_ext = Path(path).suffix.lower()

    if file_ext in ['.yml', '.yaml']:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            if section not in data:
                data[section] = {}
            data[section][key] = value

            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)

            # Сбрасываем кэш, чтобы при следующем get_config() конфигурация была перезагружена
            _config_object = None
            _config_loaded = False

            _get_logger().debug("Ключ '%s' в секции '[%s]' обновлен в файле %s", key, section, path)
            return True
        except Exception as e:
            _get_logger().error("Ошибка при сохранении в YAML файл %s: %s", path, e)
            return False

    elif file_ext == '.ini':
        if not Path(path).exists():
            _get_logger().error("Невозможно сохранить значение: файл конфигурации %s не найден.", path)
            return False

        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except IOError as e:
            _get_logger().error("Ошибка чтения файла %s для сохранения: %s", path, e)
            return False

        updated = False
        in_target_section = False
        section_found = False
        key_found_in_section = False
        section_pattern = re.compile(r'^\s*\[\s*(?P<section_name>[^]]+)\s*\]\s*')
        key_pattern = re.compile(rf'^\s*({re.escape(key)})\s*=\s*(.*)', re.IGNORECASE)

        new_lines = []
        for line in lines:
            section_match = section_pattern.match(line)
            if section_match:
                current_section_name = section_match.group('section_name').strip()
                if current_section_name.lower() == section.lower():
                    in_target_section = True
                    section_found = True
                else:
                    in_target_section = False
                new_lines.append(line)
                continue

            if in_target_section and not key_found_in_section:
                key_match = key_pattern.match(line)
                if key_match:
                    original_key = key_match.group(1)
                    new_line_content = f"{original_key} = {value}\n"
                    new_lines.append(new_line_content)
                    key_found_in_section = True
                    updated = True
                    _get_logger().debug("Ключ '%s' в секции '[%s]' будет обновлен на '%s' в файле %s", key, section,
                                        value,
                                        path)
                    continue

            new_lines.append(line)

        if not section_found:
            # Если секция не найдена, добавляем ее в конец файла
            if new_lines and new_lines[-1].strip() != "":
                new_lines.append('\n')  # Добавляем пустую строку для отступа
            new_lines.append(f'[{section}]\n')
            new_lines.append(f'{key} = {value}\n')
            updated = True
            _get_logger().debug("Новая секция '[%s]' с ключом '%s' будет добавлена в файл %s", section, key, path)

        elif not key_found_in_section:  # `section_found` is implicitly True here
            # Существующая логика для добавления ключа в существующую секцию
            key_added = False
            final_lines = []
            in_target_section_for_add = False
            for i, line in enumerate(new_lines):
                final_lines.append(line)
                section_match = section_pattern.match(line)
                if section_match:
                    current_section_name = section_match.group('section_name').strip()
                    in_target_section_for_add = current_section_name.lower() == section.lower()

                # Проверяем, является ли следующая строка началом новой секции или концом файла
                is_last_line = i == len(new_lines) - 1
                next_line_is_new_section = False
                if not is_last_line:
                    next_line_match = section_pattern.match(new_lines[i + 1])
                    if next_line_match:
                        next_line_is_new_section = True

                if in_target_section_for_add and (is_last_line or next_line_is_new_section):
                    # Вставляем ключ перед следующей секцией или в конце файла
                    final_lines.append(f"{key} = {value}\n")
                    key_added = True
                    updated = True
                    break  # Выходим из цикла, чтобы не добавлять ключ многократно
            new_lines = final_lines

        if updated:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                _get_logger().debug("Файл конфигурации %s успешно обновлен.", path)
                # Сбрасываем кэш, чтобы при следующем get_config() конфигурация была перезагружена
                _config_object = None
                _config_loaded = False
                return True
            except IOError as e:
                _get_logger().error("Ошибка записи в файл %s при сохранении: %s", path, e)
                return False
        else:
            _get_logger().debug("Обновление для ключа '%s' в секции '[%s]' не потребовалось.", key, section)
            return False
    else:
        _get_logger().warning("Сохранение для формата %s не поддерживается.", file_ext)
        return False


async def asave_config_value(
        section: str,
        key: str,
        value: Any,
        cfg_file: Optional[str] = None,
        save_to_local: bool = False
) -> bool:
    """
    Асинхронно сохраняет одно значение в конфигурационном файле.
    Работает как асинхронная обертка вокруг синхронной `save_config_value()`.

    Args:
        section: Имя секции.
        key: Имя ключа в секции.
        value: Новое значение для ключа.
        cfg_file: Опциональный путь к файлу для сохранения. Если указан,
            имеет приоритет над `save_to_local`.
        save_to_local: Если True, и существует локальный файл конфигурации
            (например, `config.local.yml`), значение будет сохранено в него.
            По умолчанию False.

    Returns:
        True: Если значение было успешно обновлено и сохранено.
        False: Если файл не найден, или произошла ошибка.
    """
    return await asyncio.to_thread(save_config_value, section, key, value, cfg_file, save_to_local)


# --- Функции-обертки для удобного получения типизированных значений ---

def get_config_value(section: str, key: str, fallback: Any = None, config: Optional[Dict] = None) -> Any:
    """
    Получает произвольное значение из конфигурации.

    Если значение не найдено или оно пустое, возвращает `fallback`.
    Для ключа `disable_keyring` в секции `secrets` проверяет переменную окружения.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или его значение пустое.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Значение из конфигурации или `fallback`.
    """
    # Проверка переменных окружения для специфических ключей (FR3: приоритет над конфигом)
    if section == "secrets" and key == "disable_keyring":
        env_val = os.getenv("CH_DISABLE_KEYRING_WARNING")
        if env_val is not None:
            return env_val

    if config is None:
        config = get_config()

    value = config.get(section, {}).get(key)

    # Если значение не найдено или является пустой строкой, возвращаем fallback
    if value is None or value == '':
        return fallback

    return value


def get_config_int(section: str, key: str, fallback: int = 0, config: Optional[Dict] = None) -> int:
    """
    Получает целочисленное значение из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть преобразован в int.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Целое число из конфигурации или `fallback`.
    """
    value = get_config_value(section, key, fallback, config)
    try:
        return int(value)
    except (ValueError, TypeError):
        _get_logger().warning(
            "Не удалось преобразовать значение '%s' для ключа '%s' в секции '[%s]' к типу int. "
            "Возвращено значение по умолчанию: %s.",
            value, key, section, fallback
        )
        return fallback


def get_config_float(section: str, key: str, fallback: float = 0.0, config: Optional[Dict] = None) -> float:
    """
    Получает дробное значение из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть преобразован в float.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Float или fallback.
    """
    value = get_config_value(section, key, fallback, config)
    try:
        return float(value)
    except (ValueError, TypeError):
        _get_logger().warning(
            "Не удалось преобразовать значение '%s' для ключа '%s' в секции '[%s]' к типу float. "
            "Возвращено значение по умолчанию: %s.",
            value, key, section, fallback
        )
        return fallback


def get_config_boolean(section: str, key: str, fallback: bool = False, config: Optional[Dict] = None) -> bool:
    """
    Получает булево значение из конфигурации.

    Распознает 'true', '1', 't', 'y', 'yes' как True и
    'false', '0', 'f', 'n', 'no' как False (без учета регистра).

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть распознан как булево.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        True или False.
    """
    value = get_config_value(section, key, fallback, config)
    if isinstance(value, bool):
        return value
    if str(value).lower() in ['true', '1', 't', 'y', 'yes']:
        return True
    if str(value).lower() in ['false', '0', 'f', 'n', 'no']:
        return False
    return fallback


def get_config_list(
        section: str,
        key: str,
        fallback: Optional[List[Any]] = None,
        config: Optional[Dict] = None) -> List[Any]:
    """
    Получает значение как список из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Список из конфигурации или `fallback`. Если `fallback` не указан,
        возвращается пустой список.
    """
    value = get_config_value(section, key, fallback, config)
    if isinstance(value, list):
        return value
    if fallback is None:
        return []
    return fallback


def get_config_section(
        section_name: str,
        fallback: Optional[Dict] = None,
        config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Получает всю секцию конфигурации как словарь.

    Args:
        section_name: Имя секции.
        fallback: Значение по умолчанию, если секция не найдена.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Словарь с содержимым секции или `fallback`. Если `fallback` не указан,
        возвращается пустой словарь.
    """
    if config is None:
        config = get_config()
    return config.get(section_name, fallback if fallback is not None else {})


def get_config_path(
        section: str,
        key: str,
        fallback: Optional[str] = None,
        config: Optional[Dict] = None,
        resolve_from_root: bool = True
) -> Optional[str]:
    """
    Получает путь из конфигурации.
    Функция автоматически добавляет _BASE_DIR к относительным путям,
    если resolve_from_root установлено в True.
    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        resolve_from_root: Если True, относительные пути будут разрешаться
            относительно _BASE_DIR. Если False, пути возвращаются как есть,
            без добавления _BASE_DIR.
    Returns:
        Путь из конфигурации или `fallback`.
    """
    path_str = get_config_value(section, key, fallback, config)

    if not path_str:
        return fallback

    path_obj = Path(path_str)

    # Если путь относительный, _BASE_DIR определен и resolve_from_root включен, объединяем их
    if resolve_from_root and not path_obj.is_absolute() and _BASE_DIR:
        return str(Path(_BASE_DIR) / path_obj)

    return path_str
