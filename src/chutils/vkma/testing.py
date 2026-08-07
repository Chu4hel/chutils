"""Алиас модуля тестирования VK / VKMA: chutils.vkma.testing."""

from chutils.vk.testing import (
    MockVKApi,
    generate_fake_init_data,
    generate_fake_launch_params,
    generate_fake_user,
    mock_vk_api_context,
)

__all__ = [
    "generate_fake_launch_params",
    "generate_fake_init_data",
    "generate_fake_user",
    "MockVKApi",
    "mock_vk_api_context",
]
