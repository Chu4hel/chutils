from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from chutils.diagnostics.manager import DiagnosticsManager
from chutils.diagnostics.web import get_fastapi_health_handler, get_flask_health_handler

if TYPE_CHECKING:
    from flask import Response


@pytest.mark.asyncio
async def test_diagnostics_manager_healthy() -> None:
    """Проверяет успешное выполнение всех проверок (HEALTHY)."""
    manager = DiagnosticsManager()

    @manager.register("check1", critical=True)
    def sync_check() -> bool:
        return True

    @manager.register("check2", critical=False)
    async def async_check() -> tuple[bool, str]:
        await asyncio.sleep(0.01)
        return True, "Все супер"

    report = await manager.run_checks()
    assert report.status == "HEALTHY"
    assert len(report.results) == 2
    assert report.results[0].name == "check1"
    assert report.results[0].success is True
    assert report.results[1].name == "check2"
    assert report.results[1].success is True
    assert report.results[1].message == "Все супер"


@pytest.mark.asyncio
async def test_diagnostics_manager_degraded() -> None:
    """Проверяет случай падения некритической проверки (DEGRADED)."""
    manager = DiagnosticsManager()

    @manager.register("critical_check", critical=True)
    def crit_check() -> bool:
        return True

    @manager.register("noncritical_check", critical=False)
    def noncrit_check() -> bool:
        return False

    report = await manager.run_checks()
    assert report.status == "DEGRADED"
    assert report.results[0].success is True
    assert report.results[1].success is False


@pytest.mark.asyncio
async def test_diagnostics_manager_unhealthy() -> None:
    """Проверяет случай падения критической проверки (UNHEALTHY)."""
    manager = DiagnosticsManager()

    @manager.register("critical_check", critical=True)
    def crit_check() -> bool:
        return False

    @manager.register("noncritical_check", critical=False)
    def noncrit_check() -> bool:
        return True

    report = await manager.run_checks()
    assert report.status == "UNHEALTHY"
    assert report.results[0].success is False
    assert report.results[1].success is True


@pytest.mark.asyncio
async def test_diagnostics_manager_timeout() -> None:
    """Проверяет корректное прерывание проверок по таймауту."""
    manager = DiagnosticsManager()

    @manager.register("slow_check", critical=True, timeout=0.05)
    async def slow_check() -> bool:
        await asyncio.sleep(0.5)
        return True

    report = await manager.run_checks()
    assert report.status == "UNHEALTHY"
    assert report.results[0].success is False
    assert "timed out after" in str(report.results[0].error)


def test_diagnostics_manager_sync() -> None:
    """Проверяет синхронный метод выполнения проверок."""
    manager = DiagnosticsManager()

    @manager.register("sync_check", critical=True)
    def sync_check() -> bool:
        return True

    report = manager.run_checks_sync()
    assert report.status == "HEALTHY"
    assert len(report.results) == 1
    assert report.results[0].success is True


@pytest.mark.asyncio
async def test_fastapi_helper() -> None:
    """Проверяет хелпер для интеграции с FastAPI."""
    manager = DiagnosticsManager()

    @manager.register("check", critical=True)
    def check() -> bool:
        return True

    handler = get_fastapi_health_handler(manager)
    response = await handler()

    assert response.status_code == 200
    # Проверяем содержимое
    import json
    body = json.loads(response.body.decode())
    assert body["status"] == "HEALTHY"

    # Теперь сделаем проверку падающей, чтобы вернуть 503
    manager_unhealthy = DiagnosticsManager()

    @manager_unhealthy.register("fail_check", critical=True)
    def fail_check() -> bool:
        return False

    handler_unhealthy = get_fastapi_health_handler(manager_unhealthy)
    response_unhealthy = await handler_unhealthy()
    assert response_unhealthy.status_code == 503


def test_flask_helper() -> None:
    """Проверяет хелпер для Flask с моканьем Flask-зависимостей."""
    import sys
    from unittest.mock import MagicMock

    # Создаем фейковый модуль flask в sys.modules
    mock_flask = MagicMock()
    mock_response_obj = MagicMock()
    mock_flask.jsonify = MagicMock(return_value="json_data")
    mock_flask.make_response = MagicMock(return_value=mock_response_obj)

    sys.modules["flask"] = mock_flask

    try:
        manager = DiagnosticsManager()

        @manager.register("check", critical=True)
        def check() -> bool:
            return True

        handler = get_flask_health_handler(manager)
        resp = handler()

        mock_flask.jsonify.assert_called_once()
        mock_flask.make_response.assert_called_once_with("json_data", 200)
        assert resp == mock_response_obj
    finally:
        # Очищаем sys.modules после теста
        if "flask" in sys.modules:
            del sys.modules["flask"]


def test_cli_diagnostics_command(mocker, capsys) -> None:
    """Проверяет запуск CLI-команды dev diagnostics."""
    import sys
    from chutils.cli import main
    test_args = ["chutils", "dev", "diagnostics"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "Общий статус здоровья системы" in captured.out
    assert "keyring" in captured.out
    assert "config" in captured.out


def test_cli_diagnostics_command_json(mocker, capsys) -> None:
    """Проверяет запуск CLI-команды dev diagnostics с флагом --json."""
    import sys
    import json
    from chutils.cli import main
    test_args = ["chutils", "dev", "diagnostics", "--json"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert "status" in data
    assert "results" in data


def test_models_without_pydantic(mocker) -> None:
    """Проверяет работоспособность dataclass-fallback моделей при отсутствии Pydantic."""
    import importlib
    import chutils.diagnostics.manager

    mocker.patch("chutils.env.has_pydantic", return_value=False)

    try:
        # Перезагружаем модули, чтобы зайти в else-блоки (без Pydantic)
        importlib.reload(chutils.diagnostics.models)
        importlib.reload(chutils.diagnostics.manager)

        from chutils.diagnostics.models import CheckResult, HealthReport
        from chutils.diagnostics.manager import DiagnosticsManager

        res = CheckResult(
            name="test",
            success=True,
            critical=False,
            execution_time=0.1,
            message="ok"
        )
        dump = res.model_dump()
        assert dump["name"] == "test"
        assert dump["success"] is True

        report = HealthReport(
            status="HEALTHY",
            results=[res],
            total_time=0.1
        )
        report_dump = report.model_dump()
        assert report_dump["status"] == "HEALTHY"
        assert len(report_dump["results"]) == 1

        # Проверим, что DiagnosticsManager работает корректно с dataclass-моделями
        manager = DiagnosticsManager()

        @manager.register("check", critical=True)
        def sync_check() -> bool:
            return True

        rep = manager.run_checks_sync()
        assert rep.status == "HEALTHY"
        assert len(rep.results) == 1

    finally:
        # Восстанавливаем pydantic обратно и перезагружаем
        mocker.patch("chutils.env.has_pydantic", return_value=True)
        importlib.reload(chutils.diagnostics.models)
        importlib.reload(chutils.diagnostics.manager)


def test_diagnostics_init_lazy_getattr() -> None:
    """Проверяет ленивый импорт __getattr__ в пакете diagnostics."""
    import chutils.diagnostics as diag

    # Должен корректно импортировать через getattr
    assert diag.DiagnosticsManager is not None
    assert diag.get_fastapi_health_handler is not None
    assert diag.get_flask_health_handler is not None

    with pytest.raises(AttributeError):
        _ = diag.non_existent_attribute


@pytest.mark.asyncio
async def test_diagnostics_edge_cases(mocker) -> None:
    """Проверяет краевые случаи выполнения проверок."""
    manager = DiagnosticsManager()

    # 1. Запуск без проверок
    report_empty = await manager.run_checks()
    assert report_empty.status == "HEALTHY"
    assert len(report_empty.results) == 0

    # 2. Проверка, возвращающая кортеж не длины 2
    @manager.register("bad_tuple")
    def bad_tuple_check() -> tuple[bool, ...]:
        return (True, "msg", "extra")

    # 3. Проверка, возвращающая строку
    @manager.register("string_res")
    def string_check() -> str:
        return "Работает отлично"

    # 4. Проверка, возвращающая None
    @manager.register("none_res")
    def none_check() -> None:
        return None

    report = await manager.run_checks()
    assert len(report.results) == 3
    assert report.results[0].success is True
    assert report.results[1].success is True
    assert report.results[1].message == "Работает отлично"
    assert report.results[2].success is True
    assert report.results[2].message == "Проверка завершена успешно"


def test_built_in_check_config_failure(mocker) -> None:
    """Проверяет встроенную проверку конфигурации при ошибках."""
    from chutils.diagnostics.manager import check_config

    # Кейс 1: путь к файлу указан, но файла нет на диске
    mocker.patch("chutils.get_config_file_path", return_value="non_existent_file.yml")
    mocker.patch("os.path.exists", return_value=False)
    success, msg = check_config()
    assert success is False
    assert "не найден на диске" in msg

    # Кейс 2: ошибка парсинга/загрузки
    mocker.patch("chutils.get_config_file_path", return_value="bad_config.yml")
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("chutils.get_config", side_effect=ValueError("Syntax Error"))
    success, msg = check_config()
    assert success is False
    assert "Ошибка парсинга/загрузки" in msg


def test_built_in_check_keyring_failures(mocker) -> None:
    """Проверяет встроенную проверку keyring при ошибках доступа."""
    from chutils.diagnostics.manager import check_keyring
    from keyring.errors import NoKeyringError

    mocker.patch("chutils.secret_manager.providers.KEYRING_AVAILABLE", True)
    import keyring

    # Кейс 1: NoKeyringError
    mocker.patch.object(keyring, "set_password", side_effect=NoKeyringError("No keyring"))
    success, msg = check_keyring()
    assert success is False
    assert "Системное хранилище секретов недоступно" in msg

    # Кейс 2: Любая другая ошибка
    mocker.patch.object(keyring, "set_password", side_effect=RuntimeError("Keyring locked"))
    success, msg = check_keyring()
    assert success is False
    assert "Ошибка при обращении к keyring" in msg


def test_web_helpers_import_errors(mocker) -> None:
    """Проверяет генерацию RuntimeError при отсутствии веб-библиотек."""
    manager = DiagnosticsManager()

    # FastAPI ImportError
    mocker.patch("builtins.__import__", side_effect=ImportError("No module named fastapi"))
    with pytest.raises(RuntimeError) as exc:
        get_fastapi_health_handler(manager)
    assert "FastAPI не установлен" in str(exc.value)

    # Flask ImportError
    with pytest.raises(RuntimeError) as exc:
        get_flask_health_handler(manager)
    assert "Flask не установлен" in str(exc.value)
