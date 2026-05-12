"""
Провайдеры для различных форматов конфигурационных файлов.
Используют паттерн Стратегия для изоляции логики чтения и записи.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

import yaml

# Настраиваем локальный логгер
logger = logging.getLogger(__name__)


class ConfigProvider(ABC):
    """
    Абстрактный базовый класс для провайдеров конфигурации.
    """

    @abstractmethod
    def load(self, path: str) -> Dict[str, Any]:
        """
        Загружает конфигурацию из файла.

        Args:
            path: Путь к файлу.

        Returns:
            Словарь с данными конфигурации.
        """
        pass

    @abstractmethod
    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        """
        Сохраняет или обновляет значение в файле конфигурации.

        Args:
            path: Путь к файлу.
            section: Имя секции.
            key: Имя ключа.
            value: Новое значение.

        Returns:
            True, если сохранение прошло успешно, иначе False.
        """
        pass


class YamlConfigProvider(ConfigProvider):
    """
    Провайдер для работы с YAML файлами (.yml, .yaml).
    """

    def load(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, FileNotFoundError) as e:
            logger.critical("Ошибка чтения YAML файла конфигурации %s: %s", path, e)
            return {}

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        try:
            # Читаем текущие данные
            data = self.load(path) if Path(path).exists() else {}

            if section not in data:
                data[section] = {}
            data[section][key] = value

            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            logger.error("Ошибка при сохранении в YAML файл %s: %s", path, e)
            return False


class JsonConfigProvider(ConfigProvider):
    """
    Провайдер для работы с JSON файлами (.json).
    """

    def load(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f) or {}
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.critical("Ошибка чтения JSON файла конфигурации %s: %s", path, e)
            return {}

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        try:
            data = {}
            if Path(path).exists():
                with open(path, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f) or {}
                    except json.JSONDecodeError:
                        logger.warning("Файл %s содержит некорректный JSON, он будет перезаписан.", path)

            if section not in data:
                data[section] = {}
            data[section][key] = value

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error("Ошибка при сохранении в JSON файл %s: %s", path, e)
            return False


class IniConfigProvider(ConfigProvider):
    """
    Провайдер для работы с INI файлами (.ini).
    Сохраняет комментарии и форматирование при записи.
    """

    def __init__(self, nest_func):
        self._nest_func = nest_func

    def load(self, path: str) -> Dict[str, Any]:
        import configparser
        try:
            with open(path, 'r', encoding='utf-8') as f:
                parser = configparser.ConfigParser()
                parser.read_string(f.read())
                flat_ini_config = {s: dict(parser.items(s)) for s in parser.sections()}
                return self._nest_func(flat_ini_config)
        except (configparser.Error, FileNotFoundError) as e:
            logger.critical("Ошибка чтения INI файла конфигурации %s: %s", path, e)
            return {}

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        if not Path(path).exists():
            logger.error("Невозможно сохранить значение: файл конфигурации %s не найден.", path)
            return False

        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except IOError as e:
            logger.error("Ошибка чтения файла %s для сохранения: %s", path, e)
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
                    continue

            new_lines.append(line)

        if not section_found:
            if new_lines and new_lines[-1].strip() != "":
                new_lines.append('\n')
            new_lines.append(f'[{section}]\n')
            new_lines.append(f'{key} = {value}\n')
            updated = True
        elif not key_found_in_section:
            final_lines = []
            in_target_section_for_add = False
            for i, line in enumerate(new_lines):
                final_lines.append(line)
                section_match = section_pattern.match(line)
                if section_match:
                    current_section_name = section_match.group('section_name').strip()
                    in_target_section_for_add = current_section_name.lower() == section.lower()

                is_last_line = i == len(new_lines) - 1
                next_line_is_new_section = False
                if not is_last_line:
                    next_line_match = section_pattern.match(new_lines[i + 1])
                    if next_line_match:
                        next_line_is_new_section = True

                if in_target_section_for_add and (is_last_line or next_line_is_new_section):
                    final_lines.append(f"{key} = {value}\n")
                    updated = True
                    break
            new_lines = final_lines

        if updated:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                return True
            except IOError as e:
                logger.error("Ошибка записи в файл %s при сохранении: %s", path, e)
                return False
        return False


def get_providers(nest_func) -> Dict[str, ConfigProvider]:
    """
    Создает и возвращает реестр провайдеров.
    """
    yaml_provider = YamlConfigProvider()
    return {
        '.yml': yaml_provider,
        '.yaml': yaml_provider,
        '.json': JsonConfigProvider(),
        '.ini': IniConfigProvider(nest_func),
    }
