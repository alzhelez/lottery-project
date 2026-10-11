"""Статистические тесты случайности тиражей.

Нулевая гипотеза H0: в каждом тираже k чисел выбираются из N равновероятно, без
возвращения, независимо от прошлых тиражей. Если H0 верна, никакой метод не может
предсказывать лучше случайного выбора. Тесты ищут отклонения, которые теоретически
можно использовать для прогноза.
"""
from __future__ import annotations

import math
import re

import numpy as np
from scipy import stats as sps

from .drawfile import BlockSpec, GameData

MIN_DRAWS = 50          # меньше — статистика бессмысленна

_DECIMAL = re.compile(r"(?<=\d)\.(?=\d)")


def ru(text: str) -> str:
    """Десятичная запятая в текстах для пользователя (не применять к датам!)."""
    return _DECIMAL.sub(",", text)
ALPHA = 0.05


def hypergeom_moments(n_total: int, k: int, k_pick: int | None = None) -> tuple[float, float]:
    """Среднее и дисперсия числа совпадений между k_pick случайными числами и k выпавшими из N.

    Работает и поэлементно для массивов k (бинго: размер множества меняется от тиража к тиражу)."""
    kp = k if k_pick is None else k_pick
    k = np.asarray(k, dtype=np.float64)
    mean = kp * k / n_total
    if n_total <= 1:
        return mean, np.zeros_like(mean)
    var = kp * (k / n_total) * ((n_total - k) / n_total) * ((n_total - kp) / (n_total - 1))
    if mean.ndim == 0:
        return float(mean), float(var)
    return mean, var


def _test(name: str, title: str, p: float, stat: float, detail: str, exploitable: bool) -> dict:
    return {
        "test": name,
        "title": title,
        "p_value": float(min(max(p, 0.0), 1.0)),
        "statistic": float(stat),
        "detail": ru(detail),
        "exploitable": exploitable,
    }


def freq_uniformity(x: np.ndarray) -> dict:
    """χ² равномерности частот с поправкой на выбор без возвращения.

    Счётчики чисел внутри одного тиража отрицательно коррелированы, поэтому статистика
    нормируется на точную дисперсию счётчика Σ p_t(1−p_t) и умножается на (N−1)/N —
    тогда её распределение χ²(N−1). p_t = k_t/N, k_t — сколько чисел в тираже t
    (для обычных игр k_t постоянно, для бинго меняется).
    """
    t, n = x.shape
    k_t = x.sum(axis=1).astype(np.float64)
    p_t = k_t / n
    counts = x.sum(axis=0).astype(np.float64)
    expected = float(k_t.sum() / n)
    var = float((p_t * (1 - p_t)).sum())
    chi = float(((counts - expected) ** 2).sum() / var) * (n - 1) / n if var > 0 else 0.0
    p = float(sps.chi2.sf(chi, n - 1))
    dev = int(np.argmax(np.abs(counts - expected)))
    return _test(
        "freq", "Равномерность частот", p, chi,
        f"χ²={chi:.1f}, df={n - 1}; ожидается {expected:.1f} выпадений на число, "
        f"макс. отклонение {counts[dev] - expected:+.0f}",
        exploitable=False,
    )


def serial_overlap(x: np.ndarray, lag: int = 1) -> dict:
    """Совпадения между тиражами t и t−lag против гипергеометрического ожидания.

    При H0 совпадения пар независимы (условно на размеры тиражей), поэтому
    z = (Σ наблюдено − Σ ожидаемо) / √Σ дисперсий точен в пределе ЦПТ.
    """
    t, n = x.shape
    overlaps = (x[lag:] * x[:-lag]).sum(axis=1)
    k_t = x.sum(axis=1)
    mean, var = hypergeom_moments(n, k_t[lag:], k_t[:-lag])
    mean, var = np.broadcast_to(mean, overlaps.shape), np.broadcast_to(var, overlaps.shape)
    total_var = float(var.sum())
    z = float((overlaps.sum() - mean.sum()) / math.sqrt(total_var)) if total_var > 0 else 0.0
    p = float(2 * sps.norm.sf(abs(z)))
    return _test(
        f"overlap{lag}", f"Повторы чисел через {lag} тираж" + ("" if lag == 1 else "а"),
        p, z,
        f"в среднем {overlaps.mean():.3f} совпадений при ожидаемых {mean.mean():.3f} (z={z:+.2f})",
        exploitable=True,
    )


def persistence(x: np.ndarray, rng: np.random.Generator, n_perm: int = 2000) -> dict:
    """«Горячие остаются горячими»: корреляция частот чисел в первой и второй половине истории.

    Это прямая проверка идеи частотных методов. Перестановочный тест (числа
    взаимозаменяемы при H0), поэтому p-value корректно и для малых N.
    """
    t, n = x.shape
    a = x[: t // 2].sum(axis=0)
    b = x[t // 2:].sum(axis=0)
    if a.std() == 0 or b.std() == 0:
        return _test("persist", "Устойчивость горячих/холодных чисел", 1.0, 0.0,
                     "частоты не различаются", exploitable=True)
    r = float(np.corrcoef(a, b)[0, 1])
    perms = np.array([np.corrcoef(a, rng.permutation(b))[0, 1] for _ in range(n_perm)])
    p = (1 + np.sum(np.abs(perms) >= abs(r) - 1e-12)) / (n_perm + 1)
    return _test(
        "persist", "Устойчивость горячих/холодных чисел", p, r,
        f"корреляция частот 1-й и 2-й половины истории r={r:+.3f}",
        exploitable=True,
    )


def sum_autocorr(x: np.ndarray, lo: int) -> dict:
    """Корреляция среднего выпавших чисел в соседних тиражах (для бинго — среднего,
    чтобы разная длина тиражей не создавала ложной связи)."""
    values = np.arange(x.shape[1]) + lo
    k_t = x.sum(axis=1)
    means = (x @ values) / np.maximum(k_t, 1)
    if means.std() == 0 or len(means) < 10:
        return _test("sumac", "Автокорреляция сумм", 1.0, 0.0, "недостаточно вариации", True)
    r, p = sps.pearsonr(means[1:], means[:-1])
    return _test("sumac", "Автокорреляция сумм тиражей", float(p), float(r),
                 f"r={r:+.3f} между средними значениями чисел соседних тиражей", exploitable=True)


def _pair_stat(x: np.ndarray, expected: float) -> float:
    m = x.T @ x
    iu = np.triu_indices(x.shape[1], 1)
    pc = m[iu]
    return float(((pc - expected) ** 2 / expected).sum())


def _simulate(k_t: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """Честная лотерея с теми же размерами тиражей: k_t случайных чисел из N в тираже t."""
    ranks = np.argsort(np.argsort(rng.random((len(k_t), n), dtype=np.float32), axis=1), axis=1)
    return (ranks < k_t[:, None]).astype(np.float32)


def pair_uniformity(x: np.ndarray, rng: np.random.Generator) -> dict:
    """Равномерность совместных выпадений пар. Распределение статистики — Монте-Карло под H0."""
    t, n = x.shape
    k_t = x.sum(axis=1).astype(np.int64)
    expected = float((k_t * (k_t - 1)).sum() / (n * (n - 1)))
    if expected <= 0:
        return _test("pairs", "Равномерность пар чисел", 1.0, 0.0, "пар нет", True)
    obs = _pair_stat(x, expected)
    sims = 99 if t * n > 400_000 else 199
    ge = sum(_pair_stat(_simulate(k_t, n, rng), expected) >= obs for _ in range(sims))
    p = (1 + ge) / (sims + 1)
    return _test("pairs", "Равномерность пар чисел", p, obs,
                 f"{n * (n - 1) // 2} пар, ожидается {expected:.1f} совместных выпадений на пару "
                 f"(Монте-Карло, {sims} симуляций)", exploitable=True)


def holm(pvalues: list[float]) -> list[float]:
    """Поправка Холма — контроль вероятности хотя бы одной ложной тревоги."""
    m = len(pvalues)
    order = np.argsort(pvalues)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adj[i] = running
    return adj.tolist()


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """Поправка Бенджамини–Хохберга (контроль доли ложных открытий) для многих игр."""
    m = len(pvalues)
    if m == 0:
        return []
    order = np.argsort(pvalues)
    adj = np.empty(m)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, pvalues[i] * m / (rank + 1))
        adj[i] = min(running, 1.0)
    return adj.tolist()


def block_tests(x: np.ndarray, spec: BlockSpec, rng: np.random.Generator) -> list[dict]:
    tests = [freq_uniformity(x), serial_overlap(x, 1), serial_overlap(x, 2),
             persistence(x, rng), sum_autocorr(x, spec.lo)]
    if x.sum(axis=1).mean() >= 2:
        tests.append(pair_uniformity(x, rng))
    for t in tests:
        t["block"] = spec.name
    return tests


def game_randomness(data: GameData, seed: int = 12345) -> dict:
    """Все тесты по игре + поправка Холма внутри игры."""
    rng = np.random.default_rng(seed)
    base = {
        "slug": data.game.slug,
        "title": data.game.title,
        "draws": data.T,
        "format": data.fmt.describe(),
        "supported": data.fmt.supported,
    }
    if not data.fmt.supported:
        return {**base, "status": "unsupported", "verdict": f"Формат не поддерживается: {data.fmt.reason}",
                "tests": [], "p_game": None}
    if data.T < MIN_DRAWS:
        return {**base, "status": "insufficient",
                "verdict": f"Мало данных: {data.T} тиражей (нужно не меньше {MIN_DRAWS})",
                "tests": [], "p_game": None}
    tests = []
    for x, spec in zip(data.matrices, data.fmt.blocks):
        tests.extend(block_tests(x, spec, rng))
    adj = holm([t["p_value"] for t in tests])
    for t, a in zip(tests, adj):
        t["p_adjusted"] = a
        t["significant"] = a < ALPHA
    return {**base, "status": "ok", "tests": tests, "p_game": float(min(adj))}


def finalize_scan(games: list[dict]) -> list[dict]:
    """Поправка BH по играм и итоговый вердикт."""
    ok = [g for g in games if g.get("status") == "ok"]
    q = benjamini_hochberg([g["p_game"] for g in ok])
    for g, qv in zip(ok, q):
        g["q_value"] = qv
        sig = [t for t in g["tests"] if t["significant"]]
        if qv < ALPHA and sig:
            useful = [t for t in sig if t["exploitable"]]
            names = ", ".join(sorted({t["title"].lower() for t in sig}))
            if useful:
                g["verdict"] = f"Найдены отклонения от случайности ({names}). Проверьте методы на странице игры."
                g["level"] = "signal"
            else:
                g["verdict"] = (f"Частоты неравномерны ({names}), но без устойчивости во времени — "
                                "для прогноза это не используется.")
                g["level"] = "weak"
        else:
            g["verdict"] = "Отклонений от случайности не найдено: тиражи ведут себя как честная лотерея."
            g["level"] = "random"
    for g in games:
        g.setdefault("level", "na")
    return games


def descriptive(data: GameData) -> list[dict]:
    """Частоты, давность и горячие/холодные числа по блокам (только описание, не прогноз)."""
    out = []
    t_total = data.T
    for x, spec in zip(data.matrices, data.fmt.blocks):
        counts = x.sum(axis=0)
        expected = float(x.sum() / spec.size)
        expected_recent = float(x[-100:].sum() / spec.size)
        last_seen = np.full(spec.size, -1)
        nz = np.nonzero(x)
        for t, j in zip(*nz):
            last_seen[j] = t
        gaps = np.where(last_seen >= 0, t_total - 1 - last_seen, t_total)
        recent = x[-100:].sum(axis=0)
        nums = list(range(spec.lo, spec.hi + 1))
        out.append({
            "block": spec.name,
            "count": spec.count,
            "lo": spec.lo,
            "hi": spec.hi,
            "expected": expected,
            "expected_recent": expected_recent,
            "numbers": nums,
            "frequency": counts.astype(int).tolist(),
            "recent100": recent.astype(int).tolist(),
            "gap": gaps.astype(int).tolist(),
        })
    return out
