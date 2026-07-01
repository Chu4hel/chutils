import json
from pathlib import Path

import pytest

from chutils.exceptions import PathTraversalError
from chutils.fs import ensure_dir, atomic_write, resolve_safe_path, remove_path, cleanup_paths


def test_resolve_safe_path_valid(tmp_path):
    """Проверка корректного разрешения пути."""
    base = tmp_path / "app"
    base.mkdir()

    target = "data/config.json"
    result = resolve_safe_path(target, base)

    assert result.is_absolute()
    assert str(result).endswith(Path(target).as_posix() if "/" in str(result) else str(Path(target)))
    assert str(base) in str(result)


def test_resolve_safe_path_traversal(tmp_path):
    """Проверка защиты от Path Traversal."""
    base = tmp_path / "app"
    base.mkdir()

    # Попытка выйти вверх
    target = "../../etc/passwd"

    with pytest.raises(PathTraversalError) as excinfo:
        resolve_safe_path(target, base)

    assert "Обнаружена попытка выхода" in str(excinfo.value)
    assert excinfo.value.context["attempted_path"] == target
    assert excinfo.value.context["base_path"] == str(base)


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


def test_get_temp_file(tmp_path):
    """Проверка контекстного менеджера временных файлов."""
    from chutils.fs import get_temp_file

    with get_temp_file(suffix=".test") as temp_path:
        assert isinstance(temp_path, Path)
        assert temp_path.exists()
        assert temp_path.suffix == ".test"

        # Проверяем запись
        temp_path.write_text("temp data")
        assert temp_path.read_text() == "temp data"

    # После выхода из блока файл должен быть удален
    assert not temp_path.exists()


def test_get_temp_file_exception(tmp_path):
    """Проверка удаления временного файла при исключении."""
    from chutils.fs import get_temp_file

    try:
        with get_temp_file() as temp_path:
            assert temp_path.exists()
            raise RuntimeError("Test error")
    except RuntimeError:
        pass

    assert not temp_path.exists()


def test_remove_path_success(tmp_path):
    """Проверка успешного удаления файла и папки."""
    # Файл
    f = tmp_path / "test.txt"
    f.write_text("data")
    assert f.exists()
    assert remove_path(f) is True
    assert not f.exists()

    # Папка
    d = tmp_path / "test_dir"
    d.mkdir()
    (d / "sub.txt").write_text("sub")
    assert d.exists()
    assert remove_path(d) is True
    assert not d.exists()

    # Несуществующий путь
    assert remove_path(tmp_path / "nonexistent") is True


def test_remove_path_retries(tmp_path, monkeypatch):
    """Проверка повторных попыток удаления при OSError."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    call_count = 0
    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    success = remove_path(f, retries=3, delay=0.01)
    assert success is True
    assert not f.exists()
    assert call_count == 3


def test_remove_path_dir_retries(tmp_path, monkeypatch):
    """Проверка повторных попыток удаления директории при OSError."""
    d = tmp_path / "test_dir"
    d.mkdir()

    call_count = 0
    import shutil
    original_rmtree = shutil.rmtree

    def mock_rmtree(path, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OSError("Locked")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", mock_rmtree)

    success = remove_path(d, retries=3, delay=0.01)
    assert success is True
    assert not d.exists()
    assert call_count == 3


def test_remove_path_on_locked_raise(tmp_path, monkeypatch):
    """Проверка on_locked='raise'."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "test.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    with pytest.raises(OSError, match="Locked"):
        remove_path(f, retries=2, delay=0.01, on_locked="raise")


def test_remove_path_on_locked_warn(tmp_path, monkeypatch):
    """Проверка on_locked='warn'."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "test.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    success = remove_path(f, retries=2, delay=0.01, on_locked="warn")
    assert success is False
    assert f.exists()


def test_remove_path_on_locked_rename_orphan(tmp_path, monkeypatch):
    """Проверка on_locked='rename_orphan'."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "test.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    success = remove_path(f, retries=2, delay=0.01, on_locked="rename_orphan")
    assert success is True
    assert not f.exists()

    orphan_path = tmp_path / "test.txt.orphan"
    assert orphan_path.exists()
    assert orphan_path.read_text() == "data"


def test_orphan_collision_raise(tmp_path, monkeypatch):
    """Проверка orphan_collision='raise'."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    orphan = tmp_path / "test.txt.orphan"
    orphan.write_text("existing_orphan")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "test.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    with pytest.raises(FileExistsError, match="Орфан-путь уже существует"):
        remove_path(
            f, retries=1, delay=0.01, on_locked="rename_orphan", orphan_collision="raise"
        )


def test_orphan_collision_overwrite(tmp_path, monkeypatch):
    """Проверка orphan_collision='overwrite'."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    orphan = tmp_path / "test.txt.orphan"
    orphan.write_text("existing_orphan")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "test.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    success = remove_path(
        f, retries=1, delay=0.01, on_locked="rename_orphan", orphan_collision="overwrite"
    )
    assert success is True
    assert not f.exists()
    assert orphan.read_text() == "data"


def test_orphan_collision_unique(tmp_path, monkeypatch):
    """Проверка orphan_collision='unique'."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    orphan = tmp_path / "test.txt.orphan"
    orphan.write_text("existing_orphan")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "test.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    success = remove_path(
        f, retries=1, delay=0.01, on_locked="rename_orphan", orphan_collision="unique"
    )
    assert success is True
    assert not f.exists()
    assert orphan.read_text() == "existing_orphan"

    orphans = list(tmp_path.glob("test.txt.orphan_*"))
    assert len(orphans) == 1
    assert orphans[0].read_text() == "data"


def test_cleanup_paths_success(tmp_path):
    """Проверка пакетного удаления."""
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("1")
    f2.write_text("2")

    cleanup_paths(f1, f2)
    assert not f1.exists()
    assert not f2.exists()


def test_cleanup_paths_fault_tolerance(tmp_path, monkeypatch):
    """Проверка отказоустойчивости cleanup_paths."""
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("1")
    f2.write_text("2")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "f1.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    cleanup_paths(f1, f2, retries=1, delay=0.01, on_locked="warn")
    assert f1.exists()
    assert not f2.exists()


def test_cleanup_paths_fast_fail(tmp_path, monkeypatch):
    """Проверка быстрого сбоя cleanup_paths."""
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("1")
    f2.write_text("2")

    original_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self.name == "f1.txt":
            raise OSError("Locked")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    with pytest.raises(OSError, match="Locked"):
        cleanup_paths(f1, f2, retries=1, delay=0.01, on_locked="raise")

    assert f1.exists()
    assert f2.exists()


def test_orphan_collision_overwrite_fails_gracefully(tmp_path, monkeypatch):
    """Проверка, что если при orphan_collision='overwrite' удаление старого орфана падает, код выполняется."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    orphan = tmp_path / "test.txt.orphan"
    orphan.write_text("existing_orphan")

    def mock_unlink(self, *args, **kwargs):
        raise OSError("Locked")

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    # Замокаем rename, чтобы на Windows не падало из-за наличия орфана
    monkeypatch.setattr(Path, "rename", lambda self, target: None)

    success = remove_path(
        f, retries=1, delay=0.01, on_locked="rename_orphan", orphan_collision="overwrite"
    )
    assert success is True


def test_remove_path_invalid_on_locked(tmp_path, monkeypatch):
    """Проверка ValueError при невалидном значении on_locked."""
    f = tmp_path / "test.txt"
    f.write_text("data")

    def mock_unlink(self, *args, **kwargs):
        raise OSError("Locked")

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    with pytest.raises(ValueError, match="Неизвестное значение on_locked"):
        remove_path(f, retries=1, delay=0.01, on_locked="invalid_action")  # type: ignore


