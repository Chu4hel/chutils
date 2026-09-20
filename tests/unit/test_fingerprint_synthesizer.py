"""Тесты синтезатора цифровой личности (Fingerprint Synthesizer Engine)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from chutils.exceptions import OptionalDependencyError
from chutils.scraping.fingerprint.models import (
    FingerprintProfile,
    HardwareFingerprint,
    ScreenFingerprint,
    WebGLFingerprint,
)
from chutils.scraping.fingerprint.synthesizer import FingerprintSynthesizer
from chutils.scraping.humanize.config import AntidetectConfig


def test_procedural_synthesizer_determinism() -> None:
    """Проверяет детерминированность генерации отпечатка от одного сида."""
    synthesizer = FingerprintSynthesizer(mode="procedural")
    seed = "alice_profile_42"

    fp1 = synthesizer.synthesize(seed)
    fp2 = synthesizer.synthesize(seed)

    assert fp1.webgl.renderer == fp2.webgl.renderer
    assert fp1.webgl.vendor == fp2.webgl.vendor
    assert fp1.hardware.concurrency == fp2.hardware.concurrency
    assert fp1.hardware.memory_gb == fp2.hardware.memory_gb
    assert fp1.screen.width == fp2.screen.width
    assert fp1.screen.height == fp2.screen.height
    assert fp1.screen.avail_height == fp2.screen.avail_height
    assert fp1.screen.device_pixel_ratio == fp2.screen.device_pixel_ratio
    assert fp1.audio.noise_factor == fp2.audio.noise_factor
    assert len(fp1.media_devices) == len(fp2.media_devices)
    if fp1.media_devices:
        assert fp1.media_devices[0].device_id == fp2.media_devices[0].device_id


def test_procedural_synthesizer_different_seeds() -> None:
    """Проверяет, что разные сиды генерируют разные комбинации параметров."""
    synthesizer = FingerprintSynthesizer(mode="procedural")

    fp1 = synthesizer.synthesize("seed_alpha_1")
    fp2 = synthesizer.synthesize("seed_beta_2")

    # Комбинаторный отпечаток должен отличаться хотя бы по части ключевых параметров
    is_different = (
        fp1.webgl.renderer != fp2.webgl.renderer
        or fp1.hardware.concurrency != fp2.hardware.concurrency
        or fp1.hardware.memory_gb != fp2.hardware.memory_gb
        or fp1.screen.width != fp2.screen.width
        or fp1.audio.noise_factor != fp2.audio.noise_factor
    )
    assert is_different


def test_procedural_synthesizer_hardware_consistency() -> None:
    """Проверяет физическую согласованность слоев железа (Tier Matrix)."""
    synthesizer = FingerprintSynthesizer(mode="procedural")

    angle_regex = re.compile(
        r"^ANGLE \([A-Za-z0-9\s]+, [A-Za-z0-9\(\)\s\-]+ Direct3D11 vs_5_0 ps_5_0, D3D11-31\.0\.\d+\.\d+\)$"
    )

    for i in range(50):
        fp = synthesizer.synthesize(f"consistency_test_seed_{i}")

        # 1. Валидный синтаксис ANGLE Direct3D11
        assert angle_regex.match(fp.webgl.renderer), f"Невалидный ANGLE: {fp.webgl.renderer}"

        # 2. Согласованность экрана и панели задач
        assert fp.screen.avail_height < fp.screen.height, "Панель задач должна уменьшать availHeight"
        assert fp.screen.avail_width == fp.screen.width
        assert fp.screen.device_pixel_ratio in (1.0, 1.25, 1.5, 1.75, 2.0)

        # 3. Согласованность High-End GPU с памятью и процессором
        if any(top_gpu in fp.webgl.renderer for top_gpu in ("RTX 4090", "RTX 4080", "RX 7900 XTX")):
            assert fp.hardware.memory_gb >= 16, "Топовый GPU не может работать с < 16 ГБ RAM"
            assert fp.hardware.concurrency >= 12, "Топовый GPU не может работать с < 12 ядрами CPU"

        # 4. Согласованность встроенной графики
        if "Iris" in fp.webgl.renderer or "UHD Graphics" in fp.webgl.renderer:
            assert fp.hardware.concurrency <= 16, "Ноутбучная встроенная графика не должна иметь > 16 ядер"


def test_fingerprint_profile_serialization(tmp_path: Path) -> None:
    """Проверяет сериализацию и восстановление профиля из файла JSON."""
    synthesizer = FingerprintSynthesizer(mode="procedural")
    original = synthesizer.synthesize("save_load_seed")

    save_file = tmp_path / "fingerprint.json"
    original.save_to_file(save_file)

    loaded = FingerprintProfile.from_file(save_file)

    assert loaded.seed == original.seed
    assert loaded.webgl.renderer == original.webgl.renderer
    assert loaded.hardware.concurrency == original.hardware.concurrency
    assert loaded.screen.width == original.screen.width
    assert loaded.source == original.source


def test_antidetect_config_from_fingerprint() -> None:
    """Проверяет интеграцию FingerprintProfile с AntidetectConfig."""
    synthesizer = FingerprintSynthesizer(mode="procedural")
    fp = synthesizer.synthesize("integration_seed")

    config = fp.to_antidetect_config(stealth_minimal=False)

    assert isinstance(config, AntidetectConfig)
    assert config.webgl_renderer == fp.webgl.renderer
    assert config.webgl_vendor == fp.webgl.vendor
    assert config.hardware_concurrency == fp.hardware.concurrency
    assert config.device_memory == fp.hardware.memory_gb
    assert config.client_hints == fp.client_hints
    assert config.stealth_minimal is False


def test_antidetect_config_from_seed() -> None:
    """Проверяет фабричный метод AntidetectConfig.from_seed()."""
    config1 = AntidetectConfig.from_seed("user_profile_1")
    config2 = AntidetectConfig.from_seed("user_profile_1")

    assert config1.webgl_renderer == config2.webgl_renderer
    assert config1.hardware_concurrency == config2.hardware_concurrency
    assert config1.device_memory == config2.device_memory
    assert config1.session_seed == "user_profile_1"


def test_browserforge_not_installed_raises_optional_dependency_error(
    mocker: MockerFixture,
) -> None:
    """Проверяет, что при отсутствии browserforge выбрасывается OptionalDependencyError."""
    import importlib.util

    orig_find_spec = importlib.util.find_spec

    def mock_spec(name: str, package: str | None = None) -> Any:
        if name == "browserforge":
            return None
        return orig_find_spec(name, package)

    mocker.patch("importlib.util.find_spec", side_effect=mock_spec)

    with pytest.raises(OptionalDependencyError, match="browserforge"):
        AntidetectConfig.from_browserforge()


def test_browserforge_mock_provider(mocker: MockerFixture) -> None:
    """Проверяет адаптер BrowserForgeProvider при установленной библиотеке."""
    mock_fg_instance = MagicMock()
    mock_fp = MagicMock()
    mock_fp.navigator.userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    mock_fp.navigator.hardwareConcurrency = 16
    mock_fp.navigator.deviceMemory = 32
    mock_fp.screen.width = 2560
    mock_fp.screen.height = 1440
    mock_fp.screen.availHeight = 1392
    mock_fp.screen.availWidth = 2560
    mock_fp.screen.colorDepth = 24
    mock_fp.screen.devicePixelRatio = 1.25
    mock_fp.videoCard.vendor = "Google Inc. (NVIDIA)"
    mock_fp.videoCard.renderer = "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11-31.0.15.5186)"
    mock_fp.headers = {"sec-ch-ua-platform": '"Windows"'}

    mock_fg_instance.generate.return_value = mock_fp

    with patch("chutils.scraping.fingerprint.external.FingerprintGenerator", return_value=mock_fg_instance, create=True):
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            synthesizer = FingerprintSynthesizer(mode="browserforge")
            fp = synthesizer.synthesize()

            assert fp.source == "browserforge"
            assert fp.webgl.renderer == mock_fp.videoCard.renderer
            assert fp.hardware.concurrency == 16
            assert fp.hardware.memory_gb == 32
            assert fp.screen.width == 2560
            assert fp.screen.avail_height == 1392


def test_availability_helpers() -> None:
    """Проверяет статические методы проверки доступности сторонних библиотек."""
    assert isinstance(FingerprintSynthesizer.is_browserforge_available(), bool)
    assert isinstance(FingerprintSynthesizer.is_fpgen_available(), bool)
