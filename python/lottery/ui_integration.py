"""
Утилита для интеграции новых функций в UI.

Предоставляет простой API для фронтенда:
- Список методов для каждой игры
- Проверка честности игры
- Анализ популярности билета
- Рекомендации по методам
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from lottery.games import get_game, all_games
from lottery.drawfile import load_game_data
from lottery.method import all_methods


def get_methods_for_game(game_slug: str) -> List[Dict]:
    """
    Получить список подходящих методов для игры.

    Returns:
        [{"name": str, "title": str, "tags": [str], "recommended": bool}]
    """
    methods = []

    for method in all_methods():
        # Проверить применимость
        if hasattr(method, 'game_slug') and method.game_slug:
            if method.game_slug != game_slug:
                continue

        methods.append({
            "name": method.name,
            "title": method.title,
            "tags": getattr(method, 'tags', []),
            "game_specific": hasattr(method, 'game_slug') and method.game_slug == game_slug,
            "description": method.__doc__.strip().split('\n')[0] if method.__doc__ else ""
        })

    # Сортировка: game-specific сначала
    methods.sort(key=lambda m: (not m['game_specific'], m['title']))

    return methods


def get_game_statistics(game_slug: str) -> Optional[Dict]:
    """
    Получить статистику игры из analysis результатов.

    Returns:
        {"hot_numbers": [int], "cold_numbers": [int], "avg_repeat": float, ...}
    """
    analysis_file = Path(__file__).parent.parent.parent / "data" / "games_analysis.json"

    if not analysis_file.exists():
        return None

    with open(analysis_file, "r", encoding="utf-8") as f:
        all_analysis = json.load(f)

    for game_data in all_analysis:
        if game_data["game"] == game_slug:
            # Упростить для UI
            if game_data["blocks"]:
                first_block = game_data["blocks"][0]
                return {
                    "draws_count": game_data["draws"],
                    "hot_numbers": first_block["hot_numbers"][:10],
                    "cold_numbers": first_block["cold_numbers"][:10],
                    "even_pct": first_block["even_pct"],
                    "avg_gap": first_block.get("avg_gap"),
                    "avg_repeat": first_block.get("avg_repeat")
                }

    return None


def check_game_fairness(game_slug: str) -> Dict:
    """
    Проверить игру на честность (если доступен FraudDetector).

    Returns:
        {"status": "fair"|"suspicious"|"error", "message": str, "tests": {...}}
    """
    try:
        from lottery.fraud_detection import FraudDetector

        game = get_game(game_slug)
        data = load_game_data(game)

        if data.T < 100:
            return {
                "status": "inconclusive",
                "message": f"Недостаточно данных для анализа ({data.T} тиражей)",
                "tests": {}
            }

        detector = FraudDetector(significance_level=0.01)
        results = detector.run_all_tests(data.matrices[0])

        return {
            "status": results["verdict"]["status"],
            "message": results["verdict"]["message"],
            "failed_tests": results["verdict"]["failed_tests"],
            "total_tests": results["verdict"]["total_tests"],
            "tests": {
                name: {
                    "name": test["name"],
                    "rejected": test["rejected"],
                    "p_value": test["p_value"]
                }
                for name, test in results.items()
                if name != "verdict"
            }
        }

    except ImportError:
        return {
            "status": "error",
            "message": "FraudDetector не установлен (требуется scipy)",
            "tests": {}
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "tests": {}
        }


def analyze_ticket_popularity(ticket: List[int], game_slug: str) -> Dict:
    """
    Проанализировать популярность билета.

    Returns:
        {"score": float, "popularity": str, "reasons": [str]}
    """
    try:
        from lottery.unpopular_generator import analyze_ticket_popularity as analyze

        return analyze(ticket, game_slug)

    except Exception as e:
        return {
            "score": 0.5,
            "popularity": "НЕИЗВЕСТНО",
            "reasons": [f"Ошибка анализа: {e}"]
        }


def get_recommended_method(game_slug: str) -> Optional[str]:
    """
    Получить рекомендуемый метод для игры.

    Returns:
        method_name или None
    """
    # Загрузить статистику игры
    stats = get_game_statistics(game_slug)

    if not stats:
        return "random"  # Дефолтный

    # Логика рекомендации на основе характеристик
    avg_repeat = stats.get("avg_repeat")

    if avg_repeat and avg_repeat > 3.0:
        # Высокие повторы → метод с эксплуатацией повторов
        if game_slug == "rapido2":
            return "rapido2_high_repeat"
        elif game_slug == "vin":
            return "vin_massive_repeat"
        elif game_slug == "keno2":
            return "keno2_super_hot"

    # Game-specific методы по умолчанию
    game_methods = {
        "6x45": "6x45_hot_cold",
        "5x36plus": "5x36plus_mega_hot",
        "rapido2": "rapido2_cluster",
        "4x20": "4x20_two_fields",
        "top-3": "top3_position"
    }

    return game_methods.get(game_slug, "random")


def get_all_games_summary() -> List[Dict]:
    """
    Сводка по всем играм для дашборда.

    Returns:
        [{"slug": str, "title": str, "draws": int, "status": str, "recommended_method": str}]
    """
    summary = []

    for game in all_games():
        try:
            stats = get_game_statistics(game.slug)
            fairness = check_game_fairness(game.slug)

            summary.append({
                "slug": game.slug,
                "title": game.title,
                "draws": stats["draws_count"] if stats else 0,
                "status": fairness["status"],
                "recommended_method": get_recommended_method(game.slug),
                "avg_repeat": stats.get("avg_repeat") if stats else None
            })

        except:
            continue

    return summary


# API для командной строки
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ui_integration.py methods <game_slug>")
        print("  python ui_integration.py stats <game_slug>")
        print("  python ui_integration.py fairness <game_slug>")
        print("  python ui_integration.py summary")
        sys.exit(1)

    command = sys.argv[1]

    if command == "methods" and len(sys.argv) >= 3:
        game_slug = sys.argv[2]
        methods = get_methods_for_game(game_slug)
        print(json.dumps(methods, ensure_ascii=False, indent=2))

    elif command == "stats" and len(sys.argv) >= 3:
        game_slug = sys.argv[2]
        stats = get_game_statistics(game_slug)
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif command == "fairness" and len(sys.argv) >= 3:
        game_slug = sys.argv[2]
        fairness = check_game_fairness(game_slug)
        print(json.dumps(fairness, ensure_ascii=False, indent=2))

    elif command == "summary":
        summary = get_all_games_summary()
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    else:
        print("❌ Неизвестная команда")
        sys.exit(1)
