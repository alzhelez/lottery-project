#!/usr/bin/env python3
"""
Упрощенная проверка Keno 2.0 без scipy.
Использует базовые статистические тесты.
"""
import sys
import math
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import get_game


def chi_square_test(observed, expected):
    """Простой Chi-Square тест."""
    chi2 = sum((o - e)**2 / e for o, e in zip(observed, expected))
    # Для df=79 (Keno), критическое значение при α=0.001 ≈ 116
    df = len(observed) - 1
    # Упрощенная оценка p-value
    if chi2 > 150:
        return chi2, "< 0.0001", True
    elif chi2 > 116:
        return chi2, "< 0.001", True
    elif chi2 > 106:
        return chi2, "< 0.01", False
    else:
        return chi2, "> 0.01", False


def runs_test(sequence):
    """Тест серий - проверка случайности последовательности."""
    # Подсчет серий (runs)
    runs = 1
    for i in range(1, len(sequence)):
        if sequence[i] != sequence[i-1]:
            runs += 1

    n = len(sequence)
    n1 = sum(sequence)  # Количество 1
    n0 = n - n1  # Количество 0

    if n1 == 0 or n0 == 0:
        return 0, 1.0, False

    # Ожидаемое количество серий
    expected_runs = (2 * n0 * n1) / n + 1

    # Дисперсия
    var_runs = (2 * n0 * n1 * (2 * n0 * n1 - n)) / (n**2 * (n - 1))

    if var_runs == 0:
        return runs, 1.0, False

    # Z-статистика
    z = (runs - expected_runs) / math.sqrt(var_runs)

    # P-value (приближенная)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

    is_suspicious = abs(z) > 3.29  # α = 0.001

    return z, p, is_suspicious


def main():
    print("\n" + "="*80)
    print("🔍 УПРОЩЕННАЯ ПРОВЕРКА KENO 2.0 НА ЧЕСТНОСТЬ")
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

    print(f"\n🔬 Запуск тестов (significance level = 0.001)...")
    print("-" * 80)

    flags = []

    # ТЕСТ 1: Равномерность частот (Chi-Square)
    print(f"\n1️⃣  ТЕСТ НА РАВНОМЕРНОСТЬ ЧАСТОТ")
    freq = X.sum(axis=0).tolist()
    expected_freq = T * spec.drawn / N

    chi2, p_value, is_suspicious = chi_square_test(freq, [expected_freq] * N)

    status = "🚨 ПОДОЗРЕНИЕ" if is_suspicious else "✅ НОРМА"
    print(f"   Chi-Square: {chi2:.2f}")
    print(f"   P-value: {p_value}")
    print(f"   Результат: {status}")

    if is_suspicious:
        flags.append("Chi-Square Test")

    # ТЕСТ 2: Тест серий для каждого числа (проверка 10 самых подозрительных)
    print(f"\n2️⃣  ТЕСТ СЕРИЙ (НЕЗАВИСИМОСТЬ ТИРАЖЕЙ)")

    suspicious_numbers = []
    for num_idx in range(N):
        sequence = [int(X[t, num_idx]) for t in range(min(1000, T))]
        z, p, is_susp = runs_test(sequence)
        if is_susp:
            suspicious_numbers.append((num_idx + spec.lo, abs(z), p))

    if suspicious_numbers:
        suspicious_numbers.sort(key=lambda x: x[1], reverse=True)
        print(f"   Найдено подозрительных чисел: {len(suspicious_numbers)}")
        print(f"   Топ-5:")
        for num, z, p in suspicious_numbers[:5]:
            print(f"     Число {num}: |Z| = {z:.2f}, p = {p:.6f}")
        flags.append("Runs Test")
        print(f"   Результат: 🚨 ПОДОЗРЕНИЕ")
    else:
        print(f"   Все числа показывают нормальное поведение")
        print(f"   Результат: ✅ НОРМА")

    # ТЕСТ 3: Кластеризация (повторы между тиражами)
    print(f"\n3️⃣  ТЕСТ НА КЛАСТЕРИЗАЦИЮ")

    repeats = []
    for t in range(1, min(1000, T)):
        prev_set = set(i for i in range(N) if X[t-1, i] == 1)
        curr_set = set(i for i in range(N) if X[t, i] == 1)
        repeats.append(len(prev_set & curr_set))

    avg_repeat = sum(repeats) / len(repeats)

    # Ожидаемое (гипергеометрическое распределение)
    expected_repeat = (spec.drawn ** 2) / N

    # Стандартное отклонение (приблизительное)
    std_repeat = math.sqrt(spec.drawn * (N - spec.drawn) * spec.drawn / (N ** 2))

    z_repeat = (avg_repeat - expected_repeat) / std_repeat

    print(f"   Среднее повторов: {avg_repeat:.2f}")
    print(f"   Ожидается: {expected_repeat:.2f}")
    print(f"   Z-score: {z_repeat:.2f}")

    is_cluster_suspicious = abs(z_repeat) > 3.29
    status = "🚨 ПОДОЗРЕНИЕ" if is_cluster_suspicious else "✅ НОРМА"
    print(f"   Результат: {status}")

    if is_cluster_suspicious:
        flags.append("Clustering Test")

    # ТЕСТ 4: Автокорреляция
    print(f"\n4️⃣  ТЕСТ АВТОКОРРЕЛЯЦИИ")

    # Проверяем автокорреляцию для нескольких чисел
    high_autocorr = []
    for num_idx in range(0, N, 10):  # Проверяем каждое 10-е число
        sequence = [int(X[t, num_idx]) for t in range(min(500, T))]

        # Lag-1 autocorrelation
        n = len(sequence)
        mean = sum(sequence) / n

        numerator = sum((sequence[i] - mean) * (sequence[i+1] - mean) for i in range(n-1))
        denominator = sum((x - mean)**2 for x in sequence)

        if denominator > 0:
            autocorr = numerator / denominator
            if abs(autocorr) > 0.1:  # Порог
                high_autocorr.append((num_idx + spec.lo, autocorr))

    if high_autocorr:
        print(f"   Найдено чисел с высокой автокорреляцией: {len(high_autocorr)}")
        for num, ac in high_autocorr[:3]:
            print(f"     Число {num}: r = {ac:.3f}")
        print(f"   Результат: 🚨 ПОДОЗРЕНИЕ")
        flags.append("Autocorrelation Test")
    else:
        print(f"   Автокорреляция в норме")
        print(f"   Результат: ✅ НОРМА")

    # Итоговый вердикт
    print("\n" + "="*80)
    if flags:
        print(f"⚠️  ВНИМАНИЕ: Обнаружены подозрительные паттерны!")
        print(f"\nПодозрительные тесты ({len(flags)}/4):")
        for test in flags:
            print(f"  • {test}")

        print(f"\n🔍 ИНТЕРПРЕТАЦИЯ:")

        if "Chi-Square Test" in flags:
            # Найти числа с макс отклонением
            indexed_freq = [(i + spec.lo, f) for i, f in enumerate(freq)]
            sorted_freq = sorted(indexed_freq, key=lambda x: abs(x[1] - expected_freq), reverse=True)
            print(f"\n  Chi-Square: Неравномерное распределение частот")
            print(f"    Самые отклоняющиеся числа:")
            for num, f in sorted_freq[:5]:
                dev = f - expected_freq
                print(f"      {num}: {f} раз ({dev:+.1f}, {100*dev/expected_freq:+.1f}%)")

        if "Clustering Test" in flags:
            print(f"\n  Clustering: Повышенная кластеризация")
            print(f"    Числа из прошлого тиража повторяются чаще ожидаемого")
            print(f"    Это может указывать на:")
            print(f"      - Недостаточное перемешивание шаров")
            print(f"      - Дефект в лототроне/машине")
            print(f"      - Проблемы с ГСЧ (если электронный)")

        print(f"\n🔍 РЕКОМЕНДАЦИИ:")
        print(f"  1. Провести техническую проверку оборудования")
        print(f"  2. Сравнить с другими периодами (временной анализ)")
        print(f"  3. Проверить процедуру розыгрыша")
        print(f"  4. Рассмотреть независимый аудит")

    else:
        print(f"✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print(f"\nИгра ведет себя как честная лотерея.")
        print(f"Статистические отклонения в пределах нормы (α=0.001).")

    print("="*80)

    # Дополнительная статистика
    print(f"\n📊 ДОПОЛНИТЕЛЬНАЯ СТАТИСТИКА:")
    print("-" * 80)

    # Частоты
    max_freq = max(freq)
    min_freq = min(freq)
    range_freq = max_freq - min_freq

    print(f"Частоты чисел:")
    print(f"  Ожидаемая: {expected_freq:.1f}")
    print(f"  Макс: {max_freq} | Мин: {min_freq} | Разброс: {range_freq}")
    print(f"  CV (коэф. вариации): {(range_freq / expected_freq):.2%}")

    # Топ и дно
    sorted_freq = sorted(enumerate(freq, start=spec.lo), key=lambda x: x[1], reverse=True)

    print(f"\n  🔥 Топ-5 горячих:")
    for num, f in sorted_freq[:5]:
        print(f"    {num}: {f} раз ({100*f/(T*spec.drawn/N)-100:+.1f}%)")

    print(f"\n  ❄️  Топ-5 холодных:")
    for num, f in sorted_freq[-5:]:
        print(f"    {num}: {f} раз ({100*f/(T*spec.drawn/N)-100:+.1f}%)")

    # Четность
    even_count = 0
    odd_count = 0
    for t in range(T):
        for i in range(N):
            if X[t, i] == 1:
                if (i + spec.lo) % 2 == 0:
                    even_count += 1
                else:
                    odd_count += 1

    total_count = even_count + odd_count
    even_pct = 100 * even_count / total_count

    print(f"\n⚖️  Четность:")
    print(f"  Четных: {even_pct:.2f}% | Нечетных: {100-even_pct:.2f}%")

    # Промежутки
    all_gaps = []
    for t in range(T):
        combo = sorted([i+spec.lo for i in range(N) if X[t,i]==1])
        if len(combo) >= 2:
            all_gaps.extend([combo[i+1] - combo[i] for i in range(len(combo)-1)])

    if all_gaps:
        avg_gap = sum(all_gaps) / len(all_gaps)
        min_gap = min(all_gaps)
        max_gap = max(all_gaps)

        print(f"\n📏 Промежутки между числами:")
        print(f"  Средний: {avg_gap:.2f} | Мин: {min_gap} | Макс: {max_gap}")

        # Частота gap=1 (соседние числа)
        gap1_count = sum(1 for g in all_gaps if g == 1)
        gap1_pct = 100 * gap1_count / len(all_gaps)
        print(f"  Соседних (gap=1): {gap1_pct:.1f}%")

    print("\n" + "="*80)
    print("✅ АНАЛИЗ ЗАВЕРШЕН")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
