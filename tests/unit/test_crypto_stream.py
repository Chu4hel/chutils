from pathlib import Path

import pytest

from chutils.crypto import encrypt_file, decrypt_file, _HAS_CRYPTOGRAPHY


@pytest.mark.skipif(not _HAS_CRYPTOGRAPHY, reason="Требуется библиотека cryptography")
def test_stream_encryption_decryption(tmp_path: Path):
    """Проверяет потоковое шифрование и расшифровку небольшого файла маленькими чанками."""
    input_file = tmp_path / "large_data.txt"
    content = b"Hello, Streaming AES-GCM Encryption World!" * 1000  # ~43 КБ
    input_file.write_bytes(content)

    enc_file = tmp_path / "encrypted.bin"
    dec_file = tmp_path / "decrypted.txt"
    seed = "secret_pass_123"

    # Шифруем чанками по 1 КБ
    encrypt_file(input_file, seed, enc_file, stream=True, chunk_size=1024)

    assert enc_file.exists()
    assert enc_file.stat().st_size > input_file.stat().st_size

    # Авто-расшифровка потокового формата
    success = decrypt_file(enc_file, seed, dec_file, raise_on_error=True)
    assert success is True
    assert dec_file.read_bytes() == content


@pytest.mark.skipif(not _HAS_CRYPTOGRAPHY, reason="Требуется библиотека cryptography")
def test_stream_decryption_corrupted_chunk(tmp_path: Path):
    """Проверяет, что подмена байт в одном из чанков вызывает ошибку расшифровки."""
    input_file = tmp_path / "data.txt"
    input_file.write_bytes(b"A" * 10000)

    enc_file = tmp_path / "encrypted_corrupt.bin"
    dec_file = tmp_path / "decrypted_corrupt.txt"
    seed = "secret_pass_123"

    encrypt_file(input_file, seed, enc_file, stream=True, chunk_size=1024)

    # Подменяем байты в середине файла
    data = bytearray(enc_file.read_bytes())
    data[100] ^= 0xFF
    enc_file.write_bytes(data)

    with pytest.raises(ValueError, match="Сбой аутентификации|Поврежден"):
        decrypt_file(enc_file, seed, dec_file, raise_on_error=True)
