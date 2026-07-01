import asyncio
import threading
import time

import pytest

from chutils import config
from chutils.cache.in_memory import InMemoryCacheBackend
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


@pytest.mark.asyncio
async def test_async_config_safety_stress_test(config_fs):
    """Стресс-тест асинхронной безопасности ConfigManager."""
    fs, project_root = config_fs
    config_path = project_root / "config.yml"

    initial_content = """
App:
  name: "AsyncTest"
"""
    fs.create_file(config_path, contents=initial_content)

    # Инициализация
    await config.aget_config()

    async def reader_task(task_id):
        for _ in range(50):
            cfg = await config.aget_config()
            assert cfg["App"]["name"] == "AsyncTest"
            await asyncio.sleep(0.001)

    async def writer_task(task_id):
        for i in range(10):
            await config.asave_config_value("App", "counter", str(i))
            await asyncio.sleep(0.005)

    # Запускаем параллельно 50 читателей и 10 писателей
    tasks = []
    for i in range(50):
        tasks.append(reader_task(i))
    for i in range(10):
        tasks.append(writer_task(i))

    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_async_cache_safety_stress_test():
    """Стресс-тест асинхронной безопасности InMemoryCacheBackend."""
    cache = InMemoryCacheBackend()

    async def reader_task(task_id):
        for _ in range(50):
            val = await cache.aget("test_key")
            await asyncio.sleep(0.001)

    async def writer_task(task_id):
        for i in range(20):
            await cache.aset("test_key", f"val_{i}", ttl=10)
            await asyncio.sleep(0.002)

    tasks = []
    for i in range(50):
        tasks.append(reader_task(i))
    for i in range(10):
        tasks.append(writer_task(i))

    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_asave_config_does_not_block_loop(config_fs, mocker):
    """Проверяет, что asave_config_value выполняется в executor и не блокирует event loop."""
    fs, project_root = config_fs
    config_path = project_root / "config.yml"

    initial_content = "App:\n  name: \"BlockTest\"\n"
    fs.create_file(config_path, contents=initial_content)
    await config.aget_config()

    # Мокаем медленную запись в файл (имитируем 0.2 секунды I/O блокировки)
    from chutils.config.providers import YamlConfigProvider
    original_save = YamlConfigProvider.save

    def slow_save(self, path, section, key, value):
        time.sleep(0.2)
        return original_save(self, path, section, key, value)

    mocker.patch.object(YamlConfigProvider, "save", slow_save)

    parallel_task_executed = False

    async def parallel_task():
        nonlocal parallel_task_executed
        # Даем asave_config_value начать выполнение
        await asyncio.sleep(0.05)
        parallel_task_executed = True

    # Запускаем параллельно сохранение конфига (которое займет 0.2с)
    # и легкую таску, которая должна успеть выполниться за 0.05с.
    start = time.monotonic()

    save_fut = asyncio.create_task(config.asave_config_value("App", "name", "NewVal"))
    bg_task = asyncio.create_task(parallel_task())

    await bg_task
    await save_fut

    elapsed = time.monotonic() - start
    assert elapsed >= 0.2
    assert parallel_task_executed is True
