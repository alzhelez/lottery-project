#!/usr/bin/env python3
"""
Walk-forward тестирование базовых методов предсказания.

Цель: Проверить, что методы НЕ работают лучше случайного выбора.
"""
import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery import models
from lottery.models import Features
from lottery.drawfile import GameData, load_game_data
from lottery.games import get_game
from scipy.stats import ttest_1samp


def walk_forward_test(game_slug: str, model: models.Model, train_size: int = 500, test_size: int = 50):
    """
    Walk-forward тест: обучаем на train_size тиражах, тестируем на test_size.
    """
    print(f"\n{'='*80}")
    print(f"🧪 {model.title} | {game_slug}")
    print(f"{'='*80}")

    # Загрузка
    game = get_game(game_slug)
    gdata = load_game_data(game)

    if not gdata.matrices or len(gdata.matrices) == 0:
        print(f"⚠️  Нет данных для {game_slug}")
        return None

    x = gdata.matrices[0]  # основной блок
    spec = gdata.fmt.blocks[0]

    if len(x) < train_size + test_size + 50:
        print(f"⚠️  Недостаточно данных: {len(x)} < {train_size + test_size + 50}")
        return None

    n = spec.size
    k = spec.count

    # Baseline: ожидаемое кол-во угаданных при случайном выборе
    baseline_expected = k * k / n

    hits_model = []
    hits_random = []

    # Walk-forward: окно [i, i+train_size], предсказываем i+train_size
    for i in range(test_size):
        train_end = train_size + i
        if train_end >= len(x):
            break

        # Данные для обучения: [0, train_end)
        train_data = x[:train_end]
        feat = Features(train_data, k)

        # Предсказание
        S = model.fn(feat)
        scores = S[-1]  # Последняя строка = предсказание для draw[train_end]

        # Выбираем топ-k
        top_k_idx = np.argsort(-scores)[:k]
        predicted = np.zeros(n, dtype=np.int32)
        predicted[top_k_idx] = 1

        # Факт
        actual = x[train_end].astype(np.int32)

        # Совпадения
        hits = (predicted & actual).sum()
        hits_model.append(hits)

        # Случайный baseline
        rng = np.random.RandomState(i)
        random_choice = rng.choice(n, k, replace=False)
        random_pred = np.zeros(n, dtype=np.int32)
        random_pred[random_choice] = 1
        hits_random.append((random_pred & actual).sum())

    # Статистика
    avg_model = np.mean(hits_model)
    avg_random = np.mean(hits_random)
    improvement = ((avg_model - baseline_expected) / baseline_expected) * 100

    # t-test: отличается ли модель от baseline?
    t_stat, p_value = ttest_1samp(hits_model, baseline_expected)

    # Вывод
    print(f"Тестов: {len(hits_model)}")
    print(f"Baseline (теор.): {baseline_expected:.2f}")
    print(f"Случайный (эмпир.): {avg_random:.2f}")
    print(f"Модель: {avg_model:.2f}")
    print(f"Улучшение: {improvement:+.1f}%")
    print(f"t-statistic: {t_stat:.3f}, p-value: {p_value:.4f}")

    if p_value > 0.05:
        verdict = "✅ НЕ отличается от случайного (OK!)"
    else:
        if avg_model > baseline_expected:
            verdict = "🚨 ЛУЧШЕ случайного (подозрительно!)"
        else:
            verdict = "🔻 ХУЖЕ случайного (шум)"

    print(f"Вывод: {verdict}")

    return {
        'game': game_slug,
        'model': model.title,
        'tests': len(hits_model),
        'avg_model': avg_model,
        'avg_random': avg_random,
        'baseline': baseline_expected,
        'improvement_pct': improvement,
        'p_value': p_value,
        'verdict': verdict
    }


def main():
    print("=" * 80)
    print("🚀 WALK-FORWARD ТЕСТИРОВАНИЕ")
    print("=" * 80)
    print("\nЦель: Проверить, работают ли методы лучше случайного выбора")
    print("Метод: Walk-forward validation (обучаем на прошлом, тестируем на будущем)")
    print("\n⚠️  ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Методы НЕ должны улучшать точность!")
    print("    В честной лотерее прошлое не предсказывает будущее.\n")

    # Получаем модели
    all_models = {m.key: m for m in models.standard_models()}

    # Тесты: (game, model_key, train, test)
    configs = [
        ("6x45", "hot_100", 500, 50),
        ("6x45", "cold_100", 500, 50),
        ("6x45", "overdue", 500, 50),
        ("7x49", "hot_50", 500, 50),
        ("keno2", "markov", 200, 30),
    ]

    results = []
    for game_slug, model_key, train, test in configs:
        if model_key not in all_models:
            print(f"⚠️  Модель '{model_key}' не найдена, пропускаем")
            continue

        model = all_models[model_key]
        try:
            res = walk_forward_test(game_slug, model, train, test)
            if res:
                results.append(res)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

    # Итоговая таблица
    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ ТАБЛИЦА")
    print("=" * 80)
    print(f"{'Игра':<10} {'Метод':<35} {'Улучш.':<10} {'p-value':<10} {'Вывод'}")
    print("-" * 80)

    for r in results:
        game = r['game']
        model = r['model'][:33]
        imp = r['improvement_pct']
        p = r['p_value']
        verdict = "OK" if p > 0.05 else "Подозр."
        print(f"{game:<10} {model:<35} {imp:>6.1f}%    {p:>8.4f}  {verdict}")

    # Общая статистика
    if results:
        avg_p = np.mean([r['p_value'] for r in results])
        significant_count = sum(1 for r in results if r['p_value'] < 0.05)

        print("\n" + "=" * 80)
        print("📈 ОБЩАЯ СТАТИСТИКА")
        print("=" * 80)
        print(f"Всего тестов: {len(results)}")
        print(f"Средний p-value: {avg_p:.4f}")
        print(f"Значимых результатов (p<0.05): {significant_count}/{len(results)}")
        print(f"\n✅ Итог: {'ВСЕ методы = случайный выбор (лотерея честная!)' if significant_count == 0 else f'{significant_count} методов показали отклонение (шум или баг)'}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
