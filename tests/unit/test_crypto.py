import pytest

from chutils.crypto import (
    encrypt_portable,
    decrypt_portable,
    encrypt_file,
    decrypt_file,
    _get_fernet_key
)


def test_get_fernet_key_deterministic():
    """Проверяет детерминированность генерации Fernet-ключа."""
    key1 = _get_fernet_key("my_seed_1")
    key2 = _get_fernet_key("my_seed_1")
    key3 = _get_fernet_key("my_seed_2")

    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 44  # Fernet key is 44 bytes in base64


def test_string_encryption_success():
    """Проверяет успешное шифрование и дешифрование строки."""
    original = "Секретные данные 123!"
    seed = "secure_password"

    encrypted = encrypt_portable(original, seed)
    assert isinstance(encrypted, str)
    assert encrypted != original

    decrypted = decrypt_portable(encrypted, seed)
    assert decrypted == original


def test_string_decryption_failure():
    """Проверяет поведение при неверном seed или поврежденных данных."""
    original = "Секрет"
    seed = "password123"

    encrypted = encrypt_portable(original, seed)

    # Неверный пароль -> None
    assert decrypt_portable(encrypted, "wrong_password") is None

    # Поврежденные данные -> None
    assert decrypt_portable(encrypted[:-2] + "xx", seed) is None
    assert decrypt_portable("not_a_valid_token", seed) is None


def test_string_operations_no_cryptography(monkeypatch):
    """Проверяет генерацию ошибки при отсутствии библиотеки cryptography."""
    import chutils.crypto
    monkeypatch.setattr(chutils.crypto, "_HAS_CRYPTOGRAPHY", False)

    with pytest.raises(RuntimeError) as exc_info:
        encrypt_portable("data", "seed")
    assert "chutils[crypto]" in str(exc_info.value)

    with pytest.raises(RuntimeError) as exc_info:
        decrypt_portable("data", "seed")
    assert "chutils[crypto]" in str(exc_info.value)


def test_file_encryption_success(tmp_path):
    """Проверяет шифрование и дешифрование файлов с явным и неявным output_path."""
    # Создаем временный файл
    src_file = tmp_path / "data.txt"
    src_file.write_text("Содержимое текстового файла для теста", encoding="utf-8")
    seed = "file_seed"

    # 1. Шифрование во второй файл (явный output_path)
    enc_file = tmp_path / "data.txt.enc"
    res_path = encrypt_file(src_file, seed, output_path=enc_file)
    assert res_path == enc_file
    assert enc_file.exists()
    assert enc_file.read_bytes() != src_file.read_bytes()

    # Дешифрование во второй файл (явный output_path)
    dec_file = tmp_path / "data.txt.dec"
    success = decrypt_file(enc_file, seed, output_path=dec_file)
    assert success is True
    assert dec_file.exists()
    assert dec_file.read_text(encoding="utf-8") == "Содержимое текстового файла для теста"

    # 2. Шифрование и дешифрование на месте (неявный output_path)
    encrypt_file(src_file, seed)
    # Файл src_file должен теперь быть зашифрован (отличаться от исходного текста)
    assert src_file.read_text(encoding="utf-8") != "Содержимое текстового файла для теста"

    success_inplace = decrypt_file(src_file, seed)
    assert success_inplace is True
    # Файл должен вернуться к исходному виду
    assert src_file.read_text(encoding="utf-8") == "Содержимое текстового файла для теста"


def test_file_decryption_failure(tmp_path):
    """Проверяет обработку ошибок при дешифровании файлов."""
    src_file = tmp_path / "data.txt"
    src_file.write_text("Содержимое", encoding="utf-8")
    seed = "seed"

    encrypt_file(src_file, seed)

    # Неверный пароль -> False
    assert decrypt_file(src_file, "wrong_seed") is False

    # Поврежденный файл -> False
    src_file.write_bytes(b"corrupted_data_bytes")
    assert decrypt_file(src_file, seed) is False


def test_file_operations_no_cryptography(tmp_path, monkeypatch):
    """Проверяет генерацию ошибки для файловых операций при отсутствии cryptography."""
    import chutils.crypto
    monkeypatch.setattr(chutils.crypto, "_HAS_CRYPTOGRAPHY", False)

    file_path = tmp_path / "test.txt"
    file_path.write_text("123")

    with pytest.raises(RuntimeError) as exc_info:
        encrypt_file(file_path, "seed")
    assert "chutils[crypto]" in str(exc_info.value)

    with pytest.raises(RuntimeError) as exc_info:
        decrypt_file(file_path, "seed")
    assert "chutils[crypto]" in str(exc_info.value)
