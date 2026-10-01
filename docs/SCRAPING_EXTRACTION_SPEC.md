# Спецификация выделения модуля автоматизации и антидетекта в отдельный пакет

Данный документ описывает архитектурный план и стратегию выделения подсистемы браузерного антидетекта, имитации поведения человека (humanize), управления профилями и прокси из монолитной библиотеки `chutils` в самостоятельный open-source пакет.

---

## 1. Мотивация и предпосылки

Библиотека `chutils` исторически объединяет утилиты самого разного назначения: логирование, конфиги, работу с Telegram/VK, криптографию, очереди и скрейпинг. При этом подсистема автоматизации браузеров (`chutils.scraping`) выросла в самодостаточный фреймворк профессионального уровня, включающий:
- биомеханическую генерацию движений мыши (**WindMouse**) и сенсорных жестов;
- продвинутый кросс-движковый антидетект для **nodriver**, **Playwright**, **Selenium** и **Camoufox**;
- автоматический прогрев сессий (**ProfileWarmer**) и обход **Google Consent / GDPR**;
- встроенный детектор и солвер **Cloudflare Turnstile**;
- защищенное хранилище профилей браузера (`.chprofile`) с шифрованием и санитизацией;
- прокси-пул с динамической генерацией Chrome-расширений авторизации и локальными туннелями.

### Почему необходим отдельный репозиторий:
1. **Независимый жизненный цикл версий**: изменения в браузерных движках (новые версии Chromium/CDP, патчи Playwright/nodriver) требуют частых и оперативных релизов без необходимости перевыпуска всей библиотеки утилит.
2. **Легковесность установки**: пользователям, которым нужен только антидетект или WindMouse, не требуются зависимости `aiogram`, `PyQt6`, `fastapi` и т.д.
3. **Виральность и позиционирование в Open Source**: специализированные библиотеки на GitHub привлекают во много раз больше звезд, контрибьюторов и пользователей, чем утилитарные «швейцарские ножи».

---

## 2. Анализ нейминга и таргетинг на GitHub (SEO & Stars)

### Анализ поисковых запросов разработчиков (Search Intent)
Пользователи на GitHub и в поисковиках ищут решения под конкретные боли:
- *«playwright stealth python»*, *«nodriver stealth bypass»*, *«undetected chromedriver alternative»*
- *«human-like mouse movement python»*, *«antidetect browser automation»*, *«cloudflare turnstile bypass»*
- *«browser fingerprint spoofing python»*

### Варианты названий

| Название | GitHub SEO / Поиск | Ассоциации и сильные стороны | PyPI доступность / Риски | Оценка (1–10) |
| :--- | :--- | :--- | :--- | :---: |
| **`browser-stealth`** | **Максимальный** (`browser`, `stealth`) | Понятно любому разработчику: делает браузер незаметным для антифрода. Покрывает nodriver, Playwright и Selenium. | Идеально для общего поиска. | **9.8 / 10** 🏆 *(Топ выбор)* |
| **`antidetect`** (`antidetect-py`) | **Очень высокий** (`antidetect`) | Промышленный термин (Dolphin, AdsPower, Multilogin), но в виде бесплатного Python SDK. | `antidetect` на PyPI может быть занят, вариант: `py-antidetect` / `antidetect-core`. | **9.4 / 10** |
| **`browser-humanize`** / **`humanize-browser`** | **Высокий** (`browser`, `humanize`, `ghost-cursor`) | Фокус на биомеханике: WindMouse, скролл, опечатки, кривые Безье, прогрев. | Отлично отражает человекоподобное поведение. | **9.2 / 10** |
| **`stealth-driver`** | **Высокий** (`stealth`, `driver`) | Звучит как логичный преемник `undetected-chromedriver` для всех движков. | Очень чистое и техническое имя. | **9.0 / 10** |
| **`nodriver-stealth`** | **Узко-целевой** (`nodriver`) | Нишевый взрывной рост: у `nodriver` нет зрелого аналога `playwright-stealth`. | Ограничивает восприятие (кажется, что только для nodriver). | **8.2 / 10** |

### Рекомендованное решение:
* **Имя репозитория на GitHub:** `browser-stealth` (или `antidetect-core`)
* **Имя пакета на PyPI:** `browser-stealth` (альтернатива: `py-antidetect`)
* **Теги (GitHub Topics):**
  `playwright`, `nodriver`, `selenium`, `stealth`, `antidetect`, `web-scraping`, `bot-detection-bypass`, `browser-automation`, `turnstile-solver`, `fingerprint-spoofing`, `human-like-mouse`, `windmouse`, `profile-warmer`.

---

## 3. Модули, подлежащие переносу

Ниже приведена карта всех компонентов из `src/chutils/scraping/`, формирующих новый пакет:

```
browser-stealth/
├── src/browser_stealth/
│   ├── __init__.py
│   ├── humanize/                  # Биомеханика и поведение человека
│   │   ├── __init__.py
│   │   ├── math_utils.py          # WindMouseGenerator, BezierCurve, JitterDelay, KeyboardTypo
│   │   ├── actions.py             # async_move_mouse, async_type_text, async_scroll_to, touch
│   │   ├── _actions_helpers.py    # Вспомогательные CDP / DOM утилиты взаимодействия
│   │   ├── touch.py               # TouchGestureGenerator, свайпы, тапы
│   │   ├── behavior.py            # Марковские цепи серфинга, поведенческие паттерны
│   │   ├── warmer.py              # ProfileWarmer, SyncProfileWarmer (органический прогрев)
│   │   ├── consent.py             # Автоматический обход Google Consent / GDPR
│   │   ├── search.py              # Банк реалистичных поисковых запросов и фильтры выдачи
│   │   └── turnstile.py           # Cloudflare Turnstile token inspector и bridge к солверам
│   ├── antidetect/                # Подмена цифрового отпечатка (Fingerprint Spoofing)
│   │   ├── __init__.py
│   │   ├── core.py                # Инъекции скриптов на NewDocument
│   │   ├── scripts.py             # JS-полифилы (WebGL, Canvas, Audio, WebRTC, Screen, Battery)
│   │   ├── config.py              # AntidetectConfig (модели и параметры отпечатков)
│   │   └── mobile.py              # Сенсорные и мобильные платформенные скрипты
│   ├── profiles/                  # Управление браузерными профилями и сессиями
│   │   ├── __init__.py
│   │   ├── manager.py             # ProfileManager (сохранение, загрузка сессий)
│   │   ├── models.py              # BrowserProfile, StorageState, Cookie
│   │   ├── storage.py             # Зашифрованное хранилище .chprofile (.stealthprofile)
│   │   ├── hygiene.py             # Санитизация кэша, истории, сервисных файлов Chromium
│   │   └── adapters/              # Адаптеры экспорта/импорта сессий
│   │       ├── nodriver.py
│   │       ├── playwright.py
│   │       └── selenium.py
│   ├── proxy/                     # Продвинутая инфраструктура прокси
│   │   ├── __init__.py
│   │   ├── pool.py                # ProxyPool (ротация, health-check, скоринг задержки)
│   │   ├── resolver.py            # Асинхронный резолвер с проверкой протоколов и геолокации
│   │   ├── cache.py               # Кэширование валидированных прокси на диске
│   │   ├── tunnel.py              # Локальный TCP/SOCKS туннель для авторизации
│   │   ├── extension.py           # Chrome Extension Generator для базовой авторизации прокси
│   │   ├── models.py              # ProxyConfig, ProxyHealthResult
│   │   └── parser.py              # Парсер любых строковых форматов прокси
│   ├── bidi/                      # Поддержка протокола WebDriver BiDi
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── session.py
│   │   └── antidetect.py
│   ├── launchers/                 # Быстрый запуск преднастроенных браузеров
│   │   ├── nodriver.py            # NodriverLauncher с автоинъекцией расширений и флагов
│   │   └── camoufox.py            # CamoufoxLauncher
│   └── testing/                   # Инструменты тестирования и отладки
│       ├── __init__.py
│       ├── recorder.py            # DOM Recorder HUD (визуализация кликов и действий)
│       ├── dom_models.py
│       ├── dom_scripts.py
│       ├── session.py             # LiveBrowserSession для тестов
│       ├── server.py              # Локальный mock HTTP-сервер с проверками ботов
│       ├── snapshot.py
│       ├── assertions.py
│       └── mocks/                 # In-memory моки для тестирования без браузера
│           ├── dom.py
│           ├── nodriver.py
│           ├── playwright.py
│           └── selenium.py
```

---

## 4. План декуплинга (устранение внешних зависимостей от `chutils`)

В текущем коде есть несколько зависимостей от родительской библиотеки `chutils`. При переносе они заменяются на стандартные решения Python или легковесные внутренние модули:

| Импорт из `chutils` | Текущее использование | Замена в новом пакете |
| :--- | :--- | :--- |
| `from chutils.logger import setup_logger` | Логирование во всех модулях | Стандартный `logging.getLogger("browser_stealth.*")`. Опциональная подсветка через `rich`, если библиотека установлена. |
| `from chutils.fs import atomic_write, ensure_dir, remove_path` | Сохранение файлов профилей и расширений | Встроенный модуль `pathlib.Path` + `tempfile` + `shutil`. Реализация микро-хелпера `atomic_write` на 15 строк. |
| `from chutils.crypto import encrypt_portable, decrypt_portable` | Шифрование `.chprofile` файлов | Опциональная зависимость `cryptography` (экстра `[crypto]`). При отсутствии — сохранение в открытом JSON/ZIP. |
| `from chutils.lifecycle import register_cleanup` | Удаление временных директорий расширений | Стандартный модуль `atexit` и финализаторы `weakref.finalize`. |
| `from chutils.time import utc_now` | Таймстемпы профилей | Стандартный `datetime.datetime.now(datetime.timezone.utc)`. |
| `from chutils.exceptions import OptionalDependencyError` | Проверка наличия playwright/nodriver | Локальное понятное исключение `BrowserStealthDependencyError`. |

---

## 5. Конфигурация пакета (`pyproject.toml`)

Пакет должен использовать модульную систему экстра-зависимостей, позволяющую устанавливать ядро с нулевыми тяжелыми зависимостями:

```toml
[project]
name = "browser-stealth"
version = "0.1.0"
description = "Next-generation browser antidetect, human-like behavior emulation (WindMouse), and profile warmer for Playwright, nodriver, and Selenium."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
keywords = [
    "playwright-stealth",
    "nodriver",
    "antidetect",
    "web-scraping",
    "windmouse",
    "turnstile-solver",
    "browser-automation",
]
authors = [{ name = "Chu4hel" }]
dependencies = [
    # Ядро не требует обязательной установки браузеров:
    # математические алгоритмы и генераторы работают автономно
]

[project.optional-dependencies]
nodriver = ["nodriver>=0.38"]
playwright = ["playwright>=1.40.0"]
selenium = ["selenium>=4.15.0"]
camoufox = ["camoufox[geoip]>=0.4.0"]
crypto = ["cryptography>=41.0.0"]
all = [
    "browser-stealth[nodriver,playwright,selenium,camoufox,crypto]"
]
```

---

## 6. Стратегия обратной совместимости в `chutils`

После создания и публикации отдельного пакета `browser-stealth`, в основном репозитории `chutils`:

1. В `pyproject.toml` секция `[project.optional-dependencies].scraping` обновляется:
   ```toml
   scraping = [
       "browser-stealth>=0.1.0",
   ]
   ```
2. В каталоге `src/chutils/scraping/` создаются легковесные прокси-модули (Shim/Facade), реэкспортирующие классы:
   ```python
   # src/chutils/scraping/humanize/warmer.py
   from browser_stealth.humanize.warmer import ProfileWarmer, SyncProfileWarmer
   ```
3. Пользователи `chutils` не получают никаких breaking changes, а проект избавляется от 15 000+ строк специализированного кода, который теперь развивается в фокусном репозитории.

---

## 7. Чек-лист шагов по реализации

1. [ ] Инициализировать репозиторий `browser-stealth` (лицензия MIT, README с интерактивными GIF-демонстрациями WindMouse).
2. [ ] Перенести код модулей `humanize`, `antidetect`, `profiles`, `proxy`, `testing`, `bidi`.
3. [ ] Заменить вызовы `chutils.logger`, `fs`, `crypto` на автономные реализации.
4. [ ] Перенести соответствующие тесты из `tests/unit/scraping/` и `tests/unit/test_profile_warmer.py`.
5. [ ] Настроить CI (GitHub Actions: запуск pytest на Python 3.10, 3.11, 3.12, 3.13, 3.14).
6. [ ] Опубликовать релиз `v0.1.0` на PyPI.
7. [ ] Обновить зависимость в `chutils` с сохранением реэкспорта API.
