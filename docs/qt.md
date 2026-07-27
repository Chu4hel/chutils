# Интеграция с PyQt6 / PySide6 (chutils.qt)

Модуль `chutils.qt` предоставляет слой совместимости и обертки для прозрачной работы с библиотеками **PyQt6** и *
*PySide6**, включая трансляцию логов в виджеты UI, выполнение асинхронных задач без блокировки графического интерфейса и
базовые шаблонные компоненты.

Данный модуль поставляется как опциональное расширение: `chutils[qt]` или `chutils[qt-pyside]`.

---

## Установка

```bash
# Для работы с PyQt6
pip install "chutils[qt]"

# Для работы с PySide6
pip install "chutils[qt-pyside]"
```

---

## 1. Слой совместимости (Qt Shim)

Слой `chutils.qt.shim` автоматически определяет установленный фреймворк и импортирует символы.

```python
from chutils.qt import QT_BINDING, QtCore, QtGui, QtWidgets, Signal, Slot, require_qt

# Проверка установленного фреймворка ('PyQt6', 'PySide6' или None)
print(f"Используемый Qt: {QT_BINDING}")

# Гарантирует наличие Qt или выбрасывает OptionalDependencyError
require_qt()
```

---

## 2. Логирование в UI (QtLogHandler)

Обработчик `QtLogHandler` перенаправляет логи Python в Qt-сигнал `message_emitted(str, int)`. Функция `setup_qt_logging`
позволяет в одну строчку привязать логи к виджетам (`QPlainTextEdit`, `QTextEdit`, `QStatusBar`, `QLabel`).

```python
import logging
from chutils.qt import setup_qt_logging

# Привязка вывода логов к QPlainTextEdit
log_widget = QPlainTextEdit()
setup_qt_logging(widget=log_widget, level=logging.INFO)

logger = logging.getLogger("my_app")
logger.info("Сообщение отобразится в виджете!")
```

---

## 3. Асинхронный мост (Async/Qt Bridge)

Для выполнения `async def` корутин или тяжелых синхронных функций в фоновом потоке без заморозки (фризов) UI
используется `run_async_task` или декоратор `async_to_qt`.

```python
import asyncio
from chutils.qt import run_async_task


async def fetch_api_data(user_id: int) -> str:
    await asyncio.sleep(2.0)
    return f"User data for {user_id}"


def on_success(data: str):
    label.setText(data)


def on_error(err: Exception):
    label.setText(f"Error: {err}")


# Запуск в фоновом QThread
run_async_task(fetch_api_data, 123, on_success=on_success, on_error=on_error)
```

---

## 4. Шаблонные виджеты (BaseMainWindow, BaseDialog)

Классы `BaseMainWindow` и `BaseDialog` предоставляют:

- Автоматическое логирование событий создания, открытия и закрытия окон.
- Сохранение и восстановление размеров и геометрии окна через `QSettings`.

```python
from chutils.qt import BaseMainWindow


class MainWindow(BaseMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Моё приложение")
```

---

## 5. Типизированные сигналы и Авто-связывание (`TypedSignal`, `AutoBindMixin`, `@qt_slot`)

Для точной проверки типов в IDE, авто-подключения слотов по соглашению об именовании и перехвата исключений:

- `TypedSignal[T1, T2]`: Создает сигнал с точной типизацией для `.emit()` и `.connect()`.
- `AutoBindMixin`: Автоматически подсоединяет сигналы компонента к методам `on_<signal_name>`.
- `@qt_slot`: Безопасный декоратор для слотов с логированием исключений в `chutils.logger`.

```python
from chutils.qt import AutoBindMixin, BaseMainWindow, TypedSignal, qt_slot


class MainWindow(BaseMainWindow, AutoBindMixin):
    user_updated = TypedSignal[str, int](str, int)

    def __init__(self):
        super().__init__()

    # Автоматически подключится к сигналу user_updated
    @qt_slot(str, int)
    def on_user_updated(self, name: str, user_id: int) -> None:
        print(f"Пользователь {name} обновился: {user_id}")
```
