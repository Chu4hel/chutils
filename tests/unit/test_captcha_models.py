from __future__ import annotations

import pytest
from pydantic import ValidationError

from chutils.captcha.models import (
    GeeTestResult,
    GeeTestTaskConfig,
    ReCaptchaEnterpriseConfig,
)


def test_geetest_task_config_valid() -> None:
    """Проверяет валидную инициализацию GeeTestTaskConfig."""
    cfg = GeeTestTaskConfig(
        captcha_id="test_captcha_id_123",
        page_url="https://example.com/login",
    )
    assert cfg.captcha_id == "test_captcha_id_123"
    assert cfg.page_url == "https://example.com/login"
    assert cfg.challenge is None
    assert cfg.risk_type is None
    assert cfg.proxy is None

    full_cfg = GeeTestTaskConfig(
        captcha_id="test_id",
        page_url="https://example.com",
        challenge="challenge_v3",
        risk_type="slide",
        api_server="gcaptcha4.geetest.com",
        user_agent="Mozilla/5.0",
        proxy="http://127.0.0.1:8080",
    )
    assert full_cfg.risk_type == "slide"
    assert full_cfg.api_server == "gcaptcha4.geetest.com"
    assert full_cfg.proxy == "http://127.0.0.1:8080"


def test_geetest_task_config_invalid() -> None:
    """Проверяет ошибки валидации GeeTestTaskConfig при некорректных аргументах."""
    with pytest.raises(ValidationError):
        GeeTestTaskConfig(captcha_id="", page_url="https://example.com")

    with pytest.raises(ValidationError):
        GeeTestTaskConfig(captcha_id="valid", page_url="")


def test_geetest_result_payload() -> None:
    """Проверяет корректность формирования payload проверки GeeTestResult."""
    res = GeeTestResult(
        lot_number="lot_abc_123",
        pass_token="pass_xyz_456",
        gen_time="1726000000",
        captcha_output="output_sig_789",
    )
    assert res.lot_number == "lot_abc_123"
    assert res.captcha_id is None

    payload = res.to_validation_payload()
    assert payload == {
        "lot_number": "lot_abc_123",
        "pass_token": "pass_xyz_456",
        "gen_time": "1726000000",
        "captcha_output": "output_sig_789",
    }

    res_with_id = GeeTestResult(
        lot_number="lot_1",
        pass_token="token_2",
        gen_time="12345",
        captcha_output="out_3",
        captcha_id="my_captcha",
    )
    payload_with_id = res_with_id.to_validation_payload()
    assert payload_with_id["captcha_id"] == "my_captcha"


def test_geetest_result_missing_fields() -> None:
    """Проверяет ошибки валидации GeeTestResult при отсутствии обязательных полей."""
    with pytest.raises(ValidationError):
        GeeTestResult(  # type: ignore[call-arg]
            lot_number="lot",
            pass_token="token",
        )


def test_recaptcha_enterprise_config_valid() -> None:
    """Проверяет валидную инициализацию ReCaptchaEnterpriseConfig."""
    cfg = ReCaptchaEnterpriseConfig(
        site_key="6Lf_site_key_enterprise",
        page_url="https://example.com/checkout",
    )
    assert cfg.site_key == "6Lf_site_key_enterprise"
    assert cfg.action is None
    assert cfg.enterprise_payload is None
    assert cfg.min_score is None

    full_cfg = ReCaptchaEnterpriseConfig(
        site_key="6Lf_site_key_enterprise",
        page_url="https://example.com/checkout",
        action="checkout",
        enterprise_payload={"custom_key": "val", "num": 42},
        s_token="secure_token",
        user_agent="Custom-Agent",
        proxy="socks5://proxy.example.com:1080",
        min_score=0.7,
    )
    assert full_cfg.action == "checkout"
    assert full_cfg.enterprise_payload == {"custom_key": "val", "num": 42}
    assert full_cfg.min_score == 0.7


def test_recaptcha_enterprise_config_invalid() -> None:
    """Проверяет валидацию граничных значений и обязательных полей reCAPTCHA Enterprise."""
    with pytest.raises(ValidationError):
        ReCaptchaEnterpriseConfig(site_key="", page_url="https://example.com")

    with pytest.raises(ValidationError):
        ReCaptchaEnterpriseConfig(
            site_key="valid",
            page_url="https://example.com",
            min_score=1.5,
        )

    with pytest.raises(ValidationError):
        ReCaptchaEnterpriseConfig(
            site_key="valid",
            page_url="https://example.com",
            min_score=-0.1,
        )
