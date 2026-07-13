"""Пример использования модуля chutils.scraping.humanize для имитации поведения человека и анти-детекта.

Демонстрирует:
1. Математическую генерацию траекторий мыши Bezier.
2. Генерацию реалистичных задержек и опечаток при вводе текста.
3. Применение анти-детекта и скрытие автоматизации для Playwright и Selenium.
"""

from chutils.scraping.humanize import (
    BezierCurveGenerator,
    JitterDelayGenerator,
    KeyboardTypoGenerator,
    get_browser_launch_args,
)


def run_math_example() -> None:
    print("=== 1. Математическая генерация ===")

    # Генерация траектории мыши по Безье
    curve_gen = BezierCurveGenerator()
    start = (100, 100)
    end = (800, 600)
    points = curve_gen.generate(start, end, steps=10)
    print(f"Сгенерированная траектория мыши (первые 5 точек): {points[:5]}")

    # Генерация реалистичных задержек
    delay_gen = JitterDelayGenerator(strategy="lognormal", jitter=0.15)
    base_delay = 1.5
    randomized_delay = delay_gen.generate(base_delay)
    print(f"Базовая задержка: {base_delay} сек -> Случайная задержка: {randomized_delay:.3f} сек")

    # Генерация клавиатурного ввода с опечатками
    typo_gen = KeyboardTypoGenerator()
    text = "Hello from chutils!"
    sequence = typo_gen.generate_sequence(text, error_rate=0.15)
    print(f"\nПоследовательность ввода текста '{text}' с опечатками:")
    for step in sequence:
        if step.action == "type":
            print(f"Нажатие: '{step.char}'")
        elif step.action == "backspace":
            print("Нажатие: Backspace (стирание ошибки)")


def run_antidetect_example() -> None:
    print("\n=== 2. Скрытие автоматизации и анти-детект ===")

    # Получение флагов запуска браузера
    launch_args = get_browser_launch_args()
    print("Рекомендуемые аргументы запуска Chromium:")
    for arg in launch_args:
        print(f"  {arg}")

    # Пример использования с Playwright (псевдокод)
    print("\nДля применения в Playwright:")
    print("  context = await browser.new_context()")
    print("  await apply_antidetect_playwright(context)")

    # Пример использования с Selenium (псевдокод)
    print("\nДля применения в Selenium:")
    print("  driver = webdriver.Chrome(options=options)")
    print("  apply_antidetect_selenium(driver)")


if __name__ == "__main__":
    run_math_example()
    run_antidetect_example()
