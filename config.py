import configparser
import os
from . import logger as logging
import sys
import re
from typing import Any

logger = logging.setup_logger(__name__, 'ERROR')

def get_base_dir() -> str:
    # Определяем базовую директорию (где скрипт или exe)
    if getattr(sys, 'frozen', False):
        # Если запущено из PyInstaller bundle
        base_dir = os.path.dirname(sys.executable)
    else:
        # Если запущено как обычный скрипт
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Поднимаемся на уровень выше utils
    return base_dir


BASE_DIR = get_base_dir()

CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")


def load_config(CONFIG_FILE: str = CONFIG_FILE) -> configparser.ConfigParser:
    """Загружает конфигурацию из файла config.ini."""
    if not os.path.exists(CONFIG_FILE):
        logger.critical(f"Файл конфигурации НЕ НАЙДЕН: {CONFIG_FILE}")
        return configparser.ConfigParser()

    config = configparser.ConfigParser()
    try:
        config.read(CONFIG_FILE, encoding='utf-8')
        logger.info(f"Конфигурация успешно загружена из {CONFIG_FILE}")
        return config
    except configparser.Error as e:
        logger.critical(f"Ошибка чтения файла конфигурации {CONFIG_FILE}: {e}")
        return configparser.ConfigParser()  # Возвращаем пустой объект в случае ошибки


def save_config_value(section: str, key: str, value: str, CONFIG_FILE: str = CONFIG_FILE) -> bool:
    """
    Сохраняет ОДНО значение в конфигурационном файле,
    ПЫТАЯСЬ СОХРАНИТЬ КОММЕНТАРИИ и структуру.
    Изменяет только первую найденную строку с ключом в нужной секции.
    Не добавляет новые секции или ключи, если они не существуют.
    """
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Невозможно сохранить значение: файл конфигурации {CONFIG_FILE} не найден.")
        return False

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except IOError as e:
        logger.error(f"Ошибка чтения файла {CONFIG_FILE} для сохранения: {e}")
        return False

    updated = False
    in_target_section = False
    section_found = False
    key_found_in_section = False
    section_pattern = re.compile(r'^\s*\[\s*(?P<section_name>[^]]+)\s*\]\s*')
    # Паттерн для поиска ключа, учитывающий пробелы и регистр (сохраняем регистр ключа из файла)
    # Он ищет начало строки (\s*), затем ключ (захватываем его), затем пробелы, '=', пробелы, и значение (.*)
    # Используем re.IGNORECASE для поиска ключа без учета регистра
    key_pattern = re.compile(rf'^\s*({re.escape(key)})\s*=\s*(.*)', re.IGNORECASE)

    new_lines = []
    for line in lines:
        section_match = section_pattern.match(line)
        if section_match:
            current_section_name = section_match.group('section_name').strip()
            # Проверяем, находимся ли мы в целевой секции (без учета регистра)
            if current_section_name.lower() == section.lower():
                in_target_section = True
                section_found = True
            else:
                in_target_section = False
            new_lines.append(line)  # Добавляем строку секции как есть
            continue

        if in_target_section and not key_found_in_section:  # Ищем ключ только в нужной секции и только первый раз
            key_match = key_pattern.match(line)
            if key_match:
                original_key = key_match.group(1)  # Ключ с оригинальным регистром из файла
                # Формируем новую строку: оригинальный ключ + разделитель + новое значение
                new_line_content = f"{original_key} = {value}\n"
                new_lines.append(new_line_content)
                key_found_in_section = True
                updated = True
                logger.info(
                    f"Ключ '{key}' в секции '[{section}]' будет обновлен значением '{value}' в файле {CONFIG_FILE}")
                continue  # Переходим к следующей строке, пропуская добавление старой

        # Если строка не заголовок секции и не целевой ключ, добавляем ее как есть
        new_lines.append(line)

    if not section_found:
        logger.warning(f"Секция '[{section}]' не найдена в файле {CONFIG_FILE}. Значение НЕ сохранено.")
        return False
    if section_found and not key_found_in_section:
        logger.warning(f"Ключ '{key}' не найден в секции '[{section}]' файла {CONFIG_FILE}. Значение НЕ сохранено.")
        # Если нужно добавлять ключ, если он не найден, логика будет здесь,
        # но текущая реализация только изменяет существующие.
        return False

    if updated:
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            logger.info(f"Файл конфигурации {CONFIG_FILE} успешно обновлен.")
            return True
        except IOError as e:
            logger.error(f"Ошибка записи в файл {CONFIG_FILE} при сохранении: {e}")
            return False
    else:
        # Это может произойти, если ключ или секция не были найдены
        logger.debug(
            f"Обновление ключа '{key}' в секции '[{section}]' не потребовалось или не удалось найти ключ/секцию.")
        return False  # Возвращаем False, если фактического обновления не было


def get_config() -> dict[str, Any]:
    """Возвращает загруженный объект конфигурации."""
    # Если конфиг нужен целиком
    return load_config()


def get_config_value(section: str, key: str, fallback: str = "", config: dict[str, Any] = None) -> str:
    """Получает значение из конфигурации с возможностью указать значение по умолчанию."""
    if config is None: config = load_config()
    return config.get(section, key, fallback=fallback)


def get_config_int(section: str, key: str, fallback: int = 0, config: dict[str, Any] = None) -> int:
    """Получает целочисленное значение из конфигурации."""
    if config is None: config = load_config()
    return config.getint(section, key, fallback=fallback)


def get_config_float(section: str, key: str, fallback: float = 0.0, config: dict[str, Any] = None) -> float:
    """Получает дробное значение из конфигурации."""
    if config is None: config = load_config()
    return config.getfloat(section, key, fallback=fallback)


def get_config_boolean(section: str, key: str, fallback: bool = False, config: dict[str, Any] = None) -> bool:
    """Получает булево значение из конфигурации."""
    if config is None: config = load_config()
    return config.getboolean(section, key, fallback=fallback)


# Получение нескольких значений
def get_multiple_config_values(section: str, keys: list, config: dict[str, Any] = None) -> dict:
    """Получает словарь значений для указанных ключей в секции."""
    if config is None: config = load_config()
    values = {}
    if config.has_section(section):
        for key in keys:
            values[key] = config.get(section, key, fallback=None)
    return values


def get_config_section(section_name: str, fallback: dict = {}, config: dict[str, Any] = None) -> dict:
    """
    Получает всю секцию из конфигурации.

    Args:
        section_name (str): Имя запрашиваемой секции.
        fallback (dict, optional): Значение, возвращаемое если секция не найдена.
                                   По умолчанию пустой словарь.
        config (configparser.ConfigParser, optional): Предзагруженный объект конфигурации.
                                                      Если None, будет загружен из CONFIG_FILE.

    Returns:
        configparser.SectionProxy or dict: Объект секции (похожий на словарь)
                                           или значение fallback, если секция не найдена.
                                           Чтобы получить обычный dict, dict(результат).
    """
    if config is None:
        config = load_config()

    if config.has_section(section_name):
        return config[section_name]
    else:
        logger.warning(f"Секция '{section_name}' не найдена в конфигурации. Возвращен fallback.")
        return fallback
