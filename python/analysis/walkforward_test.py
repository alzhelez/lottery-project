#!/usr/bin/env python3
"""
Walk-forward тестирование специализированных методов.

Проверяет, работают ли новые методы лучше случайного выбора.
Спойлер: в честной лотерее они не должны (и не будут).
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import all_games, get_game
from lottery.models_game_specific import *
from lottery.method import all_methods
import numpy as np


def walk_forward_test(game, method, train_size=100, test_size=50):
    """
    Walk-forward тестирование одного метода на одной игре.

    Returns:
        dict: результаты теста
    """
    try:
        data = load_game_data(game)
    except:
        return None

    if data.T < train_size + test_size:
        return None

    # Проверяем, применим ли метод к этой игре
    if hasattr(method, 'game_slug') and method.game_slug:
        if method.game_slug != game.slug:
            return None

    hits = []
    X_train = data.matrices[0][:train_size]

    # Тестируем на следующих test_size тиражах
    for t in range(train_size, min(train_size + test_size, data.T)):
        X_current = data.matrices[0][:t]
        actual = data.matrices[0][t]

        try:
            # Получить прогноз
            probs = method.predict_one(X_current)

            # Топ-k чисел по вероятности
            k = int(actual.sum())
            top_k = np.argsort(-probs)[:k]

            # Сколько попали
            predicted = np.zeros_like(actual)
            predicted[top_k] = 1.0

            hit_count = (predicted * actual).sum()
            hits.append(int(hit_count))

        except Exception as e:
            continue

    if not hits:
        return None

    return {
        "method": method.name,
        "game": game.slug,
        "tests": len(hits),
        "avg_hits": sum(hits) / len(hits),
        "max_hits": max(hits),
        "min_hits": min(hits),
        "hits_distribution": hits
    }


def main():
    print("="*80)
    print(" 🧪 WALK-FORWARD ТЕСТИРОВАНИЕ НОВЫХ МЕТОДОВ")
    print("="*80)

    # Найти все game-specific методы
    all_m = list(all_methods())
    game_specific = [m for m in all_m if m.name.startswith("6x45_") or
                     m.name.startswith("5x36plus_") or
                     m.name.startswith("rapido2_") or
                     m.name.startswith("keno2_") or
                     m.name.startswith("vin_") or
                     m.name.startswith("top3_") or
                     m.name.startswith("4x20_")]

    print(f"\n📊 Найдено game-specific методов: {len(game_specific)}")

    results = []

    for i, method in enumerate(game_specific, 1):
        print(f"\n[{i}/{len(game_specific)}] Тестирую: {method.title}")

        # Определить игру для метода
        game_slug = getattr(method, 'game_slug', None)
        if not game_slug:
            print("  ⚠️ Не указан game_slug, пропускаю")
            continue

        try:
            game = get_game(game_slug)
        except:
            print(f"  ❌ Игра {game_slug} не найдена")
            continue

        result = walk_forward_test(game, method, train_size=200, test_size=100)

        if result:
            print(f"  ✅ Тестов: {result['tests']}")
            print(f"  📊 Средних попаданий: {result['avg_hits']:.2f}")
            print(f"  🎯 Макс попаданий: {result['max_hits']}")
            results.append(result)
        else:
            print("  ⚠️ Недостаточно данных для теста")

    # Сохранить результаты
    output_file = Path(__file__).parent.parent.parent / "data" / "walkforward_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "="*80)
    print(" 📊 СВОДКА РЕЗУЛЬТАТОВ")
    print("="*80)

    if not results:
        print("\n⚠️ Нет результатов для анализа")
        return

    print(f"\nПротестировано методов: {len(results)}")
    print(f"\nТоп-5 по среднему попаданию:\n")

    sorted_results = sorted(results, key=lambda r: r['avg_hits'], reverse=True)

    for i, r in enumerate(sorted_results[:5], 1):
        print(f"{i}. {r['method']} ({r['game']}): {r['avg_hits']:.2f} попаданий")

    # Сравнение со случайным
    print("\n" + "="*80)
    print(" 🎲 СРАВНЕНИЕ СО СЛУЧАЙНЫМ ВЫБОРОМ")
    print("="*80)

    for r in results[:3]:  # Первые 3 для примера
        # Теоретическое ожидание для случайного
        game = get_game(r['game'])
        data = load_game_data(game)
        N = data.matrices[0].shape[1]
        k = int(data.matrices[0][0].sum())

        expected_random = k * k / N  # E[попаданий] = k²/N

        improvement = ((r['avg_hits'] - expected_random) / expected_random) * 100

        print(f"\n{r['method']} ({r['game']}):")
        print(f"  Метод: {r['avg_hits']:.2f} попаданий")
        print(f"  Случайно: {expected_random:.2f} попаданий")
        print(f"  Улучшение: {improvement:+.1f}%")

        if abs(improvement) < 10:
            print(f"  ✅ В пределах случайных флуктуаций (честная лотерея)")
        elif improvement > 10:
            print(f"  🚨 Подозрительно высокий результат! Может быть нечестность")
        else:
            print(f"  ⚠️ Хуже случайного (нормально для случайной игры)")

    print(f"\n📁 Полные результаты: {output_file}")


if __name__ == "__main__":
    main()
