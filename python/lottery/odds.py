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
    """Можно ли посчитать шансы точно (по комбинаторике). Если нет — остаются шансы по архиву."""
    if not data.fmt.supported:
        return False, data.fmt.reason
    if data.fmt.bingo:
        return False, ("В бинго выигрыш зависит от готового билета и того, на каком шаре закроется тур, — "
                       "точной формулы нет. Шансы туров ниже посчитаны по реальным итогам тиражей.")
    if any(s.mode == "position" for s in data.fmt.blocks):
        return False, ("Здесь ставят на цифры и их порядок (точный порядок, любой порядок, первые и последние "
                       "цифры), у каждой ставки свои правила. Шансы ставок ниже посчитаны по реальным итогам тиражей.")
    return True, ""


def keno_variants(data: GameData, price: float | None) -> list[dict] | None:
    """Кено: игрок выбирает K чисел (1…10), выпадает 20 из 80. Для каждого K — точное
    распределение совпадений и выплаты из архива (медиана по подписи «k из K»)."""
    specs = [s for s in data.fmt.blocks if s.drawn and s.drawn > s.count]
    if len(specs) != 1:
        return None
    from .prizes import typical_by_label
    spec = specs[0]
    prizes = typical_by_label(data.game.slug, last=500)   # у Кено призы фиксированные — берём окно шире
    out = []
    for k_pick in range(1, spec.count + 1):
        pmf = sps.hypergeom(spec.size, spec.drawn, k_pick).pmf(np.arange(k_pick + 1))
        rows = []
        ev = 0.0
        p_win = 0.0
        for hits in range(k_pick, -1, -1):
            prize = prizes.get(f"{hits} из {k_pick}")
            rows.append({"hits": hits, "p": float(pmf[hits]), "one_in": float(1 / pmf[hits]) if pmf[hits] > 0 else None,
                         "prize": prize})
            if prize:
                ev += float(pmf[hits]) * prize
                p_win += float(pmf[hits])
        out.append({"pick": k_pick, "rows": rows, "expected_value": ev if p_win else None,
                    "return_per_ruble": ev / price if p_win and price else None,
                    "p_any_prize": p_win if p_win else None})
    return out


def block_pmf(spec) -> np.ndarray:
    """Распределение совпадений в одном поле: выбрано count чисел из size, выпало balls
    (обычно столько же; в Кено — 20 выпавших на 10 выбранных)."""
    k = spec.count
    return sps.hypergeom(spec.size, getattr(spec, "balls", k), k).pmf(np.arange(k + 1))


def pattern_key(hits: tuple[int, ...]) -> str:
    return "+".join(str(h) for h in hits)


def odds_table(data: GameData) -> dict:
    ok, reason = supported(data)
    from .prizes import archive_stats
    base = {"slug": data.game.slug, "title": data.game.title, "format": data.fmt.describe(),
            "legal_prize_fund": LEGAL_PRIZE_FUND, "archive": archive_stats(data.game.slug)}
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
        tickets *= int(round(1 / sps.hypergeom(s.size, s.count, s.count).pmf(s.count)))   # C(size, count)
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
        "variants": keno_variants(data, price),
    }
