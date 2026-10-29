#!/usr/bin/env python3
"""
Глубокий анализ реальных тиражей всех игр Столото.

Цель: выявить уникальные статистические характеристики каждой игры
и разработать специализированные методы предсказания.
"""
import sys
import json
from pathlib import Path

# Добавить путь к модулям
sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import all_games
from lottery.fraud_detection import FraudDetector
import numpy as np
from scipy import stats
from collections import Counter


def analyze_game_deeply(game):
    """Глубокий анализ одной игры."""
    print(f"\n{'='*80}")
    print(f"🎲 Анализ игры: {game.title} ({game.slug})")
    print(f"{'='*80}\n")

    try:
        data = load_game_data(game)
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        return None

    if data.T < 100:
        print(f"⚠️ Недостаточно тиражей для анализа: {data.T}")
        return None

    print(f"📊 Загружено тиражей: {data.T}")
    print(f"📅 Период: {data.dates[0]} — {data.dates[-1]}")
    print(f"🎯 Формат: {data.fmt}")
    print()

    results = {
        "game": game.slug,
        "title": game.title,
        "draws_count": data.T,
        "period": {"from": str(data.dates[0]), "to": str(data.dates[-1])},
        "blocks": []
    }

    # Анализ каждого блока
    for block_idx, (x, spec) in enumerate(zip(data.matrices, data.fmt.blocks)):
        print(f"📦 Блок {block_idx + 1}: {spec}")

        T, N = x.shape
        k = spec.count

        # 1. Базовая статистика
        frequencies = x.sum(axis=0)
        expected_freq = frequencies.mean()
        most_common = np.argsort(-frequencies)[:k]
        least_common = np.argsort(frequencies)[:k]

        print(f"\n   Статистика частот:")
        print(f"   • Ожидаемая частота: {expected_freq:.1f}")
        print(f"   • Самые частые числа: {[int(i+spec.lo) for i in most_common[:5]]} "
              f"(частоты: {[int(frequencies[i]) for i in most_common[:5]]})")
        print(f"   • Самые редкие числа: {[int(i+spec.lo) for i in least_common[:5]]} "
              f"(частоты: {[int(frequencies[i]) for i in least_common[:5]]})")

        # 2. Проверка на fraud
        detector = FraudDetector(significance_level=0.01)
        fraud_results = detector.run_all_tests(x)
        fraud_status = fraud_results["verdict"]["status"]

        print(f"\n   🔍 Проверка на нечестность: {fraud_status.upper()}")
        if fraud_status == "suspicious":
            print(f"   ⚠️  {fraud_results['verdict']['message']}")

        # 3. Анализ временных паттернов
        print(f"\n   📈 Временные паттерны:")

        # Тренд частот
        window = min(100, T // 4)
        recent_freq = x[-window:].sum(axis=0)
        old_freq = x[:window].sum(axis=0)

        # Числа, которые стали популярнее/непопулярнее
        freq_change = recent_freq / max(1, recent_freq.mean()) - old_freq / max(1, old_freq.mean())
        trending_up = np.argsort(-freq_change)[:5]
        trending_down = np.argsort(freq_change)[:5]

        print(f"   • Растущий тренд: {[int(i+spec.lo) for i in trending_up]}")
        print(f"   • Падающий тренд: {[int(i+spec.lo) for i in trending_down]}")

        # 4. Анализ кластеров и промежутков
        print(f"\n   🎯 Паттерны распределения:")

        # Средний промежуток между числами в комбинации
        gaps = []
        for t in range(T):
            combo = np.where(x[t] == 1)[0]
            if len(combo) >= 2:
                combo_sorted = np.sort(combo)
                gaps.extend(np.diff(combo_sorted))

        if gaps:
            mean_gap = np.mean(gaps)
            median_gap = np.median(gaps)
            print(f"   • Средний промежуток между числами: {mean_gap:.2f}")
            print(f"   • Медианный промежуток: {median_gap:.1f}")

        # Четность
        even_count = sum(1 for t in range(T) for num in np.where(x[t] == 1)[0] if num % 2 == 0)
        odd_count = T * k - even_count
        even_ratio = even_count / (T * k)

        print(f"   • Четные/нечетные: {even_ratio:.1%} / {1-even_ratio:.1%}")

        # 5. Автокорреляция (память системы)
        print(f"\n   🔄 Автокорреляция (память):")
        max_lag = min(20, T // 10)
        autocorr = []

        for num_idx in range(min(10, N)):  # Первые 10 чисел
            for lag in range(1, max_lag):
                if lag < T:
                    seq = x[:, num_idx]
                    corr = np.corrcoef(seq[:-lag], seq[lag:])[0, 1]
                    if not np.isnan(corr):
                        autocorr.append(abs(corr))

        if autocorr:
            max_autocorr = max(autocorr)
            mean_autocorr = np.mean(autocorr)
            print(f"   • Максимальная: {max_autocorr:.4f}")
            print(f"   • Средняя: {mean_autocorr:.4f}")

            if max_autocorr > 0.1:
                print(f"   ⚠️  Обнаружена слабая память системы!")

        # 6. Энтропия
        # Shannon entropy для частот
        probs = frequencies / frequencies.sum()
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        max_entropy = np.log2(N)

        print(f"\n   📉 Энтропия:")
        print(f"   • Текущая: {entropy:.3f} бит")
        print(f"   • Максимальная (идеал): {max_entropy:.3f} бит")
        print(f"   • Нормализованная: {entropy/max_entropy:.1%}")

        # Сохранить результаты блока
        block_result = {
            "name": spec.name,
            "size": N,
            "count": k,
            "fraud_status": fraud_status,
            "frequencies": {
                "most_common": [{"number": int(i+spec.lo), "count": int(frequencies[i])}
                               for i in most_common[:10]],
                "least_common": [{"number": int(i+spec.lo), "count": int(frequencies[i])}
                                for i in least_common[:10]],
            },
            "patterns": {
                "mean_gap": float(mean_gap) if gaps else None,
                "even_ratio": float(even_ratio),
                "max_autocorr": float(max_autocorr) if autocorr else None,
                "entropy_normalized": float(entropy/max_entropy),
            },
            "trends": {
                "trending_up": [int(i+spec.lo) for i in trending_up],
                "trending_down": [int(i+spec.lo) for i in trending_down],
            }
        }

        results["blocks"].append(block_result)

    return results


def main():
    """Анализ всех игр."""
    print("\n" + "="*80)
    print(" 🎰 ГЛУБОКИЙ АНАЛИЗ РЕАЛЬНЫХ ДАННЫХ ЛОТЕРЕЙ СТОЛОТО")
    print("="*80)

    all_results = []
    games = list(all_games())

    print(f"\n📚 Найдено игр: {len(games)}")

    for i, game in enumerate(games, 1):
        print(f"\n[{i}/{len(games)}] ", end="")
        result = analyze_game_deeply(game)
        if result:
            all_results.append(result)

    # Сохранить результаты
    output_file = Path(__file__).parent.parent.parent / "data" / "deep_analysis.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n\n✅ Анализ завершен!")
    print(f"📁 Результаты сохранены в: {output_file}")
    print(f"📊 Проанализировано игр: {len(all_results)}/{len(games)}")

    # Вывод сводки
    print(f"\n{'='*80}")
    print(" 📋 СВОДКА")
    print(f"{'='*80}\n")

    suspicious_games = [r for r in all_results
                       if any(b["fraud_status"] == "suspicious" for b in r["blocks"])]

    if suspicious_games:
        print(f"⚠️  Игры с подозрительными паттернами: {len(suspicious_games)}")
        for game in suspicious_games:
            print(f"   • {game['title']} ({game['game']})")
    else:
        print("✅ Все игры прошли проверку на честность")

    # Игры с высокой энтропией (наиболее случайные)
    high_entropy_games = sorted(all_results,
                               key=lambda r: min(b["patterns"]["entropy_normalized"]
                                                for b in r["blocks"]),
                               reverse=True)[:5]

    print(f"\n🎲 Топ-5 наиболее случайных игр:")
    for game in high_entropy_games:
        entropy = min(b["patterns"]["entropy_normalized"] for b in game["blocks"])
        print(f"   • {game['title']}: {entropy:.1%}")


if __name__ == "__main__":
    main()
