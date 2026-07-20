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

*Примечание: Если вам нужны только математические генераторы (траектории, задержки, опечатки), вы можете использовать их
без установки дополнительных библиотек автоматизации.*

---

## 1. Математические генераторы

Математический модуль работает автономно и не требует внешних зависимостей.

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
    async_scroll_to,
    async_type_text,
    async_human_sleep
)

# Плавное движение мыши
await async_move_mouse(page, x=400, y=300, start=(0, 0))

# Плавный скролл страницы по оси Y
await async_scroll_to(page, x=0, y=800)

# Ввод текста со скоростью 40 WPM и вероятностью опечаток 5%
await async_type_text(page, selector="#username", text="my_user_login", error_rate=0.05, speed_wpm=40.0)

# Асинхронная пауза "на чтение" от 1 до 3 секунд
await async_human_sleep(1.0, 3.0)
```

### Обертки для nodriver (асинхронные)

Те же асинхронные функции поддерживают автоматизацию на базе `nodriver` (все действия транслируются напрямую через CDP протокол):

```python
from chutils.scraping.humanize import (
    async_move_mouse,
    async_scroll_to,
    async_type_text,
)

# Плавное движение мыши (транслируется в CDP dispatchMouseEvent)
await async_move_mouse(tab, x=400, y=300, start=(0, 0))

# Плавный скролл страницы через JS evaluate
await async_scroll_to(tab, x=0, y=800)

# Ввод текста с опечатками (через CDP dispatchKeyEvent)
await async_type_text(tab, selector="#username", text="my_user_login", error_rate=0.05, speed_wpm=40.0)
```

### Обертки для Selenium (синхронные)

```python
from chutils.scraping.humanize import (
    move_mouse,
    scroll_to,
    type_text,
    human_sleep
)

# Плавное движение мыши
move_mouse(driver, x=400, y=300, start=(0, 0))

# Плавный скролл
scroll_to(driver, x=0, y=800)

# Ввод текста
type_text(driver, selector="#username", text="my_user_login", error_rate=0.05, speed_wpm=40.0)

# Синхронная пауза
human_sleep(1.0, 3.0)
```

---

## 3. Анти-детект и маскировка браузеров

Для минимизации вероятности обнаружения бот-детектором (например, Cloudflare, Akamai, Imperva) модуль предоставляет
JS-инъекции и флаги запуска.

### JS-инъекции анти-детекта

Инъекция скрывает автоматизацию на низком уровне JavaScript до загрузки веб-страницы:

- Удаляет и переопределяет свойство `navigator.webdriver`.
- Добавляет минимальный псевдослучайный шум к пикселям Canvas (`getImageData`), искажая статический Canvas-отпечаток.
- Маскирует WebGL параметры видеокарты (переопределяет рендерер и вендор на стандартный `Google Inc. (NVIDIA)`).
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
    device_memory=16
)

# Для Selenium (применяется к WebDriver через CDP)
apply_antidetect_selenium(
    driver,
    webgl_vendor="Intel",
    webgl_renderer="Intel UHD Graphics",
    hardware_concurrency=4,
    device_memory=8
)

# Для nodriver (применяется к вкладке Tab через CDP протокол)
await apply_antidetect_nodriver(
    tab,
    webgl_vendor="NVIDIA Corporation",
    webgl_renderer="NVIDIA GeForce RTX 4090",
    hardware_concurrency=24,
    device_memory=64
)
```

### Флаги запуска браузера (`get_browser_launch_args`)

Возвращает оптимизированный список аргументов для запуска Chromium:

```python
from chutils.scraping.humanize import get_browser_launch_args

# Возвращает список флагов запуска, таких как:
# '--disable-blink-features=AutomationControlled', '--disable-infobars' и т.д.
launch_flags = get_browser_launch_args()
```


