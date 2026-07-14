from dataclasses import dataclass

from chutils.env import has_pydantic

if has_pydantic():
    from pydantic import BaseModel


    class CheckResult(BaseModel):
        name: str
        success: bool
        critical: bool
        execution_time: float
        error: str | None = None
        message: str | None = None


    class HealthReport(BaseModel):
        status: str  # HEALTHY, DEGRADED, UNHEALTHY
        results: list[CheckResult]
        total_time: float
else:
    @dataclass
    class CheckResult:
        name: str
        success: bool
        critical: bool
        execution_time: float
        error: str | None = None
        message: str | None = None

        def model_dump(self) -> dict[str, str | bool | float | None]:
            return {
                "name": self.name,
                "success": self.success,
                "critical": self.critical,
                "execution_time": self.execution_time,
                "error": self.error,
                "message": self.message,
            }


    @dataclass
    class HealthReport:
        status: str
        results: list[CheckResult]
        total_time: float

        def model_dump(self) -> dict[str, str | list[dict[str, str | bool | float | None]] | float]:
            return {
                "status": self.status,
                "results": [r.model_dump() for r in self.results],
                "total_time": self.total_time,
            }
