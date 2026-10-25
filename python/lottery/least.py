"""Наименее вероятные числа: какие числа, скорее всего, НЕ выпадут в следующем тираже.

Каждый метод прогноза ставит числам оценку: чем выше, тем вероятнее число по его логике.
Здесь берётся обратное — k чисел с самой низкой оценкой (k — столько, сколько выбирает
игрок). Так получается «анти-метод» для каждого метода, а «Консенсус наименее вероятных» —
числа с самым низким средним местом в рейтингах всех методов.

Проверка честная и та же, что у обычных методов, только в обратную сторону: на каждом тираже
анти-метод видит лишь предыдущие тиражи, и считается, сколько его чисел всё-таки выпало.
Метод работает, если на контрольном отрезке его числа выпадают РЕЖЕ, чем k случайных чисел
(одностороннее p «меньше случайного», поправка Холма на число методов). У честного розыгрыша
такого не бывает: все числа равновероятны, и «наименее вероятные» выпадают так же часто, как
любые другие.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as sps

from .drawfile import GameData
from .models import Model, top_k
from .stats import holm, ru

SEED = 51


def bottom_k(scores: np.ndarray, k: int, seed: int = 0) -> np.ndarray:
    """Индексы k чисел с самой низкой оценкой в каждой строке (ничьи — случайно)."""
    return top_k(-scores.astype(np.float64), k, seed=seed)


def _ranks(scores: np.ndarray) -> np.ndarray:
    """Место числа в строке: 0 — самая низкая оценка."""
    return np.argsort(np.argsort(scores, axis=1, kind="stable"), axis=1).astype(np.float32)


def lower_metrics(h: np.ndarray, mean0, var0) -> dict:
    """Как evaluate.metrics, но цель — угадать МЕНЬШЕ случайного: p_lower — шанс получить
    столько же или меньше совпадений случайно; deficit_pct — на сколько процентов реже."""
    from .evaluate import metrics
    m = metrics(h, mean0, var0)
    if not m.get("n"):
        return m
    m["p_lower"] = float(sps.norm.cdf(m["z"]))
    m["deficit_pct"] = -m["excess_pct"]
    return m


def evaluate(data: GameData, ev, models: list[Model], warm: int, split: int) -> dict:
    """Анти-методы на той же истории, что и обычные методы (ev — evaluate.Evaluator, оценки
    моделей уже посчитаны и лежат в его кэше)."""
    t_total = data.T
    specs = data.fmt.blocks
    voters = [m for m in models if not m.control]
    control = next((m for m in models if m.control), None)
    rows: list[tuple[str, str, bool, list[np.ndarray]]] = []
    rank_sum = [np.zeros((t_total + 1, s.size), np.float32) for s in specs]
    for m in voters:
        picks = []
        for b, (f, spec) in enumerate(zip(ev.features, specs)):
            sc = m.scores(f)
            picks.append(bottom_k(sc, spec.count, seed=SEED + b))
            rank_sum[b] += _ranks(sc)
        rows.append((f"least_{m.key}", m.title, False, picks))
    cons = [bottom_k(r, s.count, seed=SEED + 10 + b) for b, (r, s) in enumerate(zip(rank_sum, specs))]
    rows.append(("least_consensus", "Консенсус наименее вероятных", False, cons))
    if control is not None:
        rows.append(("random", control.title, True, ev.picks(control)))

    m0, v0 = ev.mean0, ev.var0
    out = []
    for key, title, is_control, picks in rows:
        h = ev.hits(picks)
        out.append({"key": key, "title": ru(title), "control": is_control,
                    "selection": lower_metrics(h[warm:split], m0[warm:split], v0[warm:split]),
                    "holdout": lower_metrics(h[split:], m0[split:], v0[split:]),
                    "next": ev.numbers(picks, t_total)})
    candidates = [r for r in out if not r["control"]]
    for r, a in zip(candidates, holm([r["holdout"]["p_lower"] for r in candidates])):
        r["holdout"]["p_adjusted"] = a
    best = min(candidates, key=lambda r: r["selection"]["mean_hits"])
    hold = best["holdout"]
    base = float(m0[split:].mean())
    significant = [r["title"] for r in candidates if r["holdout"]["p_adjusted"] < 0.05]
    if hold["p_lower"] < 0.05:
        conclusion = (f"Числа анти-метода «{best['title']}» (лучшего на отборе) на контрольном отрезке выпадают "
                      f"в среднем {hold['mean_hits']:.3f} раза против {base:.3f} у случайных чисел "
                      f"(реже на {hold['deficit_pct']:.1f}%, p={hold['p_lower']:.3f}).")
        if best["title"] not in significant:
            conclusion += " С поправкой на число проверенных методов это не значимо — может быть удачей."
    else:
        conclusion = (f"Лучший на отборе анти-метод — «{best['title']}»: на контрольном отрезке его числа выпадают "
                      f"{hold['mean_hits']:.3f} раза при {base:.3f} у случайных чисел — разница в пределах "
                      f"случайности (p={hold['p_lower']:.2f}). Предсказать, какие числа не выпадут, так же "
                      "нельзя, как и какие выпадут.")
    return {
        "status": "ok",
        "count": [s.count for s in specs],
        "baseline": {"mean": base},
        "methods": out,
        "best_key": best["key"],
        "significant_after_correction": significant,
        "conclusion": ru(conclusion),
        "next_prediction": {"model": best["title"], "numbers": best["next"]},
        "next_consensus": next(r["next"] for r in out if r["key"] == "least_consensus"),
    }
