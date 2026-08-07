# `chutils.vk.testing`: Утилиты тестирования VK Ботов и VK Mini Apps

Модуль `chutils.vk.testing` (также доступен как `chutils.vkma.testing`) позволяет генерировать поддельные подписи HMAC-SHA256, эмулировать `launchParams` / `initData` и мокировать вызовы VK API в unit-тестах.

---

## 🛠️ Функции генерации данных

- `generate_fake_launch_params(user_id=12345, app_id=77777, secret_key="...", expired=False, tampered=False, extra_params=None) -> str`
- `generate_fake_init_data(...) -> str`
- `generate_fake_user(user_id=12345, first_name="Иван", last_name="Иванов") -> dict`

## 🧪 Pytest Фикстуры

- `vk_launch_params_factory`: фикстура-фабрика для генерации строк `launchParams`.
- `mock_vk_api`: фикстура мока вызовов VK API.
- `mock_vk_api_context()`: контекстный менеджер для изоляции вызовов VK API.
