from chutils.scraping.humanize.math_utils import (
    BezierCurveGenerator,
    JitterDelayGenerator,
    KeyboardTypoGenerator,
    TypoAction,
    WindMouseGenerator,
)


def test_jitter_delay_generator() -> None:
    """Тестирует генерацию задержек с джиттером."""
    generator = JitterDelayGenerator(strategy="lognormal", jitter=0.1)

    # Задержка 0 должна возвращать 0
    assert generator.generate(0.0) == 0.0
    assert generator.generate(-1.5) == 0.0

    # Проверяем, что задержка положительна и варьируется
    delays = [generator.generate(1.0) for _ in range(50)]
    for d in delays:
        assert d > 0.0
        # Разброс при малом джиттере должен быть адекватным
        assert 0.5 < d < 2.0

    # Проверяем нормальную стратегию
    normal_gen = JitterDelayGenerator(strategy="normal", jitter=0.2)
    delays_normal = [normal_gen.generate(1.0) for _ in range(50)]
    for d in delays_normal:
        assert d > 0.0


def test_bezier_curve_generator() -> None:
    """Тестирует генератор траекторий мыши Безье."""
    generator = BezierCurveGenerator()

    start = (100, 100)
    end = (500, 400)
    steps = 30

    points = generator.generate(start, end, steps=steps)

    # Проверяем количество шагов
    assert len(points) == steps
    # Проверяем старт и финиш
    assert points[0] == start
    assert points[-1] == end

    # Проверяем короткое расстояние
    short_points = generator.generate(start, (102, 102), steps=10)
    assert short_points[0] == start
    assert short_points[-1] == (102, 102)


def test_keyboard_typo_generator() -> None:
    """Тестирует генератор опечаток."""
    generator = KeyboardTypoGenerator()
    text = "Hello, World!"

    # Сгенерированная последовательность действий с ошибками
    sequence = generator.generate_sequence(text, error_rate=0.3)

    # Симулируем ввод по сгенерированной последовательности
    typed_text: list[str] = []
    for action in sequence:
        if action.action == "type":
            typed_text.append(action.char)
        elif action.action == "backspace" and typed_text:
            typed_text.pop()

    # Результат симуляции должен в точности соответствовать исходному тексту
    final_text = "".join(typed_text)
    assert final_text == text

    # При нулевой вероятности ошибок опечаток быть не должно
    clean_sequence = generator.generate_sequence(text, error_rate=0.0)
    assert len(clean_sequence) == len(text)
    for i, action in enumerate(clean_sequence):
        assert action.action == "type"
        assert action.char == text[i]


def test_keyboard_typo_generator_cyrillic() -> None:
    """Тестирует генератор опечаток для кириллического текста (ЙЦУКЕН)."""
    generator = KeyboardTypoGenerator()
    text = "Привет, мир!"

    sequence = generator.generate_sequence(text, error_rate=0.8)

    # Должны появиться опечатки и backspace
    has_backspace = any(action.action == "backspace" for action in sequence)
    assert has_backspace, (
        "Ожидались опечатки с последующим исправлением backspace для кириллицы"
    )

    # Итоговый результат после воспроизведения действий должен совпадать с исходным
    typed_text: list[str] = []
    for action in sequence:
        if action.action == "type":
            typed_text.append(action.char)
        elif action.action == "backspace" and typed_text:
            typed_text.pop()
    assert "".join(typed_text) == text


def test_jcuken_neighbors_coverage() -> None:
    """Проверяет полноту покрытия букв русского алфавита в _JCUKEN_NEIGHBORS."""
    from chutils.scraping.humanize.math_utils import _JCUKEN_NEIGHBORS

    cyrillic_alphabet = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    for letter in cyrillic_alphabet:
        assert letter in _JCUKEN_NEIGHBORS, (
            f"Буква {letter} отсутствует в _JCUKEN_NEIGHBORS"
        )
        assert len(_JCUKEN_NEIGHBORS[letter]) > 0, (
            f"У буквы {letter} нет соседних клавиш"
        )


def test_keyboard_typo_generator_cyrillic_uppercase() -> None:
    """Проверяет сохранение верхнего регистра при опечатках в кириллице."""
    from chutils.scraping.humanize.math_utils import _JCUKEN_NEIGHBORS

    generator = KeyboardTypoGenerator()
    # Генерируем опечатки для заглавной буквы
    letter = "Й"
    sequence = generator.generate_sequence(letter, error_rate=1.0)

    # Первое действие должно быть опечаткой в верхнем регистре
    first_action = sequence[0]
    assert first_action.action == "type"
    assert first_action.char.isupper()
    assert first_action.char.lower() in _JCUKEN_NEIGHBORS["й"]


def test_keyboard_layout_typo_at_start() -> None:
    """Проверяет генерацию ошибки раскладки строго в начале ввода."""
    generator = KeyboardTypoGenerator()
    text = "Привет, мир!"

    # Запускаем с гарантированной ошибкой раскладки и без обычных опечаток
    sequence = generator.generate_sequence(text, error_rate=0.0, layout_error_rate=1.0)

    # Первые действия должны быть ошибочными символами латиницы (G, h, b...)
    # Затем ровно столько же Backspace
    # Затем весь текст "Привет, мир!"
    backspace_actions = [a for a in sequence if a.action == "backspace"]

    err_count = len(backspace_actions)
    assert 1 <= err_count <= 3
    # Первые err_count символов должны быть латиницей
    for i in range(err_count):
        assert sequence[i].action == "type"
        assert sequence[i].char.isascii()

    # Следующие err_count действий — backspace
    for i in range(err_count, err_count * 2):
        assert sequence[i].action == "backspace"

    # Воспроизведение последовательности дает исходный текст
    typed: list[str] = []
    for a in sequence:
        if a.action == "type":
            typed.append(a.char)
        elif a.action == "backspace" and typed:
            typed.pop()
    assert "".join(typed) == text


def test_keyboard_layout_typo_latin() -> None:
    """Проверяет генерацию ошибки раскладки в начале ввода латинского текста (ввод кириллицей)."""
    generator = KeyboardTypoGenerator()
    text = "Hello, world!"

    sequence = generator.generate_sequence(text, error_rate=0.0, layout_error_rate=1.0)

    backspace_actions = [a for a in sequence if a.action == "backspace"]
    err_count = len(backspace_actions)
    assert 1 <= err_count <= 3

    # Первые err_count символов должны быть кириллицей
    from chutils.scraping.humanize.math_utils import _JCUKEN_NEIGHBORS

    for i in range(err_count):
        assert sequence[i].action == "type"
        assert sequence[i].char.lower() in _JCUKEN_NEIGHBORS

    # Итоговый результат совпадает
    typed: list[str] = []
    for a in sequence:
        if a.action == "type":
            typed.append(a.char)
        elif a.action == "backspace" and typed:
            typed.pop()
    assert "".join(typed) == text


def test_keyboard_layout_typo_never_in_middle() -> None:
    """Проверяет, что ошибка раскладки не возникает в середине текста."""
    generator = KeyboardTypoGenerator()
    text = "Привет, как дела?"

    # Принудительно включаем layout_error_rate, но выключаем обычные опечатки
    sequence = generator.generate_sequence(text, error_rate=0.0, layout_error_rate=1.0)

    # Все backspace должны быть строго в начале (до того как начнется нормальный ввод)
    backspaces = [idx for idx, a in enumerate(sequence) if a.action == "backspace"]
    assert len(backspaces) > 0
    # Индексы всех backspace должны идти подряд в начале
    assert backspaces == list(range(len(backspaces), len(backspaces) * 2))


def _simulate_typing(sequence: list[TypoAction]) -> str:
    """Виртуальный эмулятор текстового поля для верификации последовательности действий ввода."""
    buffer: list[str] = []
    cursor = 0
    for a in sequence:
        if a.action == "type":
            buffer.insert(cursor, a.char)
            cursor += len(a.char)
        elif a.action == "backspace":
            if cursor > 0:
                cursor -= 1
                buffer.pop(cursor)
        elif a.action == "key":
            if a.char == "ArrowLeft":
                cursor = max(0, cursor - 1)
            elif a.char == "ArrowRight":
                cursor = min(len(buffer), cursor + 1)
            elif a.char == "End":
                cursor = len(buffer)
            elif a.char == "Home":
                cursor = 0
    return "".join(buffer)


def test_keyboard_delayed_fix_sequence() -> None:
    """Проверяет генерацию отложенного исправления опечаток клавишами стрелок и End."""
    generator = KeyboardTypoGenerator(delayed_fix_rate=1.0)
    text = "Автоматизация тестирования веб-приложений с имитацией поведения человека"

    sequence = generator.generate_sequence(
        text, error_rate=0.0, layout_error_rate=0.0, delayed_fix_rate=1.0
    )

    # Проверяем наличие навигационных клавиш ArrowLeft и End/ArrowRight
    arrow_lefts = [a for a in sequence if a.action == "key" and a.char == "ArrowLeft"]
    assert len(arrow_lefts) > 0, "Должна быть серия нажатий ArrowLeft"

    end_or_right = [
        a for a in sequence if a.action == "key" and a.char in ("End", "ArrowRight")
    ]
    assert len(end_or_right) > 0, (
        "Должно быть возвращение в конец строки через End или ArrowRight"
    )

    # Эмуляция текстового редактора должна дать исходный текст без искажений
    typed_result = _simulate_typing(sequence)
    assert typed_result == text


def test_keyboard_delayed_fix_short_text_no_op() -> None:
    """Проверяет, что для коротких текстов отложенное исправление не генерируется."""
    generator = KeyboardTypoGenerator(delayed_fix_rate=1.0)
    short_text = "Привет!"

    sequence = generator.generate_sequence(
        short_text, error_rate=0.0, layout_error_rate=0.0, delayed_fix_rate=1.0
    )

    # В коротком тексте не должно быть навигации стрелками
    arrow_keys = [a for a in sequence if a.action == "key"]
    assert len(arrow_keys) == 0
    assert _simulate_typing(sequence) == short_text


def test_keyboard_delayed_fix_latin() -> None:
    """Проверяет отложенное исправление опечатки для длинного текста на латинице."""
    generator = KeyboardTypoGenerator(delayed_fix_rate=1.0)
    text = "The quick brown fox jumps over the lazy dog near the riverbank"

    sequence = generator.generate_sequence(
        text, error_rate=0.0, layout_error_rate=0.0, delayed_fix_rate=1.0
    )

    # Должна быть навигация
    has_arrow_left = any(a.action == "key" and a.char == "ArrowLeft" for a in sequence)
    assert has_arrow_left

    # Идеальный результат после исправления
    assert _simulate_typing(sequence) == text


def test_wind_mouse_generator() -> None:
    """Тестирует генератор траекторий WindMouse."""
    generator = WindMouseGenerator()

    start = (100, 100)
    end = (500, 400)

    points = generator.generate(start, end)

    # Должен сгенерировать последовательность точек с задержками
    assert len(points) > 5
    # Последняя точка должна совпадать с целью
    assert points[-1][0] == end[0]
    assert points[-1][1] == end[1]

    # Все задержки должны быть положительными
    for px, py, delay in points:
        assert isinstance(px, int)
        assert isinstance(py, int)
        assert delay > 0.0

    # Проверка граничного случая: start == end
    same_points = generator.generate(start, start)
    assert len(same_points) == 1
    assert same_points[0][0] == start[0]
    assert same_points[0][1] == start[1]
