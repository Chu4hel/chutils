import json


def test_cli_show_paths_basic(cli_runner, project_with_marker):
    """Проверяет базовый вывод show-paths."""
    fs, project_root = project_with_marker
    result = cli_runner.invoke(["show-paths"])
    assert result.exit_code == 0
    # Приводим пути к единому формату для надежности
    assert str(project_root).replace('\\', '/') in result.stdout.replace('\\', '/')


def test_cli_show_paths_json(cli_runner, project_with_marker):
    """Проверяет вывод show-paths в JSON."""
    fs, project_root = project_with_marker
    result = cli_runner.invoke(["show-paths", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "base_dir" in data
    assert "main_config" in data
    assert "env_config" in data
    assert "local_config" in data


def test_cli_show_paths_not_found(cli_runner, monkeypatch, config_fs):
    """Проверяет вывод, когда корень не найден."""
    from chutils import config
    # Сбрасываем кэш путей и мокаем find_project_root
    config._cm._reset()
    monkeypatch.setattr("chutils.config.utils.find_project_root", lambda *args, **kwargs: None)

    result = cli_runner.invoke(["show-paths"])
    assert result.exit_code == 0
    assert "Не найден" in result.stdout


def test_cli_show_paths_rich(cli_runner, config_fs, mocker):
    """Проверяет вывод с использованием Rich."""
    fs, project_root = config_fs
    mocker.patch("chutils.env.is_rich_enabled", return_value=True)
    # Нам нужен реальный rich Console или FallbackConsole, который не падает на таблицах
    # В cli_utils FallbackConsole.print умеет обрабатывать Table

    result = cli_runner.invoke(["show-paths"])
    assert result.exit_code == 0
    assert "Диагностика путей конфигурации" in result.stdout or "Корень проекта" in result.stdout
