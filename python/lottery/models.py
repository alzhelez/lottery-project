"""Модели прогноза.

Каждая модель по матрице индикаторов X (T×N) строит матрицу оценок S ((T+1)×N):
строка S[t] вычисляется ТОЛЬКО по тиражам 0..t−1 и оценивает, какие числа выпадут
в тираже t. Строка S[T] — прогноз на следующий (ещё не сыгранный) тираж.
Прогноз — k чисел с наибольшей оценкой.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy.signal import lfilter


class Features:
    """Кэш общих вычислений по одной матрице X — модели и признаки переиспользуют их."""

    def __init__(self, x: np.ndarray, k: int):
        self.x = x.astype(np.float32, copy=False)
        self.T, self.N = x.shape
        self.k = k
        # доля чисел, входящих в блок в среднем по тиражу (для бинго размер меняется)
        total = float(self.x.sum())
        self.p = total / (self.T * self.N) if total > 0 else k / self.N
        self.kbar = self.p * self.N
        self._cache: dict = {}
        self.cum = np.vstack([np.zeros((1, self.N), np.float32), np.cumsum(self.x, axis=0, dtype=np.float32)])
        self.t_index = np.arange(self.T + 1, dtype=np.float32)[:, None]

    def memo(self, key, fn: Callable[[], np.ndarray]) -> np.ndarray:
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def window(self, w: int | None) -> np.ndarray:
        """Сколько раз число выпало за последние w тиражей (None — за всю историю)."""
        def calc():
            if w is None:
                return self.cum
            lagged = np.vstack([np.zeros((w, self.N), np.float32), self.cum[:-w]]) if w <= self.T else np.zeros_like(self.cum)
            return self.cum - lagged
        return self.memo(("win", w), calc)

    def window_rate(self, w: int | None) -> np.ndarray:
        """Частота относительно ожидаемой: 0 — как при честной лотерее, +1 — вдвое чаще."""
        def calc():
            n_eff = self.t_index if w is None else np.minimum(self.t_index, w)
            return np.where(n_eff > 0, self.window(w) / np.maximum(n_eff, 1) / self.p - 1.0, 0.0).astype(np.float32)
        return self.memo(("rate", w), calc)

    def ewma(self, half_life: float) -> np.ndarray:
        def calc():
            lam = 0.5 ** (1.0 / half_life)
            y = lfilter([1.0], [1.0, -lam], self.x, axis=0).astype(np.float32)
            s = np.vstack([np.zeros((1, self.N), np.float32), y])
            norm = lfilter([1.0], [1.0, -lam], np.ones(self.T)).astype(np.float32)
            norm = np.concatenate([[1.0], norm])[:, None]
            return (s / norm / self.p - 1.0).astype(np.float32)
        return self.memo(("ewma", half_life), calc)

    def gap(self) -> np.ndarray:
        """Сколько тиражей число не выпадало к моменту t."""
        def calc():
            idx = np.where(self.x > 0, np.arange(self.T)[:, None], -1)
            last = np.maximum.accumulate(idx, axis=0)
            last = np.vstack([np.full((1, self.N), -1), last])
            return (self.t_index - 1 - last).astype(np.float32)
        return self.memo("gap", calc)

    def last(self) -> np.ndarray:
        return self.memo("last", lambda: np.vstack([np.zeros((1, self.N), np.float32), self.x]))

    def markov(self, decay: float = 1.0, prior: float = 1.0) -> np.ndarray:
        """Переходы «число i в тираже t−1 → число j в тираже t».

        Оценка j = средняя по числам прошлого тиража вероятность перехода, делённая на k/N
        (1 — нет связи). Счётчики могут «забывать» прошлое с коэффициентом decay.
        """
        def calc():
            n = self.N
            c = np.zeros((n, n), np.float64)
            occ = np.zeros(n, np.float64)
            s = np.zeros((self.T + 1, n), np.float32)
            x = self.x.astype(np.float64)
            for t in range(1, self.T + 1):
                if t >= 2:
                    prev, cur = x[t - 2], x[t - 1]
                    if decay < 1.0:
                        c *= decay
                        occ *= decay
                    c += np.outer(prev, cur)
                    occ += prev
                probs = (c + prior * self.p) / (occ[:, None] + prior)
                last = x[t - 1]
                s[t] = (last @ probs) / max(last.sum(), 1.0) / self.p
            return s
        return self.memo(("markov", decay, prior), calc)

    def pairs(self, prior: float = 1.0) -> np.ndarray:
        """Насколько часто число выпадало ВМЕСТЕ с числами прошлого тиража (в одном тираже)."""
        def calc():
            n = self.N
            a = np.zeros((n, n), np.float64)
            occ = np.zeros(n, np.float64)
            s = np.zeros((self.T + 1, n), np.float32)
            x = self.x.astype(np.float64)
            p_pair = max(self.kbar - 1, 0.0) / max(n - 1, 1)
            for t in range(1, self.T + 1):
                cur = x[t - 1]
                # связи берутся по тиражам 0..t−2, затем в счётчики добавляется тираж t−1
                if t >= 2:
                    probs = (a + prior * p_pair) / (occ[:, None] + prior)
                    np.fill_diagonal(probs, 0.0)
                    s[t] = (cur @ probs) / max(cur.sum(), 1.0) / max(p_pair, 1e-9)
                a += np.outer(cur, cur)
                occ += cur
            return s
        return self.memo(("pairs", prior), calc)

    def zscore(self, s: np.ndarray) -> np.ndarray:
        mu = s.mean(axis=1, keepdims=True)
        sd = s.std(axis=1, keepdims=True)
        return np.where(sd > 0, (s - mu) / np.where(sd > 0, sd, 1), 0.0).astype(np.float32)

    def feature_stack(self) -> tuple[list[str], np.ndarray]:
        """Признаки для обучаемых моделей: (T+1)×N×F."""
        def calc():
            names = ["rate10", "rate50", "rate200", "rate_all", "ewma20", "gap", "last", "markov", "pairs"]
            gap = np.log1p(self.gap() * self.p)
            feats = [self.window_rate(10), self.window_rate(50), self.window_rate(200), self.window_rate(None),
                     self.ewma(20), gap, self.last(), self.markov() - 1.0, self.pairs() - 1.0]
            return names, np.stack(feats, axis=2).astype(np.float32)
        return self.memo("stack", calc)


@dataclass
class Model:
    key: str
    title: str
    family: str
    fn: Callable[[Features], np.ndarray]
    control: bool = False
    params: dict = field(default_factory=dict)

    def scores(self, f: Features) -> np.ndarray:
        return f.memo(("model", self.key), lambda: self.fn(f))


def online_logreg(f: Features, lr: float = 0.05, l2: float = 1e-4, warmup: int = 30) -> np.ndarray:
    """Онлайн-логистическая регрессия: после каждого тиража веса обновляются градиентным шагом.

    Вероятность выпадения числа зависит от признаков (частоты в окнах, давность, связи
    с прошлым тиражом). Прогноз на тираж t использует веса, обученные на тиражах < t.
    """
    _, feats = f.feature_stack()
    n_feat = feats.shape[2]
    w = np.zeros(n_feat)
    b = float(np.log(f.p / (1 - f.p))) if f.p < 1 else 0.0
    s = np.zeros((f.T + 1, f.N), np.float32)
    for t in range(f.T + 1):
        z = feats[t] @ w + b
        prob = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        s[t] = prob
        if t < f.T and t >= warmup:
            y = f.x[t]
            g = prob - y
            w -= lr * (feats[t].T @ g / f.N + l2 * w)
            b -= lr * float(g.mean())
    return s


def gbm_scores(f: Features, retrain_every: int = 500, max_rows: int = 150_000, seed: int = 0,
               deadline: float | None = None) -> np.ndarray:
    """Градиентный бустинг, переобучаемый каждые retrain_every тиражей (только на прошлом)."""
    import time
    from sklearn.ensemble import HistGradientBoostingClassifier

    _, feats = f.feature_stack()
    rng = np.random.default_rng(seed)
    s = np.zeros((f.T + 1, f.N), np.float32)
    s[:] = f.p
    start = max(200, retrain_every)
    model = None
    for t in range(start, f.T + 1):
        if model is None or (t - start) % retrain_every == 0:
            if deadline is not None and time.time() > deadline:
                raise TimeoutError
            rows = np.arange(50, t)
            if len(rows) * f.N > max_rows:
                rows = np.sort(rng.choice(rows, size=max_rows // f.N, replace=False))
            xf = feats[rows].reshape(-1, feats.shape[2])
            yv = f.x[rows].reshape(-1)
            model = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.05, max_leaf_nodes=15,
                                                   l2_regularization=1.0, random_state=seed)
            model.fit(xf, yv)
        s[t] = model.predict_proba(feats[t])[:, 1]
    return s


def tie_noise(shape: tuple[int, int], seed: int) -> np.ndarray:
    """Псевдослучайные числа [0, 1), зависящие только от (строка, столбец, seed).

    В отличие от генератора, значение для тиража t не меняется при добавлении новых
    тиражей — прогнозы воспроизводимы и не зависят от длины истории."""
    rows = np.arange(shape[0], dtype=np.uint64)[:, None]
    cols = np.arange(shape[1], dtype=np.uint64)[None, :]
    with np.errstate(over="ignore"):
        h = rows * np.uint64(0x9E3779B97F4A7C15) ^ cols * np.uint64(0xC2B2AE3D27D4EB4F) ^ np.uint64((seed * 0x165667B19E3779F9 + 1) & 0xFFFFFFFFFFFFFFFF)
        h ^= h >> np.uint64(29)
        h *= np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(32)
    return (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)


def _rand(seed: int) -> Callable[[Features], np.ndarray]:
    return lambda f: tie_noise((f.T + 1, f.N), seed).astype(np.float32)


def standard_models() -> list[Model]:
    """Набор методов для сравнения на странице игры."""
    m: list[Model] = [Model("random", "Случайный выбор (контроль)", "control", _rand(7), control=True)]
    m.append(Model("hot_all", "Горячие за всю историю", "hot", lambda f: f.window(None)))
    for w in (10, 25, 50, 100, 200, 500):
        m.append(Model(f"hot_{w}", f"Горячие, окно {w}", "hot", (lambda w: lambda f: f.window(w))(w), params={"window": w}))
    m.append(Model("cold_all", "Холодные за всю историю", "cold", lambda f: -f.window(None)))
    for w in (25, 100):
        m.append(Model(f"cold_{w}", f"Холодные, окно {w}", "cold", (lambda w: lambda f: -f.window(w))(w), params={"window": w}))
    for h in (10, 50, 200):
        m.append(Model(f"ewma_{h}", f"Экспоненциальная частота, полураспад {h}", "ewma",
                       (lambda h: lambda f: f.ewma(h))(h), params={"half_life": h}))
    m.append(Model("overdue", "Давно не выпадавшие", "gap", lambda f: f.gap()))
    m.append(Model("repeat", "Недавно выпадавшие", "gap", lambda f: -f.gap()))
    m.append(Model("markov", "Марковская цепь переходов", "markov", lambda f: f.markov()))
    m.append(Model("pairs", "Пары с числами прошлого тиража", "pairs", lambda f: f.pairs()))
    for a in (0.5, 1.0):
        m.append(Model(f"mix_{a}", f"Частота-100 + давность (α={a})", "mix",
                       (lambda a: lambda f: f.zscore(f.window(100)) + a * f.zscore(f.gap()))(a), params={"alpha": a}))
    m.append(Model("logreg", "Онлайн-логистическая регрессия", "ml", lambda f: online_logreg(f)))
    return m


def expert_grid(level: int) -> list[Model]:
    """Расширенный пул экспертов для «режима Бога». level 1 — базовый, 2 — расширенный."""
    out: list[Model] = []
    for seed in (101, 102, 103):
        out.append(Model(f"random_{seed}", f"Случайный выбор #{seed - 100}", "control", _rand(seed), control=True))
    windows = (5, 10, 20, 50, 100, 200, 500, None) if level == 1 else (3, 7, 15, 30, 40, 75, 150, 300, 750, 1000)
    for w in windows:
        tag = "all" if w is None else w
        out.append(Model(f"hot_{tag}", f"Горячие, окно {tag}", "hot", (lambda w: lambda f: f.window(w))(w)))
        out.append(Model(f"cold_{tag}", f"Холодные, окно {tag}", "cold", (lambda w: lambda f: -f.window(w))(w)))
    halves = (5, 20, 80, 300) if level == 1 else (2, 3, 8, 13, 34, 55, 144, 600)
    for h in halves:
        out.append(Model(f"ewma_{h}", f"Экспоненциальная частота, полураспад {h}", "ewma", (lambda h: lambda f: f.ewma(h))(h)))
        out.append(Model(f"ewmacold_{h}", f"Экспоненциально холодные, полураспад {h}", "ewma", (lambda h: lambda f: -f.ewma(h))(h)))
    if level == 1:
        out += [
            Model("overdue", "Давно не выпадавшие", "gap", lambda f: f.gap()),
            Model("repeat", "Недавно выпадавшие", "gap", lambda f: -f.gap()),
            Model("markov", "Марковская цепь", "markov", lambda f: f.markov()),
            Model("antimarkov", "Анти-марковская цепь", "markov", lambda f: -f.markov()),
            Model("pairs", "Пары с прошлым тиражом", "pairs", lambda f: f.pairs()),
            Model("logreg", "Онлайн-логрегрессия", "ml", lambda f: online_logreg(f)),
        ]
    else:
        for d in (0.999, 0.995, 0.98):
            out.append(Model(f"markov_d{d}", f"Марковская цепь, забывание {d}", "markov",
                             (lambda d: lambda f: f.markov(decay=d))(d)))
        for w in (20, 50, 200):
            for a in (-1.0, -0.5, 0.5, 1.0, 2.0):
                out.append(Model(f"mix_{w}_{a}", f"Частота-{w} + давность (α={a})", "mix",
                                 (lambda w, a: lambda f: f.zscore(f.window(w)) + a * f.zscore(f.gap()))(w, a)))
        for lr in (0.01, 0.2):
            out.append(Model(f"logreg_{lr}", f"Онлайн-логрегрессия (шаг {lr})", "ml",
                             (lambda lr: lambda f: online_logreg(f, lr=lr))(lr)))
    return out


def random_mixture(f_names: list[str], rng: np.random.Generator, idx: int) -> Model:
    """Случайная линейная комбинация признаков — для случайного поиска в «режиме Бога»."""
    weights = rng.normal(size=len(f_names))
    weights /= np.abs(weights).sum()

    def fn(f: Features) -> np.ndarray:
        _, feats = f.feature_stack()
        return np.tensordot(feats, weights, axes=([2], [0])).astype(np.float32)

    desc = ", ".join(f"{n}:{w:+.2f}" for n, w in zip(f_names, weights))
    return Model(f"rmix_{idx}", f"Смесь признаков #{idx}", "search", fn, params={"weights": desc})


# ── Прогноз из оценок ──────────────────────────────────────────────────────

def top_k(scores: np.ndarray, k: int, seed: int = 0) -> np.ndarray:
    """Индексы k лучших чисел в каждой строке. Ничьи разбиваются случайно (с фиксированным seed),
    чтобы не было систематического сдвига к маленьким числам."""
    scale = max(1.0, float(np.abs(scores).max())) * 1e-7
    noisy = scores.astype(np.float64) + tie_noise(scores.shape, seed) * scale
    idx = np.argpartition(-noisy, k - 1, axis=1)[:, :k]
    order = np.take_along_axis(-noisy, idx, axis=1).argsort(axis=1)
    return np.take_along_axis(idx, order, axis=1)


def hits(x: np.ndarray, picks: np.ndarray) -> np.ndarray:
    """Число угаданных чисел в каждом тираже. picks: (T+1)×k, последняя строка — будущий тираж."""
    t = x.shape[0]
    return np.take_along_axis(x, picks[:t].astype(np.int64), axis=1).sum(axis=1)


def votes_to_picks(vote_matrix: np.ndarray, k: int, seed: int = 1) -> np.ndarray:
    return top_k(vote_matrix, k, seed)


def consensus_votes(picks_list: list[np.ndarray], n: int) -> np.ndarray:
    """Сколько моделей выбрали каждое число — «наиболее часто повторяющиеся предсказания»."""
    rows = picks_list[0].shape[0]
    votes = np.zeros((rows, n), np.float32)
    r = np.arange(rows)[:, None]
    for p in picks_list:
        np.add.at(votes, (np.broadcast_to(r, p.shape), p), 1.0)
    return votes
