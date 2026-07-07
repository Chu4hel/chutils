"""
Провайдеры для различных форматов конфигурационных файлов.
Используют паттерн Стратегия для изоляции логики чтения и записи.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import tempfile
import threading
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TextIO
from collections.abc import Callable

import yaml

from chutils.exceptions import ConfigLoadError, ConfigParseError
from chutils.typing import JSONDict

# Настраиваем локальный логгер
logger = logging.getLogger(__name__)


def _atomic_write(path: str, content_writer_func: Callable[[TextIO], None]) -> None:
    """
    Вспомогательная функция для атомарной записи в файл через временный файл.
    """
    dir_path = os.path.dirname(os.path.abspath(path))
    # Создаем временный файл в той же директории, чтобы гарантировать нахождение на одном разделе (нужно для os.replace)
    fd, temp_path = tempfile.mkstemp(dir=dir_path, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            content_writer_func(f)

        # Атомарная замена (на Windows заменит существующий файл)
        os.replace(temp_path, path)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e


class ConfigProvider(ABC):
    """
    Абстрактный базовый класс для провайдеров конфигурации.
    """

    @abstractmethod
    def load(self, path: str) -> JSONDict:
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

    def load(self, path: str) -> JSONDict:
        try:
            with open(path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            raise ConfigLoadError(
                f"Файл конфигурации не найден: {path}",
                hint="Убедитесь, что путь указан верно или создайте файл с помощью 'chutils init'.",
                path=path
            )
        except yaml.YAMLError as e:
            raise ConfigParseError(
                f"Ошибка парсинга YAML в файле {path}: {e}",
                hint="Проверьте синтаксис YAML файла. Возможно, пропущены отступы или двоеточия.",
                path=path
            )
        except Exception as e:
            raise ConfigLoadError(f"Ошибка чтения файла {path}: {e}", path=path)

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        try:
            # Читаем текущие данные
            data: JSONDict = self.load(path) if Path(path).exists() else {}

            if section not in data:
                data[section] = {}
            data[section][key] = value

            def writer(f: TextIO) -> None:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)

            _atomic_write(path, writer)
            return True
        except Exception as e:
            logger.error("Ошибка при сохранении в YAML файл %s: %s", path, e)
            return False


class JsonConfigProvider(ConfigProvider):
    """
    Провайдер для работы с JSON файлами (.json).
    """

    def load(self, path: str) -> JSONDict:
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            raise ConfigLoadError(
                f"Файл конфигурации не найден: {path}",
                hint="Убедитесь, что путь указан верно или создайте файл с помощью 'chutils init'.",
                path=path
            )
        except json.JSONDecodeError as e:
            raise ConfigParseError(
                f"Ошибка парсинга JSON в файле {path}: {e}",
                hint="Проверьте синтаксис JSON файла. "
                     "Убедитесь в наличии кавычек у ключей и отсутствии лишних запятых.",
                path=path
            )
        except Exception as e:
            raise ConfigLoadError(f"Ошибка чтения файла {path}: {e}", path=path)

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        try:
            data: JSONDict = {}
            if Path(path).exists():
                with open(path, encoding='utf-8') as f:
                    try:
                        loaded_data = json.load(f)
                        data = loaded_data if isinstance(loaded_data, dict) else {}
                    except json.JSONDecodeError:
                        logger.warning("Файл %s содержит некорректный JSON, он будет перезаписан.", path)

            if section not in data:
                data[section] = {}
            data[section][key] = value

            def writer(f: TextIO) -> None:
                json.dump(data, f, indent=4, ensure_ascii=False)

            _atomic_write(path, writer)
            return True
        except Exception as e:
            logger.error("Ошибка при сохранении в JSON файл %s: %s", path, e)
            return False


class IniConfigProvider(ConfigProvider):
    """
    Провайдер для работы с INI файлами (.ini).
    Сохраняет комментарии и форматирование при записи.
    """

    def __init__(self, nest_func: Callable[[dict[str, dict[str, Any]]], JSONDict]) -> None:
        self._nest_func = nest_func

    def load(self, path: str) -> JSONDict:
        import configparser
        try:
            with open(path, encoding='utf-8') as f:
                parser = configparser.ConfigParser()
                parser.optionxform = str  # type: ignore # Сохраняем регистр ключей
                parser.read_string(f.read())
                flat_ini_config = {s: dict(parser.items(s)) for s in parser.sections()}
                return self._nest_func(flat_ini_config)
        except FileNotFoundError:
            raise ConfigLoadError(
                f"Файл конфигурации не найден: {path}",
                hint="Убедитесь, что путь указан верно или создайте файл с помощью 'chutils init'.",
                path=path
            )
        except configparser.Error as e:
            raise ConfigParseError(
                f"Ошибка парсинга INI в файле {path}: {e}",
                hint="Проверьте синтаксис INI файла. "
                     "Убедитесь в правильности заголовков секций [Section] и формата key=value.",
                path=path
            )
        except Exception as e:
            raise ConfigLoadError(f"Ошибка чтения файла {path}: {e}", path=path)

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        if not Path(path).exists():
            logger.error("Невозможно сохранить значение: файл конфигурации %s не найден.", path)
            return False

        try:
            with open(path, encoding='utf-8') as f:
                lines = f.readlines()
        except OSError as e:
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
                def writer(f: TextIO) -> None:
                    f.writelines(new_lines)

                _atomic_write(path, writer)
                return True
            except Exception as e:
                logger.error("Ошибка записи в файл %s при сохранении: %s", path, e)
                return False
        return False


class HttpConfigProvider:
    """
    Провайдер для загрузки конфигурации через HTTP/HTTPS.
    Поддерживает Basic Auth и периодический опрос (polling).
    """

    def __init__(
            self,
            url: str,
            username: str | None = None,
            password: str | None = None,
            timeout: int = 10,
            nest_func: Callable[[dict[str, dict[str, Any]]], JSONDict] | None = None
    ) -> None:
        self.url = url
        self.username = username
        self.password = password
        self.timeout = timeout
        self._nest_func = nest_func
        self._cache: JSONDict = {}
        self._polling_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def load(self) -> JSONDict:
        """
        Загружает конфигурацию из удаленного источника и парсит ее.
        В случае ошибки возвращает закешированную версию (Fallback).
        """
        try:
            content, content_type = self.fetch()
            data = self._parse_content(content, content_type)
            self._cache = data
            return data
        except Exception as e:
            if self._cache:
                logger.warning("Не удалось обновить удаленный конфиг (%s). Используем кэш.", e)
                return self._cache
            raise e

    def start_polling(self, interval: int = 60) -> None:
        """
        Запускает фоновое обновление конфигурации.

        Args:
            interval: Интервал опроса в секундах.
        """
        if self._polling_thread and self._polling_thread.is_alive():
            return

        self._stop_event.clear()
        self._polling_thread = threading.Thread(
            target=self._polling_worker,
            args=(interval,),
            name="HttpConfigPolling",
            daemon=True
        )
        self._polling_thread.start()
        logger.debug("Запущен фоновый опрос для %s (интервал %ds)", self.url, interval)

    def stop_polling(self) -> None:
        """
        Останавливает фоновое обновление.
        """
        self._stop_event.set()
        if self._polling_thread:
            self._polling_thread.join(timeout=2)
            self._polling_thread = None
        logger.debug("Опрос для %s остановлен", self.url)

    def _polling_worker(self, interval: int) -> None:
        """
        Фоновый воркер для опроса.
        """
        f_interval: float = float(interval)
        while not self._stop_event.is_set():
            # Ждем интервал, проверяя событие остановки каждые 0.5 сек для быстрой реакции
            wait_remaining = f_interval
            while wait_remaining > 0 and not self._stop_event.is_set():
                time_to_wait = min(0.5, wait_remaining)
                self._stop_event.wait(time_to_wait)
                wait_remaining -= time_to_wait

            if self._stop_event.is_set():
                break

            try:
                # Пытаемся загрузить. Если успешно - кэш обновится внутри load()
                new_data = self.load()

                # Проверяем наличие динамического интервала в конфиге
                # Секция 'polling' или 'RemoteConfig', ключ 'interval'
                dynamic_interval = None
                if isinstance(new_data, dict):
                    # Ищем в разных возможных местах
                    remote_meta = new_data.get('RemoteConfig') or new_data.get('polling')
                    if isinstance(remote_meta, dict):
                        dynamic_interval = remote_meta.get('interval')

                if isinstance(dynamic_interval, (int, float)) and dynamic_interval > 0:
                    if float(dynamic_interval) != f_interval:
                        logger.info("Интервал опроса изменен динамически: %ss -> %ss", f_interval, dynamic_interval)
                        f_interval = float(dynamic_interval)

            except Exception as e:
                logger.error("Ошибка при фоновом обновлении конфига с %s: %s", self.url, e)

    def _parse_content(self, content: str, content_type: str | None) -> JSONDict:
        """
        Парсит контент на основе Content-Type или расширения URL.
        """
        # Определяем формат
        fmt = None
        if content_type:
            ct = content_type.lower()
            if "json" in ct:
                fmt = "json"
            elif "yaml" in ct or "x-yaml" in ct:
                fmt = "yaml"

        if not fmt:
            # Пробуем по расширению URL
            ext = Path(self.url).suffix.lower()
            if ext in ('.yml', '.yaml'):
                fmt = "yaml"
            elif ext == '.json':
                fmt = "json"
            elif ext == '.ini':
                fmt = "ini"

        # По умолчанию пробуем YAML (он наиболее универсален и часто совпадает с JSON)
        if not fmt:
            fmt = "yaml"

        try:
            if fmt == "json":
                data = json.loads(content)
                return data if isinstance(data, dict) else {}
            elif fmt == "yaml":
                data = yaml.safe_load(content)
                return data if isinstance(data, dict) else {}
            elif fmt == "ini":
                import configparser
                parser = configparser.ConfigParser()
                parser.read_string(content)
                flat_ini_config = {s: dict(parser.items(s)) for s in parser.sections()}
                if self._nest_func:
                    return self._nest_func(flat_ini_config)
                return flat_ini_config
        except Exception as e:
            logger.error("Ошибка парсинга удаленного конфига (%s): %s", fmt, e)
            raise ConfigParseError(f"Ошибка парсинга {fmt}: {e}", path=self.url)

        return {}

    def fetch(self) -> tuple[str, str | None]:
        """
        Загружает сырые данные из удаленного эндпоинта.

        Returns:
            Кортеж (контент, content_type).

        Raises:
            ConfigLoadError: Если произошла ошибка сети или авторизации.
        """
        req = urllib.request.Request(self.url)

        if self.username and self.password:
            auth_str = f"{self.username}:{self.password}"
            encoded_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            req.add_header("Authorization", f"Basic {encoded_auth}")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content = response.read().decode('utf-8')
                content_type = response.headers.get("Content-Type")
                return content, content_type
        except urllib.error.HTTPError as e:
            logger.error("HTTP ошибка при загрузке конфига с %s: %s", self.url, e)
            raise ConfigLoadError(f"HTTP ошибка {e.code}: {e.reason}", path=self.url)
        except urllib.error.URLError as e:
            logger.error("Ошибка сети при загрузке конфига с %s: %s", self.url, e)
            raise ConfigLoadError(f"Ошибка сети: {e.reason}", path=self.url)
        except Exception as e:
            logger.error("Непредвиденная ошибка при загрузке конфига с %s: %s", self.url, e)
            raise ConfigLoadError(f"Непредвиденная ошибка: {e}", path=self.url)


def get_providers(
        nest_func: Callable[[dict[str, dict[str, Any]]], JSONDict]
) -> dict[str, ConfigProvider]:
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
