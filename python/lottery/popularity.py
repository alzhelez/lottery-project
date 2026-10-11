"""Популярность чисел у игроков — по числу победителей в тиражах.

Идея: если в тираже выпали числа, которые любят ставить, победителей в каждой категории
больше, чем обычно. Модель:

    y_t = log(победителей в тираже t) − обычный уровень (скользящая медиана по 51 тиражу)
    y_t ≈ Σ β_v · [число v выпало в тираже t]

Скользящая медиана убирает рост и падение продаж; β_v > 0 — число популярнее среднего.
Коэффициенты оцениваются гребневой регрессией, значимость — перестановочным тестом:
если связь не отличается от случайной, модель не используется, а генератор билетов
опирается только на эвристики (даты, ряды и т. п.).

Шанс выигрыша это не меняет: популярность влияет лишь на то, со сколькими людьми
придётся делить приз в делимых категориях.
"""
from __future__ import annotations

import numpy as np

from . import prizes as prizes_mod
from .drawfile import GameData

MIN_DRAWS = 100
MIN_MEDIAN_WINNERS = 20
WINDOW = 51
RIDGE = 5.0
PERMUTATIONS = 200


def _rolling_median(x: np.ndarray, window: int) -> np.ndarray:
    half = window // 2
    out = np.empty_like(x)
    for i in range(len(x)):
        out[i] = np.median(x[max(0, i - half): i + half + 1])
    return out


def _target(data: GameData) -> tuple[np.ndarray, np.ndarray, list[str]] | None:
    """y по тиражам (NaN — нет данных) и категории, по которым он построен."""
    counts = [s.count for s in data.fmt.blocks]
    hist = prizes_mod.keyed_history(data.game.slug, counts)
    if len(hist) < MIN_DRAWS:
        return None
    keys = sorted({k for h in hist.values() for k in h["categories"]})
    w = np.full((data.T, len(keys)), np.nan)
    for t, d in enumerate(data.draws):
        h = hist.get(d.no)
        if h:
            for j, k in enumerate(keys):
                c = h["categories"].get(k)
                if c and c["winners"] is not None:
                    w[t, j] = c["winners"]
    med = np.nanmedian(w, axis=0)
    use = [j for j in range(len(keys)) if np.isfinite(med[j]) and med[j] >= MIN_MEDIAN_WINNERS]
    if not use:
        return None
    resid = []
    for j in use:
        col = np.log(w[:, j] + 0.5)
        ok = np.isfinite(col)
        r = np.full(data.T, np.nan)
        r[ok] = col[ok] - _rolling_median(col[ok], WINDOW)
        resid.append(r)
    y = np.nanmean(np.vstack(resid), axis=0)
    return y, np.isfinite(y), [keys[j] for j in use]


def _ridge(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    a = x.T @ x + RIDGE * np.eye(x.shape[1])
    beta = np.linalg.solve(a, x.T @ y)
    resid = y - x @ beta
    r2 = 1 - float(resid @ resid) / float(y @ y) if float(y @ y) > 0 else 0.0
    return beta, r2


def fit(data: GameData, seed: int = 7) -> dict:
    base = {"available": False}
    if not data.fmt.supported or data.fmt.bingo or any(s.mode == "position" for s in data.fmt.blocks):
        return {**base, "reason": "для этого формата игры популярность не оценивается"}
    tgt = _target(data)
    if tgt is None:
        return {**base, "reason": f"нужно хотя бы {MIN_DRAWS} тиражей с числом победителей в архиве"}
    y, ok, cats = tgt
    x = np.hstack(data.matrices)[ok].astype(np.float64)
    x -= x.mean(axis=0)
    yy = y[ok] - y[ok].mean()
    beta, r2 = _ridge(x, yy)
    rng = np.random.default_rng(seed)
    perm = np.array([_ridge(x, rng.permutation(yy))[1] for _ in range(PERMUTATIONS)])
    p = float((1 + np.sum(perm >= r2)) / (PERMUTATIONS + 1))
    numbers = []
    offset = 0
    for spec in data.fmt.blocks:
        for j in range(spec.size):
            numbers.append({"block": spec.name, "number": spec.lo + j, "beta": float(beta[offset + j])})
        offset += spec.size
    main = [n for n in numbers if n["block"] == data.fmt.blocks[0].name]
    ranked = sorted(main, key=lambda n: -n["beta"])
    return {
        "available": True,
        "significant": p < 0.05,
        "p_value": p,
        "r2": r2,
        "draws": int(ok.sum()),
        "categories": cats,
        "numbers": numbers,
        "popular": [n["number"] for n in ranked[:8]],
        "unpopular": [n["number"] for n in ranked[-8:]][::-1],
        "verdict": (f"Популярность чисел видна по числу победителей (p={p:.3f}): игроки чаще ставят "
                    f"{', '.join(map(str, [n['number'] for n in ranked[:5]]))} и реже — "
                    f"{', '.join(map(str, [n['number'] for n in ranked[-5:]]))}. Генератор билетов это учитывает."
                    if p < 0.05 else
                    f"Связь числа победителей с выпавшими числами в пределах случайности (p={p:.2f}) — "
                    "генератор опирается на общие признаки популярности (даты, ряды и т. п.)."),
    }


def score(model: dict, blocks: list[list[int]], block_names: list[str]) -> float:
    """Суммарная популярность комбинации по модели (0 — средняя)."""
    beta = {(n["block"], n["number"]): n["beta"] for n in model.get("numbers", [])}
    return float(sum(beta.get((name, v), 0.0) for name, nums in zip(block_names, blocks) for v in nums))
