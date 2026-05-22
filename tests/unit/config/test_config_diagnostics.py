import json

from chutils.config.diagnostics import mask_value, format_trace


def test_mask_value():
    """Проверяет маскирование секретов."""
    assert mask_value("password", "12345") == "[MASKED]"
    assert mask_value("db_password", "12345") == "[MASKED]"
    assert mask_value("api_key", "secret") == "[MASKED]"
    assert mask_value("user_name", "admin") == "admin"
    assert mask_value("password", "12345", show_secrets=True) == "12345"


def test_format_json_masking():
    """Проверяет маскирование в формате JSON."""
    trace_data = {
        "auth": {
            "password": [{"source": "config.yml", "value": "secret"}]
        },
        "app": {
            "name": [{"source": "config.yml", "value": "myapp"}]
        }
    }

    # С маскированием (по умолчанию)
    json_output = format_trace(trace_data, format_type='json')
    parsed = json.loads(json_output)
    assert parsed["auth"]["password"][0]["value"] == "[MASKED]"
    assert parsed["app"]["name"][0]["value"] == "myapp"

    # Без маскирования
    json_output_raw = format_trace(trace_data, format_type='json', show_secrets=True)
    parsed_raw = json.loads(json_output_raw)
    assert parsed_raw["auth"]["password"][0]["value"] == "secret"


def test_format_table_text_fallback(monkeypatch):
    """Проверяет текстовый вывод таблицы (без Rich)."""
    # Принудительно отключаем Rich для теста
    monkeypatch.setenv("CH_NO_RICH", "1")

    trace_data = {
        "db": {
            "host": [{"source": "config.yml", "value": "localhost"}, {"source": "env", "value": "prod"}]
        }
    }

    output = format_trace(trace_data, format_type='table')
    assert "[db] host = prod" in output
    assert "<- env: prod" in output
    assert "<- config.yml: localhost" in output
