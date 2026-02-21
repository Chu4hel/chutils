import subprocess
import sys
from pathlib import Path

# Определяем путь к директории с примерами
# Это предполагает, что тесты запускаются из корня проекта
examples_dir = Path(__file__).parent.parent / "examples"


def run_example(script_name: str) -> subprocess.CompletedProcess:
    """Хелпер для запуска скрипта-примера в отдельном процессе."""
    script_path = examples_dir / script_name
    if not script_path.exists():
        # Создаем временный пустой файл, чтобы тест мог его найти
        # Содержимое будет добавлено на следующем шаге.
        script_path.touch()

    # Запускаем скрипт с тем же интерпретатором Python, который использует pytest
    process = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    return process


def test_decorator_example_runs_and_logs():
    """
    Тест для примера с декоратором.
    
    Проверяет, что:
    1. Скрипт `07_decorators_example.py` запускается без ошибок.
    2. В стандартном выводе (который будет содержать логи) есть
       ключевые фразы от декоратора `log_function_details`.
    """
    # Этот скрипт еще не создан, но тест пишется для него.
    # На следующем шаге мы создадим сам скрипт.
    script_name = "07_decorators_example.py"

    # Предварительно создаем пустой файл, чтобы импорт не падал
    # (Хотя в данном случае мы запускаем его как отдельный процесс)
    example_file = examples_dir / script_name
    if not example_file.exists():
        example_file.write_text("# Этот файл будет заполнен на следующем шаге", encoding='utf-8')

    # Запускаем скрипт
    result = run_example(script_name)

    # Проверяем, что скрипт выполнился успешно
    assert result.returncode == 0, f"Скрипт {script_name} завершился с ошибкой: {result.stderr}"

    # Проверяем, что в выводе есть ожидаемые строки из лога
    # (мы настроим пример так, чтобы он логировал в stdout)
    output = result.stdout + result.stderr
    assert "Вызов функции" in output
    assert "завершилась за" in output
    assert "Возвращаемое значение" in output
