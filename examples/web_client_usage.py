"""Пример использования модуля chutils.web для выполнения умных HTTP-запросов.

Демонстрирует:
1. Автоматическую ротацию User-Agent.
2. Использование пула прокси (ProxyPool).
3. Интеграцию с кэшированием (GET-запросов).
4. Ограничение частоты запросов (Rate Limiting).
5. Автоматические повторные попытки (Retries) с ротацией прокси при ошибках.
"""

import asyncio

from chutils.exceptions import RateLimitExceededError
from chutils.web import AsyncWebClient, WebClient
from chutils.web.proxy_pool import ProxyPool
from chutils.web.user_agent import UserAgentRotator


def run_sync_example() -> None:
    print("=== Синхронный пример (WebClient) ===")

    # 1. Настройка ротатора User-Agent и пула прокси
    ua_rotator = UserAgentRotator(user_agents=["MyCustomBrowser/1.0", "MyCustomBrowser/2.0"])
    proxy_pool = ProxyPool(
        proxies=["http://1.2.3.4:8080", "http://5.6.7.8:8080"],
        strategy="round_robin",
    )

    # 2. Инициализация WebClient с ретраями, кэшированием и лимитами
    with WebClient(
            user_agent_rotator=ua_rotator,
            proxy_pool=proxy_pool,
            retries=2,
            retry_delay=0.5,
            cache_ttl=10,  # Кэшировать GET-запросы на 10 секунд
            rate_limit_calls=2,  # Максимум 2 запроса
            rate_limit_period=5.0,  # за 5 секунд
            rate_limit_wait=False,
    ) as client:
        # Выполняем GET-запрос
        try:
            # Запрос пойдет через прокси http://1.2.3.4:8080, с одним из наших User-Agent
            print("Выполнение первого запроса...")
            response = client.get("https://httpbin.org/headers")
            print(f"Статус: {response.status_code}")
            print(f"Заголовки ответа: {response.json().get('headers', {})}")
        except Exception as e:
            print(f"Запрос завершился с ожидаемой ошибкой (так как прокси фейковые): {e}")

        # Демонстрация кэширования (если бы первый запрос прошел успешно,
        # второй вернулся бы моментально из кэша без выполнения сетевого вызова)
        print("\nВыполнение второго запроса (проверка кэша)...")
        try:
            client.get("https://httpbin.org/headers")
        except Exception as e:
            print(f"Ошибка второго запроса: {e}")


async def run_async_example() -> None:
    print("\n=== Асинхронный пример (AsyncWebClient) ===")

    with AsyncWebClient(
            retries=1,
            rate_limit_calls=1,
            rate_limit_period=5.0,
            rate_limit_wait=False,
    ) as client:
        # Первый запрос проходит успешно (лимит 1 запрос в 5 секунд)
        print("Выполнение первого асинхронного запроса...")
        try:
            resp = await client.get("https://httpbin.org/ip")
            print(f"Успешный ответ: {resp.status_code}")
        except Exception as e:
            print(f"Ошибка асинхронного запроса: {e}")

        # Второй запрос к тому же хосту заблокируется лимитером
        print("Выполнение второго асинхронного запроса (проверка лимита)...")
        try:
            await client.get("https://httpbin.org/ip")
        except RateLimitExceededError as e:
            print(f"Перехвачено ограничение частоты запросов: {e}")


if __name__ == "__main__":
    run_sync_example()
    asyncio.run(run_async_example())
