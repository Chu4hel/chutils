from chutils.config.utils import deep_merge


def test_deep_merge_basic():
    dict1 = {"a": 1, "b": {"c": 2}}
    dict2 = {"b": {"d": 3}, "e": 4}
    expected = {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}

    result = deep_merge(dict1, dict2)
    assert result == expected
    # Проверка изменения на месте
    assert dict1 == expected


def test_deep_merge_overwrite():
    dict1 = {"a": 1, "b": {"c": 2}}
    dict2 = {"a": 10, "b": {"c": 20}}
    expected = {"a": 10, "b": {"c": 20}}

    result = deep_merge(dict1, dict2)
    assert result == expected


def test_deep_merge_mixed_types():
    dict1 = {"a": {"b": 1}}
    dict2 = {"a": 2}
    expected = {"a": 2}

    result = deep_merge(dict1, dict2)
    assert result == expected


def test_deep_merge_empty():
    dict1 = {"a": 1}
    dict2 = {}
    assert deep_merge(dict1, dict2) == {"a": 1}

    dict1 = {}
    dict2 = {"a": 1}
    assert deep_merge(dict1, dict2) == {"a": 1}
