import importlib.util
import json
from typing import Any

from chutils.exceptions import OptionalDependencyError

DEFAULT_WEBGL_VENDOR = "Google Inc. (NVIDIA)"
DEFAULT_WEBGL_RENDERER = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
DEFAULT_HARDWARE_CONCURRENCY = 8
DEFAULT_DEVICE_MEMORY = 8


def _get_antidetect_js(
        webgl_vendor: str,
        webgl_renderer: str,
        hardware_concurrency: int,
        device_memory: int,
) -> str:
    """Генерирует JavaScript-инъекцию для скрытия признаков автоматизации браузера с заданными параметрами."""
    vendor_js = json.dumps(webgl_vendor)
    renderer_js = json.dumps(webgl_renderer)
    concurrency_js = int(hardware_concurrency)
    memory_js = int(device_memory)

    return f"""(function() {{
    // 1. Скрытие navigator.webdriver
    const newProto = Object.getPrototypeOf(navigator);
    delete newProto.webdriver;
    Object.defineProperty(navigator, 'webdriver', {{
        get: () => undefined
    }});

    // 2. Рандомизация отпечатка Canvas (шум в getImageData)
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
        const imageData = originalGetImageData.apply(this, arguments);
        // Добавляем минимальный псевдослучайный шум к первому пикселю
        if (imageData.data.length >= 4) {{
            imageData.data[0] = (imageData.data[0] + (Math.random() > 0.5 ? 1 : -1)) % 256;
        }}
        return imageData;
    }};

    // 3. Подмена WebGL параметров видеокарты
    const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {{
        // UNMASKED_VENDOR_WEBGL
        if (parameter === 37445) {{
            return {vendor_js};
        }}
        // UNMASKED_RENDERER_WEBGL
        if (parameter === 37446) {{
            return {renderer_js};
        }}
        return originalGetParameter.apply(this, arguments);
    }};

    // 4. Эмуляция navigator.plugins
    Object.defineProperty(navigator, 'plugins', {{
        get: () => {{
            const mockPlugins = [
                {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
                {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdmgglogagaboenashesapgbbbi', description: 'Google Chrome PDF Viewer' }}
            ];
            return mockPlugins;
        }}
    }});

    // 5. Эмуляция hardwareConcurrency и deviceMemory
    Object.defineProperty(navigator, 'hardwareConcurrency', {{
        get: () => {concurrency_js}
    }});
    Object.defineProperty(navigator, 'deviceMemory', {{
        get: () => {memory_js}
    }});
}})();"""


ANTIDETECT_JS_SCRIPT = _get_antidetect_js(
    DEFAULT_WEBGL_VENDOR,
    DEFAULT_WEBGL_RENDERER,
    DEFAULT_HARDWARE_CONCURRENCY,
    DEFAULT_DEVICE_MEMORY,
)
"""JavaScript-инъекция для скрытия признаков автоматизации браузера (webdriver, Canvas WebGL и др.) с настройками по умолчанию."""


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


async def apply_antidetect_playwright(
        context: Any,
        *,
        webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
        webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
        hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
        device_memory: int = DEFAULT_DEVICE_MEMORY,
) -> None:
    """Применяет JS-инъекции анти-детекта к контексту Playwright.

    Args:
        context: Объект контекста Playwright BrowserContext.
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
    """
    _ensure_playwright()
    script = _get_antidetect_js(
        webgl_vendor=webgl_vendor,
        webgl_renderer=webgl_renderer,
        hardware_concurrency=hardware_concurrency,
        device_memory=device_memory,
    )
    await context.add_init_script(script)


def apply_antidetect_selenium(
        driver: Any,
        *,
        webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
        webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
        hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
        device_memory: int = DEFAULT_DEVICE_MEMORY,
) -> None:
    """Применяет JS-инъекции анти-детекта к сессии Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
    """
    _ensure_selenium()
    script = _get_antidetect_js(
        webgl_vendor=webgl_vendor,
        webgl_renderer=webgl_renderer,
        hardware_concurrency=hardware_concurrency,
        device_memory=device_memory,
    )
    if hasattr(driver, "execute_cdp_cmd"):
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": script}
        )
    else:
        driver.execute_script(script)


def get_browser_launch_args() -> list[str]:
    """Возвращает набор аргументов запуска браузера для скрытия автоматизации.

    Returns:
        Список аргументов командной строки запуска браузера.
    """
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--excludeSwitches=enable-automation",
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
    ]
