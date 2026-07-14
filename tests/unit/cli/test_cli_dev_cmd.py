import json


def test_cli_dev_no_subcommand(cli_runner):
    """Проверяет вызов без подкоманды."""
    result = cli_runner.invoke(["dev"])
    assert result.exit_code == 0
    assert "Используйте 'chutils dev --help'" in result.stdout


def test_cli_dev_generate_context_markdown(cli_runner):
    """Проверяет генерацию Markdown контекста."""
    result = cli_runner.invoke(["dev", "generate-context"])
    assert result.exit_code == 0
    assert "# Public API Map" in result.stdout
    assert "Name" in result.stdout
    assert "Type" in result.stdout
    assert "Signature" in result.stdout
    assert "Description" in result.stdout


def test_cli_dev_generate_context_json(cli_runner):
    """Проверяет генерацию JSON контекста."""
    result = cli_runner.invoke(["dev", "generate-context", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "name" in data[0]


def test_cli_dev_generate_context_file(cli_runner, config_fs):
    """Проверяет сохранение контекста в файл."""
    fs, project_root = config_fs
    result = cli_runner.invoke(["dev", "generate-context", "-o", "api.md"])
    assert result.exit_code == 0
    assert "Контекст успешно сохранен" in result.stdout
    assert fs.exists("api.md")


def test_cli_dev_generate_tree_success(cli_runner, mocker, config_fs):
    """Проверяет генерацию иерархического индекса (tree)."""
    fs, project_root = config_fs
    mocker.patch("chutils.env.has_pydantic", return_value=True)

    mock_index = mocker.MagicMock()
    mock_index.model_dump_json.return_value = '{"nodes": []}'
    mock_indexer = mocker.patch("chutils.dev.ast_indexer.Indexer")
    mock_indexer.return_value.index.return_value = mock_index

    result = cli_runner.invoke(["dev", "generate-context", "--tree"])
    assert result.exit_code == 0
    assert '{"nodes": []}' in result.stdout


def test_cli_dev_generate_tree_no_pydantic(cli_runner, mocker):
    """Проверяет ошибку при отсутствии Pydantic для tree."""
    mocker.patch("chutils.env.has_pydantic", return_value=False)

    result = cli_runner.invoke(["dev", "generate-context", "--tree"])
    assert result.exit_code == 1
    assert (
            "Pydantic is required" in result.stderr
            or "Pydantic is required" in result.stdout
    )


def test_cli_dev_generate_tree_error(cli_runner, mocker):
    """Проверяет обработку ошибок при генерации tree."""
    mocker.patch("chutils.env.has_pydantic", return_value=True)
    mocker.patch("chutils.dev.ast_indexer.Indexer", side_effect=Exception("AST error"))

    result = cli_runner.invoke(["dev", "generate-context", "--tree"])
    assert result.exit_code == 1
    assert (
            "Ошибка при генерации индекса" in result.stderr
            or "Ошибка при генерации индекса" in result.stdout
    )


def test_cli_dev_ai_lint_success(cli_runner, mocker):
    """Проверяет успешное прохождение проверки ai-lint через CLI."""
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[])
    result = cli_runner.invoke(["dev", "ai-lint"])
    assert result.exit_code == 0
    assert "Все проверки пройдены" in result.stdout


def test_cli_dev_ai_lint_failure(cli_runner, mocker):
    """Проверяет провал проверки ai-lint (наличие ошибок) через CLI."""
    from chutils.dev.ai_lint import LintResult

    mock_error = LintResult(
        rule_name="TestRule",
        message="Critical error detected",
        severity="error",
        file_path="app.py",
        line_number=5,
    )
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[mock_error])
    result = cli_runner.invoke(["dev", "ai-lint"])
    assert result.exit_code == 1
    assert "Critical error detected" in result.stdout


def test_cli_dev_ai_lint_soft_mode(cli_runner, mocker):
    """Проверяет --soft-mode флаг, который не должен возвращать ошибку при провале."""
    from chutils.dev.ai_lint import LintResult

    mock_error = LintResult(
        rule_name="TestRule",
        message="Critical error detected",
        severity="error",
        file_path="app.py",
    )
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[mock_error])
    result = cli_runner.invoke(["dev", "ai-lint", "--soft-mode"])
    assert result.exit_code == 0
    assert "Critical error detected" in result.stdout


def test_cli_dev_ai_lint_strict_mode(cli_runner, mocker):
    """Проверяет --strict флаг, который падает при наличии только варнингов."""
    from chutils.dev.ai_lint import LintResult

    mock_warn = LintResult(
        rule_name="TestRule",
        message="Warning detected",
        severity="warn",
        file_path="app.py",
    )
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[mock_warn])

    # Сначала без strict - должен пройти успешно
    res_normal = cli_runner.invoke(["dev", "ai-lint"])
    assert res_normal.exit_code == 0

    # Со strict - должен упасть
    res_strict = cli_runner.invoke(["dev", "ai-lint", "--strict"])
    assert res_strict.exit_code == 1
    assert "Warning detected" in res_strict.stdout


def test_cli_dev_generate_context_project(cli_runner, config_fs):
    """Проверяет генерацию Markdown API карты для внешнего проекта."""
    fs, project_root = config_fs
    project_dir = "/home/user/my_project"
    fs.create_dir(f"{project_dir}/src")
    fs.create_file(
        f"{project_dir}/src/app.py",
        contents="""
def my_cool_function(x):
    \"\"\"Документация функции.\"\"\"
    return x
""",
    )

    result = cli_runner.invoke(["dev", "generate-context", "--project", project_dir])
    assert result.exit_code == 0
    assert "# Public API Map: my_project" in result.stdout
    assert "src.app.my_cool_function" in result.stdout


def test_cli_dev_generate_context_project_ignore(cli_runner, config_fs):
    """Проверяет, что .gitignore и .chutilsignore корректно исключают файлы."""
    fs, project_root = config_fs
    project_dir = "/home/user/my_project"
    fs.create_dir(f"{project_dir}/src")
    fs.create_file(f"{project_dir}/src/app.py", contents="def my_func(): pass")
    fs.create_file(
        f"{project_dir}/src/ignored_file.py", contents="def ignored_func(): pass"
    )
    fs.create_file(
        f"{project_dir}/src/chutils_ignored.py",
        contents="def chutils_ignored_func(): pass",
    )

    fs.create_file(f"{project_dir}/.gitignore", contents="ignored_file.py\n")
    fs.create_file(f"{project_dir}/.chutilsignore", contents="chutils_ignored.py\n")

    result = cli_runner.invoke(["dev", "generate-context", "--project", project_dir])
    assert result.exit_code == 0
    assert "src.app.my_func" in result.stdout
    assert "ignored_file" not in result.stdout
    assert "chutils_ignored" not in result.stdout


def test_cli_dev_chat_context_stdout(cli_runner, mocker):
    """Проверяет запуск dev chat-context с выводом в stdout."""
    mocker.patch(
        "chutils.dev.chat_context.collect_context_slice",
        return_value="# Mocked Context Slice Output",
    )

    result = cli_runner.invoke(
        [
            "dev",
            "chat-context",
            "-m",
            "logger,config",
            "-t",
            "test task",
            "-l",
            "internal",
        ]
    )
    assert result.exit_code == 0
    assert "# Mocked Context Slice Output" in result.stdout


def test_cli_dev_chat_context_file(cli_runner, mocker, config_fs):
    """Проверяет запуск dev chat-context с записью в файл."""
    fs, project_root = config_fs
    mocker.patch(
        "chutils.dev.chat_context.collect_context_slice",
        return_value="# Mocked Context Slice Output",
    )

    result = cli_runner.invoke(
        ["dev", "chat-context", "-m", "logger", "-o", "my_context.md"]
    )
    assert result.exit_code == 0
    assert "Контекстный срез успешно сохранен в: my_context.md" in result.stdout
    assert fs.exists("my_context.md")
    from pathlib import Path
    assert Path("my_context.md").read_text(encoding="utf-8") == "# Mocked Context Slice Output"


def test_cli_dev_chat_context_interactive(cli_runner, mocker):
    """Проверяет интерактивный режим dev chat-context."""
    mocker.patch(
        "chutils.dev.chat_context.run_interactive_menu",
        return_value=["logger"],
    )
    mocker.patch(
        "chutils.dev.chat_context.collect_context_slice",
        return_value="# Interactive Context Output",
    )

    result = cli_runner.invoke(["dev", "chat-context"])
    assert result.exit_code == 0
    assert "# Interactive Context Output" in result.stdout


def test_cli_dev_scaffold_success(cli_runner, config_fs):
    """Проверяет успешное создание структуры слоев Чистой Архитектуры."""
    fs, project_root = config_fs
    result = cli_runner.invoke(["dev", "scaffold", "new_test_module", "-o", f"{project_root}/new_test_module"])
    assert result.exit_code == 0
    assert "успешно инициализирован" in result.stdout or "успешно инициализирован" in result.stderr

    # Проверяем файлы в мокнутой ФС
    assert fs.exists(f"{project_root}/new_test_module/__init__.py")
    assert fs.exists(f"{project_root}/new_test_module/container.py")
    assert fs.exists(f"{project_root}/new_test_module/domain/entities.py")
    assert fs.exists(f"{project_root}/new_test_module/application/use_cases.py")
    assert fs.exists(f"{project_root}/new_test_module/infrastructure/repositories.py")
    assert fs.exists(f"{project_root}/new_test_module/presentation/cli.py")


def test_cli_dev_scaffold_invalid_name(cli_runner):
    """Проверяет ошибку при попытке использовать невалидное имя модуля."""
    result = cli_runner.invoke(["dev", "scaffold", "invalid-name"])
    assert result.exit_code == 1
    assert "Некорректное имя модуля" in result.stdout or "Некорректное имя модуля" in result.stderr


def test_cli_dev_scaffold_already_exists_error(cli_runner, config_fs):
    """Проверяет возникновение ошибки, если каталог уже существует и не пуст."""
    fs, project_root = config_fs
    module_path = f"{project_root}/existing_module"
    fs.create_dir(module_path)
    fs.create_file(f"{module_path}/dummy.txt", contents="content")

    result = cli_runner.invoke(["dev", "scaffold", "existing_module", "-o", module_path])
    assert result.exit_code == 1
    assert "уже существует и не пуста" in result.stdout or "уже существует и не пуста" in result.stderr


def test_cli_dev_scaffold_force_overwrite(cli_runner, config_fs):
    """Проверяет успешность генерации при существующем каталоге, если передан флаг --force."""
    fs, project_root = config_fs
    module_path = f"{project_root}/existing_module"
    fs.create_dir(module_path)
    fs.create_file(f"{module_path}/dummy.txt", contents="content")

    result = cli_runner.invoke(["dev", "scaffold", "existing_module", "-o", module_path, "-f"])
    assert result.exit_code == 0
    assert "успешно инициализирован" in result.stdout or "успешно инициализирован" in result.stderr
    assert fs.exists(f"{module_path}/__init__.py")


def test_cli_dev_mock_init_success(cli_runner, config_fs):
    """Проверяет успешное создание шаблона роутов через CLI."""
    fs, project_root = config_fs
    mocks_path = f"{project_root}/mocks.yml"

    result = cli_runner.invoke(["dev", "mock", "init", "-o", mocks_path])
    assert result.exit_code == 0
    assert "Шаблон конфигурации успешно сохранен" in result.stdout or "Шаблон конфигурации успешно сохранен" in result.stderr
    assert fs.exists(mocks_path)


def test_cli_dev_mock_run_mocked(cli_runner, mocker):
    """Проверяет вызов запуска сервера через CLI с моком метода run."""
    mock_run = mocker.patch("chutils.dev.mock_server.MockServerRunner.run")

    result = cli_runner.invoke(["dev", "mock", "-p", "9999", "-r", "custom_mocks.yml"])
    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_cli_dev_sync_env_success_synchronized(cli_runner, config_fs):
    """Проверяет вызов sync-env, когда файлы полностью синхронизированы."""
    fs, project_root = config_fs
    fs.create_file(f"{project_root}/.env", contents="A=1\n")
    fs.create_file(f"{project_root}/.env.example", contents="A=\n")

    result = cli_runner.invoke(
        ["dev", "sync-env", "--env-path", f"{project_root}/.env", "--example-path", f"{project_root}/.env.example"])
    assert result.exit_code == 0
    assert "Файлы полностью синхронизированы" in result.stdout


def test_cli_dev_sync_env_dry_run(cli_runner, config_fs):
    """Проверяет dry-run режим sync-env."""
    from chutils.cli_utils import set_console_width
    from pathlib import Path

    set_console_width(80)
    try:
        fs, project_root = config_fs
        fs.create_file(f"{project_root}/.env", contents="A=1\nB=2\n")
        fs.create_file(f"{project_root}/.env.example", contents="A=\n")

        result = cli_runner.invoke([
            "dev", "sync-env",
            "--env-path", f"{project_root}/.env",
            "--example-path", f"{project_root}/.env.example",
            "--dry-run"
        ])
        assert result.exit_code == 0
        assert "Dry-run режим. Изменения не внесены" in result.stdout
        assert "Обнаруженные расхождения в переменных окружения" in result.stdout
        # Файлы не должны измениться
        assert Path(f"{project_root}/.env.example").read_text(encoding="utf-8") == "A=\n"
    finally:
        set_console_width(None)


def test_cli_dev_sync_env_force(cli_runner, config_fs):
    """Проверяет принудительную синхронизацию с флагом --yes."""
    from chutils.cli_utils import set_console_width
    from pathlib import Path

    set_console_width(80)
    try:
        fs, project_root = config_fs
        fs.create_file(f"{project_root}/.env", contents="A=1\nB=2\n")
        fs.create_file(f"{project_root}/.env.example", contents="A=\nC=3\n")

        result = cli_runner.invoke([
            "dev", "sync-env",
            "--env-path", f"{project_root}/.env",
            "--example-path", f"{project_root}/.env.example",
            "--yes"
        ])
        assert result.exit_code == 0
        assert "успешно обновлен" in result.stdout

        # Проверяем, что B перенеслось в .env.example
        example_content = Path(f"{project_root}/.env.example").read_text(encoding="utf-8")
        assert "B=" in example_content
        # Проверяем, что C перенеслось в .env с дефолтным значением 3
        env_content = Path(f"{project_root}/.env").read_text(encoding="utf-8")
        assert "C=3" in env_content
    finally:
        set_console_width(None)
