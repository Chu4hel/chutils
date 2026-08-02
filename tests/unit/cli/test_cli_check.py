"""
Тесты для сводной команды chutils check / chutils doctor.
"""


def test_cli_check_all_success(cli_runner, config_fs, mocker):
    """Проверяет запуск комплексной проверки проекта (chutils check)."""
    fs, project_root = config_fs
    mocker.patch("chutils.diagnostics.manager.default_manager.run_checks_sync", return_value=mocker.MagicMock(
        status=mocker.MagicMock(value="HEALTHY"),
        total_duration_sec=0.1,
        summary={"passed": 5, "total": 5}
    ))
    mocker.patch("chutils.commands.utils._import_string", return_value=mocker.MagicMock)
    mocker.patch("chutils.config.get_config", return_value={})
    mocker.patch("chutils.dev.ai_lint.LinterEngine.collect_files", return_value=[])
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[])

    result = cli_runner.invoke(["check"])
    assert result.exit_code == 0
    assert "Комплексная проверка проекта" in result.stdout
    assert "Системный Health Check" in result.stdout
    assert "HEALTHY" in result.stdout
    assert "Все проверенные компоненты проекта в порядке" in result.stdout


def test_cli_doctor_alias(cli_runner, config_fs, mocker):
    """Проверяет вызов псевдонима chutils doctor."""
    mocker.patch("chutils.diagnostics.manager.default_manager.run_checks_sync", return_value=mocker.MagicMock(
        status=mocker.MagicMock(value="HEALTHY"),
        total_duration_sec=0.1,
        summary={"passed": 5, "total": 5}
    ))
    mocker.patch("chutils.commands.utils._import_string", return_value=None)
    mocker.patch("chutils.dev.ai_lint.LinterEngine.collect_files", return_value=[])
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[])

    result = cli_runner.invoke(["doctor"])
    assert result.exit_code == 0
    assert "Комплексная проверка проекта" in result.stdout


def test_cli_check_json(cli_runner, config_fs, mocker):
    """Проверяет вывод отчета в формате JSON."""
    mock_report = mocker.MagicMock()
    mock_report.status = "HEALTHY"
    mock_report.total_duration = 0.1
    mock_report.passed_checks = 5
    mock_report.total_checks = 5
    mock_report.checks = []

    mocker.patch("chutils.diagnostics.manager.default_manager.run_checks_sync", return_value=mock_report)
    mocker.patch("chutils.commands.utils._import_string", return_value=None)
    mocker.patch("chutils.dev.ai_lint.LinterEngine.collect_files", return_value=[])
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[])

    result = cli_runner.invoke(["check", "--json"])
    assert result.exit_code == 0
    assert '"status": "HEALTHY"' in result.stdout
    assert '"checks"' in result.stdout
