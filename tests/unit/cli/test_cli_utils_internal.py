from chutils.commands.utils import _import_string


def test_import_string_with_colon():
    """Проверяет импорт через двоеточие (module:class)."""
    # Импортируем сам _import_string для теста
    obj = _import_string("chutils.commands.utils:_import_string")
    assert obj == _import_string


def test_import_string_with_dot():
    """Проверяет импорт через точку (module.class)."""
    obj = _import_string("chutils.commands.utils._import_string")
    assert obj == _import_string


def test_import_string_invalid_module():
    """Проверяет поведение при несуществующем модуле."""
    obj = _import_string("non_existent_module:SomeClass")
    assert obj is None


def test_import_string_invalid_attribute():
    """Проверяет поведение при несуществующем атрибуте."""
    obj = _import_string("chutils.commands.utils:NonExistent")
    assert obj is None


def test_import_string_invalid_format():
    """Проверяет поведение при некорректном формате строки."""
    obj = _import_string("just_a_string")
    assert obj is None


def test_cli_runner_basic(cli_runner):
    """Проверяет базовую работоспособность cli_runner."""
    # Вызываем chutils без аргументов (должен показать help и выйти с 0)
    result = cli_runner.invoke([])
    assert result.exit_code == 0
    assert "chutils" in result.stdout
    assert "COMMAND" in result.stdout


def test_cli_runner_error(cli_runner):
    """Проверяет захват ошибок через cli_runner."""
    # Вызываем несуществующую команду
    result = cli_runner.invoke(["non-existent-command"])
    assert result.exit_code != 0
    # argparse обычно пишет ошибку в stderr
    assert "invalid choice" in result.stderr or "error" in result.stderr
