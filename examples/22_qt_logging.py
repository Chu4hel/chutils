"""
Пример использования QtLogHandler для перенаправления логов в Qt виджет.
"""

import logging
import sys

from chutils.qt import setup_qt_logging
from chutils.qt.shim import QApplication, QPlainTextEdit, QVBoxLayout, QWidget, require_qt


def main() -> None:
    try:
        require_qt()
    except Exception as e:
        print(f"Qt не установлен: {e}")
        return

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Chutils Qt Logging Example")
    layout = QVBoxLayout(window)

    log_widget = QPlainTextEdit()
    log_widget.setReadOnly(True)
    layout.addWidget(log_widget)

    # Настраиваем привязку логов
    setup_qt_logging(widget=log_widget, level=logging.INFO)

    logger = logging.getLogger("qt_example")
    logger.info("Приложение успешно запущено.")
    logger.warning("Это тестовое предупреждение.")

    window.resize(500, 300)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
