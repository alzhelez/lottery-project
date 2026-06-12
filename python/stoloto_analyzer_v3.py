#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================
  СТОЛОТО — Анализатор предсказуемости v3
  Написан под реальную структуру API (проверено на живых ответах)
=============================================================
Запуск:  python stoloto_analyzer_v3.py
Зависимости: pip install requests numpy scipy
=============================================================

Структура ответов API (задокументировано по реальным ответам):

  GET /games/info-new
  → { "games": [ { "name": "6x45plus", "active": true,
                   "completedDraw": { "combination": { ... } } }, ... ] }

  GET /draws/archive?game=6x45plus&...
  → { "draws": [ { "combination": { "structured": ... },
                   "winningCombination": ["01","02",...] }, ... ],
      "hasMore": true }

  combination.structured может быть:
    • список чисел:            [22, 10, 44, 2, 7, 35]
    • {"played": [...], ...}   (нарды, раппидо и т.д.)
    • {"notPlayed": [...], ...} (руслото, гжель и т.д.)
    • [{"first":[7,9,1], "second":[1]}]  (spec — пропускаем)
=============================================================
"""

import os
import requests
import json
import time
import sys
import itertools
from collections import Counter

# Отключаем системный прокси для прямого доступа к stoloto.ru
for _pv in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(_pv, None)

try:
    import numpy as np
    from scipy import stats
    SCIPY = True
except ImportError:
    SCIPY = False
    print("⚠  numpy/scipy не найдены — pip install numpy scipy\n")

# ══════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════════════════

DATE_FROM          = "01.01.2009"
DATE_TO            = ""            # пусто = сегодня
MAX_DRAWS_PER_GAME = 15000     # максимум тиражей на игру (максимум доступных)
DRAWS_PER_PAGE     = 50       # API caps at 50 regardless of count param
REQUEST_DELAY      = 0.2      # сек между запросами
MIN_DRAWS          = 5        # минимум тиражей для анализа

HEADERS = {
    "accept": "*/*",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/x-www-form-urlencoded",
    "device-platform": "DESKTOP",
    "device-type": "STOLOTO",
    "gosloto-partner": "bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg",
    "gosloto-token":   "7ec1530511-3a8b64-498989-81db45-c10b0c6087d137",
    "referer": "https://www.stoloto.ru/6x45plus/archive",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

COOKIES = {
    "ga":             "7ec1530511-3a8b64-498989-81db45-c10b0c6087d137",
    "accept_cookies": "true",
    "gosloto_locale": "ru",
}

BASE = "https://www.stoloto.ru/p/api/mobile/api/v35/service"

# Module-level cache for game existence checks
# Format: {game_name: {"exists": bool, "redirect_target": str|None}}
_game_exists_cache = {}

# ══════════════════════════════════════════════════════════
#  1. СПИСОК ИГР
# ══════════════════════════════════════════════════════════

def game_exists_on_site(game_name: str) -> bool:
    """
    Проверяет, существует ли игра на сайте stoloto.ru.
    Также определяет, перенаправляется ли игра на другую страницу.
    Результаты кешируются в _game_exists_cache.
    При ошибках сети считается что существует (lenient).
    """
    # Check cache first
    if game_name in _game_exists_cache:
        return _game_exists_cache[game_name].get('exists', True)

    try:
        r = requests.get(
            f"https://www.stoloto.ru/{game_name}/game",
            headers={
                "user-agent": HEADERS["user-agent"],
                "accept": "text/html,application/xhtml+xml",
                "accept-language": "ru-RU,ru;q=0.9",
            },
            timeout=3,
            allow_redirects=False,  # Don't follow redirects to detect them
        )
        # Check for redirect to homepage or other non-game page
        if r.status_code in (301, 302, 303, 307, 308):
            location = r.headers.get('Location', '')
            # If redirecting to homepage or root — game doesn't exist
            if '/game' not in location or location.rstrip('/') == 'https://www.stoloto.ru' or location.rstrip('/') == 'https://www.stoloto.ru/':
                _game_exists_cache[game_name] = {'exists': False, 'redirect_target': None}
                return False
            # v25.0: Check if redirect target is ANOTHER game page
            # e.g., "klava" → "/5x36plus/archive" means klava was merged into 5x36plus
            import re as _re
            # Extract game name from redirect location (e.g., /5x36plus/archive → 5x36plus)
            _redirect_match = _re.search(r'stoloto\.ru/([a-z0-9_]+)/', location)
            if _redirect_match:
                _redirect_game = _redirect_match.group(1)
                if _redirect_game != game_name and _redirect_game not in ('', 'archive', 'rules', 'game'):
                    # Redirecting to a different game — mark as non-existent
                    _game_exists_cache[game_name] = {'exists': False, 'redirect_target': _redirect_game}
                    return False
        # If 200, check content
        if r.status_code == 200:
            if "Такой страницы у нас нет" in r.text:
                _game_exists_cache[game_name] = {'exists': False, 'redirect_target': None}
                return False
            # Game page should have some game-specific content (simplified keywords)
            has_game_content = any(keyword in r.text for keyword in [
                'archive', 'тираж', 'data-game', 'game-content',
            ])
            if not has_game_content:
                # Very likely a redirect-to-homepage without 30x
                if 'www.stoloto.ru/"' in r.text or '<title>Столото' in r.text:
                    _game_exists_cache[game_name] = {'exists': False, 'redirect_target': None}
                    return False
            _game_exists_cache[game_name] = {'exists': True, 'redirect_target': None}
            return True
        # Other status codes — assume exists (safe default)
        _game_exists_cache[game_name] = {'exists': True, 'redirect_target': None}
        return True
    except Exception:
        # при ошибке сети считаем что существует (lenient)
        _game_exists_cache[game_name] = {'exists': True, 'redirect_target': None}
        return True


def get_games() -> list[dict]:
    """
    GET /games/info-new
    Возвращает только активные игры (active == true),
    которые реально существуют на сайте stoloto.ru.
    """
    hdrs = dict(HEADERS)
    hdrs["gosloto-token"] = "161aa1be13-07d882-41dd32-8fa380-de2eea7bf30a66"

    try:
        r = requests.get(f"{BASE}/games/info-new",
                         headers=hdrs, cookies=COOKIES, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ОШИБКА] /games/info-new: {e}")
        sys.exit(1)

    all_games = data.get("games", [])
    active = [g for g in all_games if g.get("active") and g.get("name")]
    print(f"  Всего игр: {len(all_games)}, активных: {len(active)}")

    # Фильтруем: только игры, у которых есть страница на сайте
    verified = []
    for g in active:
        name = g["name"]
        try:
            if game_exists_on_site(name):
                g["redirect_target"] = None
                verified.append(g)
            else:
                # v25.0: Include redirect target info for redirected games
                _cache_entry = _game_exists_cache.get(name, {})
                _redirect = _cache_entry.get('redirect_target')
                if _redirect:
                    g["redirect_target"] = _redirect
                    print(f"  ⚠ {name} — перенаправлена на {_redirect}, пропускаем")
                else:
                    g["redirect_target"] = None
                    print(f"  ⚠ {name} — страница не найдена, пропускаем")
        except Exception:
            # If the check itself fails, include the game anyway
            print(f"  ⚠ {name} — ошибка проверки, включаем")
            g["redirect_target"] = None
            verified.append(g)

    if len(verified) < len(active):
        print(f"  Проверка существования: {len(verified)}/{len(active)} игр подтверждены")

    return verified


# ══════════════════════════════════════════════════════════
#  2. АРХИВ ТИРАЖЕЙ
# ══════════════════════════════════════════════════════════

def fetch_draws(game_name: str, max_draws: int = 0) -> list[dict]:
    """
    GET /draws/archive?game=...
    Постраничная загрузка. Останавливается когда hasMore == false
    или достигнут max_draws (или MAX_DRAWS_PER_GAME если max_draws=0).
    """
    effective_max = max_draws if max_draws > 0 else MAX_DRAWS_PER_GAME
    url    = f"{BASE}/draws/archive"
    result = []
    page   = 1

    while len(result) < effective_max:
        params = {
            "game":      game_name,
            "date_from": DATE_FROM,
            "date_to":   DATE_TO,
            "count":     DRAWS_PER_PAGE,
            "page":      page,
        }
        try:
            r = requests.get(url, headers=HEADERS, cookies=COOKIES,
                             params=params, timeout=15)
            if r.status_code in (400, 404, 405):
                break
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.HTTPError:
            break
        except Exception as e:
            print(f"    ⚠ {game_name} стр.{page}: {e}")
            break

        # Реальная структура: {"draws": [...], "hasMore": true/false}
        draws_page = data.get("draws", [])
        if not draws_page:
            break

        result.extend(draws_page)

        # Если API говорит «больше нет» — прекращаем
        if not data.get("hasMore", False):
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return result[:effective_max]


# ══════════════════════════════════════════════════════════
#  3. ИЗВЛЕЧЕНИЕ ЧИСЕЛ ИЗ ТИРАЖА
# ══════════════════════════════════════════════════════════

def parse_structured(structured) -> list[int]:
    """
    Разбирает combination.structured в список целых чисел.

    Форматы (из реальных ответов):
      A) [22, 10, 44, 2, 7, 35]                 → список чисел
      B) {"played": [15,20,...], "parity": ...}  → берём played
      C) {"notPlayed": [59,74,...]}              → берём notPlayed
      D) [{"first":[7,9,1],"second":[1]}]        → spec, пропускаем
    """
    if structured is None:
        return []

    # Формат A — уже список чисел
    if isinstance(structured, list):
        if not structured:
            return []
        # Формат D — список словарей (spec-лотерея)
        if isinstance(structured[0], dict):
            return []
        # Нормальный список чисел или строк
        nums = []
        for v in structured:
            try:
                n = int(v)
                if 0 < n <= 90:
                    nums.append(n)
            except (ValueError, TypeError):
                pass
        return nums

    # Форматы B и C — словарь
    if isinstance(structured, dict):
        for key in ("played", "notPlayed"):
            val = structured.get(key)
            if isinstance(val, list) and val:
                nums = []
                for v in val:
                    try:
                        n = int(v)
                        if 0 < n <= 90:
                            nums.append(n)
                    except (ValueError, TypeError):
                        pass
                if nums:
                    return nums
    return []


def extract_numbers(draw: dict) -> list[int]:
    """
    Основной метод извлечения чисел из одного тиража.
    Приоритет: combination.structured > winningCombination
    """
    # 1) combination.structured (самый надёжный источник)
    comb = draw.get("combination", {})
    if isinstance(comb, dict):
        nums = parse_structured(comb.get("structured"))
        if nums:
            return nums

    # 2) winningCombination — список строк вроде ["01","02","37","22","27","04","02"]
    wc = draw.get("winningCombination", [])
    if isinstance(wc, list) and wc:
        nums = []
        for v in wc:
            try:
                n = int(v)
                if 0 < n <= 90:
                    nums.append(n)
            except (ValueError, TypeError):
                pass
        if nums:
            return nums

    return []


# ══════════════════════════════════════════════════════════
#  4. СТАТИСТИЧЕСКИЙ АНАЛИЗ
# ══════════════════════════════════════════════════════════

class GameStats:
    def __init__(self, name: str):
        self.name   = name
        self.draws  : list[list[int]] = []
        self.freq   : Counter = Counter()
        self.pairs  : Counter = Counter()
        self.redirect_target = None  # v25.0: target game if this game was redirected

    def add(self, nums: list[int]):
        if not nums:
            return
        self.draws.append(nums)
        self.freq.update(nums)
        for a, b in itertools.combinations(sorted(set(nums)), 2):
            self.pairs[(a, b)] += 1

    @property
    def n(self):
        return len(self.draws)

    def report(self) -> dict:
        r = {
            "name":            self.name,
            "draws":           self.n,
            "unique_nums":     len(self.freq),
            "top10":           self.freq.most_common(10),
            "cold10":          self.freq.most_common()[:-11:-1],
            "top_pairs":       self.pairs.most_common(5),
            "chi2_p":          None,
            "chi2_info":       "—",
            "autocorr":        None,
            "score":           0.0,
            "verdict":         "❓ Мало данных",
            "redirect_target": self.redirect_target,  # v25.0: target game if redirected
        }

        if self.n < MIN_DRAWS:
            return r

        # ── χ²-тест на равномерность ──────────────────────
        if SCIPY and self.freq:
            nums_seen = sorted(self.freq.keys())
            if nums_seen:
                lo_num, hi_num = nums_seen[0], nums_seen[-1]
                rng   = list(range(lo_num, hi_num + 1))
                obs   = [self.freq.get(i, 0) for i in rng]
                total = sum(obs)
                if total > 0 and len(rng) > 1:
                    exp = [total / len(rng)] * len(rng)
                    chi2, p = stats.chisquare(obs, f_exp=exp)
                    r["chi2_p"]    = round(p, 4)
                    r["chi2_info"] = (
                        "✅ Равномерное (случайное)"
                        if p > 0.05
                        else f"⚠️  Неравномерное! p={p:.4f}"
                    )

        # ── Автокорреляция сумм тиражей ───────────────────
        if SCIPY and self.n >= 20:
            sums = np.array([sum(d) for d in self.draws], dtype=float)
            if np.std(sums) > 0:
                ac = float(np.corrcoef(sums[:-1], sums[1:])[0, 1])
                if not np.isnan(ac):
                    r["autocorr"] = round(ac, 4)

        # ── Оценка аномальности 0–100 ─────────────────────
        score = 0.0
        p = r["chi2_p"]
        if p is not None:
            if   p < 0.001: score += 40
            elif p < 0.01:  score += 25
            elif p < 0.05:  score += 10

        ac = r["autocorr"]
        if ac is not None:
            a = abs(ac)
            if   a > 0.30: score += 30
            elif a > 0.15: score += 15
            elif a > 0.08: score += 5

        # Концентрация горячих чисел
        if r["top10"] and r["unique_nums"] > 0 and self.n > 0:
            avg_per_draw = sum(len(d) for d in self.draws) / self.n
            top_share    = sum(c for _, c in r["top10"]) / (self.n * avg_per_draw)
            exp_share    = 10 / r["unique_nums"]
            if exp_share > 0:
                ratio = top_share / exp_share
                if   ratio > 1.5: score += 20
                elif ratio > 1.2: score += 10

        r["score"]   = min(score, 100.0)
        r["verdict"] = self._verdict(r["score"])
        return r

    @staticmethod
    def _verdict(s: float) -> str:
        if   s >= 50: return "🔴 ВЫСОКАЯ аномальность"
        elif s >= 25: return "🟡 Умеренная аномальность"
        else:         return "🟢 Статистически случайная"


# ══════════════════════════════════════════════════════════
#  5. ВЫВОД
# ══════════════════════════════════════════════════════════

SEP = "=" * 72

def print_report(r: dict):
    print(f"\n{'─'*72}")
    print(f"  🎲 {r['name']}")
    print(f"{'─'*72}")
    print(f"  Тиражей          : {r['draws']}")
    print(f"  Уникальных чисел : {r['unique_nums']}")
    print(f"  χ²-тест          : {r['chi2_info']}")
    if r["autocorr"] is not None:
        print(f"  Автокорреляция   : {r['autocorr']}")
    print(f"  Горячие числа    : {[n for n,_ in r['top10']]}")
    print(f"  Холодные числа   : {[n for n,_ in r['cold10']]}")
    print(f"  Топ-5 пар        : {r['top_pairs']}")
    print(f"\n  Аномальность : {r['score']:.1f}/100  →  {r['verdict']}")


def print_summary(results: list[dict]):
    analyzed = [r for r in results if r["draws"] >= MIN_DRAWS]
    skipped  = [r for r in results if r["draws"] <  MIN_DRAWS]

    print(f"\n\n{SEP}")
    print("  СВОДНАЯ ТАБЛИЦА (от наиболее к наименее аномальным)")
    print(SEP)
    print(f"  {'Игра':<22} {'Тиражей':>8}  {'Аномальность':>13}  Вывод")
    print(f"  {'─'*22} {'─'*8}  {'─'*13}  {'─'*35}")
    for r in sorted(analyzed, key=lambda x: x["score"], reverse=True):
        print(
            f"  {r['name']:<22} {r['draws']:>8}  "
            f"{r['score']:>12.1f}  {r['verdict']}"
        )
    print(SEP)

    top = [r for r in analyzed if r["score"] >= 50]
    if top:
        print("\n  ⚠️  Игры с ВЫСОКОЙ аномальностью:")
        for r in top:
            print(f"     • {r['name']}  (score={r['score']:.1f})")
    else:
        print("\n  ✅ Ни одна из проанализированных игр не показала явной предсказуемости.")

    if skipped:
        names = ", ".join(r["name"] for r in skipped[:20])
        print(f"\n  ⚪ Пропущено (мало тиражей): {names}")
    print()


# ══════════════════════════════════════════════════════════
#  6. MAIN
# ══════════════════════════════════════════════════════════

def main():
    print(SEP)
    print("  СТОЛОТО — Анализатор предсказуемости v3")
    print(f"  Период: {DATE_FROM} → {DATE_TO}")
    print(f"  scipy/numpy: {'✅' if SCIPY else '❌  pip install numpy scipy'}")
    print(SEP)

    # ─── 1. Список активных игр ───────────────────────────
    print("\n[1/3] Получение активных игр...")
    games = get_games()
    print(f"  Игры: {[g['name'] for g in games]}")

    # ─── 2. Загрузка тиражей и анализ ────────────────────
    print("\n[2/3] Загрузка тиражей и статистика...")
    results = []

    for g in games:
        name = g["name"]
        print(f"\n  ▶ {name} ...", end=" ", flush=True)

        draws_raw = fetch_draws(name)
        print(f"{len(draws_raw)} тиражей", end=" → ", flush=True)

        gs = GameStats(name)
        ok = 0
        for draw in draws_raw:
            nums = extract_numbers(draw)
            if nums:
                gs.add(nums)
                ok += 1

        print(f"распознано {ok} тиражей с числами")

        r = gs.report()
        # v25.0: Attach redirect_target from game dict if available
        if "redirect_target" in g:
            r["redirect_target"] = g["redirect_target"]
        results.append(r)
        if ok >= MIN_DRAWS:
            print_report(r)

        time.sleep(REQUEST_DELAY)

    # ─── 3. Сводка ────────────────────────────────────────
    print("\n[3/3] Итоговая сводка")
    print_summary(results)

    # Сохраняем JSON
    out = "stoloto_analysis_v3.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2,
                  default=lambda x: list(x) if isinstance(x, Counter) else str(x))
    print(f"  💾 Полные данные → {out}\n")


if __name__ == "__main__":
    main()
