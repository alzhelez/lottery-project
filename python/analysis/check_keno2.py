#!/usr/bin/env python3
"""
Глубокая проверка Keno 2.0 на нечестность.

Обнаруженные аномалии требуют детального статистического анализа.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lottery.drawfile import load_game_data
from lottery.games import get_game

print("="*80)
print(" 🔍 ГЛУБОКАЯ ПРОВЕРКА KENO 2.0 НА НЕЧЕСТНОСТЬ")
print("="*80)

try:
    from lottery.fraud_detection import FraudDetector

    print("\n📥 Загрузка данных Keno 2.0...")
    game = get_game("keno2")
    data = load_game_data(game)

    print(f"✅ Загружено: {data.T} тиражей")
    print(f"📅 Период: {data.draws[0].date} — {data.draws[-1].date}")
    print(f"🎯 Формат: 10 из 80")

    print("\n" + "="*80)
    print(" 🧪 СТАТИСТИЧЕСКИЕ ТЕСТЫ")
    print("="*80)

    # Строгий уровень значимости (0.001 = 99.9% уверенности)
    detector = FraudDetector(significance_level=0.001)

    print("\n⏳ Выполнение тестов (это может занять минуту)...")
    results = detector.run_all_tests(data.matrices[0])

    print("\n" + "="*80)
    print(" 📊 РЕЗУЛЬТАТЫ ТЕСТОВ")
    print("="*80)

    for test_name, test_result in results.items():
        if test_name == "verdict":
            continue

        status = "❌ ОТКЛОНЕН" if test_result["rejected"] else "✅ ПРОЙДЕН"
        print(f"\n{test_result['name']}: {status}")
        print(f"  Статистика: {test_result['statistic']:.4f}")
        print(f"  P-value: {test_result['p_value']:.6f}")
        print(f"  Критический уровень: {test_result['critical_level']}")

        if test_result["rejected"]:
            print(f"  ⚠️  {test_result['interpretation']}")

    print("\n" + "="*80)
    print(" 🎯 ИТОГОВЫЙ ВЕРДИКТ")
    print("="*80)

    verdict = results["verdict"]
    status_emoji = {
        "fair": "✅",
        "suspicious": "🚨",
        "inconclusive": "🟡"
    }

    print(f"\n{status_emoji[verdict['status']]} Статус: {verdict['status'].upper()}")
    print(f"📝 {verdict['message']}")
    print(f"🧪 Тестов провалено: {verdict['failed_tests']}/{verdict['total_tests']}")

    if verdict["status"] == "suspicious":
        print("\n⚠️  ВНИМАНИЕ: Обнаружены статистические аномалии!")
        print("   Это может указывать на:")
        print("   • Неравномерный износ шаров")
        print("   • Дефекты механизма розыгрыша")
        print("   • Предсказуемость ГСЧ")
        print("   • Возможные манипуляции")
        print("\n   Рекомендуется дополнительное расследование.")
    elif verdict["status"] == "fair":
        print("\n✅ Игра прошла все тесты — признаков нечестности не обнаружено.")

    print("\n" + "="*80)

except ImportError as e:
    print(f"\n❌ Ошибка: Не установлены зависимости для fraud_detection")
    print(f"   {e}")
    print(f"\n💡 Установите: pip install scipy --break-system-packages")
    print(f"   Или активируйте виртуальное окружение.")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
