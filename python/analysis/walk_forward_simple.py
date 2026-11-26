#!/usr/bin/env python3
"""
Walk-forward тестирование базовых методов из models.py.
Проверяем, работают ли они лучше случайного выбора.
"""
import sys
from pathlib import Path
import random
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import get_game
from lottery import models


def walk_forward_test_model(game_slug, model, train_size=1000, test_size=100):
    """
    Walk-forward тест модели.

    Args:
        game_slug: ID игры
        model: Model из models.py
        train_size: Размер обучающей выборки
        test_size: Сколько тиражей тестировать

    Returns:
        dict с результатами
    """
    print(f"\n{'='*80}")
    print(f"🧪 Тест: {model.title} на {game_slug}")
    print(f"{'='*80}")

    # Загрузка данных
    game = get_game(game_slug)
    data = load_game_data(game)

    X = data.matrices[0]
    spec = data.fmt.blocks[0]
    T, N = X.shape
    k = spec.count

    if T < train_size + test_size:
        print(f"❌ Недостаточно данных: {T} < {train_size + test_size}")
        return None

    print(f"📊 Всего тиражей: {T}")
    print(f"🏋️  Обучение: первые {train_size}")
    print(f"🧪 Тест: следующие {test_size}")

    # Статистика
    total_matches = 0  # Всего совпадений (модель)
    random_matches = 0  # Совпадения для случайного выбора

    # Walk-forward
    for i in range(test_size):
        # Текущая позиция
        train_end = train_size + i
        test_idx = train_end

        if test_idx >= T:
            break

        # Обучающая выборка
        X_train = X[:train_end]

        # Создаем Features
        try:
            feat = models.Features(X_train, k)

            # Получаем оценки (scores matrix: T+1 x N)
            S = model.fn(feat)

            # Предсказание - последняя строка (t=T)
            scores = S[-1]  # Оценки для тиража T+1 (у нас это test_idx)
            pred_indices = np.argsort(scores)[-k:]  # Топ-k индексов
            pred = set(pred_indices.tolist())

            # Реальный результат
            actual = set(j for j in range(N) if X[test_idx, j] == 1)

            # Подсчет совпадений
            matches = len(pred & actual)
            total_matches += matches

            # Случайный выбор для сравнения
            random_pred = set(random.sample(range(N), k))
            random_match = len(random_pred & actual)
            random_matches += random_match

        except Exception as e:
            print(f"⚠️ Ошибка на итерации {i}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if test_size > 0:
        avg_matches = total_matches / test_size
        avg_random = random_matches / test_size
        expected = k * k / N  # Матожидание совпадений

        print(f"\n📈 РЕЗУЛЬТАТЫ:")
        print(f"  Модель: {avg_matches:.2f} совпадений/тираж")
        print(f"  Случайный: {avg_random:.2f} совпадений/тираж")
        print(f"  Ожидается: {expected:.2f} совпадений/тираж")

        improvement = 100 * (avg_matches - expected) / expected if expected > 0 else 0
        random_improvement = 100 * (avg_random - expected) / expected if expected > 0 else 0

        print(f"\n  Улучшение модели: {improvement:+.1f}%")
        print(f"  Улучшение случайного: {random_improvement:+.1f}%")

        # Вывод
        if abs(improvement) < 5:
            verdict = "✅ Модель работает как случайный выбор (ожидаемо для честной лотереи)"
        elif improvement > random_improvement + 3:
            verdict = "🎯 Модель немного лучше случайного (вероятно, статистический шум)"
        else:
            verdict = "⚠️ Модель не лучше случайного выбора"

        print(f"\n💡 ВЫВОД: {verdict}")

        return {
            "model": model_name,
            "game": game_slug,
            "tests": test_size,
            "avg_matches": avg_matches,
            "expected": expected,
            "improvement_pct": improvement,
        }

    return None


def main():
    print("\n" + "="*80)
    print("🚀 WALK-FORWARD ТЕСТИРОВАНИЕ БАЗОВЫХ МЕТОДОВ")
    print("="*80)
    print("\nЦель: Проверить, работают ли методы лучше случайного выбора")
    print("Метод: Walk-forward validation (обучение на прошлом, тест на будущем)")
    print("\nОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Методы НЕ должны улучшать точность в честной лотерее!")
    print("Если метод показывает >5% улучшение - это либо шум, либо баг!")

    # Список тестов: (игра, модель, название, train_size, test_size)
    tests = [
        ("6x45", models.hot, "Hot Numbers", 500, 50),
        ("6x45", models.cold, "Cold Numbers", 500, 50),
        ("6x45", models.recent_repeat, "Recent Repeat", 500, 50),
        ("5x36plus", models.hot, "Hot Numbers", 1000, 100),
        ("rapido2", models.hot, "Hot Numbers", 500, 50),
        ("keno2", models.hot, "Hot Numbers", 1000, 100),
    ]

    results = []
    for game_slug, model_fn, model_name, train, test in tests:
        try:
            result = walk_forward_test_model(game_slug, model_fn, model_name, train, test)
            if result:
                results.append(result)
        except Exception as e:
            print(f"❌ Ошибка для {game_slug} / {model_name}: {e}")
            import traceback
            traceback.print_exc()

    # Итоговая сводка
    print(f"\n{'='*80}")
    print("📊 ИТОГОВАЯ СВОДКА")
    print(f"{'='*80}")

    print(f"\n{'МОДЕЛЬ':<20} {'ИГРА':<15} {'ТЕСТОВ':<10} {'УЛУЧШ.':<12} {'ВЫВОД'}")
    print("-" * 80)

    for r in results:
        imp = r['improvement_pct']
        if abs(imp) < 5:
            verdict = "Случайный ✓"
        elif imp > 5:
            verdict = "Лучше (шум?)"
        else:
            verdict = "Хуже"

        print(f"{r['model']:<20} {r['game']:<15} {r['tests']:<10} {imp:+6.1f}%      {verdict}")

    # Анализ
    if results:
        avg_improvement = sum(r['improvement_pct'] for r in results) / len(results)
        max_improvement = max(r['improvement_pct'] for r in results)
        min_improvement = min(r['improvement_pct'] for r in results)

        print(f"\n📊 СТАТИСТИКА:")
        print(f"  Среднее улучшение: {avg_improvement:+.1f}%")
        print(f"  Макс: {max_improvement:+.1f}%, Мин: {min_improvement:+.1f}%")

    print("\n" + "="*80)
    print("🎓 ГЛАВНЫЙ ВЫВОД:")
    print("-" * 80)
    print("""
В честной лотерее НЕВОЗМОЖНО предсказать результат лучше случайного выбора.

Математическое доказательство:
1) Каждый тираж независим от прошлых (по определению честной лотереи)
2) Все комбинации равновероятны (1/C(n,k) для каждой)
3) Прошлые результаты не влияют на будущие

Если модель показывает \"улучшение\" >5%, это:
  • Статистический шум (малая выборка)
  • Случайная флуктуация (luck)
  • Переобучение на артефактах данных
  • Баг в коде

Правильный результат: ~0% улучшения для всех моделей.

💡 ПРИМЕНЕНИЕ МЕТОДОВ:
  ✅ Fraud Detection - обнаружить если лотерея НЕчестная
  ✅ Entertainment - генерация "интересных" комбинаций
  ✅ Education - изучение статистики и вероятностей
  ✅ Unpopular Tickets - комбинации, которые редко выбирают
  ❌ Prediction - НЕ работает для честной лотереи!
""")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Фиксируем seed для воспроизводимости
    random.seed(42)
    np.random.seed(42)
    main()
