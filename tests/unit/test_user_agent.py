import pytest

from chutils.web.user_agent import UserAgentRotator


def test_user_agent_rotator_default_list() -> None:
    """Проверяет, что по умолчанию используется непустой список User-Agent."""
    rotator = UserAgentRotator()
    assert len(rotator.user_agents) > 0
    assert all(isinstance(ua, str) for ua in rotator.user_agents)


def test_user_agent_rotator_get_random() -> None:
    """Проверяет случайный выбор User-Agent."""
    rotator = UserAgentRotator(user_agents=["UA1", "UA2", "UA3"])
    ua = rotator.get(strategy="random")
    assert ua in ["UA1", "UA2", "UA3"]


def test_user_agent_rotator_get_round_robin() -> None:
    """Проверяет выбор User-Agent по кругу (Round-Robin)."""
    rotator = UserAgentRotator(user_agents=["UA1", "UA2"])
    assert rotator.get(strategy="round_robin") == "UA1"
    assert rotator.get(strategy="round_robin") == "UA2"
    assert rotator.get(strategy="round_robin") == "UA1"


def test_user_agent_rotator_fallback() -> None:
    """Проверяет использование fallback значения при пустом списке."""
    rotator = UserAgentRotator(user_agents=[], fallback="FallbackUA")
    assert rotator.get() == "FallbackUA"


def test_user_agent_rotator_invalid_strategy() -> None:
    """Проверяет, что при невалидной стратегии вызывается ValueError."""
    rotator = UserAgentRotator()
    with pytest.raises(ValueError):
        rotator.get(strategy="invalid_strategy")
