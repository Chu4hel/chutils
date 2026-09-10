"""
Утверждения (assertions) качества и полноты извлеченных скрапером данных.

Предоставляет специализированные валидаторы для автотестов:
- Полнота извлечения (`assert_extraction_complete`)
- Валидность HTTP(S) ссылок (`assert_valid_url`)
- Корректность цен и валют (`assert_valid_price`)
- Соответствие Pydantic-схемам (`assert_schema_match`)
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from chutils.logger import setup_logger

logger = setup_logger(__name__)


def assert_extraction_complete(
    data: dict[str, Any] | list[dict[str, Any]],
    required_keys: list[str] | None = None,
    allow_empty_strings: bool = False,
) -> None:
    """Проверяет полноту и отсутствие пустых значений в распарсенных данных.

    Args:
        data: Распарсенный словарь или список словарей.
        required_keys: Список обязательных ключей, которые должны присутствовать.
        allow_empty_strings: Разрешать ли пустые строки в качестве валидных значений.

    Raises:
        AssertionError: Если обнаружен отсутствующий ключ, значение None или пустая строка.
    """
    if isinstance(data, list):
        for index, item in enumerate(data):
            try:
                assert_extraction_complete(
                    item,
                    required_keys=required_keys,
                    allow_empty_strings=allow_empty_strings,
                )
            except AssertionError as err:
                raise AssertionError(f"Элемент [{index}]: {err}") from None
        return

    # Проверка наличия обязательных ключей
    if required_keys:
        for key in required_keys:
            if key not in data:
                raise AssertionError(
                    f"Отсутствует обязательный ключ: {key!r} в {data!r}"
                )

    # Проверка значений
    for key, val in data.items():
        if val is None:
            raise AssertionError(
                f"Поле {key!r} содержит недопустимое пустое значение None в {data!r}"
            )
        if isinstance(val, str) and not val.strip() and not allow_empty_strings:
            raise AssertionError(
                f"Поле {key!r} содержит недопустимое пустое значение (пустая строка) в {data!r}"
            )


def assert_valid_url(
    url: str,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
    require_netloc: bool = True,
) -> None:
    """Проверяет корректность извлеченного URL адреса.

    Args:
        url: Строка URL для проверки.
        allowed_schemes: Допустимые схемы протоколов (по умолчанию http, https).
        require_netloc: Требовать ли наличие доменного имени или сетевого хоста.

    Raises:
        AssertionError: Если URL невалиден, относителен или имеет недопустимую схему.
    """
    if not isinstance(url, str) or not url.strip():
        raise AssertionError(f"URL не является непустой строкой: {url!r}")

    parsed = urlparse(url.strip())

    if not parsed.scheme:
        raise AssertionError(f"Относительный URL без схемы: {url!r}")

    if parsed.scheme.lower() not in allowed_schemes:
        raise AssertionError(
            f"Недопустимая схема URL '{parsed.scheme}': {url!r}. "
            f"Ожидались схемы: {allowed_schemes}"
        )

    if require_netloc and not parsed.netloc:
        raise AssertionError(f"Отсутствует сетевой хост (domain/netloc) в URL: {url!r}")


def assert_valid_price(
    price: float | Decimal | str,
    min_value: float = 0.0,
    max_value: float | None = None,
) -> None:
    """Проверяет корректность и границы цены товара.

    Args:
        price: Значение цены в виде числа, Decimal или форматированной строки ("1 499 ₽", "$19.99").
        min_value: Минимально допустимое значение цены (по умолчанию 0.0).
        max_value: Опциональное максимально допустимое значение цены.

    Raises:
        AssertionError: Если цена нераспознаваема или выходит за установленные границы.
    """
    numeric_price: float

    if isinstance(price, (int, float, Decimal)):
        numeric_price = float(price)
    elif isinstance(price, str):
        # Удаляем неразрывные пробелы и пробелы
        clean_str = price.replace("\xa0", " ").replace(" ", "")
        # Ищем числовой паттерн
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", clean_str)
        if not match:
            raise AssertionError(
                f"Не удалось распознать числовое значение цены из строки: {price!r}"
            )
        raw_num = match.group(0).replace(",", ".")
        try:
            numeric_price = float(raw_num)
        except ValueError:
            raise AssertionError(
                f"Не удалось преобразовать значение {raw_num!r} в число из цены {price!r}"
            )
    else:
        raise TypeError(f"Неподдерживаемый тип для цены: {type(price).__name__}")

    if numeric_price < min_value:
        raise AssertionError(
            f"Цена меньше минимального порога ({numeric_price} < {min_value}) для значения {price!r}"
        )

    if max_value is not None and numeric_price > max_value:
        raise AssertionError(
            f"Цена превышает максимальный порог ({numeric_price} > {max_value}) для значения {price!r}"
        )


def assert_schema_match(
    data: dict[str, Any] | list[dict[str, Any]],
    schema_cls: type,
) -> None:
    """Проверяет соответствие извлеченных данных Pydantic схеме или классу модели.

    Args:
        data: Распарсенный словарь или список словарей.
        schema_cls: Класс модели (например, Pydantic BaseModel или dataclass).

    Raises:
        AssertionError: Если данные не соответствуют сигнатуре схемы.
    """
    items_to_check = data if isinstance(data, list) else [data]

    validate_fn: Any
    if hasattr(schema_cls, "model_validate"):
        validate_fn = schema_cls.model_validate
    elif hasattr(schema_cls, "parse_obj"):
        validate_fn = schema_cls.parse_obj
    else:
        validate_fn = schema_cls

    for idx, item in enumerate(items_to_check):
        try:
            validate_fn(item)
        except Exception as exc:
            prefix = f"Элемент [{idx}]: " if isinstance(data, list) else ""
            raise AssertionError(
                f"{prefix}Ошибка валидации схемы {schema_cls.__name__}: {exc}"
            ) from None
