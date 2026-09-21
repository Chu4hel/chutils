from unittest.mock import AsyncMock, MagicMock, patch


# Создаем фиктивный playwright-контекст и selenium-драйвер для тестов
# Потребуется mock_ensure, чтобы исключить ошибки импорта библиотек
@patch("chutils.scraping.humanize.antidetect._ensure_playwright")
@patch("chutils.scraping.humanize.antidetect._ensure_selenium")
def test_antidetect_helpers(
    mock_ensure_sel: MagicMock, mock_ensure_pw: MagicMock
) -> None:
    from chutils.scraping.humanize.antidetect import (
        apply_antidetect_playwright,
        apply_antidetect_selenium,
        get_browser_launch_args,
    )

    # 1. Тестируем аргументы запуска
    args = get_browser_launch_args()
    assert isinstance(args, list)
    assert "--disable-blink-features=AutomationControlled" not in args
    assert "--no-first-run" in args

    # 2. Тестируем Playwright-интеграцию
    pw_context = MagicMock()
    pw_context.add_init_script = AsyncMock()

    import asyncio

    asyncio.run(apply_antidetect_playwright(pw_context))
    pw_context.add_init_script.assert_called_once()

    # Проверяем, что JS скрипт переопределяет webdriver
    script_source = pw_context.add_init_script.call_args[0][0]
    assert "navigator.webdriver" in script_source
    assert "getImageData" in script_source

    # 3. Тестируем Selenium-интеграцию (Chromium с поддержкой CDP)
    sel_driver = MagicMock()
    sel_driver.execute_cdp_cmd = MagicMock()

    apply_antidetect_selenium(sel_driver)
    sel_driver.execute_cdp_cmd.assert_called_once_with(
        "Page.addScriptToEvaluateOnNewDocument", {"source": script_source}
    )


@patch("chutils.scraping.humanize.antidetect._ensure_playwright")
@patch("chutils.scraping.humanize.antidetect._ensure_selenium")
def test_antidetect_custom_params(
    mock_ensure_sel: MagicMock, mock_ensure_pw: MagicMock
) -> None:
    import asyncio

    from chutils.scraping.humanize.antidetect import (
        apply_antidetect_playwright,
        apply_antidetect_selenium,
    )

    # Тестируем кастомные параметры для Playwright
    pw_context = MagicMock()
    pw_context.add_init_script = AsyncMock()

    asyncio.run(
        apply_antidetect_playwright(
            pw_context,
            webgl_vendor="AMD Inc.",
            webgl_renderer="Radeon RX 6800",
            hardware_concurrency=16,
            device_memory=32,
        )
    )
    pw_context.add_init_script.assert_called_once()
    script_source = pw_context.add_init_script.call_args[0][0]

    assert '"AMD Inc."' in script_source
    assert '"Radeon RX 6800"' in script_source
    assert "hardwareConcurrency" in script_source
    assert "16" in script_source
    assert "deviceMemory" in script_source
    assert "32" in script_source

    # Тестируем кастомные параметры для Selenium
    sel_driver = MagicMock()
    sel_driver.execute_cdp_cmd = MagicMock()

    apply_antidetect_selenium(
        sel_driver,
        webgl_vendor="Intel",
        webgl_renderer="Intel UHD Graphics",
        hardware_concurrency=4,
        device_memory=16,
    )
    sel_driver.execute_cdp_cmd.assert_called_once()
    sel_script = sel_driver.execute_cdp_cmd.call_args[0][1]["source"]

    assert '"Intel"' in sel_script
    assert '"Intel UHD Graphics"' in sel_script
    assert "4" in sel_script
    assert "16" in sel_script


@patch("chutils.scraping.humanize.antidetect._ensure_nodriver")
def test_antidetect_nodriver(mock_ensure: MagicMock) -> None:
    import sys

    mock_page = MagicMock()
    mock_page.add_script_to_evaluate_on_new_document = MagicMock(
        return_value="mock_cdp_command"
    )

    mock_cdp = MagicMock()
    mock_cdp.page = mock_page

    modules = {
        "nodriver": MagicMock(),
        "nodriver.cdp": mock_cdp,
        "nodriver.cdp.page": mock_page,
    }

    with patch.dict(sys.modules, modules):
        import asyncio

        from chutils.scraping.humanize.antidetect import apply_antidetect_nodriver

        tab = MagicMock()
        tab.send = AsyncMock()

        asyncio.run(
            apply_antidetect_nodriver(
                tab,
                webgl_vendor="NVIDIA Corporation",
                webgl_renderer="NVIDIA GeForce RTX 4090",
                hardware_concurrency=24,
                device_memory=64,
            )
        )

        # Проверяем, что CDP-метод вызван с правильным JS-кодом
        mock_page.add_script_to_evaluate_on_new_document.assert_called_once()
        js_code = mock_page.add_script_to_evaluate_on_new_document.call_args[1][
            "source"
        ]
        assert '"NVIDIA Corporation"' in js_code
        assert '"NVIDIA GeForce RTX 4090"' in js_code
        assert "24" in js_code
        assert "64" in js_code

        # Проверяем, что команда отправлена вкладке
        tab.send.assert_called_once_with("mock_cdp_command")


def test_antidetect_js_tampering_protection() -> None:
    from chutils.scraping.humanize.antidetect import _get_antidetect_js

    js = _get_antidetect_js("Custom Vendor", "Custom Renderer", 8, 16)

    # 1. Проверка маскировки [native code] для Function.prototype.toString
    assert "[native code]" in js
    assert "makeNative" in js or "toString" in js

    # 2. Проверка одновременного патчинга WebGL1 и WebGL2
    assert "WebGLRenderingContext" in js
    assert "WebGL2RenderingContext" in js
    assert "37445" in js  # UNMASKED_VENDOR_WEBGL
    assert "37446" in js  # UNMASKED_RENDERER_WEBGL
    assert '"Custom Vendor"' in js
    assert '"Custom Renderer"' in js

    # 3. Проверка синхронизации Permissions API и Notification
    assert "permissions.query" in js
    assert "Notification.permission" in js

    # 4. Проверка корректного удаления / маскировки navigator.webdriver
    assert "webdriver" in js
    assert "Navigator.prototype" in js or "Object.getPrototypeOf(navigator)" in js


@patch("chutils.scraping.humanize.antidetect._ensure_nodriver")
def test_antidetect_nodriver_stealth_minimal(mock_ensure: MagicMock) -> None:
    import asyncio
    import sys

    mock_page = MagicMock()
    mock_page.add_script_to_evaluate_on_new_document = MagicMock(
        return_value="mock_cdp_command"
    )

    mock_cdp = MagicMock()
    mock_cdp.page = mock_page

    modules = {
        "nodriver": MagicMock(),
        "nodriver.cdp": mock_cdp,
        "nodriver.cdp.page": mock_page,
    }

    with patch.dict(sys.modules, modules):
        from chutils.scraping.humanize.antidetect import apply_antidetect_nodriver

        tab = MagicMock()
        tab.send = AsyncMock()

        asyncio.run(apply_antidetect_nodriver(tab, stealth_minimal=True))

        mock_page.add_script_to_evaluate_on_new_document.assert_called_once()
        js_code = mock_page.add_script_to_evaluate_on_new_document.call_args[1][
            "source"
        ]

        # В минимальном режиме не должны подменяться Canvas и WebGL
        assert "isMinimal = true" in js_code
        assert "webdriver" in js_code
        assert "permissions.query" in js_code


def test_browser_launch_args_enhanced() -> None:
    from chutils.scraping.humanize.antidetect import get_browser_launch_args

    args = get_browser_launch_args()
    assert "--disable-blink-features=AutomationControlled" not in args
    assert "--no-first-run" in args
    assert "--no-default-browser-check" in args
    assert "--password-store=basic" in args
