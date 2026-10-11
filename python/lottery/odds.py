"""Калькулятор шансов: точные вероятности каждого исхода билета и ожидаемый возврат.

Билет в игре «k из N» (по каждому полю) — это выбор k чисел; число совпадений с тиражом
в поле подчиняется гипергеометрическому распределению, поля независимы. Поэтому
вероятность исхода «a+b» (a совпадений в первом поле, b во втором) — произведение.

Суммы призов и цену билета вводит пользователь (data/prizes/<игра>.json): правила игр
меняются, а автоматически проверить их нельзя. По закону «О лотереях» (ст. 10)
призовой фонд — не меньше 50% выручки: в среднем лотерея возвращает игрокам не больше
половины ставок, остальное — выручка оператора и отчисления.
"""
from __future__ import annotations

import itertools
import json

import numpy as np
from scipy import stats as sps

from .drawfile import GameData
from .games import data_dir

LEGAL_PRIZE_FUND = 0.5
MAX_PATTERNS = 5000


def prizes_path(slug: str):
    return data_dir() / "prizes" / f"{slug}.json"


def load_prizes(slug: str) -> dict:
    try:
        raw = json.loads(prizes_path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"price": None, "prizes": {}}
    prizes = {str(k): float(v) for k, v in (raw.get("prizes") or {}).items()
              if isinstance(v, (int, float)) and v > 0}
    price = raw.get("price")
    return {"price": float(price) if isinstance(price, (int, float)) and price > 0 else None, "prizes": prizes}


def save_prizes(slug: str, price, prizes: dict) -> dict:
    from .fsutil import write_text
    clean = {"price": price, "prizes": {k: v for k, v in prizes.items() if v}}
    write_text(prizes_path(slug), json.dumps(clean, ensure_ascii=False, indent=1))
    return load_prizes(slug)


def supported(data: GameData) -> tuple[bool, str]:
    if not data.fmt.supported:
        return False, data.fmt.reason
    if data.fmt.bingo:
        return False, ("В бинго-играх выигрыш зависит от готового билета и туров, а не от выбранных "
                       "чисел, — калькулятор к ним не применим.")
    return True, ""


def block_pmf(spec) -> np.ndarray:
    """Распределение совпадений в одном поле: выбрано count чисел, выпало count из size."""
    k = spec.count
    return sps.hypergeom(spec.size, k, k).pmf(np.arange(k + 1))


def pattern_key(hits: tuple[int, ...]) -> str:
    return "+".join(str(h) for h in hits)


def odds_table(data: GameData) -> dict:
    ok, reason = supported(data)
    base = {"slug": data.game.slug, "title": data.game.title, "format": data.fmt.describe(),
            "legal_prize_fund": LEGAL_PRIZE_FUND}
    if not ok:
        return {**base, "supported": False, "reason": reason}
    specs = data.fmt.blocks
    pmfs = [block_pmf(s) for s in specs]
    combos = 1
    for p in pmfs:
        combos *= len(p)
    if combos > MAX_PATTERNS:
        return {**base, "supported": False, "reason": "слишком много вариантов исходов"}
    rows = []
    for hits in itertools.product(*[range(len(p)) for p in pmfs]):
        prob = float(np.prod([p[h] for p, h in zip(pmfs, hits)]))
        rows.append({"key": pattern_key(hits), "hits": list(hits), "total": int(sum(hits)), "p": prob,
                     "one_in": (1 / prob) if prob > 0 else None})
    rows.sort(key=lambda r: (-r["total"], [-h for h in r["hits"]]))
    jackpot = rows[0]
    tickets = 1
    for s in specs:
        tickets *= int(round(1 / sps.hypergeom(s.size, s.count, s.count).pmf(s.count)))
    user = load_prizes(data.game.slug)
    archive = {"prizes": {}, "price": None, "draws": 0}
    if not any(s.mode == "position" for s in specs):
        from .prizes import typical_prizes
        archive = typical_prizes(data.game.slug, [s.count for s in specs])
    ev = None
    win_p = 0.0
    any_prize = False
    for r in rows:
        # приоритет у введённого вами; иначе — медиана реальных выплат из архива
        prize, source = user["prizes"].get(r["key"]), "user"
        if not prize and r["key"] in archive["prizes"]:
            prize, source = archive["prizes"][r["key"]], "archive"
        r["prize"] = prize
        r["prize_source"] = source if prize else None
        r["archive_prize"] = archive["prizes"].get(r["key"])
        if prize:
            any_prize = True
            win_p += r["p"]
            ev = (ev or 0.0) + r["p"] * prize
    price = user["price"] or archive["price"]
    return {
        **base,
        "supported": True,
        "blocks": [{"name": s.name, "count": s.count, "lo": s.lo, "hi": s.hi} for s in specs],
        "patterns": rows,
        "jackpot": {"key": jackpot["key"], "p": jackpot["p"], "one_in": jackpot["one_in"]},
        "combinations": tickets,
        "price": price,
        "price_source": "user" if user["price"] else ("archive" if archive["price"] else None),
        "expected_value": ev,
        "return_per_ruble": (ev / price) if ev is not None and price else None,
        "p_any_prize": win_p if any_prize else None,
        "prizes_entered": len(user["prizes"]),
        "archive_draws": archive["draws"],
    }
