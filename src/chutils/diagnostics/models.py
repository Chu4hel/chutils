from dataclasses import dataclass

from chutils.env import has_pydantic

if has_pydantic():
    from pydantic import BaseModel


    class CheckResult(BaseModel):
        """Результат выполнения проверки диагностики.

        Attributes:
            name: Название проверки.
            success: Флаг успешности проверки.
            critical: Флаг критичности проверки.
            execution_time: Время выполнения проверки в секундах.
            error: Текст ошибки, если проверка завершилась неудачно.
            message: Дополнительное информационное сообщение.
        """
        name: str
        success: bool
        critical: bool
        execution_time: float
        error: str | None = None
        message: str | None = None


    class HealthReport(BaseModel):
        """Отчет о состоянии работоспособности (Health Check) системы.

        Attributes:
            status: Общий статус системы (HEALTHY, DEGRADED, UNHEALTHY).
            results: Список результатов проверок.
            total_time: Общее время выполнения всех проверок в секундах.
        """
        status: str  # HEALTHY, DEGRADED, UNHEALTHY
        results: list[CheckResult]
        total_time: float
else:
    @dataclass
    class CheckResult:  # type: ignore[no-redef]
        """Результат выполнения проверки диагностики (вариант без Pydantic).

        Attributes:
            name: Название проверки.
            success: Флаг успешности проверки.
            critical: Флаг критичности проверки.
            execution_time: Время выполнения проверки в секундах.
            error: Текст ошибки, если проверка завершилась неудачно.
            message: Дополнительное информационное сообщение.
        """
        name: str
        success: bool
        critical: bool
        execution_time: float
        error: str | None = None
        message: str | None = None

        def model_dump(self) -> dict[str, str | bool | float | None]:
            """Преобразует модель в словарь.

            Returns:
                Словарь с данными о результате проверки.
            """
            return {
                "name": self.name,
                "success": self.success,
                "critical": self.critical,
                "execution_time": self.execution_time,
                "error": self.error,
                "message": self.message,
            }


    @dataclass
    class HealthReport:  # type: ignore[no-redef]
        """Отчет о состоянии работоспособности системы (вариант без Pydantic).

        Attributes:
            status: Общий статус системы (HEALTHY, DEGRADED, UNHEALTHY).
            results: Список результатов проверок.
            total_time: Общее время выполнения всех проверок в секундах.
        """
        status: str
        results: list[CheckResult]
        total_time: float

        def model_dump(self) -> dict[str, str | list[dict[str, str | bool | float | None]] | float]:
            """Преобразует отчет в словарь.

            Returns:
                Словарь с данными о состоянии здоровья системы.
            """
            return {
                "status": self.status,
                "results": [r.model_dump() for r in self.results],
                "total_time": self.total_time,
            }
