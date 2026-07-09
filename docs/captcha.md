# Интеграция с решателями капчи (chutils.scraping.captcha)

Модуль `chutils.scraping.captcha` предоставляет единый абстрактный интерфейс и набор клиентов для работы с внешними
сервисами распознавания капч:

- **RuCaptcha / 2Captcha** (совместимы по API)
- **Anti-Captcha**
- **CapMonster Cloud**

Этот функционал поставляется как опциональный экстра-пакет `chutils[captcha]`.

---

## Установка

Для использования клиентов капчи установите пакет с поддержкой экстра-зависимостей:

```bash
pip install "chutils[captcha]"
```

---

## 1. Поддерживаемые типы капч

Все клиенты предоставляют методы для решения следующих видов капч:

- **ImageToText**: Распознавание текста по картинке (передается как `bytes` или base64-строка).
- **ReCaptcha (v2 / v3)**: Решение капчи через передачу параметров `sitekey` и `page_url`.

---

## 2. Интеграция с SecretManager

Если API-ключ не передан в конструктор класса-решателя явно, клиент автоматически пытается загрузить его из
`chutils.secret_manager` по стандартным именам ключей:

- RuCaptcha / 2Captcha: `RUCAPTCHA_API_KEY` или `TWOCAPTCHA_API_KEY`
- Anti-Captcha: `ANTICAPTCHA_API_KEY`
- CapMonster: `CAPMONSTER_API_KEY`

Если ключ отсутствует как в конструкторе, так и в `secret_manager`, генерируется ошибка `ChutilsConfigurationError`.

---

## 3. Синхронные клиенты

Синхронные клиенты автоматически опрашивают готовность капчи с заданным интервалом до истечения таймаута.

```python
from chutils.scraping.captcha import RuCaptchaSolver, AntiCaptchaSolver, CapMonsterSolver
from chutils.scraping.captcha import CaptchaError

try:
    # Инициализация (ключ автоматически подгрузится из SecretManager)
    solver = RuCaptchaSolver()

    # 1. Решение текстовой капчи по картинке (передаем байты)
    with open("captcha.png", "rb") as f:
        text = solver.solve_image(f.read(), timeout=60.0, poll_interval=5.0)
    print(f"Текст капчи: {text}")

    # 2. Решение ReCaptcha v2
    token = solver.solve_recaptcha(
        sitekey="6LeOeSkUAAAAACl2pxhXLD37t3h7wJz16F8ySU73",
        page_url="https://rucaptcha.com/demo/recaptcha-v2"
    )
    print(f"Токен ReCaptcha: {token}")

except CaptchaError as e:
    print(f"Ошибка решения капчи: {e}")
```

---

## 4. Асинхронные клиенты

Асинхронные клиенты поддерживают аналогичные методы с приставкой `async_` (для запуска неблокирующих опросов через
`asyncio.sleep`).

```python
import asyncio
from chutils.scraping.captcha import AsyncAntiCaptchaSolver, AsyncCapMonsterSolver


async def main():
    # Автоматически считывает ANTICAPTCHA_API_KEY из secret_manager
    solver = AsyncAntiCaptchaSolver()

    # Асинхронный скролл/опрос
    token = await solver.solve_recaptcha(
        sitekey="sitekey_value_here",
        page_url="https://example.com/login"
    )
    print(f"Токен: {token}")


asyncio.run(main())
```

---

## 5. Иерархия исключений

Все ошибки при работе с модулем наследуются от базового класса `CaptchaError`:

- `CaptchaError`: Базовая ошибка решения капчи.
- `CaptchaTimeoutError`: Превышено время ожидания решения (таймаут).
- `CaptchaBalanceError`: Нулевой или недостаточный баланс на аккаунте сервиса.
- `CaptchaServiceError`: Сервис вернул ошибку API (неверный ключ, плохие параметры и т.д.).
