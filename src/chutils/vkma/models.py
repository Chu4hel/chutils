"""Pydantic-модели для параметров запуска VK Mini Apps (launchParams / initData)."""

from pydantic import BaseModel, ConfigDict, Field


class VKMALaunchParams(BaseModel):
    """Строго типизированная Pydantic-модель параметров запуска VK Mini App.

    Официальная документация VK Mini Apps parameters:
    https://dev.vk.com/ru/mini-apps/development/launch-params
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    vk_user_id: int = Field(..., description="ID пользователя VK")
    vk_app_id: int = Field(..., description="ID приложения VK Mini App")
    vk_is_app_user: int = Field(default=0, description="Приложение установлено пользователем (1 - да, 0 - нет)")
    vk_are_notifications_enabled: int = Field(default=0, description="Разрешены ли уведомления")
    vk_language: str = Field(default="ru", description="Язык интерфейса VK (ru, en, uk, etc.)")
    vk_ref: str = Field(default="other", description="Источник перехода в сервис")
    vk_ts: int = Field(..., description="Timestamp формирования параметров в секундах")
    sign: str = Field(..., description="Подпись параметров HMAC-SHA256")

    # Дополнительные опциональные параметры VK
    vk_group_id: int | None = Field(default=None, description="ID сообщества, если запущен из группы")
    vk_viewer_group_role: str | None = Field(default=None, description="Роль пользователя в сообществе (admin, editor, member, none)")
    vk_platform: str | None = Field(default=None, description="Платформа (desktop_web, mobile_web, mobile_android, mobile_iphone, etc.)")
    vk_is_favorite: int | None = Field(default=None, description="Добавлено ли сервис в избранное")
    vk_has_profile_button: int | None = Field(default=None, description="Есть ли кнопка в профиле")
    vk_testing_group_id: int | None = Field(default=None, description="ID группы тестирования")

    @property
    def user_id(self) -> int:
        """Alias для `vk_user_id`."""
        return self.vk_user_id

    @property
    def app_id(self) -> int:
        """Alias для `vk_app_id`."""
        return self.vk_app_id

    @property
    def is_app_user(self) -> bool:
        """Установлено ли приложение пользователем (True/False)."""
        return bool(self.vk_is_app_user)

    @property
    def language(self) -> str:
        """Alias для `vk_language`."""
        return self.vk_language

    @property
    def platform(self) -> str | None:
        """Alias для `vk_platform`."""
        return self.vk_platform

    @property
    def ts(self) -> int:
        """Alias для `vk_ts`."""
        return self.vk_ts
