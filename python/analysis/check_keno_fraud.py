#!/usr/bin/env python3
"""
Глубокая статистическая проверка Keno 2.0 на честность.
Используем модуль fraud_detection для всесторонней проверки.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import get_game
from lottery.fraud_detection import FraudDetector

def main():
    print("\n" + "="*80)
    print("🔍 ГЛУБОКАЯ ПРОВЕРКА KENO 2.0 НА ЧЕСТНОСТЬ")
    print("="*80)

    # Загрузка данных
    game = get_game("keno2")
    print(f"\n📥 Загрузка данных: {game.title}...")
    data = load_game_data(game)

    X = data.matrices[0]
    spec = data.fmt.blocks[0]
    T, N = X.shape

    print(f"✅ Загружено: {T} тиражей, {N} чисел ({spec.lo}-{spec.hi})")
    print(f"📊 Выпадает {spec.drawn} чисел из {N}, игрок выбирает {spec.count}")

    # Создаем detector
    detector = FraudDetector(significance=0.001)  # Очень строгий уровень

    print(f"\n🔬 Запуск тестов (significance level = 0.001)...")
    print("-" * 80)

    # Запускаем все тесты
    results = detector.analyze_game(X, spec)

    # Выводим результаты
    print(f"\n{'ТЕСТ':<30} {'СТАТИСТИКА':<15} {'P-VALUE':<12} {'РЕЗУЛЬТАТ':<10}")
    print("-" * 80)

    flags = []
    for test_name, result in results.items():
        status = "🚨 ПОДОЗРЕНИЕ" if result["is_suspicious"] else "✅ НОРМА"
        if result["is_suspicious"]:
            flags.append(test_name)

        print(f"{test_name:<30} {result['statistic']:<15.4f} {result['p_value']:<12.6f} {status}")

    # Итоговый вердикт
    print("\n" + "="*80)
    if flags:
        print(f"⚠️  ВНИМАНИЕ: Обнаружены подозрительные паттерны!")
        print(f"\nПодозрительные тесты ({len(flags)}/{len(results)}):")
        for test in flags:
            print(f"  • {test}: {results[test]['interpretation']}")

        print(f"\n🔍 РЕКОМЕНДАЦИЯ:")
        print(f"  1. Провести аудит оборудования генератора случайных чисел")
        print(f"  2. Проверить калибровку лототрона/машины розыгрыша")
        print(f"  3. Сравнить с результатами других операторов (если есть)")
        print(f"  4. Рассмотреть временной анализ (изменения со временем)")

    else:
        print(f"✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print(f"\nИгра ведет себя как честная лотерея с настоящим ГСЧ.")
        print(f"Никаких статистических отклонений не обнаружено (α=0.001).")

    print("="*80)

    # Дополнительный анализ аномалий
    print(f"\n📊 ДОПОЛНИТЕЛЬНЫЙ АНАЛИЗ:")
    print("-" * 80)

    # Частоты чисел
    freq = X.sum(axis=0)
    expected_freq = T * spec.drawn / N
    max_dev = max(abs(f - expected_freq) for f in freq)
    max_dev_pct = 100 * max_dev / expected_freq

    print(f"Частоты чисел:")
    print(f"  Ожидаемая частота: {expected_freq:.1f}")
    print(f"  Макс. отклонение: {max_dev:.1f} ({max_dev_pct:.2f}%)")

    # Топ-5 и дно-5
    sorted_freq = sorted(enumerate(freq, start=spec.lo), key=lambda x: x[1], reverse=True)
    print(f"\n  Топ-5 чисел:")
    for num, f in sorted_freq[:5]:
        dev = f - expected_freq
        print(f"    {num}: {f} раз ({dev:+.1f})")

    print(f"\n  Дно-5 чисел:")
    for num, f in sorted_freq[-5:]:
        dev = f - expected_freq
        print(f"    {num}: {f} раз ({dev:+.1f})")

    # Серии
    print(f"\n📈 АНАЛИЗ СЕРИЙ (последовательные появления):")
    print("-" * 80)

    # Подсчет серий для каждого числа
    longest_runs = []
    for num_idx in range(N):
        max_run = 0
        current_run = 0
        for t in range(T):
            if X[t, num_idx] == 1:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 0
        if max_run > 0:
            longest_runs.append((num_idx + spec.lo, max_run))

    longest_runs.sort(key=lambda x: x[1], reverse=True)
    print(f"Самые длинные серии:")
    for num, run in longest_runs[:5]:
        print(f"  Число {num}: {run} тиражей подряд")

    # Повторы между тиражами
    print(f"\n🔁 АНАЛИЗ ПОВТОРОВ:")
    print("-" * 80)

    repeats = []
    for t in range(1, min(1000, T)):
        prev_set = set(i for i in range(N) if X[t-1, i] == 1)
        curr_set = set(i for i in range(N) if X[t, i] == 1)
        repeats.append(len(prev_set & curr_set))

    avg_repeat = sum(repeats) / len(repeats)
    max_repeat = max(repeats)
    min_repeat = min(repeats)

    # Ожидаемое количество повторов (гипергеометрическое)
    # Если выпадает drawn из N, вероятность повтора ~ drawn^2/N
    expected_repeat = (spec.drawn ** 2) / N

    print(f"Повторы чисел между соседними тиражами:")
    print(f"  Среднее: {avg_repeat:.2f} (ожидается ~{expected_repeat:.2f})")
    print(f"  Макс: {max_repeat}, Мин: {min_repeat}")
    print(f"  Отклонение: {avg_repeat - expected_repeat:+.2f}")

    if abs(avg_repeat - expected_repeat) > 1.0:
        print(f"  ⚠️ Значительное отклонение от ожидаемого!")

    print("\n" + "="*80)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
