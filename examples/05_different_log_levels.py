# examples/05_different_log_levels.py
from chutils.logger import setup_logger, ChutilsLogger

# Представим, что у нас есть приложение с двумя модулями: "core" и "utils".
# Мы хотим видеть подробные отладочные сообщения от нашего "core" модуля,
# но для "utils" нас интересуют только предупреждения и ошибки.

# 1. Настраиваем логгер для модуля "core" с уровнем DEVDEBUG.
#    Мы явно передаем уровень логирования при настройке.
core_logger: ChutilsLogger = setup_logger("core_module", log_level_str='DEVDEBUG')

# 2. Настраиваем логгер для модуля "utils" с уровнем WARNING.
utils_logger: ChutilsLogger = setup_logger("utils_module", log_level_str='WARNING')

# 3. Настроим основной логгер приложения.
#    Если уровень не указать явно, он будет взят из config.yml.
#    В файле examples/config.yml установлен уровень DEBUG.
app_logger: ChutilsLogger = setup_logger("main_app")

print("--- Начало демонстрации логирования ---")

# Логируем сообщения из разных "модулей"
app_logger.info("Приложение запущено.")
app_logger.debug("Это debug-сообщение от app_logger. Оно будет показано, т.к. в config.yml стоит уровень DEBUG.")

core_logger.info("Core-модуль начинает работу...")
core_logger.devdebug("Это детальное сообщение от core_logger, оно должно появиться.")
core_logger.mediumdebug("Сообщение средней детализации от core_logger.")

utils_logger.info("Это информационное сообщение от utils_logger, оно будет скрыто.")
utils_logger.warning("А вот это предупреждение от utils_logger мы увидим.")

app_logger.info("Приложение завершает работу.")

print("\n--- Конец демонстрации ---")
print("Проверьте вывод в консоли. Вы должны увидеть все сообщения от 'main_app' и 'core_module' (включая debug),")
print("а также предупреждение от 'utils_module', но не информационные сообщения от него.")
