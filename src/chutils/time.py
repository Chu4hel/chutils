"""
Модуль для работы со временем и датами.
Обеспечивает UTC-first подход, корректную обработку часовых поясов и парсинг.
"""

import logging
from datetime import datetime, timezone
from typing import Union, Optional

# Настраиваем логгер
logger = logging.getLogger(__name__)


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


# --- Humanize Time ---

_DEFAULT_LOCALES = {
    'en': {
        'now': 'just now',
        'yesterday': 'yesterday',
        'tomorrow': 'tomorrow',
        'past': '{n} {unit} ago',
        'future': 'in {n} {unit}',
        'units': {
            'second': ('second', 'seconds'),
            'minute': ('minute', 'minutes'),
            'hour': ('hour', 'hours'),
            'day': ('day', 'days'),
            'month': ('month', 'months'),
            'year': ('year', 'years'),
        }
    },
    'ru': {
        'now': 'только что',
        'yesterday': 'вчера',
        'tomorrow': 'завтра',
        'past': '{n} {unit} назад',
        'future': 'через {n} {unit}',
        'units': {
            'second': ('секунду', 'секунды', 'секунд'),
            'minute': ('минуту', 'минуты', 'минут'),
            'hour': ('час', 'часа', 'часов'),
            'day': ('день', 'дня', 'дней'),
            'month': ('месяц', 'месяца', 'месяцев'),
            'year': ('год', 'года', 'лет'),
        }
    }
}


def _pluralize_ru(n: int, forms: tuple) -> str:
    """Хелпер для русской плюрализации."""
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    elif 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return forms[1]
    else:
        return forms[2]


def humanize_timedelta(dt: datetime, locale: str = 'ru', custom_locales: Optional[dict] = None) -> str:
    """
    Превращает дату в человекочитаемую строку относительно текущего времени.
    
    Args:
        dt: Дата для сравнения.
        locale: Код локали ('ru' или 'en').
        custom_locales: Дополнительные локали или переопределения.
        
    Returns:
        Строка вида "5 минут назад", "вчера" и т.д.
    """
    target_dt = _ensure_aware_utc(dt)
    now = utc_now()
    diff = now - target_dt
    seconds = diff.total_seconds()
    abs_seconds = abs(seconds)

    # Объединяем локали
    all_locales = _DEFAULT_LOCALES.copy()
    if custom_locales:
        all_locales.update(custom_locales)

    if locale not in all_locales:
        logger.warning("Locale '%s' not found, falling back to 'en'", locale)
        locale = 'en'

    loc = all_locales[locale]

    if abs_seconds < 10:
        return loc['now']

    # Определяем единицу измерения и количество
    # Используем небольшое смещение (округление)
    if abs_seconds < 60:
        n, unit_key = int(abs_seconds), 'second'
    elif abs_seconds < 3600:
        n, unit_key = int((abs_seconds + 30) / 60), 'minute'
    elif abs_seconds < 86400 - 1800:  # Все что меньше 23.5 часов - это часы
        n, unit_key = int((abs_seconds + 1800) / 3600), 'hour'
    elif abs_seconds < 2592000:  # 30 дней
        n, unit_key = int((abs_seconds + 43200) / 86400), 'day'
    elif abs_seconds < 31536000:  # 365 дней
        n, unit_key = int(abs_seconds / 2592000), 'month'
    else:
        n, unit_key = int(abs_seconds / 31536000), 'year'

    # Специальные случаи для дней
    if unit_key == 'day' and n == 1:
        if seconds > 0:
            return loc['yesterday']
        else:
            return loc['tomorrow']

    # Форматируем единицу измерения
    forms = loc['units'][unit_key]
    if locale == 'ru':
        unit_str = _pluralize_ru(n, forms)
    else:
        unit_str = forms[0] if n == 1 else forms[1]

    # Собираем финальную строку
    pattern = loc['past'] if seconds > 0 else loc['future']
    return pattern.format(n=n, unit=unit_str)
