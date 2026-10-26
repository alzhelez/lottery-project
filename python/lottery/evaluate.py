"""Честная проверка методов на истории (walk-forward).

Протокол:
  1. Каждый тираж t прогнозируется только по тиражам < t.
  2. Тестовый отрезок делится по времени: первые 2/3 — «отбор» (выбираем лучший метод),
     последняя 1/3 — «контроль» (проверяем выбранный метод на данных, которые не влияли
     на выбор). Без этого лучший из 20 методов всегда выглядит лучше случайного —
     просто потому что из 20 случайных результатов выбрали максимальный.
  3. Сравнение со случайным выбором — по точной теории (гипергеометрическое
     распределение), а не по одному прогону генератора.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from .drawfile import GameData
from .models import Features, Model, consensus_votes, hits, standard_models, top_k
from .stats import holm, hypergeom_moments, ru

SELECTION_SHARE = 2 / 3
MIN_TEST = 60


def warmup_size(t_total: int) -> int:
    return int(max(30, min(200, t_total // 5)))


def baseline(data: GameData) -> tuple[np.ndarray, np.ndarray]:
    """Ожидание и дисперсия числа угаданных при случайном выборе — по каждому тиражу
    (сумма по блокам). Для обычных игр одинаковы во всех тиражах, для бинго зависят
    от того, сколько чисел вошло в блок в данном тираже."""
    mean = np.zeros(data.T)
    var = np.zeros(data.T)
    for x, spec in zip(data.matrices, data.fmt.blocks):
        m, v = hypergeom_moments(spec.size, x.sum(axis=1), spec.count)
        mean += m
        var += v
    return mean, var


def baseline_pmf(data: GameData, rows: slice = slice(None)) -> np.ndarray:
    """Распределение числа угаданных у случайного выбора, усреднённое по тиражам rows."""
    ks = np.stack([x[rows].sum(axis=1).astype(int) for x in data.matrices], axis=1)
    total = np.zeros(sum(s.count for s in data.fmt.blocks) + 1)
    if len(ks) == 0:
        return total
    combos, freq = np.unique(ks, axis=0, return_counts=True)
    for combo, cnt in zip(combos, freq):
        pmf = np.array([1.0])
        for k_t, spec in zip(combo, data.fmt.blocks):
            pmf = np.convolve(pmf, sps.hypergeom(spec.size, int(k_t), spec.count).pmf(np.arange(spec.count + 1)))
        total[: len(pmf)] += cnt * pmf
    return total / len(ks)


def metrics(h: np.ndarray, mean0, var0) -> dict:
    """Средний результат против случайного выбора. mean0/var0 — ожидание и дисперсия
    по тем же тиражам (массивы той же длины или числа)."""
    n = int(len(h))
    if n == 0:
        return {"n": 0}
    m0 = np.broadcast_to(np.asarray(mean0, dtype=np.float64), h.shape)
    v0 = np.broadcast_to(np.asarray(var0, dtype=np.float64), h.shape)
    base = float(m0.mean())
    mean = float(h.mean())
    excess = mean - base
    total_var = float(v0.sum())
    z = float((h.sum() - m0.sum()) / math.sqrt(total_var)) if total_var > 0 else 0.0
    return {
        "n": n,
        "mean_hits": mean,
        "baseline": base,
        "excess": excess,
        "excess_pct": excess / base * 100 if base else 0.0,
        "z": z,
        "p_better": float(sps.norm.sf(z)),   # вероятность получить такой результат случайно
    }


def rolling_curve(h: np.ndarray, mean0, points: int = 160) -> list[float]:
    """Накопленное превышение над случайным (в угаданных числах) — для графика."""
    cum = np.cumsum(h - mean0)
    if len(cum) == 0:
        return []
    idx = np.unique(np.linspace(0, len(cum) - 1, min(points, len(cum))).astype(int))
    return [round(float(cum[i]), 2) for i in idx]


def _numbers(picks_row: np.ndarray, lo: int) -> list[int]:
    return sorted(int(v) + lo for v in picks_row)


class Evaluator:
    """Считает прогнозы моделей по всем блокам игры и кэширует признаки."""

    def __init__(self, data: GameData):
        self.data = data
        self.features = [Features(x, s.count) for x, s in zip(data.matrices, data.fmt.blocks)]
        self.mean0, self.var0 = baseline(data)
        # порядок выпадения (если архив его хранит) — для метода «позиции выпадения»
        try:
            from .mechanics import _ordered_rows
            for f, spec in zip(self.features, data.fmt.blocks):
                arr = _ordered_rows(data, spec)
                if arr is not None and arr.shape[0] == f.T:
                    f.ordered = (arr - spec.lo).astype(np.int64)
        except Exception:  # noqa: BLE001 — без порядка метод считает обычную частоту
            pass

    def picks(self, model: Model) -> list[np.ndarray]:
        out = []
        for i, (f, spec) in enumerate(zip(self.features, self.data.fmt.blocks)):
            out.append(f.memo(("picks", model.key), lambda f=f, spec=spec, i=i: top_k(model.scores(f), spec.count, seed=11 + i)))
        return out

    def hits(self, picks: list[np.ndarray]) -> np.ndarray:
        total = np.zeros(self.data.T, np.float32)
        for x, p in zip(self.data.matrices, picks):
            total += hits(x, p)
        return total

    def numbers(self, picks: list[np.ndarray], row: int) -> list[list[int]]:
        return [_numbers(p[row], s.lo) for p, s in zip(picks, self.data.fmt.blocks)]


def evaluate_game(data: GameData, progress=None, models: list[Model] | None = None) -> dict:
    """models — свой набор методов (по умолчанию стандартный); первый метод-контроль обязателен."""
    t_total = data.T
    ev = Evaluator(data)
    warm = warmup_size(t_total)
    test_len = t_total - warm
    if test_len < MIN_TEST:
        return {"status": "insufficient",
                "message": f"Для проверки методов нужно хотя бы {warm + MIN_TEST} тиражей, есть {t_total}."}
    split = warm + int(test_len * SELECTION_SHARE)
    models = models or standard_models()
    results = []
    all_picks: dict[str, list[np.ndarray]] = {}
    for i, m in enumerate(models):
        if progress:
            progress({"stage": "models", "done": i, "total": len(models) + 1, "model": m.title})
        p = ev.picks(m)
        all_picks[m.key] = p
        h = ev.hits(p)
        results.append((m, h))

    # ансамбль: голосование трёх методов, лучших на прошлых тиражах (на каждый тираж — свои)
    voters = [m.key for m in models if not m.control]
    if len(voters) >= 3:
        from .models_extra import leaders_ensemble
        hrows = np.stack([h for m, h in results if not m.control])
        ens = leaders_ensemble([all_picks[k] for k in voters], hrows, [s.size for s in data.fmt.blocks],
                               [s.count for s in data.fmt.blocks])
        ens_model = Model("leaders_3", "Ансамбль: голосование трёх лидеров", "ensemble", lambda f: None)
        all_picks["leaders_3"] = ens
        results.append((ens_model, ev.hits(ens)))

    # консенсус: числа, которые чаще всего попадают в прогнозы разных моделей
    cons_picks = []
    for b, spec in enumerate(data.fmt.blocks):
        votes = consensus_votes([all_picks[k][b] for k in voters], spec.size)
        cons_picks.append(top_k(votes, spec.count, seed=31 + b))
    cons_model = Model("consensus", "Консенсус всех моделей", "consensus", lambda f: None)
    all_picks["consensus"] = cons_picks
    results.append((cons_model, ev.hits(cons_picks)))
    if progress:
        progress({"stage": "models", "done": len(models) + 1, "total": len(models) + 1, "model": "консенсус"})

    m0, v0 = ev.mean0, ev.var0
    base_test = float(m0[warm:].mean())
    base_hold = float(m0[split:].mean())
    from . import money
    mctx = money.context(data)
    rows = []
    for m, h in results:
        row_money = None
        if mctx and mctx.get("available"):
            won = money.payouts(mctx, data, all_picks[m.key])
            row_money = {"selection": money.summary(mctx, won, slice(warm, split)),
                         "holdout": money.summary(mctx, won, slice(split, None))}
        rows.append({
            "money": row_money,
            "key": m.key,
            "title": ru(m.title),
            "family": m.family,
            "control": m.control,
            "all": metrics(h[warm:], m0[warm:], v0[warm:]),
            "selection": metrics(h[warm:split], m0[warm:split], v0[warm:split]),
            "holdout": metrics(h[split:], m0[split:], v0[split:]),
            "curve": rolling_curve(h[warm:], m0[warm:]),
            "next": ev.numbers(all_picks[m.key], t_total),
        })

    candidates = [r for r in rows if not r["control"]]
    adj = holm([r["holdout"]["p_better"] for r in candidates])
    for r, a in zip(candidates, adj):
        r["holdout"]["p_adjusted"] = a
    best = max(candidates, key=lambda r: r["selection"]["mean_hits"])
    best_hold = best["holdout"]
    significant = [r["title"] for r in candidates if r["holdout"]["p_adjusted"] < 0.05]

    if best_hold["p_better"] < 0.05:
        conclusion = (f"«{best['title']}» лучше всех на отрезке отбора и на контрольном отрезке "
                      f"угадывает в среднем {best_hold['mean_hits']:.3f} против {base_hold:.3f} у случайного "
                      f"выбора (p={best_hold['p_better']:.3f}).")
        if best["title"] not in significant:
            conclusion += (" После поправки на число проверенных методов результат не значим — "
                           "это может быть удачей.")
    else:
        conclusion = (f"Лучший на отрезке отбора метод — «{best['title']}». На контрольном отрезке он угадывает "
                      f"{best_hold['mean_hits']:.3f} при {base_hold:.3f} у случайного выбора — разница в пределах "
                      f"случайности (p={best_hold['p_better']:.2f}).")
        if not significant:
            conclusion += " Ни один метод не даёт устойчивого преимущества."
    others = [r for r in candidates if r["title"] in significant and r["key"] != best["key"]]
    if others:
        desc = "; ".join(f"«{r['title']}» {r['holdout']['mean_hits']:.3f} "
                         f"({r['holdout']['excess_pct']:+.1f}%, p с поправкой {r['holdout']['p_adjusted']:.3f})"
                         for r in others)
        conclusion += (f" На контрольном отрезке значимо лучше случайного: {desc}. Этот метод не был лучшим "
                       "на отборе, поэтому находку нужно подтвердить на новых тиражах; выигрыш в угаданных "
                       "числах очень мал.")

    # подробности по последним тиражам для лучшего метода и консенсуса
    recent = []
    best_picks = all_picks[best["key"]]
    for t in range(max(warm, t_total - 30), t_total):
        d = data.draws[t]
        recent.append({
            "no": d.no,
            "date": d.date,
            "actual": [sorted(v + s.lo for v in np.nonzero(x[t])[0]) for x, s in zip(data.matrices, data.fmt.blocks)],
            "best": ev.numbers(best_picks, t),
            "best_hits": int(ev.hits(best_picks)[t]),
            "consensus": ev.numbers(cons_picks, t),
            "consensus_hits": int(ev.hits(cons_picks)[t]),
        })
    recent.reverse()

    next_votes = []
    for b, spec in enumerate(data.fmt.blocks):
        votes = consensus_votes([all_picks[k][b][t_total:t_total + 1] for k in voters], spec.size)[0]
        order = np.argsort(-votes, kind="stable")
        next_votes.append({
            "block": spec.name,
            "votes": [{"number": int(j) + spec.lo, "votes": int(votes[j])} for j in order if votes[j] > 0],
            "models": len(voters),
        })

    # наименее вероятные числа: те же методы «наоборот» (least.py)
    from . import least as least_mod
    if progress:
        progress({"stage": "models", "done": len(models) + 1, "total": len(models) + 1, "model": "наименее вероятные числа"})
    try:
        least = least_mod.evaluate(data, ev, models, warm, split)
    except Exception as exc:  # noqa: BLE001 — дополнительный раздел не должен ронять анализ
        least = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}

    pmf = baseline_pmf(data, slice(warm, None))
    best_h = next(h for m, h in results if m.key == best["key"])[warm:]
    dist_obs = np.bincount(best_h.astype(int), minlength=len(pmf))[: len(pmf)]

    return {
        "status": "ok",
        "draws": t_total,
        "warmup": warm,
        "test": {"from": data.draws[warm].no, "split": data.draws[split].no, "to": data.draws[-1].no,
                 "selection_draws": split - warm, "holdout_draws": t_total - split},
        "baseline": {"mean": base_test, "sd": math.sqrt(float(v0[warm:].mean()))},
        "models": rows,
        "best_key": best["key"],
        "conclusion": ru(conclusion),
        "significant_after_correction": significant,
        "recent": recent,
        "next_votes": next_votes,
        "next_prediction": {"model": best["title"], "numbers": best["next"]},
        "next_consensus": ev.numbers(cons_picks, t_total),
        "money": None if not mctx else {
            "available": bool(mctx.get("available")),
            "reason": mctx.get("reason"),
            "price": mctx.get("price"),
            "price_source": mctx.get("price_source"),
            "draws_with_prizes": mctx.get("draws_with_prizes"),
        },
        "distribution": {"observed": dist_obs.tolist(), "expected": (pmf * len(best_h)).round(1).tolist()},
        "least": least,
    }
