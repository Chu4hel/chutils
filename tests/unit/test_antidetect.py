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
