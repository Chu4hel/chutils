from unittest.mock import AsyncMock, MagicMock, patch


# Создаем фиктивный playwright-контекст и selenium-драйвер для тестов
# Потребуется mock_ensure, чтобы исключить ошибки импорта библиотек
@patch("chutils.scraping.humanize.antidetect._ensure_playwright")
@patch("chutils.scraping.humanize.antidetect._ensure_selenium")
def test_antidetect_helpers(mock_ensure_sel: MagicMock, mock_ensure_pw: MagicMock) -> None:
    from chutils.scraping.humanize.antidetect import (
        apply_antidetect_playwright,
        apply_antidetect_selenium,
        get_browser_launch_args,
    )

    # 1. Тестируем аргументы запуска
    args = get_browser_launch_args()
    assert isinstance(args, list)
    assert "--disable-blink-features=AutomationControlled" in args

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
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": script_source}
    )


@patch("chutils.scraping.humanize.antidetect._ensure_playwright")
@patch("chutils.scraping.humanize.antidetect._ensure_selenium")
def test_antidetect_custom_params(mock_ensure_sel: MagicMock, mock_ensure_pw: MagicMock) -> None:
    from chutils.scraping.humanize.antidetect import (
        apply_antidetect_playwright,
        apply_antidetect_selenium,
    )
    import asyncio

    # Тестируем кастомные параметры для Playwright
    pw_context = MagicMock()
    pw_context.add_init_script = AsyncMock()

    asyncio.run(apply_antidetect_playwright(
        pw_context,
        webgl_vendor="AMD Inc.",
        webgl_renderer="Radeon RX 6800",
        hardware_concurrency=16,
        device_memory=32
    ))
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
        device_memory=16
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
    mock_page.add_script_to_evaluate_on_new_document = MagicMock(return_value="mock_cdp_command")

    mock_cdp = MagicMock()
    mock_cdp.page = mock_page

    modules = {
        "nodriver": MagicMock(),
        "nodriver.cdp": mock_cdp,
        "nodriver.cdp.page": mock_page
    }

    with patch.dict(sys.modules, modules):
        from chutils.scraping.humanize.antidetect import apply_antidetect_nodriver
        import asyncio

        tab = MagicMock()
        tab.send = AsyncMock()

        asyncio.run(apply_antidetect_nodriver(
            tab,
            webgl_vendor="NVIDIA Corporation",
            webgl_renderer="NVIDIA GeForce RTX 4090",
            hardware_concurrency=24,
            device_memory=64
        ))

        # Проверяем, что CDP-метод вызван с правильным JS-кодом
        mock_page.add_script_to_evaluate_on_new_document.assert_called_once()
        js_code = mock_page.add_script_to_evaluate_on_new_document.call_args[1]["source"]
        assert '"NVIDIA Corporation"' in js_code
        assert '"NVIDIA GeForce RTX 4090"' in js_code
        assert "24" in js_code
        assert "64" in js_code

        # Проверяем, что команда отправлена вкладке
        tab.send.assert_called_once_with("mock_cdp_command")
