import json
from unittest.mock import patch, MagicMock

import pytest
from chutils.config.schema import export_schema, import_model_class, PYDANTIC_AVAILABLE
from pydantic import BaseModel, Field


class SampleConfigModel(BaseModel):
    """Тестовая модель для генерации схемы."""
    name: str = Field(description="Test name")
    value: int = 42


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_import_model_class():
    """Тест импорта класса по строковому пути."""
    with patch("importlib.import_module") as mock_import:
        mock_module = MagicMock()
        setattr(mock_module, "SampleConfigModel", SampleConfigModel)
        mock_import.return_value = mock_module

        cls = import_model_class("some.module:SampleConfigModel")
        assert cls == SampleConfigModel
        mock_import.assert_called_once_with("some.module")


def test_import_model_class_invalid_format():
    """Тест ошибки формата пути."""
    with pytest.raises(ValueError, match="Некорректный формат пути"):
        import_model_class("invalid_path")


def test_import_model_class_not_found():
    """Тест ошибки отсутствия модуля или класса."""
    with patch("importlib.import_module") as mock_import:
        mock_import.side_effect = ImportError("Module not found")
        with pytest.raises(ImportError, match="Не удалось импортировать модуль"):
            import_model_class("non_existent_module:Model")

    with patch("importlib.import_module") as mock_import:
        mock_module = MagicMock()
        del mock_module.NonExistentModel
        mock_import.return_value = mock_module
        with pytest.raises(ImportError, match="не найден в модуле"):
            import_model_class("some.module:NonExistentModel")


def test_import_model_class_type_error():
    """Тест ошибки типа (не BaseModel)."""

    class NotABaseModel:
        pass

    with patch("importlib.import_module") as mock_import:
        mock_module = MagicMock()
        setattr(mock_module, "NotABaseModel", NotABaseModel)
        mock_import.return_value = mock_module
        with pytest.raises(TypeError, match="не является подклассом"):
            import_model_class("some.module:NotABaseModel")


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_export_schema_basic():
    """Тест базовой генерации схемы."""
    schema_str = export_schema(SampleConfigModel)
    schema = json.loads(schema_str)

    assert "$schema" in schema
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == "SampleConfigModel"
    assert "name" in schema["properties"]
    assert schema["properties"]["name"]["description"] == "Test name"


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_export_schema_with_string_path():
    """Тест генерации схемы при передаче пути строкой."""
    with patch("chutils.config.schema.import_model_class") as mock_import:
        mock_import.return_value = SampleConfigModel
        schema_str = export_schema("some.module:SampleConfigModel")
        schema = json.loads(schema_str)
        assert schema["title"] == "SampleConfigModel"
        mock_import.assert_called_once_with("some.module:SampleConfigModel")


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_export_schema_to_file(tmp_path):
    """Тест сохранения схемы в файл."""
    output_file = tmp_path / "subdir" / "myschema.json"
    export_schema(SampleConfigModel, output_path=output_file)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    schema = json.loads(content)
    assert "$schema" in schema
    assert schema["title"] == "SampleConfigModel"
