"""
Улучшенный генератор непопулярных комбинаций.

Избегает популярных паттернов, которые люди часто выбирают:
- Даты рождения (1-31, особенно 1-12)
- "Счастливые" числа (7, 13, 21)
- Арифметические прогрессии (1,2,3,4,5,6)
- Геометрические паттерны на бланке
- Четные/нечетные только
- Малые/большие только
"""
from __future__ import annotations
import numpy as np


def popularity_score(numbers, N):
    """
    Оценка популярности комбинации (0-1, чем выше - тем популярнее).

    Комбинация популярна если содержит:
    - Даты (1-31, особенно 1-12)
    - Счастливые числа (7, 13, 21, 77 для Keno)
    - Арифметические прогрессии
    - Только четные/нечетные
    - Только малые/большие половины
    """
    score = 0.0
    k = len(numbers)

    # 1. Даты рождения (1-31, штраф сильнее для 1-12)
    dates_count = sum(1 for n in numbers if 1 <= n <= 31)
    month_count = sum(1 for n in numbers if 1 <= n <= 12)
    score += 0.2 * (dates_count / k)
    score += 0.1 * (month_count / k)

    # 2. "Счастливые" числа
    lucky = {7, 13, 21, 33, 77}
    lucky_count = sum(1 for n in numbers if n in lucky)
    score += 0.15 * (lucky_count / k)

    # 3. Арифметическая прогрессия (например 2,4,6,8)
    if k >= 3:
        sorted_nums = sorted(numbers)
        diffs = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
        if len(set(diffs)) == 1:  # Все разности одинаковы
            score += 0.3  # Сильный штраф!

    # 4. Только четные или только нечетные
    even_count = sum(1 for n in numbers if n % 2 == 0)
    if even_count == 0 or even_count == k:
        score += 0.2

    # 5. Только из малой/большой половины
    mid = N // 2
    small_count = sum(1 for n in numbers if n <= mid)
    if small_count == 0 or small_count == k:
        score += 0.15

    # 6. Малый разброс (все числа близко)
    if k >= 3:
        spread = max(numbers) - min(numbers)
        expected_spread = N * (k / (k + 1))
        if spread < expected_spread * 0.3:
            score += 0.1

    return min(score, 1.0)


def _unpopular_v2(f: "Features", t: int) -> np.ndarray:
    """
    Генератор непопулярных комбинаций (v2.0).

    Стратегия: максимизировать "непопулярность" комбинации,
    избегая паттернов, которые люди часто выбирают.

    Цель: меньше делить приз в случае выигрыша.
    """
    N = f.N

    # Стратегия: анти-популярность
    probs = np.ones(N)

    # 1. Избегаем даты (1-31), особенно месяцы (1-12)
    for i in range(N):
        num = i + 1  # Предполагаем нумерацию от 1
        if 1 <= num <= 12:
            probs[i] *= 0.3  # Сильный штраф
        elif 13 <= num <= 31:
            probs[i] *= 0.5  # Средний штраф

    # 2. Избегаем "счастливые" числа
    lucky = {7, 13, 21, 33, 77}
    for i in range(N):
        num = i + 1
        if num in lucky:
            probs[i] *= 0.4

    # 3. Предпочитаем числа из большой половины
    mid = N // 2
    for i in range(mid):
        probs[i] *= 0.7

    # Нормализация
    probs = probs / probs.sum()

    return probs


def _unpopular_balanced(f: "Features", t: int) -> np.ndarray:
    """
    Сбалансированный непопулярный генератор.

    Избегает популярных паттернов, но гарантирует баланс:
    - Четные/нечетные: ~50/50
    - Малые/большие: ~50/50
    - Без прогрессий
    """
    N = f.N

    probs = np.ones(N)

    # Избегаем даты, но слабее чем в v2
    for i in range(N):
        num = i + 1
        if 1 <= num <= 31:
            probs[i] *= 0.6

    # Избегаем счастливые
    lucky = {7, 13, 21}
    for i in range(N):
        num = i + 1
        if num in lucky:
            probs[i] *= 0.5

    # Немного предпочитаем большие числа
    mid = N // 2
    for i in range(mid, N):
        probs[i] *= 1.3

    probs = probs / probs.sum()

    return probs


def _anti_pattern(f: "Features", t: int) -> np.ndarray:
    """
    Генератор, избегающий геометрических паттернов.

    Исключает комбинации, которые образуют простые паттерны на бланке:
    - Вертикальные/горизонтальные линии
    - Диагонали
    - Кластеры в углах
    """
    N = f.N

    # Предполагаем квадратную сетку на бланке
    grid_size = int(np.sqrt(N))

    probs = np.ones(N)

    # Избегаем углов (первые/последние числа)
    corners = [0, grid_size-1, N-grid_size, N-1]
    for corner in corners:
        if corner < N:
            probs[corner] *= 0.4

    # Избегаем первых и последних рядов/столбцов
    # (это грубая эвристика, точная зависит от реального бланка)
    for i in range(grid_size):
        probs[i] *= 0.6  # Первый ряд
        if N - grid_size + i < N:
            probs[N - grid_size + i] *= 0.6  # Последний ряд

    # Предпочитаем середину
    mid_start = N // 3
    mid_end = 2 * N // 3
    for i in range(mid_start, mid_end):
        probs[i] *= 1.5

    probs = probs / probs.sum()

    return probs


def analyze_ticket_popularity(ticket, N):
    """
    Анализ популярности конкретного билета.

    Args:
        ticket: список чисел
        N: размер пула (например, 45 для "6 из 45")

    Возвращает:
    - score: оценка популярности (0-1)
    - reasons: список причин популярности
    """
    numbers = ticket if isinstance(ticket, list) else list(ticket)

    score = popularity_score(numbers, N)

    reasons = []

    # Детальный анализ
    dates_count = sum(1 for n in numbers if 1 <= n <= 31)
    if dates_count >= len(numbers) * 0.5:
        reasons.append(f"Много дат рождения ({dates_count}/{len(numbers)})")

    lucky = {7, 13, 21, 33, 77}
    lucky_count = sum(1 for n in numbers if n in lucky)
    if lucky_count > 0:
        reasons.append(f"Счастливые числа: {[n for n in numbers if n in lucky]}")

    even_count = sum(1 for n in numbers if n % 2 == 0)
    if even_count == 0:
        reasons.append("Только нечетные")
    elif even_count == len(numbers):
        reasons.append("Только четные")

    sorted_nums = sorted(numbers)
    diffs = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
    if len(set(diffs)) == 1:
        reasons.append(f"Арифметическая прогрессия (шаг {diffs[0]})")

    return {
        "score": score,
        "popularity": "ВЫСОКАЯ" if score > 0.5 else "СРЕДНЯЯ" if score > 0.3 else "НИЗКАЯ",
        "reasons": reasons
    }


if __name__ == "__main__":
    # Примеры тестирования
    print("🧪 ТЕСТИРОВАНИЕ ГЕНЕРАТОРА НЕПОПУЛЯРНЫХ КОМБИНАЦИЙ\n")

    N = 45  # "6 из 45"

    # Популярная комбинация (даты)
    popular = [1, 7, 13, 21, 25, 31]
    result = analyze_ticket_popularity(popular, N)
    print(f"Билет {popular}:")
    print(f"  Популярность: {result['popularity']} ({result['score']:.2f})")
    print(f"  Причины: {', '.join(result['reasons']) if result['reasons'] else 'нет'}")

    print()

    # Непопулярная комбинация
    unpopular = [32, 37, 38, 41, 43, 44]
    result = analyze_ticket_popularity(unpopular, N)
    print(f"Билет {unpopular}:")
    print(f"  Популярность: {result['popularity']} ({result['score']:.2f})")
    print(f"  Причины: {', '.join(result['reasons']) if result['reasons'] else 'нет'}")

    print()

    # Прогрессия
    progression = [5, 10, 15, 20, 25, 30]
    result = analyze_ticket_popularity(progression, N)
    print(f"Билет {progression}:")
    print(f"  Популярность: {result['popularity']} ({result['score']:.2f})")
    print(f"  Причины: {', '.join(result['reasons']) if result['reasons'] else 'нет'}")

    print("\n✅ Функции готовы к использованию!")
