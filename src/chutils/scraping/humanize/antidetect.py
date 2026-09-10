import importlib.util
import json
import re
from typing import Any

from chutils.exceptions import OptionalDependencyError

DEFAULT_WEBGL_VENDOR = "Google Inc. (NVIDIA)"
DEFAULT_WEBGL_RENDERER = (
    "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
)
DEFAULT_HARDWARE_CONCURRENCY = 8
DEFAULT_DEVICE_MEMORY = 8


def get_client_hints(user_agent: str | None = None) -> dict[str, Any]:
    """Генерирует словарь согласованных Client Hints (navigator.userAgentData) на основе User-Agent.

    Args:
        user_agent: Строка User-Agent. Если None, используется стандартный Chrome на Windows.

    Returns:
        Словарь с параметрами Client Hints: platform, mobile, brands.
    """
    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    platform = "Windows"
    if "Macintosh" in ua or "Mac OS X" in ua:
        platform = "macOS"
    elif "Android" in ua:
        platform = "Android"
    elif "Linux" in ua:
        platform = "Linux"
    elif "iPhone" in ua or "iPad" in ua:
        platform = "iOS"

    mobile = platform in ("Android", "iOS") or "Mobile" in ua

    # Извлечение версии Chrome
    chrome_match = re.search(r"Chrome/(\d+)", ua)
    chrome_version = chrome_match.group(1) if chrome_match else "120"

    brands = [
        {"brand": "Not_A Brand", "version": "8"},
        {"brand": "Chromium", "version": chrome_version},
        {"brand": "Google Chrome", "version": chrome_version},
    ]

    return {
        "platform": platform,
        "mobile": mobile,
        "brands": brands,
    }


def _get_antidetect_js(
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    stealth_minimal: bool = False,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
) -> str:
    """Генерирует JavaScript-инъекцию для скрытия признаков автоматизации браузера с заданными параметрами."""
    vendor_js = json.dumps(webgl_vendor)
    renderer_js = json.dumps(webgl_renderer)
    concurrency_js = int(hardware_concurrency)
    memory_js = int(device_memory)
    minimal_js = "true" if stealth_minimal else "false"
    seed_js = json.dumps(str(session_seed))
    hints_js = json.dumps(client_hints) if client_hints is not None else "null"

    return f"""(function() {{
    // Утилита для маскировки функций под нативные [native code]
    const makeNative = (fn, name) => {{
        try {{
            Object.defineProperty(fn, 'name', {{ value: name, configurable: true }});
            const fnToString = function toString() {{ return `function ${{name}}() {{ [native code] }}`; }};
            fn.toString = fnToString;
            fn.toString.toString = function toString() {{ return "function toString() {{ [native code] }}"; }};
        }} catch (e) {{}}
        return fn;
    }};

    // Детерминированный LCG PRNG для Canvas шума
    const sessionSeed = {seed_js};
    let seedNum = 0;
    for (let i = 0; i < sessionSeed.length; i++) {{
        seedNum = ((seedNum << 5) - seedNum + sessionSeed.charCodeAt(i)) & 0xffffffff;
    }}
    const pseudoRandom = (offset) => {{
        const x = Math.sin(seedNum + offset) * 10000;
        return x - Math.floor(x);
    }};

    // 1. Скрытие и очистка navigator.webdriver
    const navProto = Navigator.prototype || Object.getPrototypeOf(navigator);
    try {{
        delete navProto.webdriver;
    }} catch (e) {{}}
    try {{
        delete navigator.webdriver;
    }} catch (e) {{}}
    try {{
        const webdriverGetter = makeNative(() => undefined, 'get webdriver');
        Object.defineProperty(navProto, 'webdriver', {{
            get: webdriverGetter,
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    const isMinimal = {minimal_js};

    if (!isMinimal) {{
        // 2. Рандомизация отпечатка Canvas с детерминированным шумом
        try {{
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            const patchedGetImageData = function getImageData(x, y, w, h) {{
                const imageData = originalGetImageData.apply(this, arguments);
                if (imageData && imageData.data && imageData.data.length >= 4) {{
                    const delta = pseudoRandom(x + y * 57) > 0.5 ? 1 : -1;
                    imageData.data[0] = (imageData.data[0] + delta) % 256;
                }}
                return imageData;
            }};
            CanvasRenderingContext2D.prototype.getImageData = makeNative(patchedGetImageData, 'getImageData');
        }} catch (e) {{}}

        // 3. Подмена WebGL параметров видеокарты (WebGL 1 и WebGL 2)
        const webglContexts = [];
        if (typeof WebGLRenderingContext !== 'undefined') webglContexts.push(WebGLRenderingContext);
        if (typeof WebGL2RenderingContext !== 'undefined') webglContexts.push(WebGL2RenderingContext);

        for (const ctx of webglContexts) {{
            try {{
                const originalGetParameter = ctx.prototype.getParameter;
                const patchedGetParameter = function getParameter(parameter) {{
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
                ctx.prototype.getParameter = makeNative(patchedGetParameter, 'getParameter');
            }} catch (e) {{}}
        }}
    }}

    // 4. Эмуляция navigator.plugins
    try {{
        const pluginsGetter = makeNative(() => {{
            return [
                {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
                {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdmgglogagaboenashesapgbbbi', description: 'Google Chrome PDF Viewer' }}
            ];
        }}, 'get plugins');
        Object.defineProperty(navigator, 'plugins', {{
            get: pluginsGetter,
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    // 5. Эмуляция hardwareConcurrency и deviceMemory
    try {{
        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: makeNative(() => {concurrency_js}, 'get hardwareConcurrency'),
            enumerable: true,
            configurable: true,
        }});
        Object.defineProperty(navigator, 'deviceMemory', {{
            get: makeNative(() => {memory_js}, 'get deviceMemory'),
            enumerable: true,
            configurable: true,
        }});
    }} catch (e) {{}}

    // 6. Синхронизация Permissions API и Notification
    try {{
        if (navigator.permissions && navigator.permissions.query) {{
            const origQuery = navigator.permissions.query;
            const patchedQuery = function query(parameters) {{
                if (parameters && parameters.name === 'notifications' && typeof Notification !== 'undefined') {{
                    return Promise.resolve({{
                        state: Notification.permission === 'default' ? 'prompt' : Notification.permission,
                        onchange: null
                    }});
                }}
                return origQuery.apply(this, arguments);
            }};
            navigator.permissions.query = makeNative(patchedQuery, 'query');
        }}
    }} catch (e) {{}}

    // 7. Защита от извлечения прототипов через скрытый iframe (Cross-realm prototype inspection)
    try {{
        const originalCreateElement = Document.prototype.createElement;
        Document.prototype.createElement = makeNative(function createElement(tagName, options) {{
            const element = originalCreateElement.apply(this, arguments);
            if (element && typeof tagName === 'string' && tagName.toLowerCase() === 'iframe') {{
                element.addEventListener('load', function() {{
                    try {{
                        if (element.contentWindow) {{
                            const cw = element.contentWindow;
                            if (cw.Function && cw.Function.prototype) {{
                                cw.Function.prototype.toString = window.Function.prototype.toString;
                            }}
                            if (cw.navigator) {{
                                Object.defineProperty(cw.navigator, 'webdriver', {{
                                    get: makeNative(() => undefined, 'get webdriver'),
                                    enumerable: true,
                                    configurable: true
                                }});
                            }}
                        }}
                    }} catch (err) {{}}
                }});
            }}
            return element;
        }}, 'createElement');
    }} catch (e) {{}}

    // 8. Эмуляция Client Hints (navigator.userAgentData) при наличии hints
    const clientHintsData = {hints_js};
    if (clientHintsData) {{
        try {{
            const uaData = {{
                brands: clientHintsData.brands || [],
                mobile: Boolean(clientHintsData.mobile),
                platform: clientHintsData.platform || 'Windows',
                getHighEntropyValues: makeNative(function getHighEntropyValues(hints) {{
                    return Promise.resolve({{
                        brands: clientHintsData.brands || [],
                        mobile: Boolean(clientHintsData.mobile),
                        platform: clientHintsData.platform || 'Windows',
                        architecture: 'x86',
                        bitness: '64',
                        model: '',
                        platformVersion: '15.0.0',
                        uaFullVersion: (clientHintsData.brands && clientHintsData.brands[2] ? clientHintsData.brands[2].version : '120') + '.0.0.0'
                    }});
                }}, 'getHighEntropyValues')
            }};
            Object.defineProperty(navigator, 'userAgentData', {{
                get: makeNative(() => uaData, 'get userAgentData'),
                enumerable: true,
                configurable: true
            }});
        }} catch (e) {{}}
    }}
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
            hint="Выполните pip install chutils[scraping]",
        )


def _ensure_selenium() -> None:
    if importlib.util.find_spec("selenium") is None:
        raise OptionalDependencyError(
            "Для использования Selenium-функций требуется библиотека 'selenium'.\n"
            "Установите её: pip install chutils[scraping]",
            dependency="selenium",
            hint="Выполните pip install chutils[scraping]",
        )


def _ensure_nodriver() -> None:
    if importlib.util.find_spec("nodriver") is None:
        raise OptionalDependencyError(
            "Для использования nodriver-функций требуется библиотека 'nodriver'.\n"
            "Установите её: pip install nodriver",
            dependency="nodriver",
            hint="Выполните pip install nodriver",
        )


async def apply_antidetect_playwright(
    context: Any,
    *,
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
) -> None:
    """Применяет JS-инъекции анти-детекта к контексту Playwright.

    Args:
        context: Объект контекста Playwright BrowserContext.
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
        session_seed: Сид для детерминированного шума Canvas.
        client_hints: Дополнительные параметры Client Hints (navigator.userAgentData).
    """
    _ensure_playwright()
    script = _get_antidetect_js(
        webgl_vendor=webgl_vendor,
        webgl_renderer=webgl_renderer,
        hardware_concurrency=hardware_concurrency,
        device_memory=device_memory,
        session_seed=session_seed,
        client_hints=client_hints,
    )
    await context.add_init_script(script)


def apply_antidetect_selenium(
    driver: Any,
    *,
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
) -> None:
    """Применяет JS-инъекции анти-детекта к сессии Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
        session_seed: Сид для детерминированного шума Canvas.
        client_hints: Дополнительные параметры Client Hints (navigator.userAgentData).
    """
    _ensure_selenium()
    script = _get_antidetect_js(
        webgl_vendor=webgl_vendor,
        webgl_renderer=webgl_renderer,
        hardware_concurrency=hardware_concurrency,
        device_memory=device_memory,
        session_seed=session_seed,
        client_hints=client_hints,
    )
    if hasattr(driver, "execute_cdp_cmd"):
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument", {"source": script}
        )
    else:
        driver.execute_script(script)


async def apply_antidetect_nodriver(
    tab: Any,
    *,
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    stealth_minimal: bool = False,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
) -> None:
    """Применяет JS-инъекции анти-детекта к вкладке (Tab) nodriver.

    Args:
        tab: Объект вкладки nodriver Tab.
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
        stealth_minimal: Если True, не накладывать синтетический шум на Canvas и не подменять WebGL,
            сохраняя естественный отпечаток установленного браузера Google Chrome.
        session_seed: Сид для детерминированного шума Canvas.
        client_hints: Дополнительные параметры Client Hints (navigator.userAgentData).
    """
    _ensure_nodriver()
    from nodriver.cdp import page

    script = _get_antidetect_js(
        webgl_vendor=webgl_vendor,
        webgl_renderer=webgl_renderer,
        hardware_concurrency=hardware_concurrency,
        device_memory=device_memory,
        stealth_minimal=stealth_minimal,
        session_seed=session_seed,
        client_hints=client_hints,
    )
    await tab.send(page.add_script_to_evaluate_on_new_document(source=script))


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
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
    ]
