"""
Модуль для работы с конфигурацией.

Обеспечивает автоматический поиск файла `config.ini` в корне проекта
и предоставляет удобные функции для чтения и записи настроек.
"""

import configparser
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional, List, Dict

# Настраиваем логгер для этого модуля
logger = logging.getLogger(__name__)

# --- Глобальное состояние для хранения путей ---
# Эти переменные инициализируются один раз при первом обращении к конфигурации.

_BASE_DIR: Optional[str] = None
_CONFIG_FILE_PATH: Optional[str] = None
_paths_initialized = False


def find_project_root(start_path: Path, markers: List[str]) -> Optional[Path]:
    """
    Ищет корень проекта, двигаясь вверх по дереву каталогов от `start_path`.

    Корень определяется наличием одного из файлов-маркеров (например, 'config.ini').
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
    """
    Автоматически находит и устанавливает пути. Вызывается при первом доступе.
    Это "сердце" автоматического обнаружения.
    """
    global _BASE_DIR, _CONFIG_FILE_PATH, _paths_initialized
    if _paths_initialized:
        return

    # Ищем корень проекта, начиная от текущей рабочей директории.
    # Приоритетный маркер — 'config.ini', запасной — 'pyproject.toml'.
    project_root = find_project_root(Path.cwd(), markers=['config.ini', 'pyproject.toml'])

    if project_root:
        _BASE_DIR = str(project_root)
        _CONFIG_FILE_PATH = os.path.join(_BASE_DIR, "config.ini")
        logger.info(f"Корень проекта автоматически определен: {_BASE_DIR}")
    else:
        # Если не нашли, оставляем пути пустыми. Функции ниже будут выбрасывать ошибку.
        logger.warning("Не удалось автоматически найти корень проекта (отсутствуют config.ini или pyproject.toml).")

    _paths_initialized = True


def _get_config_path(cfg_file: Optional[str] = None) -> str:
    """
    Внутренняя функция-шлюз для получения пути к файлу конфигурации.

    Если путь не был установлен, запускает автоматический поиск.
    Если путь не передан явно и автоматический поиск не дал результатов,
    выбрасывает исключение с понятным сообщением.
    """
    # Если путь к файлу передан явно, используем его.
    if cfg_file:
        return cfg_file

    # Если пути еще не инициализированы, запускаем поиск.
    if not _paths_initialized:
        _initialize_paths()

    # Если после инициализации путь все еще не определен, это ошибка.
    if _CONFIG_FILE_PATH is None:
        raise FileNotFoundError(
            "Файл конфигурации не найден. Не удалось автоматически определить корень проекта. "
            "Убедитесь, что в корне вашего проекта есть 'config.ini' или 'pyproject.toml', "
            "либо укажите путь к конфигу вручную через chutils.init(base_dir=...)"
        )
    return _CONFIG_FILE_PATH


def load_config(cfg_file: Optional[str] = None) -> configparser.ConfigParser:
    """
    Загружает конфигурацию из .ini файла.

    Args:
        cfg_file (str, optional): Явный путь к файлу конфигурации.
                                  Если не указан, будет использован автоматически найденный путь.

    Returns:
        configparser.ConfigParser: Загруженный объект конфигурации.
    """
    path = _get_config_path(cfg_file)
    if not os.path.exists(path):
        logger.critical(f"Файл конфигурации НЕ НАЙДЕН: {path}")
        return configparser.ConfigParser()

    config = configparser.ConfigParser()
    try:
        config.read(path, encoding='utf-8')
        logger.info(f"Конфигурация успешно загружена из {path}")
        return config
    except configparser.Error as e:
        logger.critical(f"Ошибка чтения файла конфигурации {path}: {e}")
        return configparser.ConfigParser()


def save_config_value(section: str, key: str, value: str, cfg_file: Optional[str] = None) -> bool:
    """
    Сохраняет одно значение в конфигурационном файле, пытаясь сохранить комментарии.

    Изменяет только первую найденную строку с ключом в нужной секции.
    Не добавляет новые секции или ключи, если они не существуют.
    """
    path = _get_config_path(cfg_file)
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
                logger.info(f"Ключ '{key}' в секции '[{section}]' будет обновлен на '{value}' в файле {path}")
                continue

        new_lines.append(line)

    if not section_found:
        logger.warning(f"Секция '[{section}]' не найдена в файле {path}. Значение НЕ сохранено.")
        return False
    if section_found and not key_found_in_section:
        logger.warning(f"Ключ '{key}' не найден в секции '[{section}]' файла {path}. Значение НЕ сохранено.")
        return False

    if updated:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            logger.info(f"Файл конфигурации {path} успешно обновлен.")
            return True
        except IOError as e:
            logger.error(f"Ошибка записи в файл {path} при сохранении: {e}")
            return False
    else:
        logger.debug(f"Обновление для ключа '{key}' в секции '[{section}]' не потребовалось.")
        return False


def get_config() -> configparser.ConfigParser:
    """Возвращает полностью загруженный объект конфигурации."""
    return load_config()


# --- Функции-обертки для удобного получения значений ---

def get_config_value(section: str, key: str, fallback: str = "", config: Optional[configparser.ConfigParser] = None) -> str:
    """Получает строковое значение из конфигурации."""
    if config is None: config = load_config()
    return config.get(section, key, fallback=fallback)


def get_config_int(section: str, key: str, fallback: int = 0, config: Optional[configparser.ConfigParser] = None) -> int:
    """Получает целочисленное значение из конфигурации."""
    if config is None: config = load_config()
    return config.getint(section, key, fallback=fallback)


def get_config_float(section: str, key: str, fallback: float = 0.0, config: Optional[configparser.ConfigParser] = None) -> float:
    """Получает дробное значение из конфигурации."""
    if config is None: config = load_config()
    return config.getfloat(section, key, fallback=fallback)


def get_config_boolean(section: str, key: str, fallback: bool = False, config: Optional[configparser.ConfigParser] = None) -> bool:
    """Получает булево значение из конфигурации."""
    if config is None: config = load_config()
    return config.getboolean(section, key, fallback=fallback)


def get_config_list(section: str, key: str, fallback: Optional[List[str]] = None, config: Optional[configparser.ConfigParser] = None) -> List[str]:
    """
    Получает многострочное значение и возвращает его в виде списка очищенных строк.

    Идеально подходит для списков:
    - Разделяет значение по переносам строк.
    - Удаляет пустые строки и лишние пробелы.
    - Игнорирует строки, начинающиеся с '#' (комментарии).
    """
    if fallback is None:
        fallback = []
    raw_value = get_config_value(section, key, fallback="", config=config)
    if not raw_value:
        return fallback

    lines = [line.strip() for line in raw_value.splitlines() if line.strip() and not line.strip().startswith('#')]
    return lines


def get_multiple_config_values(section: str, keys: List[str], config: Optional[configparser.ConfigParser] = None) -> Dict[str, Optional[str]]:
    """Получает словарь значений для указанных ключей в секции."""
    if config is None: config = load_config()
    values = {}
    if config.has_section(section):
        for key in keys:
            values[key] = config.get(section, key, fallback=None)
    return values


def get_config_section(section_name: str, fallback: Optional[Dict] = None, config: Optional[configparser.ConfigParser] = None) -> Dict[str, str]:
    """
    Получает всю секцию из конфигурации как словарь.
    """
    if fallback is None:
        fallback = {}
    if config is None:
        config = load_config()

    if config.has_section(section_name):
        # Преобразуем секцию в обычный словарь
        return dict(config.items(section_name))
    else:
        logger.warning(f"Секция '{section_name}' не найдена в конфигурации. Возвращен fallback.")
        return fallback