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

Генерирует последовательности нажатий клавиш, включая реалистичные опечатки на близкорасположенных клавишах (поддерживаются раскладки QWERTY и ЙЦУКЕН), с
последующим стиранием опечаток через Backspace и вводом правильных букв.

Также поддерживается имитация редкой ошибки переключения раскладки (`layout_error_rate`), возникающей **строго в начале ввода** (например, ввод 1–3 символов латиницей `Ghb...` вместо кириллицы с последующим стиранием и повторным вводом `Привет...`).

Кроме того, генератор поддерживает продвинутую механику **отложенного исправления опечаток** (`delayed_fix_rate`): когда пользователь допускает ошибку в слове, по инерции допечатывает несколько последующих слов, а затем, не удаляя написанный хвост через каскад Backspace, возвращается клавишами стрелок (`ArrowLeft`) к месту опечатки, исправляет её, и мгновенно возвращается в конец строки клавишей `End` (или серией `ArrowRight`).

```python
from chutils.scraping.humanize import KeyboardTypoGenerator

typo_gen = KeyboardTypoGenerator(layout_error_rate=0.03, delayed_fix_rate=0.02)
# Или передавая напрямую в generate_sequence:
sequence = typo_gen.generate_sequence(
    "Автоматизация сбора данных и имитация поведения пользователя",
    error_rate=0.04,
    layout_error_rate=0.02,
    delayed_fix_rate=0.015,
)

# Возвращает список объектов TypoAction (action='type'|'backspace'|'key', char='...')
```


### Биометрический профиль моторики (`BehavioralProfile`)

`BehavioralProfile` объединяет все поведенческие параметры пользователя (скорость печати, опечатки, физику мыши и интервалы удержания) в единую Pydantic-модель.
С помощью фабричного метода `.from_seed(seed)` можно детерминированно сгенерировать уникальный реалистичный почерк для конкретной сессии, аккаунта или браузерного профиля:

```python
from chutils.scraping.humanize import BehavioralProfile

# Детерминированный профиль по сиду аккаунта:
profile = BehavioralProfile.from_seed("user_account_42")

print(profile.speed_wpm)        # напр., 52.4 WPM
print(profile.typo_rate)        # напр., 0.038 (3.8% опечаток)
print(profile.delayed_fix_rate) # отложенное исправление стрелками (напр., 0.015)
print(profile.gravity)          # физика мыши WindMouse

print(profile.key_hold_time)    # диапазон удержания клавиш (напр., 0.035 - 0.075 сек)
print(profile.click_hold_time)  # диапазон удержания клика (напр., 0.052 - 0.114 сек)

# Готовые фабрики генераторов:
wind_mouse = profile.create_wind_mouse()
typo_gen = profile.create_typo_generator()

# Прямые вызовы действий с биометрией профиля:
await profile.async_type_text(page, selector="#login", text="admin@example.com")
await profile.async_click(page, selector="#submit-btn")
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

# Адаптивный ввод (Paste/Ctrl+V для длинных текстов, промптов и кода):
# Короткие строки печатаются по буквам, а тексты длиннее paste_threshold вставляются
# целиком через буфер с паузами обдумывания до и после вставки.
await async_type_text(
    tab,
    selector="#prompt-input",
    text=long_prompt_or_code,
    paste_threshold=100,
    paste_delay_before=(0.5, 1.2),
    paste_delay_after=(0.4, 0.8),
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
# По умолчанию stealth_minimal=True: отключает синтетический шум Canvas/WebGL,
# сохраняя естественный отпечаток установленного браузера Google Chrome:
await apply_antidetect_nodriver(tab)
```

### Декларативная конфигурация `AntidetectConfig`

Для унифицированного управления параметрами антидетекта во внешних проектах используется Pydantic-модель `AntidetectConfig`. Она валидирует параметры, предоставляет готовые фабричные пресеты и позволяет применять маскировку к любому браузерному движку в одну строчку:

```python
from chutils.scraping.humanize import AntidetectConfig

# 1. Рекомендуемый пресет для nodriver (Zero-Footprint Stealth)
# Сохраняет 100% нативный WebGL и Canvas, предотвращая обнаружение искусственного шума WAF-системами:
cfg_nodriver = AntidetectConfig.preset_stealth_nodriver()
await cfg_nodriver.apply_to_nodriver(tab)

# 2. Агрессивный пресет для Playwright/Selenium в Headless-режиме (рандомизация Canvas, Audio, WebGL):
cfg_aggressive = AntidetectConfig.preset_aggressive(
    hardware_concurrency=16,
    device_memory=16,
)
await cfg_aggressive.apply_to_playwright(browser_context)

# 3. Пользовательская конфигурация:
custom_cfg = AntidetectConfig(
    webgl_vendor="Google Inc. (NVIDIA)",
    webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    hardware_concurrency=8,
    device_memory=16,
    stealth_minimal=True,
    session_seed="custom_seed_42",
)
await apply_antidetect_nodriver(tab, config=custom_cfg)

# 4. Мгновенная генерация из детерминированного сида:
seed_cfg = AntidetectConfig.from_seed("user_session_42")
await seed_cfg.apply_to_nodriver(tab)
```

### Синтезатор цифровой личности браузера (`FingerprintSynthesizer`)

В стиле профессиональных антидетект-браузеров (Linken Sphere, Octo Browser, Dolphin Anty), генератор отпечатков в `chutils` использует многоуровневый комбинаторный синтез цифровой личности. Отпечаток не выбирается из фиксированного списка и не генерируется чисто случайно (что создало бы невозможные комбинации вроде 7 ядер CPU или видеокарты Apple Metal на Windows), а строится по физически непротиворечивой матрице оборудования:

- **Матрица Hardware Tiers**:
  - `enthusiast_desktop`: мощные GPU (RTX 4090/4080/4070 Ti, RX 7900 XTX), 16–32 потока CPU, 32–64 ГБ RAM, мониторы 4K/2K (144–240 Гц).
  - `mainstream_desktop`: народные GPU (RTX 4060, RTX 3060, RX 6700 XT), 8–16 потоков CPU, 16–32 ГБ RAM, Full HD/2K.
  - `budget_desktop`: базовые GPU (GTX 1660, RTX 3050, RX 6500 XT), 6–12 потоков CPU, 8–16 ГБ RAM, Full HD.
  - `laptop`: мобильные GPU (Laptop GPU, Iris Xe, Radeon Graphics), 4–16 потоков CPU, 8–16 ГБ RAM, экраны ноутбуков (1920×1080, 2560×1600, DPR 1.25–1.5).
- **Синтез ANGLE D3D11 строк**: точная грамматика драйверов Windows (`Direct3D11 vs_5_0 ps_5_0, D3D11-31.0.15.xxxx`), согласованная с версиями драйверов NVIDIA и AMD.
- **Геометрия экранов**: строгий расчет высоты панели задач Windows (`availHeight = height - 40` или `48`) и Device Pixel Ratio.
- **Периферийные устройства**: согласованная эмуляция микрофонов, камер и аудиовыходов (`MediaDevices`) со стабильными SHA-256 хэшами `deviceId` и `groupId`.
- **Субпиксельный шум аудио**: эмуляция аппаратного джиттера ЦАП звуковой карты с порядком $10^{-7}$.
- **Двухуровневый движок**:
  - **Режим `auto`**: автоматически использует `browserforge`, если библиотека установлена (включая детерминированную генерацию по `seed`), либо прозрачно переключается на процедурный движок (Zero-Dependency fallback).
  - **Tier B (Zero-Dependency)**: полностью автономный встроенный процедурный генератор. Строго детерминирован по `seed` — один и тот же сид гарантирует идентичность отпечатка между перезапусками браузера.
  - **Tier A (Bayesian/ML)**: опциональный адаптер над библиотекой `browserforge` (Apify), если она установлена (`pip install browserforge`). Поддерживает детерминизацию по сиду с изоляцией PRNG.

#### Использование синтезатора

```python
from chutils.scraping import FingerprintProfile, FingerprintSynthesizer
from chutils.scraping.humanize import AntidetectConfig

# 1. Быстрая процедурная генерация по сиду (Zero-Dependency)
profile = FingerprintSynthesizer.create_procedural(seed="profile_account_102")

print(profile.webgl.renderer)  # ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 ...)
print(profile.hardware.concurrency)  # 12
print(profile.hardware.memory_gb)  # 16
print(profile.screen.width, profile.screen.avail_height)  # 1920 1040

# 2. Преобразование в AntidetectConfig и применение к сессии
antidetect_cfg = profile.to_antidetect_config()
await antidetect_cfg.apply_to_nodriver(tab)

# Или прямое применение профиля:
await profile.apply_to_tab(tab)  # nodriver
await profile.apply_to_page(page)  # Playwright

# 3. Автоматическое кэширование и сохранение профилей на диск:
# При первом вызове генерирует и сохраняет в ./profiles/acc_102.json, при последующих — быстро загружает:
profile = synthesizer.get_or_create(seed="acc_102", storage_dir="./profiles")

# Ручное сохранение и загрузка профиля (JSON)
profile.save_to_file("my_fingerprint.json")
loaded_profile = FingerprintProfile.from_file("my_fingerprint.json")

# 4. Использование ML-генератора browserforge с поддержкой сида
if FingerprintSynthesizer.is_browserforge_available():
    # browserforge детерминирован по сиду с автоматической изоляцией PRNG:
    bf_profile = FingerprintSynthesizer.create_from_browserforge(seed="acc_102")
```

### Автоматическое решение Cloudflare Turnstile (`solve_cf_turnstile`)

Функция `solve_cf_turnstile` автоматически обнаруживает появление интерактивного виджета Turnstile (включая контейнеры `.cf-turnstile`, `#turnstile-wrapper` и iframe `challenges.cloudflare.com`), рассчитывает координаты интерактивного чекбокса, выполняет плавное наведение курсора мыши по модели `WindMouse` и осуществляет физический клик с ожиданием токена валидации:

```python
from chutils.scraping.humanize import (
    detect_cf_turnstile,
    is_cf_turnstile_solved,
    solve_cf_turnstile,
)

# Проверить наличие и координаты виджета на странице
widget_info = await detect_cf_turnstile(tab)
if widget_info and widget_info.get("visible"):
    print(f"Turnstile обнаружен в координатах ({widget_info['x']}, {widget_info['y']})")

# Автоматически навести мышь, кликнуть и дождаться прохождения проверки
solved = await solve_cf_turnstile(tab, timeout=15.0, check_interval=0.5)
if solved:
    print("Капча успешно пройдена, токен валидирован!")
```

### Флаги запуска браузера (`get_browser_launch_args`)

Возвращает оптимизированный список аргументов для запуска Chromium (включая подавление первого запуска, детекта автоматизации и предупреждений профиля):

```python
from chutils.scraping.humanize import get_browser_launch_args

# Возвращает список флагов запуска без триггерящего антифрод '--no-sandbox' (по умолчанию),
# подавляя всплывающие окна падений и первого запуска:
# '--disable-dev-shm-usage', '--no-first-run', '--password-store=basic',
# '--mute-audio', '--disable-background-timer-throttling', '--disable-component-update',
# '--disable-session-crashed-bubble', '--hide-crash-restore-bubble', '--restore-last-session=false'
launch_flags = get_browser_launch_args()

# Для изолированных Docker-контейнеров без root-прав можно включить no_sandbox:
# docker_flags = get_browser_launch_args(no_sandbox=True)
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

### Гигиена профилей и сброс флагов аварийного завершения (`sanitize_profile`)

При аварийном завершении процессов Chromium или закрытии по таймауту/сигналу браузер сохраняет в `Preferences` флаги `exit_type = "Crashed"` и `exited_cleanly = false`. При следующем старте Chromium отображает плашку *"Восстановить страницы? Chromium завершился некорректно"*. Этот инфобар меняет геометрию окна (`viewport`), сдвигает координаты кликов и детектируется антифрод-системами как автоматизация.

Функция [`sanitize_profile`](file:///D:/PROJECTS/chutils/src/chutils/scraping/profiles/hygiene.py) автоматически:
1. Сбрасывает флаг `exit_type` в `"Normal"` и выставляет `exited_cleanly = True` в файле `Preferences`.
2. Устанавливает `session.restore_on_startup = 1` (открытие чистой вкладки).
3. Очищает директории и файлы артефактов старых сессий (`Default/Sessions/Session_*`, `Tabs_*`, `Current Session/Tabs`, `Last Session/Tabs`).

```python
from chutils.scraping import sanitize_profile, ProfileManager, launch_nodriver

# 1. Прямой вызов санитайзинга пользовательского профиля
sanitize_profile("/path/to/chrome/user_data_dir")

# Или через фасад ProfileManager:
ProfileManager.sanitize_profile("/path/to/chrome/user_data_dir")

# 2. В launch_nodriver и nodriver_session санитайзинг включен автоматически:
browser = await launch_nodriver(
    user_data_dir="/path/to/chrome/user_data_dir",
    sanitize_profile_dir=True,  # по умолчанию True
)
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
3. **Полноценная эмуляция `window.chrome`**: В headless-режиме и Playwright свойство `window.chrome` отсутствует или пустое. Антидетект эмулирует нативные методы `chrome.loadTimes()`, `chrome.csi()`, `chrome.runtime` и `chrome.app` с сохранением правильных сигнатур и `[native code]`.
4. **Защита от утечки IP через WebRTC (`RTCPeerConnection`)**: Блокирует утечку локальных (LAN) и прямых IP через STUN/TURN SDP кандидаты при работе через прокси.
5. **Детерминированный микрошум AudioContext**: Внедряет микрошум в `AudioBuffer.prototype.getChannelData` на базе `session_seed`, исключая снятие стабильного аудио-отпечатка антифрод-системами без искажения звука.
6. **Эмуляция геометрии окна и экрана**: В headless-браузерах `outerWidth` и `outerHeight` равны 0 либо строго равны `innerWidth`/`innerHeight`. Модуль выставляет реалистичные габариты с учетом тулбаров браузера и панели задач ОС.
7. **Эмуляция свойств `navigator.connection` и `navigator.getBattery`**: Предоставляет согласованные данные сетевого статуса (4G, RTT) и Battery API.
8. **Детерминированный Canvas Noise (`session_seed`)**: Шум накладывается через псевдослучайный алгоритм на базе стабильного сида сессии. Это исключает обнаружение антифрод-скриптами частой мутации канваса при многократном чтении `getImageData`.
9. **Cross-realm iframe prototype protection**: Перехват создания элементов `iframe` и предотвращение извлечения чистых непатченных прототипов (`Function.prototype.toString`, `navigator.webdriver`).
10. **Генерация Client Hints (`get_client_hints`)**: Формирование согласованной структуры `navigator.userAgentData` (brands, platform, mobile, entropy values) под указанный User-Agent.
11. **Мост Cookie и Clearance токенов (`extract_clearance_cookies`)**: Извлечение сессионных токенов (включая `cf_clearance`) и User-Agent из браузера для последующей передачи в быстрый сетевой клиент `TLSAsyncClient` / `TLSSession`:

```python
from chutils.scraping import extract_clearance_cookies
from chutils.http import TLSAsyncClient

# Извлечение из Playwright Page / Nodriver Tab
clearance_data = await extract_clearance_cookies(page)
print(clearance_data["cookies"])  # {'cf_clearance': '...', ...}

# Прямая инициализация быстрого TLS-клиента из браузерной сессии
client = await TLSAsyncClient.from_browser_session(page, impersonate="chrome120")
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
3. **Полноценная эмуляция `window.chrome`**: В headless-режиме и Playwright свойство `window.chrome` отсутствует или пустое. Антидетект эмулирует нативные методы `chrome.loadTimes()`, `chrome.csi()`, `chrome.runtime` и `chrome.app` с сохранением правильных сигнатур и `[native code]`.
4. **Защита от утечки IP через WebRTC (`RTCPeerConnection`)**: Блокирует утечку локальных (LAN) и прямых IP через STUN/TURN SDP кандидаты при работе через прокси.
5. **Детерминированный микрошум AudioContext**: Внедряет микрошум в `AudioBuffer.prototype.getChannelData` на базе `session_seed`, исключая снятие стабильного аудио-отпечатка антифрод-системами без искажения звука.
6. **Эмуляция геометрии окна и экрана**: В headless-браузерах `outerWidth` и `outerHeight` равны 0 либо строго равны `innerWidth`/`innerHeight`. Модуль выставляет реалистичные габариты с учетом тулбаров браузера и панели задач ОС.
7. **Эмуляция свойств `navigator.connection` и `navigator.getBattery`**: Предоставляет согласованные данные сетевого статуса (4G, RTT) и Battery API.
8. **Детерминированный Canvas Noise (`session_seed`)**: Шум накладывается через псевдослучайный алгоритм на базе стабильного сида сессии. Это исключает обнаружение антифрод-скриптами частой мутации канваса при многократном чтении `getImageData`.
9. **Cross-realm iframe prototype protection**: Перехват создания элементов `iframe` и предотвращение извлечения чистых непатченных прототипов (`Function.prototype.toString`, `navigator.webdriver`).
10. **Генерация Client Hints (`get_client_hints`)**: Формирование согласованной структуры `navigator.userAgentData` (brands, platform, mobile, entropy values) под указанный User-Agent.
11. **Мост Cookie и Clearance токенов (`extract_clearance_cookies`)**: Извлечение сессионных токенов (включая `cf_clearance`) и User-Agent из браузера для последующей передачи в быстрый сетевой клиент `TLSAsyncClient` / `TLSSession`:

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

---

## 9. Запуск Nodriver с антидетектом (`launch_nodriver`, `nodriver_session`)

Для браузерной автоматизации без следов веб-драйвера модуль `chutils.scraping` предоставляет фабрику `launch_nodriver` и асинхронный контекстный менеджер `nodriver_session`. Они автоматически накладывают рекомендованные флаги запуска Chromium (`--disable-dev-shm-usage` для Docker, параметры изоляции и др.), настраивают прокси (с прозрачной поддержкой авторизации через расширение) и применяют `AntidetectConfig`.

Фабрика поддерживает передачу постоянного каталога профиля (`user_data_dir`) для сохранения сессий, авторизаций и прогретых куки, а также кастомного пути к бинарнику браузера (`browser_executable_path`):

```python
import asyncio
from chutils.scraping import AntidetectConfig, nodriver_session


async def main():
    # Запуск браузера с нулевым вмешательством в Chromium и прогретым профилем
    config = AntidetectConfig.preset_stealth_nodriver()

    async with nodriver_session(
        config=config,
        user_data_dir="./chrome_profile",
        headless=False,
    ) as browser:
        tab = await browser.get("https://nowecurity.com")
        print("Заголовок страницы:", await tab.evaluate("document.title"))


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 10. Автоматическое решение Cloudflare Turnstile (`solve_cf_turnstile`)

Функция `solve_cf_turnstile` автоматически обнаруживает виджет Turnstile на странице (включая контейнеры внутри Shadow DOM), проверяет его интерактивность (отсутствие спиннеров/состояния проверки), центрирует в области вьюпорта (`scrollIntoView`), перемещает курсор по физической модели `windmouse` и производит клик с микропаузами удержания клавиши.

```python
import asyncio
from chutils.scraping import nodriver_session, solve_cf_turnstile


async def main():
    async with nodriver_session(headless=False) as browser:
        tab = await browser.get("https://peet.ws/turnstile-test/staging-turnstile.html")

        # Автоматическое ожидание и решение капчи Turnstile
        solved = await solve_cf_turnstile(
            tab,
            timeout=15.0,
            natural_hover=True,  # Естественная траектория наведения курсора из случайной точки
        )
        if solved:
            print("Turnstile успешно пройден!")
        else:
            print("Не удалось решить капчу Turnstile.")


if __name__ == "__main__":
    asyncio.run(main())
```

### Ключевые возможности `solve_cf_turnstile`:
- **Точные экранные координаты Viewport**: Клик передается в координатах видимой области браузера без смещения при скролле.
- **Поддержка Shadow DOM**: Рекурсивный поиск iframe и контейнеров капчи внутри открытых `shadowRoot`.
- **Адаптивная геометрия и `click_offset`**: Автоматическое определение компактного режима виджета (Compact mode) или возможность ручной передачи смещения клика `click_offset=(offset_x, offset_y)`.
- **Авто-повтор при Expired/Error**: Автоматический сброс состояния клика при переходе виджета в `data-state="expired"`, что позволяет повторно обновить решение.
- **Естественное наведение (`natural_hover`)**: Старт траектории WindMouse из случайной точки экрана вместо телепортации курсора в виджет.
- **Активация фокуса окна (`bring_to_front`)**: Принудительный перевод вкладки на передний план для сохранения `document.hasFocus()` и валидной доставки системных событий.
- **Детекция Hard Challenge**: Автоматическое распознавание интерактивных челленджей с предупреждением в лог и детализированной ошибкой при `raise_on_failure=True`.
- **Проверка интерактивности**: Ожидание готовности виджета и пропуск неинтерактивных состояний (`opacity: 0`, `data-state="checking"`).
- **CDP Fallback**: Автоматический резервный расчет границ через Box Model CDP при нулевых размерах DOM-прямоугольника.

---

## 11. Синтезатор цифровой личности и генератор отпечатков (`chutils.scraping.fingerprint`)

Модуль `chutils.scraping.fingerprint` обеспечивает генерацию физически согласованных и статистически достоверных цифровых личностей (Browser Fingerprints) для обхода систем антифрода и фингерпринтинга (CreepJS, Pixelscan, BrowserLeaks).

### Концепция архитектуры
1. **Физическая валидность параметров**: Видеокарта, процессор, объем памяти, Client Hints и разрешение экрана строго взаимосвязаны (например, исключены аномалии вроде видеокарты Apple Metal на Windows или нечетного количества ядер).
2. **Детерминизм по сиду**: Один и тот же сид (`seed="session_123"`) генерирует абсолютно идентичный отпечаток цифровой личности в любое время.
3. **Два независимых движка**:
   - **`ProceduralFingerprintEngine` (Zero-Dependency)**: Встроенный комбинаторный генератор с детерминированным расчетом геометрии дисплея, вычетом системной панели задач и валидными ANGLE WebGL строками. Не требует сторонних библиотек.
   - **`BrowserForgeProvider` (Байесовская сеть)**: Опциональный провайдер на базе пакета `browserforge` (`pip install chutils[fingerprint]`), использующий генеративную байесовскую сеть, обученную на миллионах реальных пользовательских сессий.
4. **Бесшовная интеграция с `nodriver` и `Playwright`**: Прямое применение параметров через методы профиля или `AntidetectConfig`.

### Быстрый старт

```python
import asyncio
from chutils.scraping import FingerprintSynthesizer, AntidetectConfig

# 1. Детерминированный синтез по сиду
synthesizer = FingerprintSynthesizer(os_target="windows")
profile = synthesizer.synthesize(seed="user_account_42")

print(f"Платформа: {profile.platform}")
print(f"User-Agent: {profile.user_agent}")
print(f"Экран: {profile.screen.width}x{profile.screen.height} (доступно: {profile.screen.avail_width}x{profile.screen.avail_height})")
print(f"GPU: {profile.webgl.renderer}")
print(f"Ядра CPU: {profile.hardware_concurrency}, RAM: {profile.device_memory} GB")

# 2. Быстрое создание AntidetectConfig через сид
config = AntidetectConfig.from_seed("user_account_42")
# или из готового профиля:
config = AntidetectConfig.from_fingerprint(profile)

# 3. Прямое применение профиля к вкладке nodriver или странице Playwright
# await profile.apply_to_tab(tab)
# await profile.apply_to_page(page)
```

### Сохранение и сериализация профиля

Сгенерированные отпечатки можно сериализовать в JSON / Dict и восстанавливать для долгосрочного использования сессий:

```python
# Экспорт в словарь / JSON
data = profile.to_dict()

# Восстановление профиля
from chutils.scraping import FingerprintProfile
restored_profile = FingerprintProfile.from_dict(data)
assert restored_profile.user_agent == profile.user_agent
```

---

## 12. Управление профилями браузеров и сессиями (`chutils.scraping.profiles`)

Модуль `chutils.scraping.profiles` предоставляет универсальную абстракцию профиля браузера (`BrowserProfile`) для сохранения, переноса и переиспользования сессий между различными браузерными движками (`nodriver`, `Playwright`, `Selenium`).

### Основные компоненты

* **`BrowserProfile`**: Унифицированный контейнер данных сессии, включающий куки (`cookies: list[CookieData]`), локальное хранилище (`storage: StorageData`) и заголовки с User-Agent (`headers: HeaderData`).
* **`ProfileManager`**: Менеджер жизненного цикла сессий на диске с поддержкой автоматической ротации, проверки валидности и кэширования.
* **Адаптеры движков (`chutils.scraping.profiles.adapters`)**:
  * **`nodriver`**: `export_nodriver_profile(tab)` и `import_nodriver_profile(tab, profile)`. Поддерживает полиморфное чтение кук из CDP (словари, прямой список, объекты `cdp.network.Cookie` с enum-полями `same_site`), а также каскадный вызов `Network.getAllCookies` / `network.get_all_cookies()` / `network.get_cookies()`.
  * **`Playwright`**: `export_playwright_profile(context)` и `import_playwright_profile(context, profile)`. Экспортирует состояние кук и localStorage через `context.storage_state()`.
  * **`Selenium`**: `export_selenium_profile(driver)` и `import_selenium_profile(driver, profile)`.

### Пример использования адаптера nodriver

```python
import nodriver as uc
from chutils.scraping.profiles.adapters.nodriver import export_nodriver_profile, import_nodriver_profile
from chutils.scraping.profiles.storage import save_profile_to_file, load_profile_from_file

async def main():
    browser = await uc.start()
    tab = await browser.get("https://example.com/login")
    # ... авторизация на сайте ...

    # Экспорт профиля сессии с куками и User-Agent
    profile = await export_nodriver_profile(tab)
    save_profile_to_file(profile, "session_profile.json")

    # В новой сессии — импорт сохраненного профиля
    restored_profile = load_profile_from_file("session_profile.json")
    new_tab = await browser.get("https://example.com")
    await import_nodriver_profile(new_tab, restored_profile)
```

---

## 13. Умный резолвер и валидатор прокси (`SmartProxyResolver`)

При работе с пулами прокси от различных поставщиков строки подключения часто поступают в нестандартных форматах (`ip:port:user:pass`, `user:pass:ip:port`, `user:pass@ip:port`, без протокола или с неверно указанным протоколом `http://` вместо `socks5://`).

Класс `SmartProxyResolver` (`chutils.scraping.proxy.SmartProxyResolver` или `chutils.SmartProxyResolver`) решает эту проблему:
1. **Эвристический разбор строк**: Распознает любые вариации форматов `host:port:user:pass`, `user:pass:host:port`, `@` нотацию и формирует приоритизированный список кандидатов.
2. **Активный сетевой Handshake (Probe)**:
   - Для HTTP/HTTPS: проверяет поддержку туннелирования через `CONNECT` или легковесный `GET /generate_204`, корректно обрабатывая ошибки авторизации `407 Proxy Authentication Required`.
   - Для SOCKS5: выполняет полноценное рукопожатие RFC 1928 и авторизацию RFC 1929 (`0x02 username/password`).
   - Для SOCKS4: выполняет SOCKS4 connect handshake.
3. **Персистентный дисковый кэш (`FileCacheBackend`)**: Валидированные канонические URL сохраняются на диск с TTL (по умолчанию 7 дней) и атомарной записью (`atomic_write`), избегая повторных сетевых задержек при последующих запусках.
4. **Live Health-Check и замер задержки**: Метод `check_health` возвращает `ProxyHealthResult` со статусом доступности `is_alive`, задержкой `latency_ms` и текстом ошибки `error`.
5. **Синхронные обертки**: Методы `resolve_sync` и `resolve_config_sync` корректно работают как в синхронных скриптах, так и внутри уже работающего цикла событий `asyncio` (например, в Jupyter Notebook, FastAPI или GUI).

### Пример использования

```python
import asyncio
from chutils import SmartProxyResolver

async def main():
    resolver = SmartProxyResolver()

    # Автоматическое определение протокола и формата
    # Строка вида "ip:port:user:pass" превращается в валидный рабочий URL
    proxy_url = await resolver.resolve("185.199.229.156:8080:login:password")
    print(f"Рабочий URL прокси: {proxy_url}")
    # Вывод: http://login:password@185.199.229.156:8080 (или socks5://...)

    # Получение готовой типизированной конфигурации ProxyConfig
    config = await resolver.resolve_config("185.199.229.156:8080:login:password")
    if config:
        print(f"Хост: {config.host}, Порт: {config.port}, Протокол: {config.protocol}")

    # Проверка задержки и живости прокси (Health Check)
    health = await resolver.check_health(proxy_url)
    print(f"Живой: {health.is_alive}, Задержка: {health.latency_ms} ms")

asyncio.run(main())
```

### Синхронный вызов

```python
from chutils import SmartProxyResolver

resolver = SmartProxyResolver()
# Работает без явного вызова asyncio.run(), безопасно внутри любого контекста
proxy_url = resolver.resolve_sync("185.199.229.156:8080:login:password")
proxy_cfg = resolver.resolve_config_sync("185.199.229.156:8080:login:password")
```

### Локальный прокси-туннель (`AsyncProxyTunnel`)

Позволяет безопасно проксировать трафик браузеров (включая Chromium в headless-режиме) через локальный HTTP/CONNECT форвардер с прозрачной подстановкой заголовков `Proxy-Authorization` и логированием сбоев соединения:

```python
from chutils.scraping.proxy import AsyncProxyTunnel

tunnel = AsyncProxyTunnel("http://user:pass@1.2.3.4:8000")
await tunnel.start()
print("Chrome flag:", tunnel.to_chrome_arg())  # --proxy-server=http://127.0.0.1:<port>
...
await tunnel.stop()
```

---

## 14. Тестирование скраперов и Pytest-фикстуры (`chutils.scraping.testing`)

Модуль предоставляет готовый набор фикстур для автотестирования парсеров, эмуляции моков браузеров и сквозных live-тестов.

### Авторегистрация плагина Pytest

Плагин автоматически регистрируется в Pytest через точку входа `pytest11`. При этом импорт плагина полностью изолирован и не имеет побочных эффектов (Zero Side-Effects): все серверы, браузерные сессии и утилиты снапшотов импортируются **лениво** только в момент запроса соответствующей фикстуры тестом.

### Доступные фикстуры

* **`local_test_server`**: Локальный HTTP-сервер песочницы для проверки отдачи статических HTML/JSON и перехватов запросов.
* **`live_browser_session`**: Контекст реального браузера с гарантированным удалением zombie-процессов через `chutils.lifecycle`.
* **`html_snapshot_recorder`**: Менеджер сохранения и сверки HTML-снапшотов для оффлайн регрессионного тестирования парсеров.
* **`mock_nodriver_tab`**, **`mock_playwright_page`**, **`mock_selenium_driver`**: Быстрые фабрики моков вкладок и страниц без необходимости запуска реального браузера.

### Утверждения качества данных (Data Assertions)

* **`assert_extraction_complete`**: Проверяет обязательные ключи и непустые значения в распарсенных словарях.
* **`assert_price_valid`**: Валидирует числовые значения цен.
* **`assert_pagination_valid`**: Проверяет корректность URL следующей страницы.


