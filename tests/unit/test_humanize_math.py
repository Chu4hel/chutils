from chutils.scraping.humanize.math_utils import (
    BezierCurveGenerator,
    JitterDelayGenerator,
    KeyboardTypoGenerator,
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
        elif action.action == "backspace":
            if typed_text:
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
