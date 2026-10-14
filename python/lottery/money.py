"""Оценка в рублях: сколько выиграл бы билет с прогнозом метода на самом деле.

Для каждого тиража берётся его реальная таблица выплат (prizes_<игра>.jsonl): совпадения
прогноза с выпавшими числами дают категорию («4+3»), за неё — выплата на одного победителя
в этом тираже. Сравнение — с ожидаемым выигрышем случайного билета в том же тираже:
Σ P(категория) × выплата. Тиражи без данных о выплатах в расчёт не входят.

Выигрыши очень неравномерны (редкий крупный приз перевешивает тысячи мелких), поэтому
рублёвая оценка шумнее, чем по угаданным числам, — её стоит читать вместе с ней.
"""
from __future__ import annotations

import itertools

import numpy as np

from . import prizes as prizes_mod
from .drawfile import GameData
from .models import hits as block_hits
from .odds import block_pmf, load_prizes

MIN_DRAWS = 30


def context(data: GameData) -> dict | None:
    """Выплаты по тиражам игры в виде матрицы «тираж × категория» и цена билета."""
    if not data.fmt.supported or data.fmt.bingo or any(s.mode == "position" for s in data.fmt.blocks):
        return None
    counts = [s.count for s in data.fmt.blocks]
    hist = prizes_mod.keyed_history(data.game.slug, counts)
    if len(hist) < MIN_DRAWS:
        return None
    user = load_prizes(data.game.slug)
    typical = prizes_mod.typical_prizes(data.game.slug, counts)
    price = user["price"] or typical["price"]
    if not price:
        return {"available": False, "reason": "нет цены билета — введите её на вкладке «Шансы»",
                "draws_with_prizes": len(hist)}
    keys = ["+".join(map(str, h)) for h in itertools.product(*[range(c + 1) for c in counts])]
    col = {k: i for i, k in enumerate(keys)}
    table = np.full((data.T, len(keys)), np.nan)
    # цена билета в каждом тираже: она менялась (4 из 20 — 100 ₽ раньше, 350 ₽ сейчас),
    # и считать всю историю по сегодняшней цене — занижать возврат. Свою цену пользователь
    # вводит как сегодняшнюю — она применяется ко всем тиражам.
    prices = np.full(data.T, float(price))
    for t, d in enumerate(data.draws):
        h = hist.get(d.no)
        if not h:
            continue
        if not user["price"] and h.get("price"):
            prices[t] = float(h["price"])
        table[t] = 0.0                                   # категории, которых нет в таблице, — без выигрыша
        for key, c in h["categories"].items():
            if key in col and c["prize"]:
                table[t, col[key]] = c["prize"]
    pmfs = [block_pmf(s) for s in data.fmt.blocks]
    p_key = np.array([np.prod([p[int(x)] for p, x in zip(pmfs, k.split("+"))]) for k in keys])
    return {"available": True, "price": float(price), "prices": prices, "keys": keys, "col": col, "table": table,
            "random_ev": table @ p_key, "has": ~np.isnan(table[:, 0]), "draws_with_prizes": len(hist),
            "price_source": "введена вами" if user["price"] else "из ответа API"}


def payouts(ctx: dict, data: GameData, picks: list[np.ndarray]) -> np.ndarray:
    """Выплата по каждому тиражу для прогнозов picks (NaN — нет данных о выплатах)."""
    per_block = [block_hits(x, p).astype(int) for x, p in zip(data.matrices, picks)]
    keys = ["+".join(str(int(v)) for v in row) for row in zip(*per_block)]
    idx = np.array([ctx["col"][k] for k in keys])
    return ctx["table"][np.arange(data.T), idx]


def summary(ctx: dict, won: np.ndarray, rows: slice) -> dict:
    mask = ctx["has"][rows]
    n = int(mask.sum())
    if n == 0:
        return {"n": 0}
    w = float(np.nansum(won[rows][mask]))
    r = float(np.nansum(ctx["random_ev"][rows][mask]))
    spent = float(ctx["prices"][rows][mask].sum()) if "prices" in ctx else ctx["price"] * n
    return {"n": n, "won": w, "spent": spent, "return": w / spent, "random_return": r / spent,
            "excess_pct": (w - r) / r * 100 if r else 0.0}
