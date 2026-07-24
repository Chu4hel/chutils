"""
Пример использования моста Async/Qt (run_async_task) для выполнения длинных операций.
"""

import asyncio
import sys

from chutils.qt.asyncio import run_async_task
from chutils.qt.shim import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget, require_qt


async def fetch_data_async(item_id: int) -> str:
    """Имитация длительного асинхронного сетевого запроса."""
    await asyncio.sleep(1.5)
    return f"Данные для объекта #{item_id} успешно загружены!"


def main() -> None:
    try:
        require_qt()
    except Exception as e:
        print(f"Qt не установлен: {e}")
        return

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Chutils Qt Async Example")
    layout = QVBoxLayout(window)

    label = QLabel("Нажмите кнопку для старта фоновой загрузки")
    button = QPushButton("Запустить асинхронную задачу")
    layout.addWidget(label)
    layout.addWidget(button)

    def on_click() -> None:
        button.setEnabled(False)
        label.setText("Загрузка данных в фоновом режиме...")

        def on_success(result: str) -> None:
            label.setText(result)
            button.setEnabled(True)

        def on_error(err: Exception) -> None:
            label.setText(f"Ошибка: {err}")
            button.setEnabled(True)

        # Выполняем асинхронную функцию без блокировки интерфейса Qt
        run_async_task(fetch_data_async, 42, on_success=on_success, on_error=on_error)

    button.clicked.connect(on_click)

    window.resize(400, 200)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
