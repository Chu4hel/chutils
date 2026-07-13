import importlib.util
from typing import Any

from chutils.exceptions import OptionalDependencyError

# JS-скрипт для скрытия автоматизации и подмены Canvas/WebGL/Plugins/Hardware
ANTIDETECT_JS_SCRIPT = """
(function() {
    // 1. Скрытие navigator.webdriver
    const newProto = Object.getPrototypeOf(navigator);
    delete newProto.webdriver;
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // 2. Рандомизация отпечатка Canvas (шум в getImageData)
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
        const imageData = originalGetImageData.apply(this, arguments);
        // Добавляем минимальный псевдослучайный шум к первому пикселю
        if (imageData.data.length >= 4) {
            imageData.data[0] = (imageData.data[0] + (Math.random() > 0.5 ? 1 : -1)) % 256;
        }
        return imageData;
    };

    // 3. Подмена WebGL параметров видеокарты
    const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        // UNMASKED_VENDOR_WEBGL
        if (parameter === 37445) {
            return 'Google Inc. (NVIDIA)';
        }
        // UNMASKED_RENDERER_WEBGL
        if (parameter === 37446) {
            return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        }
        return originalGetParameter.apply(this, arguments);
    };

    // 4. Эмуляция navigator.plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const mockPlugins = [
                { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdmgglogagaboenashesapgbbbi', description: 'Google Chrome PDF Viewer' }
            ];
            return mockPlugins;
        }
    });

    // 5. Эмуляция hardwareConcurrency и deviceMemory
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8
    });
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8
    });
})();
"""


def _ensure_playwright() -> None:
    if importlib.util.find_spec("playwright") is None:
        raise OptionalDependencyError(
            "Для использования Playwright-функций требуется библиотека 'playwright'.\n"
            "Установите её: pip install chutils[scraping]",
            dependency="playwright",
            hint="Выполните pip install chutils[scraping]"
        )


def _ensure_selenium() -> None:
    if importlib.util.find_spec("selenium") is None:
        raise OptionalDependencyError(
            "Для использования Selenium-функций требуется библиотека 'selenium'.\n"
            "Установите её: pip install chutils[scraping]",
            dependency="selenium",
            hint="Выполните pip install chutils[scraping]"
        )


async def apply_antidetect_playwright(context: Any) -> None:
    """Применяет JS-инъекции анти-детекта к контексту Playwright."""
    _ensure_playwright()
    await context.add_init_script(ANTIDETECT_JS_SCRIPT)


def apply_antidetect_selenium(driver: Any) -> None:
    """Применяет JS-инъекции анти-детекта к сессии Selenium."""
    _ensure_selenium()
    if hasattr(driver, "execute_cdp_cmd"):
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": ANTIDETECT_JS_SCRIPT}
        )
    else:
        driver.execute_script(ANTIDETECT_JS_SCRIPT)


def get_browser_launch_args() -> list[str]:
    """Возвращает набор аргументов запуска браузера для скрытия автоматизации."""
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--excludeSwitches=enable-automation",
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
    ]
