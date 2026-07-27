"""
Пример использования типизированных сигналов (TypedSignal) и авто-связывания слотов.

Демонстрирует безопасную авто-подключение методов on_<signal_name> и логирование
ошибок в слотах с помощью декоратора @qt_slot.
"""

import sys

from chutils.qt import (
    AutoBindMixin,
    BaseMainWindow,
    QApplication,
    QPushButton,
    TypedSignal,
    QVBoxLayout,
    QWidget,
    qt_slot,
    require_qt,
)


class MyTypedWindow(BaseMainWindow, AutoBindMixin):
    """Окно приложения с типизированными сигналами и авто-связыванием."""

    # Определяем типизированные сигналы
    user_logged_in = TypedSignal[str, int](str, int)
    action_triggered = TypedSignal[](void=None) if False else TypedSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chutils Typed Signals Example")

        central = QWidget()
        layout = QVBoxLayout(central)

        self.btn_login = QPushButton("Войти (авто-сигнал)")
        self.btn_error = QPushButton("Вызвать ошибку в слоте")
        layout.addWidget(self.btn_login)
        layout.addWidget(self.btn_error)
        self.setCentralWidget(central)

        # Привязка кнопки к отправке сигнала
        self.btn_login.clicked.connect(lambda: self.user_logged_in.emit("Alice", 101))
        self.btn_error.clicked.connect(lambda: self.on_error_slot())

    # Автоматически связывается с сигналом user_logged_in благодаря AutoBindMixin
    @qt_slot(str, int)
    def on_user_logged_in(self, username: str, user_id: int) -> None:
        self.logger.info("Слот перехватил вход пользователя: %s (ID: %d)", username, user_id)

    @qt_slot(catch_exceptions=True)
    def on_error_slot(self) -> None:
        self.logger.info("Вызов слота с делением на ноль...")
        _ = 1 / 0  # Ошибка автоматически залогируется через chutils.logger!


def main() -> None:
    try:
        require_qt()
    except Exception as e:
        print(f"Qt не установлен: {e}")
        return

    app = QApplication(sys.argv)
    window = MyTypedWindow()
    window.resize(400, 200)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
