"""
Пример использования API диагностики конфигурации.
Демонстрирует программное получение истории загрузки настроек.
"""

import os

from chutils import get_config, setup_logger
from chutils.config.diagnostics import format_trace
from chutils.config.manager import _cm

logger = setup_logger()


def main():
    # 1. Включаем режим трассировки ДО загрузки конфигурации
    _cm.tracing_enabled = True

    # 2. Устанавливаем переменные окружения для имитации переопределения
    os.environ["CH_APP_NAME"] = "DiagnosticsDemo"
    os.environ["CH_DATABASE_PORT"] = "9999"

    logger.info("Загружаем конфигурацию...")
    # Сбрасываем кэш, чтобы гарантированно пройти по всем источникам
    _cm.clear_cache()
    get_config()

    # 3. Получаем данные трассировки
    # Это словарь, где ключи - это (секция, ключ), а значения - список источников
    trace_data = _cm.get_trace()

    logger.info("\n--- История изменения параметров (Текстовый отчет) ---")
    # Используем встроенную функцию форматирования (доступны форматы: tree, table, json)
    report = format_trace(trace_data, format_type='tree')
    print(report)

    logger.info("\n--- Прямой доступ к метаданным ---")
    # Например, проверим откуда пришел порт базы данных
    db_port_history = trace_data.get('database', {}).get('port', [])
    for entry in db_port_history:
        logger.info(f"Параметр 'database.port' был найден в '{entry['source']}' со значением '{entry['value']}'")


if __name__ == "__main__":
    main()
