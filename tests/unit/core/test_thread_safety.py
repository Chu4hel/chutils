import threading
import time

from chutils import config
from chutils.config.manager import _cm
from chutils.config.watcher import ConfigChangeHandler


def test_config_manager_thread_safety(config_fs):
    """
    Стресс-тест для проверки потокобезопасности ConfigManager.
    Запускает множество потоков на чтение и запись одновременно.
    """
    fs, project_root = config_fs
    config_path = project_root / "config.yml"

    initial_content = """
App:
  name: "ThreadTest"
  version: "1.0"
Database:
  host: "localhost"
"""
    fs.create_file(config_path, contents=initial_content)

    # Гарантируем инициализацию
    config.get_config()

    stop_event = threading.Event()
    errors = []

    def reader_thread(thread_id):
        try:
            while not stop_event.is_set():
                val = config.get_config_value("App", "name")
                assert val == "ThreadTest"
                # Интенсивное чтение всей секции
                section = config.get_config_section("Database")
                assert section["host"] == "localhost"
                time.sleep(0.001)
        except Exception as e:
            errors.append(f"Reader {thread_id} error: {e}")

    def writer_thread(thread_id):
        try:
            i = 0
            while not stop_event.is_set():
                # Сохраняем значение (это сбрасывает кэш)
                config.save_config_value("App", "counter", str(i))
                i += 1
                time.sleep(0.01)
        except Exception as e:
            errors.append(f"Writer {thread_id} error: {e}")

    def reload_simulator_thread():
        try:
            handler = ConfigChangeHandler([str(config_path)])
            while not stop_event.is_set():
                # Симулируем событие изменения файла (сброс кэша в ConfigManager)
                handler._on_modified()
                time.sleep(0.05)
        except Exception as e:
            errors.append(f"Reloader error: {e}")

    # Запускаем 20 потоков на чтение, 5 на запись и 1 на симуляцию перезагрузки
    threads = []
    for i in range(20):
        t = threading.Thread(target=reader_thread, args=(i,))
        threads.append(t)

    for i in range(5):
        t = threading.Thread(target=writer_thread, args=(i,))
        threads.append(t)

    threads.append(threading.Thread(target=reload_simulator_thread))

    for t in threads:
        t.start()

    # Даем поработать 3 секунды под нагрузкой
    time.sleep(3)
    stop_event.set()

    for t in threads:
        t.join(timeout=1.0)

    # Проверяем наличие ошибок
    assert not errors, f"Обнаружены ошибки при многопоточной работе: {errors}"


def test_concurrent_callback_registration():
    """Проверяет безопасность одновременной регистрации коллбэков."""
    _cm._reset()

    def dummy_callback():
        pass

    def register_task():
        for _ in range(100):
            config.on_config_change(dummy_callback)

    threads = [threading.Thread(target=register_task) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # После 1000 попыток регистрации (10 потоков по 100)
    # в списке должен быть ровно 1 экземпляр коллбэка, так как add_callback делает проверку
    assert len(_cm.get_callbacks()) == 1
