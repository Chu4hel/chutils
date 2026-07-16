import typing as t

from .base import ChutilsException


class ChutilsConfigurationError(ChutilsException):
    """Ошибка конфигурации компонентов chutils."""

    pass


class ChutilsValidationError(ChutilsException):
    """Исключение при ошибке валидации данных."""

    def __init__(
            self,
            message: str,
            errors: list[dict[str, t.Any]] | None = None,
            raw_error: Exception | None = None,
            hint: str | None = None,
            **context: t.Any,
    ) -> None:
        """Инициализирует исключение валидации.

        Args:
            message: Сообщение об ошибке.
            errors: Список ошибок в структурированном виде.
            raw_error: Исходное исключение (например, ValidationError), если доступно.
            hint: Опциональная подсказка.
            **context: Дополнительный контекст.
        """
        super().__init__(message, hint=hint, **context)
        self.errors = errors or []
        self.raw_error = raw_error

    def __str__(self) -> str:
        parts = [self.message]
        if self.errors:
            parts.append("Ошибки валидации:")
            for err in self.errors:
                loc_path = ".".join(str(x) for x in err.get("loc", ()))
                msg = err.get("msg", "Unknown error")
                inp = err.get("input")

                if inp is not None:
                    parts.append(f"  - {loc_path}: {msg} (получено: {inp!r})")
                else:
                    parts.append(f"  - {loc_path}: {msg}")

        if self.context:
            context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            parts.append(f"[Контекст: {context_str}]")

        if self.hint:
            parts.append(f"\nСОВЕТ: {self.hint}")

        return "\n".join(parts)

    def __rich__(self) -> t.Any:
        """Рендерит красивую таблицу ошибок валидации для rich.

        Returns:
            Экземпляр rich.table.Table.
        """
        from rich.table import Table

        table = Table(title=self.message, show_header=True, header_style="bold red")
        table.add_column("Поле / Путь", style="cyan")
        table.add_column("Причина ошибки", style="yellow")
        table.add_column("Полученное значение", style="green")

        for err in self.errors:
            loc_path = ".".join(str(x) for x in err.get("loc", ()))
            msg = err.get("msg", "Unknown error")
            inp = err.get("input")

            table.add_row(loc_path, msg, repr(inp) if inp is not None else "")

        return table


class EnvValidationError(ChutilsException):
    """Исключение при ошибке валидации переменных окружения."""

    def __init__(
            self,
            message: str,
            errors: list[dict[str, t.Any]] | None = None,
            hint: str | None = None,
            **context: t.Any,
    ) -> None:
        """Инициализирует исключение валидации переменных окружения.

        Args:
            message: Сообщение об ошибке.
            errors: Список ошибок в структурированном виде.
            hint: Опциональная подсказка.
            **context: Дополнительный контекст.
        """
        super().__init__(message, hint=hint, **context)
        self.errors = errors or []

    def __str__(self) -> str:
        parts = [self.message]
        if self.errors:
            parts.append("Ошибки валидации переменных окружения:")
            for err in self.errors:
                loc = err.get("loc", ())
                var_name = str(loc[0]) if loc else "UNKNOWN"
                msg = err.get("msg", "Unknown error")
                inp = err.get("input")

                if inp is not None:
                    parts.append(f"  - {var_name}: {msg} (получено: {inp!r})")
                else:
                    parts.append(f"  - {var_name}: {msg}")

        if self.context:
            context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            parts.append(f"[Контекст: {context_str}]")

        if self.hint:
            parts.append(f"\nСОВЕТ: {self.hint}")

        return "\n".join(parts)

    def __rich__(self) -> t.Any:
        """Рендерит красивую таблицу ошибок для rich.

        Returns:
            Экземпляр rich.table.Table.
        """
        from rich.table import Table

        table = Table(title=self.message, show_header=True, header_style="bold red")
        table.add_column("Переменная окружения", style="cyan")
        table.add_column("Причина ошибки", style="yellow")
        table.add_column("Полученное значение", style="green")

        for err in self.errors:
            loc = err.get("loc", ())
            var_name = str(loc[0]) if loc else "UNKNOWN"
            msg = err.get("msg", "Unknown error")
            inp = err.get("input")

            table.add_row(var_name, msg, repr(inp) if inp is not None else "")

        return table
