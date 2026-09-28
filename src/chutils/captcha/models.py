from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GeeTestTaskConfig(BaseModel):
    """Конфигурация задачи для решения GeeTest v4 / v3.

    Attributes:
        captcha_id: Идентификатор капчи GeeTest v4 (параметр captcha_id).
        page_url: Полный URL страницы, на которой расположена капча.
        challenge: Токен челленджа (обязателен для v3, опционален для v4).
        risk_type: Подтип или тип риска проверки (например, 'slide', 'verify').
        api_server: Домен сервера GeeTest (например, 'gcaptcha4.geetest.com').
        user_agent: Пользовательский User-Agent для решения с эмуляцией заголовков.
        proxy: Прокси-сервер в формате scheme://user:password@host:port.
    """

    model_config = ConfigDict(extra="ignore")

    captcha_id: str = Field(..., min_length=1, description="Идентификатор капчи GeeTest")
    page_url: str = Field(..., min_length=1, description="URL страницы с капчей")
    challenge: str | None = Field(default=None, description="Токен челленджа для v3")
    risk_type: str | None = Field(default=None, description="Тип риска или сценарий капчи")
    api_server: str | None = Field(default=None, description="Домен сервера GeeTest")
    user_agent: str | None = Field(default=None, description="User-Agent браузера")
    proxy: str | None = Field(default=None, description="Прокси для решения капчи")


class GeeTestResult(BaseModel):
    """Результат успешного решения капчи GeeTest v4.

    Attributes:
        lot_number: Идентификатор лота (раунда верификации).
        pass_token: Токен прохождения проверки.
        gen_time: Временная метка генерации решения.
        captcha_output: Подпись решения капчи (output).
        captcha_id: Идентификатор капчи, для которой получено решение.
    """

    model_config = ConfigDict(extra="ignore")

    lot_number: str = Field(..., description="Идентификатор раунда верификации (lot_number)")
    pass_token: str = Field(..., description="Токен подтверждения (pass_token)")
    gen_time: str = Field(..., description="Временная метка генерации (gen_time)")
    captcha_output: str = Field(..., description="Подпись верификации (captcha_output)")
    captcha_id: str | None = Field(default=None, description="ID капчи")

    def to_validation_payload(self) -> dict[str, str]:
        """Формирует словарь параметров для отправки на целевой бэкенд проверки.

        Returns:
            Словарь параметров с lot_number, pass_token, gen_time, captcha_output.
        """
        payload: dict[str, str] = {
            "lot_number": self.lot_number,
            "pass_token": self.pass_token,
            "gen_time": self.gen_time,
            "captcha_output": self.captcha_output,
        }
        if self.captcha_id:
            payload["captcha_id"] = self.captcha_id
        return payload


class ReCaptchaEnterpriseConfig(BaseModel):
    """Конфигурация задачи для решения reCAPTCHA Enterprise.

    Attributes:
        site_key: Публичный ключ сайта (sitekey) reCAPTCHA Enterprise.
        page_url: Полный URL страницы, на которой расположена капча.
        action: Название защищаемого действия (action).
        enterprise_payload: Дополнительные параметры Enterprise payload.
        s_token: Защитный токен s_token (если используется).
        user_agent: Пользовательский User-Agent для соответствия браузерному окружению.
        proxy: Прокси-сервер в формате scheme://user:password@host:port.
        min_score: Минимальный требуемый score для скоринговых проверок (0.1 - 0.9).
    """

    model_config = ConfigDict(extra="ignore")

    site_key: str = Field(..., min_length=1, description="Публичный ключ сайта reCAPTCHA Enterprise")
    page_url: str = Field(..., min_length=1, description="URL страницы с reCAPTCHA Enterprise")
    action: str | None = Field(default=None, description="Защищаемое действие (action)")
    enterprise_payload: dict[str, str | int | float | bool] | None = Field(
        default=None, description="Дополнительный Enterprise payload"
    )
    s_token: str | None = Field(default=None, description="Защитный токен s_token")
    user_agent: str | None = Field(default=None, description="User-Agent браузера")
    proxy: str | None = Field(default=None, description="Прокси для решения капчи")
    min_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Минимальный требуемый score (0.0 - 1.0)"
    )
