import sys
from pathlib import Path

from chutils.cli_booster import cli_command


@cli_command
def test_func(name: str, age: int, is_admin: bool = False, tags: list[str] = None, home: Path = None):
    """
    Тестовая функция для CLI Booster.
    """
    print(f"Name: {name} (type: {type(name)})")
    print(f"Age: {age} (type: {type(age)})")
    print(f"Admin: {is_admin} (type: {type(is_admin)})")
    print(f"Tags: {tags} (type: {type(tags)})")
    print(f"Home: {home} (type: {type(home)})")


if __name__ == "__main__":
    # Симулируем вызов CLI
    # Ожидаем: Name: Alice, Age: 30, Admin: True, Tags: ['dev', 'test'], Home: /tmp
    sys.argv = ["test_script.py", "Alice", "30", "--is-admin", "--tags", "dev", "test", "--home", "/tmp"]
    test_func()
