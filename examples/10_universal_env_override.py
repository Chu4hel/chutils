"""
Пример универсального переопределения конфигурации через переменные окружения.

Этот пример демонстрирует, как значения из любого источника (YAML, INI, JSON)
могут быть перекрыты переменными окружения по шаблону CH_[SECTION]_[KEY].
"""

import os

from chutils import get_config_value, get_config_int


def run_example():
    print("--- Демонстрация универсального переопределения через ENV ---")

    # 1. Значение по умолчанию (если ничего не установлено)
    host = get_config_value("Database", "host", fallback="localhost")
    port = get_config_int("Database", "port", fallback=5432)
    print(f"1. До установки ENV: {host}:{port}")

    # 2. Переопределяем через переменные окружения
    # Шаблон: CH_{SECTION}_{KEY} в верхнем регистре
    os.environ["CH_DATABASE_HOST"] = "production-db-server"
    os.environ["CH_DATABASE_PORT"] = "9999"

    # Теперь библиотека должна вернуть значения из окружения
    host_env = get_config_value("Database", "host", fallback="localhost")
    port_env = get_config_int("Database", "port", fallback=5432)
    print(f"2. После установки ENV: {host_env}:{port_env}")

    # 3. Отключаем механизм через CH_DISABLE_ENV_OVERRIDE
    os.environ["CH_DISABLE_ENV_OVERRIDE"] = "true"
    host_disabled = get_config_value("Database", "host", fallback="localhost")
    print(f"3. С отключенным переопределением: {host_disabled}")

    # Очистка
    del os.environ["CH_DATABASE_HOST"]
    del os.environ["CH_DATABASE_PORT"]
    del os.environ["CH_DISABLE_ENV_OVERRIDE"]


if __name__ == "__main__":
    run_example()
