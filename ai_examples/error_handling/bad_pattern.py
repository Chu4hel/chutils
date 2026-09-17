"""
Антипаттерн: Неправильная обработка ошибок и глотание исключений.
"""


def read_system_config(file_path):
    # Плохо: Нет type hints в аргументах и возвращаемом значении.
    # Плохо: Нет docstring по стандарту Google Style.
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = f.read()
        return data
    except Exception:
        # Плохо: Перехватывается слишком широкий класс Exception.
        # Плохо: Ошибка полностью заглатывается (swallowed), вызывающий код
        # получит None и упадет позже с невнятной ошибкой AttributeError.
        pass


def parse_port(port_str):
    try:
        return int(port_str)
    except Exception as e:
        # Плохо: Возбуждается неспецифичное базовое исключение.
        # Плохо: Теряется оригинальный стек вызовов (traceback) ошибки.
        raise Exception(f"Ошибка парсинга порта: {e}")
