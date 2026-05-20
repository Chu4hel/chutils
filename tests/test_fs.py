import json
from pathlib import Path

import pytest

from chutils.fs import ensure_dir, atomic_write


def test_ensure_dir_str(tmp_path):
    """Проверка создания директории из строки."""
    target = tmp_path / "test_dir_str"
    assert not target.exists()

    result = ensure_dir(str(target))

    assert target.exists()
    assert target.is_dir()
    assert isinstance(result, Path)
    assert result == target


def test_ensure_dir_path(tmp_path):
    """Проверка создания директории из объекта Path."""
    target = tmp_path / "test_dir_path"
    assert not target.exists()

    result = ensure_dir(target)

    assert target.exists()
    assert target.is_dir()
    assert result == target


def test_ensure_dir_nested(tmp_path):
    """Проверка создания вложенных директорий."""
    target = tmp_path / "a" / "b" / "c"
    assert not target.exists()

    result = ensure_dir(target)

    assert target.exists()
    assert target.is_dir()
    assert result == target


def test_ensure_dir_exists(tmp_path):
    """Проверка идемпотентности (директория уже существует)."""
    target = tmp_path / "existing_dir"
    target.mkdir()
    assert target.exists()

    result = ensure_dir(target)

    assert target.exists()
    assert target.is_dir()
    assert result == target


def test_atomic_write_text(tmp_path):
    """Проверка атомарной записи текста."""
    target = tmp_path / "test.txt"
    data = "Hello, World!"

    atomic_write(target, data)

    assert target.exists()
    assert target.read_text(encoding='utf-8') == data


def test_atomic_write_bytes(tmp_path):
    """Проверка атомарной записи байт."""
    target = tmp_path / "test.bin"
    data = b"\x00\x01\x02\x03"

    atomic_write(target, data, mode='wb')

    assert target.exists()
    assert target.read_bytes() == data


def test_atomic_write_json(tmp_path):
    """Проверка авто-сериализации JSON."""
    target = tmp_path / "test.json"
    data = {"key": "value", "list": [1, 2, 3]}

    atomic_write(target, data)

    assert target.exists()
    assert json.loads(target.read_text(encoding='utf-8')) == data


def test_atomic_write_yaml(tmp_path):
    """Проверка авто-сериализации YAML."""
    target = tmp_path / "test.yaml"
    data = {"key": "value", "nested": {"a": 1}}

    atomic_write(target, data)

    assert target.exists()
    import yaml
    assert yaml.safe_load(target.read_text(encoding='utf-8')) == data


def test_atomic_write_failure(tmp_path, monkeypatch):
    """Проверка устойчивости к ошибкам."""
    target = tmp_path / "fail.json"

    # Мокаем json.dump так, чтобы он кидал ошибку
    def mock_dump(*args, **kwargs):
        raise IOError("Simulated write failure")

    with pytest.raises(IOError, match="Simulated write failure"):
        monkeypatch.setattr("json.dump", mock_dump)
        atomic_write(target, {"a": 1})

    # Проверяем, что целевой файл не создался (или не изменился, если бы существовал)
    assert not target.exists()

    # Проверяем, что в директории нет временных файлов .tmp
    temp_files = list(tmp_path.glob("*.tmp"))
    assert len(temp_files) == 0
