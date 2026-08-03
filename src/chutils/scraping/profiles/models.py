"""Модели данных профилей и сессий браузеров."""

from typing import Literal
from pydantic import BaseModel, Field


class CookieData(BaseModel):
    """Данные Cookie записи."""

    name: str
    value: str
    domain: str
    path: str = "/"
    expires: float | None = None
    http_only: bool = False
    secure: bool = False
    same_site: Literal["Strict", "Lax", "None"] | None = None


class StorageData(BaseModel):
    """Данные хранилищ браузера (LocalStorage, SessionStorage, IndexedDB)."""

    local_storage: dict[str, dict[str, str]] = Field(default_factory=dict)
    session_storage: dict[str, dict[str, str]] = Field(default_factory=dict)
    indexed_db: dict[str, dict[str, str]] = Field(default_factory=dict)


class HeaderData(BaseModel):
    """Метаданные заголовков и браузера."""

    user_agent: str | None = None
    accept_language: str | None = None
    sec_ch_ua: str | None = None
    custom_headers: dict[str, str] = Field(default_factory=dict)


class BrowserProfile(BaseModel):
    """Универсальная модель профиля браузера для экспорта/импорта."""

    version: str = "1.0"
    engine_origin: str | None = None
    cookies: list[CookieData] = Field(default_factory=list)
    storage: StorageData = Field(default_factory=StorageData)
    headers: HeaderData = Field(default_factory=HeaderData)
    metadata: dict[str, str] = Field(default_factory=dict)
