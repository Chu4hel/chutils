"""Базы данных и матрицы физической совместимости оборудования (Hardware Tiers)."""

from __future__ import annotations

from typing import NamedTuple


class GPUTier(NamedTuple):
    """Описание тира оборудования с допустимыми диапазонами характеристик."""

    tier_name: str
    gpus: list[tuple[str, str]]  # (Vendor, FullRendererName)
    memory_options: list[int]  # RAM в ГБ
    cpu_cores_options: list[int]  # Логические ядра CPU
    screen_options: list[tuple[int, int, float]]  # (width, height, devicePixelRatio)
    has_webcam_probability: float


TIER_ENTHUSIAST = GPUTier(
    tier_name="enthusiast",
    gpus=[
        ("NVIDIA", "NVIDIA GeForce RTX 4090"),
        ("NVIDIA", "NVIDIA GeForce RTX 4080"),
        ("NVIDIA", "NVIDIA GeForce RTX 4070 Ti"),
        ("NVIDIA", "NVIDIA GeForce RTX 3090"),
        ("NVIDIA", "NVIDIA GeForce RTX 3080"),
        ("AMD", "AMD Radeon RX 7900 XTX"),
        ("AMD", "AMD Radeon RX 6900 XT"),
    ],
    memory_options=[32, 64],
    cpu_cores_options=[12, 16, 20, 24, 32],
    screen_options=[
        (2560, 1440, 1.0),
        (2560, 1440, 1.25),
        (3840, 2160, 1.5),
        (3840, 2160, 2.0),
        (1920, 1080, 1.0),
    ],
    has_webcam_probability=0.35,
)
"""Аппаратный тир для энтузиастов и высокопроизводительных ПК."""

TIER_MAINSTREAM = GPUTier(
    tier_name="mainstream",
    gpus=[
        ("NVIDIA", "NVIDIA GeForce RTX 4060 Ti"),
        ("NVIDIA", "NVIDIA GeForce RTX 4060"),
        ("NVIDIA", "NVIDIA GeForce RTX 3070"),
        ("NVIDIA", "NVIDIA GeForce RTX 3060"),
        ("NVIDIA", "NVIDIA GeForce RTX 2070"),
        ("NVIDIA", "NVIDIA GeForce RTX 2060"),
        ("AMD", "AMD Radeon RX 7700 XT"),
        ("AMD", "AMD Radeon RX 6700 XT"),
        ("AMD", "AMD Radeon RX 6600"),
    ],
    memory_options=[16, 32],
    cpu_cores_options=[8, 12, 16],
    screen_options=[
        (1920, 1080, 1.0),
        (1920, 1080, 1.25),
        (2560, 1440, 1.0),
        (2560, 1440, 1.25),
    ],
    has_webcam_probability=0.45,
)
"""Аппаратный тир массовых игровых и рабочих ПК."""

TIER_BUDGET_DESKTOP = GPUTier(
    tier_name="budget_desktop",
    gpus=[
        ("NVIDIA", "NVIDIA GeForce GTX 1660 SUPER"),
        ("NVIDIA", "NVIDIA GeForce GTX 1650"),
        ("NVIDIA", "NVIDIA GeForce GTX 1060 6GB"),
        ("NVIDIA", "NVIDIA GeForce GTX 1050 Ti"),
        ("AMD", "Radeon RX 580 Series"),
        ("AMD", "Radeon RX 570 Series"),
        ("Intel", "Intel(R) Arc(TM) A750 Graphics"),
        ("Intel", "Intel(R) Arc(TM) A770 Graphics"),
    ],
    memory_options=[8, 16],
    cpu_cores_options=[6, 8, 12],
    screen_options=[
        (1920, 1080, 1.0),
        (1600, 900, 1.0),
        (1920, 1080, 1.25),
    ],
    has_webcam_probability=0.30,
)
"""Аппаратный тир бюджетных и офисных десктопов."""

TIER_LAPTOP = GPUTier(
    tier_name="laptop",
    gpus=[
        ("Intel", "Intel(R) Iris(R) Xe Graphics"),
        ("Intel", "Intel(R) UHD Graphics 770"),
        ("Intel", "Intel(R) UHD Graphics 630"),
        ("AMD", "AMD Radeon(TM) Graphics"),
        ("AMD", "AMD Radeon 680M"),
    ],
    memory_options=[8, 16],
    cpu_cores_options=[4, 6, 8, 12, 16],
    screen_options=[
        (1920, 1080, 1.0),
        (1920, 1080, 1.25),
        (1536, 864, 1.25),
        (1366, 768, 1.0),
        (1440, 900, 1.0),
        (2880, 1800, 2.0),
    ],
    has_webcam_probability=0.95,
)
"""Аппаратный тир ноутбуков и ультрабуков."""

ALL_TIERS = [TIER_MAINSTREAM, TIER_ENTHUSIAST, TIER_BUDGET_DESKTOP, TIER_LAPTOP]
"""Список всех доступных аппаратных конфигураций."""

AUDIO_INPUTS_RU = [
    "Микрофон (Realtek(R) Audio)",
    "Микрофон (Realtek High Definition Audio)",
    "Микрофон (USB Audio Device)",
    "Массив микрофонов (Intel(R) Smart Sound Technology)",
]
"""Список русскоязычных названий микрофонов."""

AUDIO_INPUTS_EN = [
    "Microphone (Realtek(R) Audio)",
    "Microphone (Realtek High Definition Audio)",
    "Microphone (USB Audio Device)",
    "Microphone Array (Intel(R) Smart Sound Technology)",
]
"""Список англоязычных названий микрофонов."""

AUDIO_OUTPUTS_RU = [
    "Динамики (Realtek(R) Audio)",
    "Динамики (Realtek High Definition Audio)",
    "Наушники (Realtek(R) Audio)",
    "Динамики (High Definition Audio Device)",
]
"""Список русскоязычных названий аудиовыходов."""

AUDIO_OUTPUTS_EN = [
    "Speakers (Realtek(R) Audio)",
    "Speakers (Realtek High Definition Audio)",
    "Headphones (Realtek(R) Audio)",
    "Speakers (High Definition Audio Device)",
]
"""Список англоязычных названий аудиовыходов."""

VIDEO_INPUTS = [
    "Integrated Camera (04f2:b6d9)",
    "HD User Facing Webcam",
    "USB Video Device",
    "FHD Webcam",
]
"""Список названий веб-камер."""
