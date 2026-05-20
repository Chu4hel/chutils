"""
Модуль для работы со временем и датами.
Обеспечивает UTC-first подход, корректную обработку часовых поясов и парсинг.
"""

from datetime import datetime, timezone
from typing import Union


def utc_now() -> datetime:
    """
    Возвращает текущее время в формате UTC с информацией о часовом поясе.
    
    Returns:
        Объект datetime, представляющий текущее время в UTC.
    """
    return datetime.now(timezone.utc)


def _ensure_aware_utc(dt: datetime) -> datetime:
    """
    Гарантирует, что объект datetime является "timezone aware" в зоне UTC.
    
    Если dt наивный (naive), он считается локальным временем и конвертируется в UTC.
    Если dt уже осведомленный (aware), он просто конвертируется в UTC.
    
    Args:
        dt: Исходный объект datetime.
        
    Returns:
        Объект datetime в зоне UTC.
    """
    if dt.tzinfo is None:
        # Наивный объект -> считаем локальным и переводим в UTC
        return dt.astimezone(timezone.utc)

    # Осведомленный объект -> просто переводим в UTC
    return dt.astimezone(timezone.utc)


def parse_datetime(value: Union[str, int, float]) -> datetime:
    """
    Парсит дату и время из различных форматов и приводит к UTC aware объекту.
    
    Поддерживаемые форматы:
    - ISO 8601 строки (например, "2023-01-01T12:00:00").
    - UNIX timestamps в секундах (int/float).
    - UNIX timestamps в миллисекундах (длинные числа).
    
    Если установлена библиотека python-dateutil (chutils[date]), 
    поддерживается более широкий спектр форматов.
    
    Args:
        value: Строка с датой или числовое представление (timestamp).
        
    Returns:
        Объект datetime в зоне UTC.
        
    Raises:
        ValueError: Если формат не распознан.
    """
    # 1. Обработка числовых значений (timestamps)
    if isinstance(value, (int, float)):
        # Эвристика: если число слишком большое, считаем это миллисекундами
        if value > 1e11:  # Примерно после 2286 года в секундах
            value = value / 1000.0
        return datetime.fromtimestamp(value, timezone.utc)

    # 2. Попытка парсинга строки
    # Сначала пробуем стандартный ISO формат
    try:
        dt = datetime.fromisoformat(value)
        return _ensure_aware_utc(dt)
    except ValueError:
        pass

    # Пытаемся использовать dateutil, если он доступен
    try:
        from dateutil import parser
        dt = parser.parse(value)
        return _ensure_aware_utc(dt)
    except (ImportError, ValueError, OverflowError):
        pass

    # Если ничего не помогло, кидаем ошибку
    raise ValueError(f"Не удалось распознать формат даты/времени: {value}")
