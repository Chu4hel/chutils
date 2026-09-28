"""Кроссбраузерный антидетект на основе механизма предзагрузки WebDriver BiDi."""

from __future__ import annotations

from chutils.logger import setup_logger
from chutils.scraping.bidi.client import BiDiClient
from chutils.scraping.bidi.session import BiDiSession
from chutils.scraping.humanize.config import AntidetectConfig

logger = setup_logger(__name__)


async def apply_antidetect_bidi(
    session_or_client: BiDiSession | BiDiClient,
    config: AntidetectConfig | None = None,
    *,
    contexts: list[str] | None = None,
    sandbox: str | None = None,
) -> str:
    """Применяет маскировку антидетекта через скрипты предзагрузки WebDriver BiDi.

    В отличие от CDP (Chrome DevTools Protocol), WebDriver BiDi является W3C-стандартом
    и поддерживается кроссбраузерно как в движках на базе Chromium (Chrome, Edge), так и в
    Gecko (Firefox), а также в Safari (WebKit).

    Скрипт предзагрузки внедряется в каждый новый контекст и документ до исполнения любого
    пользовательского кода на целевом сайте.

    Args:
        session_or_client: Активная сессия BiDiSession или клиент BiDiClient.
        config: Конфигурация отпечатка AntidetectConfig (если None, используются дефолтные параметры).
        contexts: Опциональный список идентификаторов контекстов, к которым применить скрипт.
            Если None, скрипт применяется ко всем контекстам сессии.
        sandbox: Опциональное имя песочницы JavaScript. По умолчанию None (глобальный контекст окна).

    Returns:
        Идентификатор зарегистрированного скрипта предзагрузки (preload script ID).

    Raises:
        BiDiCommandError: Если браузер вернул ошибку при регистрации скрипта.
        BiDiConnectionError: Если соединение с браузером разорвано.
    """
    effective_config = config or AntidetectConfig()
    init_js = effective_config.get_init_script()

    # Оборачиваем код в декларацию анонимной функции для WebDriver BiDi script.addPreloadScript
    function_declaration = (
        "() => {\n"
        "  // chutils WebDriver BiDi Antidetect Preload Script\n"
        "  try {\n"
        f"    {init_js}\n"
        "  } catch (err) {\n"
        "    console.warn('[chutils BiDi Antidetect] Init script error:', err);\n"
        "  }\n"
        "}"
    )

    if isinstance(session_or_client, BiDiSession):
        script_id = await session_or_client.add_preload_script(
            function_declaration=function_declaration,
            contexts=contexts,
            sandbox=sandbox,
        )
    elif isinstance(session_or_client, BiDiClient):
        script_id = await session_or_client.script_add_preload_script(
            function_declaration=function_declaration,
            contexts=contexts,
            sandbox=sandbox,
        )
    else:
        raise TypeError(
            f"Ожидался BiDiSession или BiDiClient, получен {type(session_or_client).__name__}"
        )

    logger.debug("WebDriver BiDi antidetect preload script успешно зарегистрирован (id=%s)", script_id)
    return script_id
