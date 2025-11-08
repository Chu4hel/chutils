"""
Модуль для работы с конфигурацией.

Обеспечивает автоматический поиск файла `config.yml`, `config.yaml` или `config.ini`
в корне проекта и предоставляет удобные функции для чтения настроек.
"""

import configparser
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional, List, Dict

import yaml

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

# --- Глобальное состояние для "ленивой" инициализации ---
_BASE_DIR: Optional[str] = None
_CONFIG_FILE_PATH: Optional[str] = None
_paths_initialized = False

_config_object: Optional[Dict] = None
_config_loaded = False


def find_project_root(start_path: Path, markers: List[str]) -> Optional[Path]:
    """Ищет корень проекта, двигаясь вверх по дереву каталогов.

    Args:
        start_path: Директория, с которой начинается поиск.
        markers: Список имен файлов или папок (маркеров), наличие которых
            в директории указывает на то, что это корень проекта.

    Returns:
        Объект Path, представляющий корневую директорию проекта
        None: Если корень не был найден.
    """
    current_path = start_path.resolve()
    # Идем вверх до тех пор, пока не достигнем корня файловой системы
    while current_path != current_path.parent:
        for marker in markers:
            if (current_path / marker).exists():
                logger.debug(f"Найден маркер '{marker}' в директории: {current_path}")
                return current_path
        current_path = current_path.parent
    logger.debug("Корень проекта не найден.")
    return None


def _initialize_paths():
    """Автоматически находит и кэширует пути к корню проекта и файлу конфигурации."""
    global _BASE_DIR, _CONFIG_FILE_PATH, _paths_initialized
    if _paths_initialized:
        return

    # Приоритет поиска: сначала YAML, потом INI, потом общий маркер проекта.
    markers = ['config.yml', 'config.yaml', 'config.ini', 'pyproject.toml']
    project_root = find_project_root(Path.cwd(), markers)

    if project_root:
        _BASE_DIR = str(project_root)
        # Находим, какой именно конфигурационный файл был найден
        for marker in markers:
            if (project_root / marker).is_file() and marker.startswith('config'):
                _CONFIG_FILE_PATH = str(project_root / marker)
                break
        logger.debug(f"Корень проекта автоматически определен: {_BASE_DIR}")
    else:
        logger.warning("Не удалось автоматически найти корень проекта.")

    _paths_initialized = True


def _get_config_path(cfg_file: Optional[str] = None) -> Optional[str]:
    """
    Внутренняя функция-шлюз для получения пути к файлу конфигурации.

    Если путь не был установлен, запускает автоматический поиск.

    Args:
        cfg_file: Опциональный путь к файлу конфигурации. Если указан,
            используется он.

    Returns:
        Строка с путем к файлу конфигурации или None, если файл не найден.

    """
    # Если путь к файлу передан явно, используем его.
    if cfg_file:
        return cfg_file

    # Если пути еще не инициализированы, запускаем поиск.
    if not _paths_initialized:
        _initialize_paths()

    # Если после инициализации путь все еще не определен, возвращаем None.
    if _CONFIG_FILE_PATH is None:
        logger.debug("Файл конфигурации не найден, автоматический поиск не дал результатов.")
        return None
    return _CONFIG_FILE_PATH


def get_config() -> Dict:
    """
    Загружает конфигурацию из файла (YAML или INI) и возвращает ее как словарь.
    Результат кэшируется для последующих вызовов.

    Returns:
        _config_object: Словарь с загруженной конфигурацией.
        {}: Если файл не найден или произошла ошибка, возвращается пустой словарь.
    """
    global _config_object, _config_loaded
    if _config_loaded and _config_object is not None:
        return _config_object

    path = _get_config_path()
    if path is None or not os.path.exists(path):
        logger.debug("Файл конфигурации не найден или не указан. Возвращен пустой конфиг.")
        _config_object = {}
        _config_loaded = True
        return _config_object

    file_ext = Path(path).suffix.lower()

    try:
        with open(path, 'r', encoding='utf-8') as f:
            if file_ext in ['.yml', '.yaml']:
                _config_object = yaml.safe_load(f)
                logger.debug(f"Конфигурация успешно загружена из YAML: {path}")
            elif file_ext == '.ini':
                parser = configparser.ConfigParser()
                parser.read_string(f.read())
                # Преобразуем объект ConfigParser в словарь
                _config_object = {s: dict(parser.items(s)) for s in parser.sections()}
                logger.debug(f"Конфигурация успешно загружена из INI: {path}")
            else:
                _config_object = {}
                logger.warning(f"Неподдерживаемый формат файла конфигурации: {path}")

    except (yaml.YAMLError, configparser.Error) as e:
        logger.critical(f"Ошибка чтения файла конфигурации {path}: {e}")
        _config_object = {}

    if _config_object is None:
        _config_object = {}

    _config_loaded = True
    return _config_object


def save_config_value(
        section: str,
        key: str,
        value: Any,
        cfg_file: Optional[str] = None
) -> bool:
    """
    Сохраняет одно значение в конфигурационном файле.

    Warning:
        Важно: При сохранении в `.yml` комментарии и форматирование будут утеряны.
        При сохранении в `.ini` - сохраняются.

    Args:
        section: Имя секции.
        key: Имя ключа в секции.
        value: Новое значение для ключа.
        cfg_file: Опциональный путь к файлу. Если не указан, будет
            использован автоматически найденный файл.

    Returns:
        True: Если значение было успешно обновлено и сохранено.
        False: Если файл не найден, или произошла ошибка.
    """
    global _config_object, _config_loaded

    path = _get_config_path(cfg_file)
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

            if _config_loaded:
                _config_object = data

            logger.debug(f"Ключ '{key}' в секции '[{section}]' обновлен в файле {path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении в YAML файл {path}: {e}")
            return False

    elif file_ext == '.ini':
        if not os.path.exists(path):
            logger.error(f"Невозможно сохранить значение: файл конфигурации {path} не найден.")
            return False

        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except IOError as e:
            logger.error(f"Ошибка чтения файла {path} для сохранения: {e}")
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
                    logger.debug(f"Ключ '{key}' в секции '[{section}]' будет обновлен на '{value}' в файле {path}")
                    continue

            new_lines.append(line)

        if not section_found:
            # Если секция не найдена, добавляем ее в конец файла
            if new_lines and new_lines[-1].strip() != "":
                new_lines.append('\n')  # Добавляем пустую строку для отступа
            new_lines.append(f'[{section}]\n')
            new_lines.append(f'{key} = {value}\n')
            updated = True
            logger.debug(f"Новая секция '[{section}]' с ключом '{key}' будет добавлена в файл {path}")

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
                logger.debug(f"Файл конфигурации {path} успешно обновлен.")
                return True
            except IOError as e:
                logger.error(f"Ошибка записи в файл {path} при сохранении: {e}")
                return False
        else:
            logger.debug(f"Обновление для ключа '{key}' в секции '[{section}]' не потребовалось.")
            return False
    else:
        logger.warning(f"Сохранение для формата {file_ext} не поддерживается.")
        return False


# --- Функции-обертки для удобного получения значений ---

def get_config_value(section: str, key: str, fallback: Any = "", config: Optional[Dict] = None) -> Any:
    """
    Получает значение из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Значение из конфигурации или `fallback`.
    """
    if config is None:
        config = get_config()
    return config.get(section, {}).get(key, fallback)


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
        logger.warning(
            f"Не удалось преобразовать значение '{value}' для ключа '{key}' в секции '[{section}]' к типу int. "
            f"Возвращено значение по умолчанию: {fallback}."
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
        Дробное число из конфигурации или `fallback`.
    """
    value = get_config_value(section, key, fallback, config)
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(
            f"Не удалось преобразовать значение '{value}' для ключа '{key}' в секции '[{section}]' к типу float. "
            f"Возвращено значение по умолчанию: {fallback}."
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
        Булево значение из конфигурации или `fallback`.
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
