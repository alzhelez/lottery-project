#!/usr/bin/env python3
"""
Анализатор лотерейных данных v2 — сканирует ВСЕ активные игры с stoloto.ru API.
Использует stoloto_analyzer_v3.py для получения списка игр и анализа.
Кеширует результаты в stoloto_analysis_v3.json.
Возвращает JSON: { games: [...], high_anomaly: [...], categories: {...} }

Modes:
  python analyze.py              — Full analysis (or cache if available)
  python analyze.py --list-only  — Quick: just list games from API without analysis
"""
import json
import os
import sys
import time
import signal
from io import StringIO

# All progress messages go to stderr; stdout is reserved for JSON output
def log(msg):
    print(msg, file=sys.stderr, flush=True)


class _StdoutRedirect:
    """Context manager to redirect stdout to stderr."""
    def __enter__(self):
        self._orig = sys.stdout
        sys.stdout = sys.stderr
        return self
    def __exit__(self, *args):
        sys.stdout = self._orig


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CACHE_FILE = os.path.join(PROJECT_ROOT, 'python', 'stoloto_analysis_v3.json')
CACHE_TTL = 7 * 86400  # 7 days

def timeout_handler(signum, frame):
    raise TimeoutError("Analysis timed out")


def get_game_list_only():
    """Quick mode: fetch just the game list from API, no draw fetching."""
    sys.path.insert(0, SCRIPT_DIR)

    with _StdoutRedirect():
        try:
            from stoloto_analyzer_v3 import get_games
        except ImportError as e:
            log(f"Import error: {e}")
            print(json.dumps({"error": f"Import error: {e}"}))
            sys.exit(1)

        try:
            games_list = get_games()
        except Exception as e:
            log(f"Failed to get games: {e}")
            print(json.dumps({"error": f"Failed to get games: {e}"}))
            sys.exit(1)

        if not games_list:
            log("No active games found")
            print(json.dumps({"error": "No active games found"}))
            sys.exit(1)

    # Convert to frontend format with "loading" status
    games = []
    for g in games_list:
        name = g.get("name", "unknown")
        # Try to extract last draw count from API response
        last_draw = g.get("completedDraw", {})
        draw_number = last_draw.get("number", 0) if isinstance(last_draw, dict) else 0

        games.append({
            "name": name,
            "key": name,
            "score": 0,
            "verdict": "⏳ Анализ загружается...",
            "verdict_color": "green",
            "draws": draw_number if draw_number > 0 else 0,
            "hot_numbers": [],
            "cold_numbers": [],
            "chi2_p": None,
            "autocorr": None,
            "data_file": "",
            "source": "api-list",
            "has_local_data": False,
        })

    # All games go to "insufficient" category since no analysis was done
    result = {
        "games": games,
        "high_anomaly": [],
        "total_games_analyzed": len(games),
        "categories": {
            "high": [],
            "moderate": [],
            "normal": [],
            "insufficient": games,
        },
        "_refreshing": True,
    }

    log(f"  Список игр: {len(games)}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_full_analysis(max_draws=10000):
    """Run stoloto_analyzer_v3 to analyze all active games from API.

    Args:
        max_draws: Maximum draws to fetch per game (default 10000 for comprehensive analysis).
    """
    sys.path.insert(0, SCRIPT_DIR)

    with _StdoutRedirect():
        try:
            from stoloto_analyzer_v3 import (
                get_games, fetch_draws, extract_numbers, GameStats,
                MAX_DRAWS_PER_GAME, REQUEST_DELAY, MIN_DRAWS
            )
        except ImportError as e:
            log(f"Import error: {e}")
            print(json.dumps({"error": f"Import error: {e}"}))
            sys.exit(1)

        # Limit draws per game for reasonable analysis time
        effective_max = min(max_draws, MAX_DRAWS_PER_GAME)
        log(f"  Max draws per game: {effective_max}")

        # 1. Get all active games
        log("  [1/2] Получение списка активных игр...")
        try:
            games_list = get_games()
        except Exception as e:
            log(f"Failed to get games: {e}")
            print(json.dumps({"error": f"Failed to get games: {e}"}))
            sys.exit(1)

        if not games_list:
            log("No active games found")
            print(json.dumps({"error": "No active games found"}))
            sys.exit(1)

        log(f"  Найдено {len(games_list)} активных игр")

        # 2. Analyze each game
        results = []
        for idx, g in enumerate(games_list):
            name = g["name"]
            log(f"  ▶ [{idx+1}/{len(games_list)}] {name}...")

            try:
                if hasattr(signal, 'SIGALRM'):
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(600)  # 60s per game

                # Limit fetch size to avoid downloading thousands of draws
                draws_raw = fetch_draws(name, max_draws=effective_max)

                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)

                gs = GameStats(name)
                ok = 0
                for draw in draws_raw:
                    nums = extract_numbers(draw)
                    if nums:
                        gs.add(nums)
                        ok += 1

                r = gs.report()
                log(f"    {ok} тиражей, score={r['score']}")
                results.append(r)

            except TimeoutError:
                log("    таймаут")
                results.append({"name": name, "draws": 0, "unique_nums": 0, "top10": [], "cold10": [], "top_pairs": [], "chi2_p": None, "chi2_info": "—", "autocorr": None, "score": 0.0, "verdict": "❓ Мало данных"})
            except Exception as e:
                log(f"    ошибка: {e}")
                results.append({"name": name, "draws": 0, "unique_nums": 0, "top10": [], "cold10": [], "top_pairs": [], "chi2_p": None, "chi2_info": "—", "autocorr": None, "score": 0.0, "verdict": "❓ Мало данных"})
            finally:
                if hasattr(signal, 'SIGALRM'):
                    try:
                        signal.alarm(0)
                    except (ValueError, OSError):
                        pass
                time.sleep(REQUEST_DELAY)

    return results


def convert_to_frontend(results):
    """Convert stoloto_analyzer_v3 results to frontend GameAnalysis format."""
    games = []
    for r in results:
        # Determine verdict_color from verdict text
        verdict = r.get("verdict", "❓ Мало данных")
        if "ВЫСОКАЯ" in verdict:
            verdict_color = "red"
        elif "Умеренная" in verdict:
            verdict_color = "yellow"
        elif "Статистически" in verdict or "случайная" in verdict:
            verdict_color = "green"
        else:
            verdict_color = "green"

        # Extract hot/cold numbers from top10/cold10
        hot_numbers = [n for n, _ in r.get("top10", [])[:5]]
        cold_numbers = [n for n, _ in r.get("cold10", [])[:5]]

        game = {
            "name": r["name"],
            "key": r["name"],
            "score": r.get("score", 0),
            "verdict": verdict,
            "verdict_color": verdict_color,
            "draws": r.get("draws", 0),
            "hot_numbers": hot_numbers,
            "cold_numbers": cold_numbers,
            "chi2_p": r.get("chi2_p"),
            "autocorr": r.get("autocorr"),
            "data_file": "",
            "source": "api",
            "has_local_data": False,
        }
        games.append(game)

    # Sort by score descending
    games.sort(key=lambda g: g["score"], reverse=True)
    high_anomaly = [g for g in games if g["score"] >= 50]

    # Group by verdict categories
    categories = {
        "high": [g for g in games if g["verdict_color"] == "red"],
        "moderate": [g for g in games if g["verdict_color"] == "yellow"],
        "normal": [g for g in games if g["verdict_color"] == "green" and g.get("draws", 0) >= 10],
        "insufficient": [g for g in games if g.get("draws", 0) < 10 or "Мало данных" in g.get("verdict", "")],
    }

    return {
        "games": games,
        "high_anomaly": high_anomaly,
        "total_games_analyzed": len(games),
        "categories": categories,
    }


def load_cached():
    """Load cached analysis if it exists and is fresh."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        stat = os.stat(CACHE_FILE)
        age = time.time() - stat.st_mtime
        if age > CACHE_TTL:
            return None
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list) and len(raw) > 0:
            return raw
        return None
    except (json.JSONDecodeError, IOError, OSError):
        return None


def save_cache(results):
    """Save analysis results to cache file."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    except (IOError, OSError) as e:
        log(f"  [WARN] Failed to save cache: {e}")


def main():
    # Check for --list-only flag
    if '--list-only' in sys.argv:
        get_game_list_only()
        return

    # Try cache first
    cached = load_cached()
    if cached:
        log(f"  Используем кеш ({len(cached)} игр)")
        frontend = convert_to_frontend(cached)
        # Only JSON goes to stdout
        print(json.dumps(frontend, ensure_ascii=False, indent=2))
        return

    # Try stale cache as fallback (even if expired)
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                stale = json.load(f)
            if isinstance(stale, list) and len(stale) > 0:
                log(f"  Используем устаревший кеш ({len(stale)} игр)")
                frontend = convert_to_frontend(stale)
                print(json.dumps(frontend, ensure_ascii=False, indent=2))
                return
    except Exception:
        pass

    # No cache at all — run full analysis
    log("  Запуск полного анализа всех игр...")
    try:
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(1800)  # 30 min max for full analysis
        results = run_full_analysis()
    except TimeoutError:
        log("  Анализ превысил таймаут, используем пустой результат")
        results = []
    finally:
        if hasattr(signal, 'SIGALRM'):
            try:
                signal.alarm(0)
            except (ValueError, OSError):
                pass

    # Save to cache
    if results:
        save_cache(results)
        log(f"  Кеш обновлён ({len(results)} игр)")

    frontend = convert_to_frontend(results)
    # Only JSON goes to stdout
    print(json.dumps(frontend, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
