# Имитация поведения человека и анти-детект (chutils.scraping.humanize)

Модуль `chutils.scraping.humanize` разработан для имитации естественного человеческого поведения при автоматизации
браузеров и обхода систем защиты от ботов. Он предоставляет математические алгоритмы генерации человекоподобных
траекторий мыши, неравномерного ввода текста, случайных пауз, а также средства настройки анти-детект профилей для
Playwright и Selenium.

Данный модуль поставляется как опциональный экстра-пакет `chutils[scraping]`.

---

## Установка

Для работы с интеграциями для Playwright и Selenium установите пакет с поддержкой экстра-зависимостей:

```bash
pip install "chutils[scraping]"
```

Для использования антидетект-браузера нового поколения Camoufox (Playwright Firefox с C++ инъекциями):

```bash
pip install "chutils[camoufox]"
```

*Примечание: Если вам нужны только математические генераторы (траектории, задержки, опечатки), вы можете использовать их
без установки дополнительных библиотек автоматизации.*

---

## 1. Математические генераторы

Математический модуль работает автономно и не требует внешних зависимостей.

### Физический генератор траекторий WindMouse (`WindMouseGenerator`)

Имитирует движение руки человека на основе физической модели (гравитация, случайный ветер/дрейф, инерция и микродоводка у цели). Обеспечивает наилучший обход поведенческого антифрода (Cloudflare, DataDome, reCAPTCHA).

```python
from chutils.scraping.humanize import WindMouseGenerator

generator = WindMouseGenerator(gravity=9.0, wind=3.0)
start_point = (100, 150)
end_point = (500, 450)

# Генерирует список кортежей (x, y, delay) с реалистичными таймингами
points = generator.generate(start_point, end_point)
```

### Генератор траекторий Безье (`BezierCurveGenerator`)

Позволяет рассчитывать плавные кривые перемещения мыши с естественным ускорением в начале и замедлением в конце
движения (ease-in-out).

```python
from chutils.scraping.humanize import BezierCurveGenerator

generator = BezierCurveGenerator()
start_point = (100, 150)
end_point = (500, 450)

# Генерирует список из 30 координат (x, y)
points = generator.generate(start_point, end_point, steps=30)
```

### Генератор задержек с джиттером (`JitterDelayGenerator`)

Рассчитывает задержки на основе логнормального или нормального распределения. Большинство задержек будут короткими, но
изредка будут возникать естественные длинные паузы.

```python
from chutils.scraping.humanize import JitterDelayGenerator

delay_gen = JitterDelayGenerator(strategy="lognormal", jitter=0.15)
base_delay = 2.0

# Возвращает случайное число вокруг 2.0
delay = delay_gen.generate(base_delay)
```

### Генератор опечаток клавиатуры (`KeyboardTypoGenerator`)

Генерирует последовательности нажатий клавиш, включая случайные опечатки на близкорасположенных QWERTY-клавишах, с
последующим стиранием опечаток через Backspace и вводом правильных букв.

```python
from chutils.scraping.humanize import KeyboardTypoGenerator

typo_gen = KeyboardTypoGenerator()
sequence = typo_gen.generate_sequence("Hello!", error_rate=0.1)

# Возвращает список объектов TypoAction (action='type'|'backspace', char='...')
```

---

## 2. Имитация мыши, скролла и клавиатуры

Модуль предоставляет обертки для Playwright (асинхронные) и Selenium (синхронные).

### Обертки для Playwright (асинхронные)

```python
from chutils.scraping.humanize import (
    async_move_mouse,
    async_click,
    async_scroll_to,
    async_type_text,
    async_human_sleep,
)

# Плавное движение мыши (по умолчанию используется WindMouse или Bezier)
await async_move_mouse(page, x=400, y=300, start=(0, 0), algorithm="windmouse")

# Реалистичный клик по селектору или координатам (с наведением, микропаузами и удержанием)
await async_click(page, selector="#submit-btn")

# Плавный скролл страницы по оси Y
await async_scroll_to(page, x=0, y=800)

# Ввод текста со скоростью 40 WPM и вероятностью опечаток 5%
await async_type_text(
    page, selector="#username", text="my_user_login", error_rate=0.05, speed_wpm=40.0
)

# Асинхронная пауза "на чтение" от 1 до 3 секунд
await async_human_sleep(1.0, 3.0)
```

### Обертки для nodriver (асинхронные)

Те же асинхронные функции поддерживают автоматизацию на базе `nodriver` (все действия транслируются напрямую через CDP протокол):

```python
from chutils.scraping.humanize import (
    async_move_mouse,
    async_click,
    async_scroll_to,
    async_type_text,
)

# Плавное движение мыши (транслируется в CDP dispatchMouseEvent)
await async_move_mouse(tab, x=400, y=300, start=(0, 0), algorithm="windmouse")

# Реалистичный клик через CDP с паузой фокусировки и настраиваемым удержанием (hold_time)
await async_click(tab, x=400, y=300, hold_time=(0.05, 0.12))

# Плавный скролл страницы через JS evaluate
await async_scroll_to(tab, x=0, y=800)

# Ввод текста с опечатками и физиологической задержкой нажатия клавиш (key_hold_time)
await async_type_text(
    tab,
    selector="#username",
    text="my_user_login",
    error_rate=0.05,
    speed_wpm=40.0,
    key_hold_time=(0.04, 0.09),
)
```

### Обертки для Selenium (синхронные)

```python
from chutils.scraping.humanize import (
    move_mouse,
    click,
    scroll_to,
    type_text,
    human_sleep,
)

# Плавное движение мыши с физической моделью WindMouse
move_mouse(driver, x=400, y=300, start=(0, 0), algorithm="windmouse")

# Реалистичный клик
click(driver, selector="#submit-btn")

# Плавный скролл
scroll_to(driver, x=0, y=800)

# Ввод текста
type_text(
    driver, selector="#username", text="my_user_login", error_rate=0.05, speed_wpm=40.0
)

# Синхронная пауза
human_sleep(1.0, 3.0)
```

---

## 3. Анти-детект и маскировка браузеров

Для минимизации вероятности обнаружения бот-детектором (например, Cloudflare, Akamai, Imperva) модуль предоставляет
JS-инъекции и флаги запуска.

### JS-инъекции анти-детекта

Инъекция скрывает автоматизацию на низком уровне JavaScript до загрузки веб-страницы:

- Защита от детекта вмешательства (Anti-Tampering): все подмененные методы возвращают `[native code]` при вызове `Function.prototype.toString`.
- Удаляет и переопределяет свойство `navigator.webdriver` с сохранением корректных атрибутов дескриптора.
- Добавляет минимальный псевдослучайный шум к пикселям Canvas (`getImageData`), искажая статический Canvas-отпечаток.
- Маскирует WebGL параметры видеокарты одновременно для `WebGLRenderingContext` (WebGL 1) и `WebGL2RenderingContext` (WebGL 2).
- Синхронизирует `navigator.permissions.query` с `Notification.permission`.
- Эмулирует список установленных системных плагинов и количество ядер процессора.

```python
from chutils.scraping.humanize import (
    apply_antidetect_playwright,
    apply_antidetect_selenium,
    apply_antidetect_nodriver,
)

# Для Playwright (применяется к BrowserContext)
# Все параметры ниже опциональны (по умолчанию эмулируется NVIDIA RTX 3060, 8 ядер CPU и 8 ГБ RAM):
await apply_antidetect_playwright(
    context,
    webgl_vendor="AMD Inc.",
    webgl_renderer="Radeon RX 6800",
    hardware_concurrency=12,
    device_memory=16,
)

# Для Selenium (применяется к WebDriver через CDP)
apply_antidetect_selenium(
    driver,
    webgl_vendor="Intel",
    webgl_renderer="Intel UHD Graphics",
    hardware_concurrency=4,
    device_memory=8,
)

# Для nodriver (применяется к вкладке Tab через CDP протокол)
# Флаг stealth_minimal=True отключает синтетический шум Canvas/WebGL,
# сохраняя естественный отпечаток установленного браузера Google Chrome:
await apply_antidetect_nodriver(
    tab,
    stealth_minimal=True,
)
```

### Флаги запуска браузера (`get_browser_launch_args`)

Возвращает оптимизированный список аргументов для запуска Chromium (включая подавление первого запуска, детекта автоматизации и предупреждений профиля):

```python
from chutils.scraping.humanize import get_browser_launch_args

# Возвращает список флагов запуска, таких как:
# '--disable-blink-features=AutomationControlled', '--no-first-run', '--password-store=basic' и т.д.
launch_flags = get_browser_launch_args()
```

---

## 4. Прогрев профилей (ProfileWarmer)

Инструмент `ProfileWarmer` (асинхронный для Playwright/nodriver) и `SyncProfileWarmer` (синхронный для Selenium) предназначены для прогрева браузерных профилей (сохраняемых в директории `user_data_dir`) путем посещения трастовых веб-ресурсов и симуляции действий реального пользователя (скроллинг, движения курсора по траектории Безье, паузы, клики по внутренним ссылкам).

Это позволяет сформировать историю посещений, нагулять cookies и заполнить localStorage/sessionStorage, повышая Trust Score сессии браузера.

### Асинхронный прогрев (Playwright и nodriver)

```python
from chutils.scraping.humanize import ProfileWarmer

# Для Playwright (принимает объект Page)
# или для nodriver (принимает объект Tab)
warmer = ProfileWarmer(page_or_tab)

# 1. Обычный прогрев по сайтам (посетит 3 случайных сайта из встроенного списка)
await warmer.warm_up(
    sites_count=3, duration_per_site=(10.0, 20.0), click_random_links=True
)

# 2. Органический поиск (Google / Yandex Search Surfing)
# Вводит запросы из банка категорий ('tech', 'news', 'science', 'lifestyle'),
# скроллит выдачу, находит органические результаты (исключая рекламу и внутренние ссылки),
# переходит на целевой сайт и имитирует естественное чтение/скроллинг
await warmer.warm_up_search(
    category="tech",
    queries_count=2,
    search_engine="google",
    click_result=True,
    surf_result_duration=(10.0, 25.0),
)

# 3. Сохранение прогретой сессии в .chprofile через ProfileManager
await warmer.save_profile("warmed_profile.chprofile", password="secret_password")
```

### Синхронный прогрев (Selenium)

```python
from chutils.scraping.humanize import SyncProfileWarmer

# Принимает экземпляр Selenium WebDriver
warmer = SyncProfileWarmer(driver)

# Обычный прогрев
warmer.warm_up(sites_count=3, duration_per_site=(10.0, 20.0), click_random_links=True)

# Органический поиск в Selenium
warmer.warm_up_search(
    queries=["python async tutorials", "fastapi performance"],
    search_engine="google",
    click_result=True,
    surf_result_duration=(5.0, 15.0),
)

# Сохранение прогретой сессии
warmer.save_profile("warmed_selenium.chprofile", password="secret_password")
```

### Вспомогательные утилиты органического поиска

```python
from chutils.scraping.humanize import (
    DEFAULT_SEARCH_QUERIES,
    get_random_search_queries,
    get_search_engine_config,
    is_organic_url,
)

# Получение реалистичных запросов по категории
queries = get_random_search_queries(count=3, category="tech")

# Проверка, является ли ссылка органической (отсекает Google Ads, Yandex Direct и трекинговые редиректы)
assert is_organic_url("https://en.wikipedia.org/wiki/Python", "google")
assert not is_organic_url("https://googleads.g.doubleclick.net/...", "google")
```

---

## 5. Параллельный скрапинг (chutils.scraping.concurrency)

Модуль `chutils.scraping.concurrency` предоставляет инструменты для параллельного скрапинга с дедупликацией, приоритизацией, доменными лимитами (`DomainRateLimiter`), пулом воркеров (`WorkerPool`) и автоматическим экспортом Prometheus-метрических показателей (`chutils_queue_pending_size`, `chutils_tasks_processed_total`, `chutils_task_execution_duration_seconds`, `chutils_worker_pool_active_workers`).

```python
import asyncio
from chutils.scraping.concurrency import (
    DomainRateLimiter,
    InMemoryTaskQueue,
    ScrapingTask,
    WorkerPool,
)


async def main():
    # Очередь с включенным трекингом Prometheus-метрических показателей
    queue = InMemoryTaskQueue(name="wiki_queue", enable_metrics=True)
    await queue.push(
        ScrapingTask(url="https://ru.wikipedia.org/wiki/Python", priority=5)
    )

    limiter = DomainRateLimiter(
        default_delay=0.5, domain_rules={"*.wikipedia.org": 1.0}
    )

    async def process(task):
        print(f"Обработка: {task.url}")

    pool = WorkerPool(queue=queue, handler=process, limiter=limiter, max_workers=2)
    await pool.run_until_complete()
```



---

## 6. Перенос профилей и сессий браузеров (`ProfileManager`)

Класс `ProfileManager` (`chutils.scraping.ProfileManager`) позволяет легко экспортировать, сохранять, конвертировать и импортировать авторизованные сессии и профили между `Playwright`, `nodriver` и `Selenium`.

```python
from chutils.scraping import ProfileManager

# 1. Экспорт сессии из Playwright
profile = await ProfileManager.export_from_playwright(browser_context)

# 2. Сохранение в защищенный .chprofile файл
ProfileManager.save(profile, "my_session.chprofile", password="secret_password")

# 3. Загрузка и импорт сессии в nodriver
loaded_profile = ProfileManager.load("my_session.chprofile", password="secret_password")
await ProfileManager.import_to_nodriver(nodriver_tab, loaded_profile)
```

---

## 7. Конфигурация и парсинг прокси (`ProxyConfig`, `parse_proxy`)

Модуль `chutils.scraping.proxy` предоставляет Pydantic-модель `ProxyConfig` и функцию `parse_proxy` для гибкой работы с прокси-серверами, поддерживая аутентификацию и форматы аргументов для различных браузеров:

```python
from chutils.scraping import ProxyConfig, parse_proxy

# Парсинг строки любого распространенного формата
proxy = parse_proxy("socks5://user:pass@proxy.example.com:1080")
# Или из колоночной строки
proxy2 = parse_proxy("192.168.1.100:8080:login:password")

# Получение параметров для различных движков:
# Playwright
pw_proxy = proxy.to_playwright()  # {"server": "socks5://...", "username": "user", ...}

# Chrome CLI (Chromium/nodriver)
chrome_arg = proxy.to_chrome_arg()  # "--proxy-server=socks5://proxy.example.com:1080"

# Selenium Capabilities
selenium_proxy = proxy.to_selenium()  # {"proxyType": "MANUAL", "httpProxy": ..., ...}
```

### Авторизация прокси в nodriver / Chromium через расширение (`ChromeProxyExtension`)

Так как флаг Chromium `--proxy-server` не поддерживает передачу логина и пароля, `ChromeProxyExtension` автоматически формирует временное Manifest v3 расширение с обработчиком `chrome.webRequest.onAuthRequired`:

```python
from chutils.scraping import ChromeProxyExtension

# Создание расширения в контекстном менеджере с авто-очисткой
with ChromeProxyExtension("http://user:pass@1.2.3.4:8080") as ext:
    # Получение аргументов для запуска Chromium / nodriver
    args = ext.get_chrome_args()
    # ['--load-extension=...', '--disable-extensions-except=...']
    # nodriver.start(browser_args=args)
```

### Локальный асинхронный туннель-форвардер (`AsyncProxyTunnel`)

Для headless-окружений, где расширения браузера могут быть отключены, используется легковесный асинхронный локальный сервер `AsyncProxyTunnel`. Браузер подключается к локальному адресу без авторизации, а туннель прозрачно инжектирует заголовок `Proxy-Authorization` в удаленный HTTP/SOCKS5 прокси:

```python
from chutils.scraping import AsyncProxyTunnel

# Запуск туннеля
async with AsyncProxyTunnel("socks5://user:pass@remote-proxy.com:1080") as tunnel:
    # Браузер направляется на локальный туннель:
    browser_arg = tunnel.to_chrome_arg()  # "--proxy-server=http://127.0.0.1:54321"
    # nodriver.start(browser_args=[browser_arg])
```

### Пул прокси и стратегии ротации (`ProxyPool`)

Класс `ProxyPool` управляет набором прокси, обеспечивая потокобезопасную ротацию, закрепление сессий и автоматический вывод из строя сбойных узлов (failover):

```python
from chutils.scraping import ProxyPool, check_proxy

# Инициализация пула с авто-баном при 3 сбоях на 5 минут
pool = ProxyPool(
    proxies=[
        "http://user:pass@proxy1.com:8080",
        "socks5://user:pass@proxy2.com:1080",
        "proxy3.com:8080:login:pass",
    ],
    strategy="sticky",  # 'round_robin', 'random', 'sticky', 'failover'
    sticky_ttl=600.0,
    ban_timeout=300.0,
    max_fails=3,
)

# Получение прокси для конкретной пользовательской сессии
proxy = pool.get_next(key="session_user_42")

try:
    # Выполнение запроса через прокси...
    pool.report_success(proxy)
except Exception:
    # При ошибке фиксируем сбой
    pool.report_failure(proxy)

# Проверка работоспособности и замер задержки (Health Check)
health = check_proxy(proxy, timeout=5.0)
if health.is_alive:
    print(f"IP: {health.external_ip}, Latency: {health.latency_ms} ms")
```

### Фабрики адаптеров для браузерных движков (`nodriver_proxy`, `get_playwright_proxy`, `get_selenium_proxy`)

Для быстрого подключения прокси (как с авторизацией, так и без) к браузерам предоставляются специализированные функции-фабрики и контекстные менеджеры:

```python
from chutils.scraping import (
    async_nodriver_proxy,
    get_playwright_proxy,
    get_selenium_proxy,
    nodriver_proxy,
)

# 1. Playwright
browser = await playwright.chromium.launch(
    proxy=get_playwright_proxy("http://user:pass@1.2.3.4:8080")
)

# 2. Selenium
get_selenium_proxy("http://1.2.3.4:8080", options=chrome_options)

# 3. nodriver (через синхронный контекстный менеджер с расширением)
with nodriver_proxy("http://user:pass@1.2.3.4:8080") as browser_args:
    browser = await nodriver.start(browser_args=browser_args)

# 4. nodriver (через асинхронный туннель)
async with async_nodriver_proxy(
    "socks5://user:pass@1.2.3.4:1080", mode="tunnel"
) as browser_args:
    browser = await nodriver.start(browser_args=browser_args)
```

---

## 8. Автотестирование парсеров и моки страниц (`chutils.scraping.testing`)

Модуль `chutils.scraping.testing` предоставляет легковесные in-memory моки страниц для мгновенного модульного тестирования парсеров без необходимости запуска реального браузера:

### Мок nodriver (`MockNodriverTab`)

```python
from chutils.scraping import MockNodriverTab

tab = MockNodriverTab("""
    <div class="product">
        <h1 class="title">Ноутбук</h1>
        <span class="price">99990 ₽</span>
    </div>
""")

# Тестирование парсера nodriver
title = await tab.select(".title")
print(title.text)  # "Ноутбук"
```

### Мок Playwright (`MockPlaywrightPage`)

```python
from chutils.scraping import MockPlaywrightPage

page = MockPlaywrightPage("<ul><li>Элемент 1</li><li>Элемент 2</li></ul>")
items = await page.locator("li").all()
assert len(items) == 2
```

### Мок Selenium (`MockSeleniumDriver`)

```python
from chutils.scraping import MockSeleniumDriver

driver = MockSeleniumDriver("<div id='content'>Привет</div>")
elem = driver.find_element("css selector", "#content")
assert elem.text == "Привет"
```

### Локальный тестовый HTTP-сервер песочницы (`LocalTestServer`)

Для тестирования парсеров в реальных сетевых условиях без обращения к внешним сайтам используется легковесный сервер:

```python
from chutils.scraping import LocalTestServer

with LocalTestServer() as server:
    # Регистрация страниц и API фикстур
    html_url = server.serve_html("/catalog", "<h1>Каталог товаров</h1>")
    json_url = server.serve_json("/api/items", [{"id": 1, "title": "Товар"}])

    # Прямой запрос в обход системных прокси
    response = server.fetch("/catalog")
    assert response.status == 200
    assert "Каталог товаров" in response.text

    # Проверка журнала входящих запросов от браузера
    assert len(server.requests_log) == 1
    assert server.requests_log[0].path == "/catalog"
```

### Менеджер живых браузерных сессий (`LiveBrowserSession`)

При сквозном тестировании реальных браузеров часто возникают висячие зомби-процессы (`chrome.exe`) и остаточные временные папки профилей. `LiveBrowserSession` гарантирует их полное удаление:

```python
from chutils.scraping import LiveBrowserSession
import nodriver

async with LiveBrowserSession(browser_name="chromium") as session:
    # Автоматически создается временный изолированный user_data_dir
    browser = await nodriver.start(user_data_dir=str(session.user_data_dir))
    
    # Регистрируем процесс браузера для отслеживания
    session.track_process(browser)

    tab = await browser.get("http://127.0.0.1:8080/test")
    # ... выполнение скрапинга ...

# При выходе: браузер гарантированно завершается (SIGTERM -> SIGKILL),
# а временный каталог профиля удаляется с диска даже при падении теста!
```

### Оффлайн-снапшоты страниц (`SnapshotRecorder`, `@use_html_snapshot`)

Позволяет сохранять разметку страниц реального сайта при первом обращении (`fetcher`) и мгновенно воспроизводить ее в оффлайн-режиме в тестах без обращения к сети и без запуска браузера:

```python
from chutils.scraping import use_html_snapshot, MockPlaywrightPage

# 1. Использование в качестве контекстного менеджера с моком Playwright/nodriver/Selenium
with use_html_snapshot("product_card", as_mock="playwright") as page:
    # page имеет тип MockPlaywrightPage с загруженной разметкой из tests/fixtures/snapshots/product_card.html
    title = page.locator("h1").text_content()


# 2. Использование в качестве декоратора тестовой функции
@use_html_snapshot("catalog_listing", as_mock="nodriver")
async def test_parse_catalog(tab):
    # tab - это MockNodriverTab
    items = await tab.select_all(".catalog-item")
    assert len(items) > 0


# 3. Автоматическая запись при отсутствии снапшота (fetcher)
def fetch_real_page():
    # Реальный сетевой запрос или вызов браузера
    return "<div class='price'>1000 ₽</div>"


with use_html_snapshot("price_page", fetcher=fetch_real_page) as html:
    # Сохраняется в tests/fixtures/snapshots/price_page.html и не пересоздается при повторных тестах
    assert "1000" in html
```

### Валидация качества извлечения данных (`Extraction Quality Assertions`)

Для быстрой и надежной верификации структуры и качества распарсенных данных модуль предоставляет специализированные ассерты с информативными сообщениями об ошибках:

```python
from chutils.scraping import (
    assert_extraction_complete,
    assert_valid_url,
    assert_valid_price,
    assert_schema_match,
)
from pydantic import BaseModel


class ProductSchema(BaseModel):
    id: int
    title: str
    price: float


item = {
    "id": 1,
    "title": "Умные часы",
    "price": 14990.0,
    "url": "https://example.com/item/1",
}

# 1. Проверка полноты и отсутствия None / пустых строк
assert_extraction_complete(item, required_keys=["id", "title", "price", "url"])

# 2. Проверка корректности ссылок
assert_valid_url(item["url"])

# 3. Проверка числовых или текстовых цен ("14 990 ₽", "$199.99") и диапазонов
assert_valid_price(item["price"], min_value=100.0, max_value=100000.0)

# 4. Проверка соответствия Pydantic-схеме (для одиночных элементов или списков)
assert_schema_match(item, ProductSchema)
```

### Встроенные фикстуры Pytest (`chutils.scraping.testing.fixtures`)

При установленном `chutils` pytest автоматически подхватывает плагин со следующими фикстурами:

- `local_test_server`: запущенный экземпляр `LocalTestServer` (автоматическая остановка при teardown).
- `live_browser_session`: экземпляр `LiveBrowserSession` с изолированным временным каталогом и уничтожением зомби-процессов.
- `html_snapshot_recorder`: настроенный `SnapshotRecorder` с каталогом во временной папке теста.
- `mock_nodriver_tab`, `mock_playwright_page`, `mock_selenium_driver`: фабрики для мгновенного создания моков из переданной HTML-строки.

Пример использования в тестах:

```python
async def test_scraper_with_fixtures(local_test_server, mock_playwright_page):
    # Тест через сервер песочницы
    local_test_server.serve_html("/item", "<h1>Товар</h1>")
    resp = local_test_server.fetch("/item")
    assert resp.status == 200

    # Быстрый мок Playwright
    page = mock_playwright_page("<h1>Товар</h1>")
    assert await page.locator("h1").inner_text() == "Товар"
```

---

## 7. Антидетект-браузер Camoufox (`chutils.scraping.camoufox`)

Для сценариев, где инъекций в CDP/JS недостаточно (например, при сложной проверке C++ рендеринга и WebGL Cloudflare Turnstile), рекомендуется использовать антидетект-браузер Camoufox (модифицированный Playwright Firefox со встроенной защитой на уровне ядра движка).

Фабрика `launch_camoufox` возвращает асинхронный контекстный менеджер браузера:

```python
import asyncio
from chutils.scraping import launch_camoufox


async def main():
    async with await launch_camoufox(headless=True, os="windows") as browser:
        page = await browser.new_page()
        await page.goto("https://nowecurity.com")
        print(await page.title())


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Улучшенный JS-антидетект, Web Workers и Client Hints

В модуль `chutils.scraping.humanize.antidetect` добавлены следующие передовые механизмы защиты:

1. **Защита изолированных Web Workers и SharedWorkers**: Антифрод-системы (Cloudflare Turnstile, Kasada, CreepJS) часто создают фоновые воркеры (`new Worker(...)`), чтобы проверить чистый контекст `self.navigator.webdriver` в обход основных инъекций в страницу. Модуль перехватывает конструкторы `Worker` и `SharedWorker`, автоматически оборачивает исходный скрипт в защитную преамбулу через `Blob` и `URL.createObjectURL`, полностью скрывая автоматизацию внутри воркеров.
2. **Маскировка V8 Stack Traces (`makeNative`)**: При инспекции стектрейсов ошибок (`Error().stack` или `Error.captureStackTrace`) антифрод обнаруживает следы monkey-patching (`at patched... (eval at...)`). Функция `makeNative` маскирует стек вызовов под нативные вызовы браузера (`at FunctionName (<anonymous>)`).
3. **Детерминированный Canvas Noise (`session_seed`)**: Шум накладывается через псевдослучайный алгоритм на базе стабильного сида сессии. Это исключает обнаружение антифрод-скриптами частой мутации канваса при многократном чтении `getImageData`.
4. **Cross-realm iframe prototype protection**: Перехват создания элементов `iframe` и предотвращение извлечения чистых непатченных прототипов (`Function.prototype.toString`, `navigator.webdriver`).
5. **Генерация Client Hints (`get_client_hints`)**: Формирование согласованной структуры `navigator.userAgentData` (brands, platform, mobile, entropy values) под указанный User-Agent.
6. **Мост Cookie и Clearance токенов (`extract_clearance_cookies`)**: Извлечение сессионных токенов (включая `cf_clearance`) и User-Agent из браузера для последующей передачи в быстрый сетевой клиент `TLSAsyncClient` / `TLSSession`:

```python
from chutils.scraping import extract_clearance_cookies
from chutils.http import TLSAsyncClient

# Извлечение из Playwright Page / Nodriver Tab
clearance_data = await extract_clearance_cookies(page)
print(clearance_data["cookies"])  # {'cf_clearance': '...', ...}

# Прямая инициализация быстрого TLS-клиента из браузерной сессии
client = await TLSAsyncClient.from_browser_session(page, impersonate="chrome120")
resp = await client.get("https://protected-site.com/api/data")
```





