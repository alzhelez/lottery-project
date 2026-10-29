#!/usr/bin/env python3
"""
Упрощенный анализ реальных тиражей для выявления характеристик игр.
Не требует scipy и других тяжелых зависимостей.
"""
import sys
import json
from pathlib import Path
from collections import Counter

# Добавить путь к модулям
sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import all_games


def analyze_game_simple(game):
    """Упрощенный анализ одной игры."""
    print(f"\n{'='*80}")
    print(f"🎲 {game.title} ({game.slug})")
    print(f"{'='*80}")

    try:
        data = load_game_data(game)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

    if data.T < 50:
        print(f"⚠️ Мало тиражей: {data.T}")
        return None

    dates = [d.date for d in data.draws] if data.draws else []
    period = f"{dates[0]} — {dates[-1]}" if dates else "?"
    print(f"📊 Тиражей: {data.T} | Период: {period}")

    results = {
        "game": game.slug,
        "title": game.title,
        "draws": data.T,
        "blocks": []
    }

    for block_idx, (x, spec) in enumerate(zip(data.matrices, data.fmt.blocks)):
        T, N = x.shape
        k = spec.count

        print(f"\n📦 Блок: {spec.name} ({k} из {N})")

        # Частоты
        freq = x.sum(axis=0).tolist()
        avg_freq = sum(freq) / len(freq)

        # Топ-10 и дно-10
        indexed_freq = [(i + spec.lo, f) for i, f in enumerate(freq)]
        sorted_freq = sorted(indexed_freq, key=lambda p: p[1], reverse=True)

        hot = sorted_freq[:10]
        cold = sorted_freq[-10:]

        print(f"🔥 Горячие: {[num for num, _ in hot[:5]]}")
        print(f"❄️  Холодные: {[num for num, _ in cold[:5]]}")

        # Четность
        even_nums = sum(1 for t in range(T) for num in range(N) if x[t,num]==1 and (num+spec.lo)%2==0)
        total_nums = T * k
        even_pct = 100.0 * even_nums / total_nums if total_nums > 0 else 50.0

        print(f"⚖️  Четные: {even_pct:.1f}% | Нечетные: {100-even_pct:.1f}%")

        # Промежутки
        gaps = []
        for t in range(T):
            combo = sorted([i+spec.lo for i in range(N) if x[t,i]==1])
            if len(combo) >= 2:
                gaps.extend([combo[i+1] - combo[i] for i in range(len(combo)-1)])

        if gaps:
            avg_gap = sum(gaps) / len(gaps)
            print(f"📏 Средний промежуток: {avg_gap:.2f}")

        # Повторы между тиражами
        repeats = []
        for t in range(1, min(100, T)):
            prev_set = set(i for i in range(N) if x[t-1, i] == 1)
            curr_set = set(i for i in range(N) if x[t, i] == 1)
            repeats.append(len(prev_set & curr_set))

        if repeats:
            avg_repeat = sum(repeats) / len(repeats)
            print(f"🔁 Средних повторов с пред. тиражом: {avg_repeat:.2f} (из {k})")

        # Сохранить данные
        block_data = {
            "name": spec.name,
            "size": N,
            "count": k,
            "hot_numbers": [num for num, _ in hot],
            "cold_numbers": [num for num, _ in cold],
            "even_pct": round(even_pct, 1),
            "avg_gap": round(avg_gap, 2) if gaps else None,
            "avg_repeat": round(avg_repeat, 2) if repeats else None,
        }

        results["blocks"].append(block_data)

    return results


def main():
    print("\n" + "="*80)
    print(" 🎰 АНАЛИЗ РЕАЛЬНЫХ ДАННЫХ")
    print("="*80)

    games = list(all_games())
    print(f"\n📚 Игр: {len(games)}\n")

    all_results = []
    for i, game in enumerate(games, 1):
        print(f"[{i}/{len(games)}]", end=" ")
        result = analyze_game_simple(game)
        if result:
            all_results.append(result)

    # Сохранить
    out_file = Path(__file__).parent.parent.parent / "data" / "games_analysis.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n\n✅ Готово!")
    print(f"📁 {out_file}")
    print(f"📊 Игр: {len(all_results)}")


if __name__ == "__main__":
    main()
