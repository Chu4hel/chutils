import os
import threading
import time

from chutils.logger import setup_logger


def test_async_logging():
    # Настраиваем асинхронный логгер
    logger = setup_logger(
        name="async_test",
        log_file_name="async_test.log",
        use_async=True,
        force_reconfigure=True
    )

    main_thread_id = threading.get_ident()
    print(f"Main thread ID: {main_thread_id}")

    # Записываем сообщение
    logger.info("Test async message")

    # Даем время на обработку в фоновом потоке
    time.sleep(0.5)

    # Проверяем, что файл создан и содержит лог
    log_file = os.path.join("logs", "async_test.log")
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            content = f.read()
            print(f"Log content:\n{content}")
            if "Test async message" in content:
                print("SUCCESS: Async log message found in file.")
            else:
                print("FAILURE: Async log message NOT found in file.")
    else:
        print(f"FAILURE: Log file {log_file} not found.")


if __name__ == "__main__":
    test_async_logging()
