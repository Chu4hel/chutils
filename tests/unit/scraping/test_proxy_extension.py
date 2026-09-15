"""Тесты генератора расширения авторизации прокси для Chromium (ChromeProxyExtension)."""

import json
from pathlib import Path

from chutils.scraping.proxy.extension import ChromeProxyExtension
from chutils.scraping.proxy.models import ProxyConfig


def test_chrome_proxy_extension_generation_with_auth(tmp_path: Path) -> None:
    """Проверяет генерацию файлов расширения с учетными данными."""
    proxy = ProxyConfig(
        host="proxy.corp.internal",
        port=3128,
        protocol="http",
        username="testuser",
        password="testpassword",
    )
    ext_dir = tmp_path / "ext_test"
    extension = ChromeProxyExtension(proxy=proxy)
    path = extension.generate(output_dir=ext_dir)

    assert path.exists()
    assert (path / "manifest.json").is_file()
    assert (path / "background.js").is_file()

    # Проверка манифеста
    manifest_data = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["manifest_version"] == 3
    assert "webRequest" in manifest_data["permissions"]
    assert "webRequestAuthProvider" in manifest_data["permissions"]

    # Проверка фонового скрипта
    bg_code = (path / "background.js").read_text(encoding="utf-8")
    assert "proxy.corp.internal" in bg_code
    assert "3128" in bg_code
    assert "testuser" in bg_code
    assert "testpassword" in bg_code
    assert "chrome.webRequest.onAuthRequired" in bg_code

    # Проверка аргументов Chrome
    args = extension.get_chrome_args()
    assert any(a.startswith("--load-extension=") for a in args)
    assert any(a.startswith("--disable-extensions-except=") for a in args)

    extension.cleanup()
    assert not path.exists()


def test_chrome_proxy_extension_without_auth(tmp_path: Path) -> None:
    """Проверяет генерацию расширения для прокси без авторизации."""
    proxy = ProxyConfig(host="1.1.1.1", port=8080, protocol="http")
    extension = ChromeProxyExtension(proxy=proxy)
    path = extension.generate(output_dir=tmp_path / "no_auth_ext")

    bg_code = (path / "background.js").read_text(encoding="utf-8")
    assert "1.1.1.1" in bg_code
    assert "8080" in bg_code
    assert "onAuthRequired" not in bg_code

    extension.cleanup()
    assert not path.exists()


def test_chrome_proxy_extension_context_manager() -> None:
    """Проверяет работу ChromeProxyExtension как контекстного менеджера."""
    proxy = "http://admin:pass@127.0.0.1:8888"
    ext_path: Path
    with ChromeProxyExtension(proxy=proxy) as ext:
        ext_path = ext.path
        assert ext_path.exists()
        assert (ext_path / "manifest.json").exists()

    assert not ext_path.exists()
