from datetime import datetime, timezone, timedelta

import pytest

from chutils.time import utc_now, _ensure_aware_utc, parse_datetime


def test_utc_now():
    now = utc_now()
    assert now.tzinfo == timezone.utc
    # Проверяем, что время актуальное (разница меньше секунды)
    assert abs((datetime.now(timezone.utc) - now).total_seconds()) < 1.0


def test_ensure_aware_utc_already_aware():
    # Уже в UTC
    dt_utc = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert _ensure_aware_utc(dt_utc) == dt_utc

    # В другом часовом поясе
    dt_ny = datetime(2023, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=-5)))
    aware_utc = _ensure_aware_utc(dt_ny)
    assert aware_utc.tzinfo == timezone.utc
    assert aware_utc.hour == 17  # 12 + 5


def test_ensure_aware_utc_naive():
    # Наивный объект
    dt_naive = datetime(2023, 1, 1, 12, 0)
    aware_utc = _ensure_aware_utc(dt_naive)

    assert aware_utc.tzinfo == timezone.utc
    # Проверяем корректность конвертации из локального времени
    assert aware_utc == dt_naive.astimezone(timezone.utc)


def test_parse_datetime_timestamps():
    # Секунды
    ts = 1672574400  # 2023-01-01 12:00:00 UTC
    dt = parse_datetime(ts)
    assert dt == datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)

    # Миллисекунды
    ts_ms = 1672574400000
    dt_ms = parse_datetime(ts_ms)
    assert dt_ms == datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_parse_datetime_iso_strings():
    # ISO без зоны
    s = "2023-01-01T12:00:00"
    dt = parse_datetime(s)
    assert dt.tzinfo == timezone.utc
    # ISO с зоной
    s_zone = "2023-01-01T12:00:00+03:00"
    dt_zone = parse_datetime(s_zone)
    assert dt_zone == datetime(2023, 1, 1, 9, 0, tzinfo=timezone.utc)


def test_parse_datetime_invalid():
    with pytest.raises(ValueError):
        parse_datetime("not a date")
