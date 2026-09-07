import math
import random
from typing import NamedTuple

_QWERTY_NEIGHBORS = {
    "q": "wa",
    "w": "qase",
    "e": "wsdr",
    "r": "edft",
    "t": "rfgy",
    "y": "tghu",
    "u": "yhji",
    "i": "ujko",
    "o": "iklp",
    "p": "ol",
    "a": "qwsz",
    "s": "wedcxz",
    "d": "erfvcxs",
    "f": "rtgbvcd",
    "g": "tyhnbvf",
    "h": "yujmnbg",
    "j": "uikmnh",
    "k": "ijlm",
    "l": "okp",
    "z": "asx",
    "x": "zsdc",
    "c": "xdfv",
    "v": "cfgb",
    "b": "vghn",
    "n": "bhjm",
    "m": "njk",
}
"""Карта соседних клавиш для QWERTY-раскладки, используемая для имитации опечаток."""


class WindMouseGenerator:
    """Генератор траекторий перемещения мыши на основе физической модели WindMouse (гравитация, ветер, инерция)."""

    def __init__(
        self,
        gravity: float = 9.0,
        wind: float = 3.0,
        min_wait: float = 0.002,
        max_wait: float = 0.005,
        max_step: float = 15.0,
        target_area: float = 8.0,
    ) -> None:
        """Инициализирует генератор WindMouse.

        Args:
            gravity: Сила притяжения курсора к целевой точке.
            wind: Величина случайного отклонения (ветра/дрейфа).
            min_wait: Минимальная пауза между смещениями (в секундах).
            max_wait: Максимальная пауза между смещениями (в секундах).
            max_step: Максимальное расстояние одного шага.
            target_area: Радиус целевой зоны, при входе в которую уменьшается влияние ветра.
        """
        self.gravity = gravity
        self.wind = wind
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.max_step = max_step
        self.target_area = target_area

    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        gravity: float | None = None,
        wind: float | None = None,
        min_wait: float | None = None,
        max_wait: float | None = None,
        max_step: float | None = None,
        target_area: float | None = None,
    ) -> list[tuple[int, int, float]]:
        """Генерирует последовательность точек (x, y, delay) от start к end.

        Args:
            start: Начальные координаты (x, y).
            end: Конечные координаты (x, y).
            gravity: Переопределение силы гравитации.
            wind: Переопределение силы ветра.
            min_wait: Переопределение минимальной задержки шага.
            max_wait: Переопределение максимальной задержки шага.
            max_step: Переопределение максимального размера шага.
            target_area: Переопределение радиуса целевой зоны.

        Returns:
            Список кортежей (x, y, step_delay), описывающих перемещение курсора с таймингами.
        """
        g = self.gravity if gravity is None else gravity
        w = self.wind if wind is None else wind
        min_w = self.min_wait if min_wait is None else min_wait
        max_w = self.max_wait if max_wait is None else max_wait
        max_s = self.max_step if max_step is None else max_step
        t_area = self.target_area if target_area is None else target_area

        start_x, start_y = start
        dest_x, dest_y = end

        if start_x == dest_x and start_y == dest_y:
            return [(dest_x, dest_y, random.uniform(min_w, max_w))]

        current_x, current_y = float(start_x), float(start_y)
        v_x, v_y = 0.0, 0.0
        w_x, w_y = 0.0, 0.0

        points: list[tuple[int, int, float]] = []
        max_iterations = 2000
        iteration = 0

        sqrt3 = math.sqrt(3)
        sqrt5 = math.sqrt(5)

        while iteration < max_iterations:
            iteration += 1
            dist = math.hypot(dest_x - current_x, dest_y - current_y)
            if dist < 1.0:
                break

            # В целевой зоне снижаем воздействие случайного ветра для точной доводки к цели
            cur_wind = w
            if dist < t_area:
                cur_wind = w * (dist / max(1.0, t_area))

            # Вектор случайного ветра (дрейф)
            w_x = (
                w_x / sqrt3 + (random.random() * (cur_wind * 2 + 1) - cur_wind) / sqrt5
            )
            w_y = (
                w_y / sqrt5 + (random.random() * (cur_wind * 2 + 1) - cur_wind) / sqrt5
            )

            # Сила притяжения к цели
            mag = max(dist, 1.0)
            g_x = (dest_x - current_x) * (g / mag)
            g_y = (dest_y - current_y) * (g / mag)

            v_x += w_x + g_x
            v_y += w_y + g_y

            # Ограничение максимальной скорости с динамическим затуханием
            v_mag = math.hypot(v_x, v_y)
            if v_mag > max_s:
                v_clip = max_s / 2.0 + random.random() * (max_s / 2.0)
                v_x = (v_x / v_mag) * v_clip
                v_y = (v_y / v_mag) * v_clip

            current_x += v_x
            current_y += v_y

            step_delay = random.uniform(min_w, max_w)
            points.append((round(current_x), round(current_y), step_delay))

        # Гарантируем попадание в конечную точку с небольшой паузой перед кликом/остановкой
        post_delay = random.uniform(0.04, 0.12)
        if not points or points[-1][0] != dest_x or points[-1][1] != dest_y:
            points.append((dest_x, dest_y, post_delay))
        else:
            last_x, last_y, _ = points[-1]
            points[-1] = (last_x, last_y, post_delay)

        return points


class BezierCurveGenerator:
    """Генератор траекторий перемещения на основе кривых Безье."""

    def generate(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        steps: int = 30,
        deviation: float = 0.2,
    ) -> list[tuple[int, int]]:
        """Генерирует сглаженную траекторию от start к end.

        Args:
            start: Начальная координата (x, y).
            end: Конечная координата (x, y).
            steps: Количество шагов (точек) в траектории.
            deviation: Максимальное отклонение контрольных точек от прямой линии.

        Returns:
            Список координат точек траектории движения.
        """
        if steps < 2:
            return [start, end]

        x0, y0 = start
        x3, y3 = end

        # Вычисляем расстояние
        dx = x3 - x0
        dy = y3 - y0
        dist = math.hypot(dx, dy)

        if dist < 10:
            return [start, end]

        # Генерируем случайные контрольные точки P1 и P2, отклоненные от прямой
        # Перпендикулярный вектор
        if dist == 0:
            nx, ny = 0.0, 0.0
        else:
            nx = -dy / dist
            ny = dx / dist

        offset_magnitude = dist * deviation

        # Первая контрольная точка P1 на 1/3 пути
        t1 = 0.33
        p1_base_x = x0 + dx * t1
        p1_base_y = y0 + dy * t1
        offset1 = random.uniform(-offset_magnitude, offset_magnitude)
        x1 = int(p1_base_x + nx * offset1)
        y1 = int(p1_base_y + ny * offset1)

        # Вторая контрольная точка P2 на 2/3 пути
        t2 = 0.66
        p2_base_x = x0 + dx * t2
        p2_base_y = y0 + dy * t2
        offset2 = random.uniform(-offset_magnitude, offset_magnitude)
        x2 = int(p2_base_x + nx * offset2)
        y2 = int(p2_base_y + ny * offset2)

        points = []
        for i in range(steps):
            # Используем нелинейное распределение t для имитации ускорения и замедления (ease-in-out)
            raw_t = i / (steps - 1)
            # Кубический ease-in-out
            if raw_t < 0.5:
                t = 4 * raw_t * raw_t * raw_t
            else:
                f = 2 * raw_t - 2
                t = 0.5 * f * f * f + 1

            # Кубическая кривая Безье
            mt = 1.0 - t
            mt2 = mt * mt
            mt3 = mt2 * mt
            t2_val = t * t
            t3 = t2_val * t

            x = int(mt3 * x0 + 3 * mt2 * t * x1 + 3 * mt * t2_val * x2 + t3 * x3)
            y = int(mt3 * y0 + 3 * mt2 * t * y1 + 3 * mt * t2_val * y2 + t3 * y3)

            points.append((x, y))

        return points


class JitterDelayGenerator:
    """Генератор реалистичных задержек."""

    def __init__(self, strategy: str = "lognormal", jitter: float = 0.15) -> None:
        """Инициализирует генератор задержек.

        Args:
            strategy: Стратегия ('lognormal' или 'normal').
            jitter: Коэффициент разброса (джиттер).
        """
        self.strategy = strategy
        self.jitter = max(0.01, jitter)

    def generate(self, base_delay: float) -> float:
        """Возвращает сгенерированную задержку на основе базовой.

        Args:
            base_delay: Базовая величина задержки (в секундах).

        Returns:
            Полученное случайное значение задержки с учетом джиттера.
        """
        if base_delay <= 0.0:
            return 0.0

        if self.strategy == "lognormal":
            # Логнормальное распределение: большинство значений близки к base, но бывают длинные хвосты
            # mu и sigma подбираются так, чтобы среднее значение было близко к base_delay
            sigma = self.jitter
            mu = math.log(base_delay) - (sigma**2) / 2
            val = random.lognormvariate(mu, sigma)
            return max(0.001, val)
        else:
            # Нормальное распределение
            val = random.gauss(base_delay, base_delay * self.jitter)
            return max(0.001, val)


class TypoAction(NamedTuple):
    """Представляет действие ввода символа или нажатия backspace при имитации печати."""

    action: str  # 'type' или 'backspace'
    char: str  # символ для ввода (пусто для backspace)


class KeyboardTypoGenerator:
    """Генератор последовательностей ввода символов с реалистичными опечатками."""

    def generate_sequence(
        self, text: str, error_rate: float = 0.05
    ) -> list[TypoAction]:
        """Генерирует последовательность нажатий клавиш для ввода текста.

        Включает случайные опечатки, их обнаружение и исправление через Backspace.

        Args:
            text: Исходный текст.
            error_rate: Вероятность совершения ошибки на каждом символе.

        Returns:
            Список действий TypoAction, имитирующий последовательный ввод текста человеком.
        """
        sequence: list[TypoAction] = []
        i = 0
        n = len(text)

        while i < n:
            char = text[i]

            # Решаем, делать ли опечатку
            if (
                error_rate > 0.0
                and random.random() < error_rate
                and char.lower() in _QWERTY_NEIGHBORS
            ):
                # Берем случайного соседа
                neighbors = _QWERTY_NEIGHBORS[char.lower()]
                wrong_char = random.choice(neighbors)
                # Сохраняем регистр
                if char.isupper():
                    wrong_char = wrong_char.upper()

                # Печатаем неверный символ
                sequence.append(TypoAction("type", wrong_char))

                # Иногда пользователь печатает еще один символ перед тем, как заметит ошибку
                notice_immediately = random.choice([True, False])
                if not notice_immediately and i + 1 < n:
                    next_char = text[i + 1]
                    sequence.append(TypoAction("type", next_char))

                    # Заметили ошибку, стираем оба символа
                    sequence.append(TypoAction("backspace", ""))
                    sequence.append(TypoAction("backspace", ""))
                    # Повторяем ввод текущего символа и переходим к следующему
                    sequence.append(TypoAction("type", char))
                    sequence.append(TypoAction("type", next_char))
                    i += 2
                else:
                    # Заметили сразу, стираем и пишем правильно
                    sequence.append(TypoAction("backspace", ""))
                    sequence.append(TypoAction("type", char))
                    i += 1
            else:
                sequence.append(TypoAction("type", char))
                i += 1

        return sequence
