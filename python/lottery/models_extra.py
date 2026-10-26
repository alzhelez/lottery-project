"""Дополнительные семейства методов (42.2.0): структура тиража, позиции выпадения, обучаемые
модели (нейросеть, бустинг, случайный лес) и ансамбль лидеров.

Как и у остальных методов, строка t оценок использует только тиражи < t: признаки берутся из
Features (они уже сдвинуты на один тираж), обучаемые модели переобучаются только на прошлом,
а их прогноз на отрезок до следующего переобучения считается одной пачкой — так бустинг и лес
укладываются в секунды даже на 60 тыс. тиражей.
"""
from __future__ import annotations

import numpy as np

from .models import Features, Model, _seed, tie_noise

# ── Структура тиража ───────────────────────────────────────────────────────


def _groups(n: int) -> np.ndarray:
    """N×G: десятки (1–10, 11–20, …), чётность, нижняя/верхняя половина диапазона."""
    idx = np.arange(n)
    decades = [(idx // 10 == d) for d in range(int(np.ceil(n / 10)))]
    parity = [(idx % 2 == 0), (idx % 2 == 1)]
    halves = [(idx < n / 2), (idx >= n / 2)]
    return np.stack(decades + parity + halves, axis=1).astype(np.float32)


def structure_scores(f: Features, w: int = 100) -> np.ndarray:
    """«Форма» последних w тиражей: в каких десятках, какой чётности и в какой половине
    диапазона выпадало больше чисел, чем положено по их доле. Оценка числа — сумма
    логарифмов этих перекосов по его группам (сглаживание +1)."""
    def calc():
        g = _groups(f.N)
        counts = f.window(w) @ g                                  # (T+1)×G
        drawn = f.window(w).sum(axis=1, keepdims=True)
        expected = drawn * g.sum(axis=0, keepdims=True) / f.N
        ratio = np.log((counts + 1.0) / (expected + 1.0))
        return (ratio @ g.T).astype(np.float32)
    return f.memo(("structure", w), calc)


def center_scores(f: Features, w: int = 50) -> np.ndarray:
    """Центр тяжести: среднее выпавшее число за последние w тиражей — ближе к нему лучше
    (тираж «держит» сумму)."""
    def calc():
        win = f.window(w)
        idx = np.arange(f.N, dtype=np.float32)
        total = np.maximum(win.sum(axis=1, keepdims=True), 1.0)
        center = (win * idx).sum(axis=1, keepdims=True) / total
        return (-np.abs(idx[None, :] - center)).astype(np.float32)
    return f.memo(("center", w), calc)


# ── Позиции выпадения ──────────────────────────────────────────────────────


def position_scores(f: Features, w: int = 300) -> np.ndarray:
    """Если архив хранит порядок выпадения (f.ordered — T×k индексов чисел): частота числа на
    каждой позиции за последние w тиражей против равномерной; оценка — самый сильный перекос
    по позициям (число «любит» какую-то позицию). Без порядка — частота за w тиражей."""
    ordered = getattr(f, "ordered", None)
    if ordered is None:
        return f.window_rate(w)

    def calc():
        t_len, k = ordered.shape
        best = np.full((f.T + 1, f.N), -np.inf, np.float32)
        for p in range(k):
            one = np.zeros((t_len, f.N), np.float32)
            one[np.arange(t_len), ordered[:, p]] = 1.0
            cum = np.vstack([np.zeros((1, f.N), np.float32), np.cumsum(one, axis=0, dtype=np.float32)])
            lag = np.vstack([np.zeros((min(w, t_len + 1), f.N), np.float32), cum[: max(t_len + 1 - w, 0)]])
            cnt = cum - lag
            n_rows = np.minimum(np.arange(t_len + 1), w)[:, None].astype(np.float32)
            exp = n_rows / f.N
            z = (cnt - exp) / np.sqrt(np.maximum(exp * (1 - 1 / f.N), 1e-6))
            best = np.maximum(best, z)
        return best
    return f.memo(("positions", w), calc)


# ── Обучаемые модели ───────────────────────────────────────────────────────


def online_mlp(f: Features, hidden: int = 8, lr: float = 0.03, warmup: int = 30, seed: int = 7) -> np.ndarray:
    """Маленькая нейросеть (признаки → 8 нейронов tanh → вероятность), обучаемая онлайн: после
    каждого тиража — шаг градиента по его 0/1-исходам. Прогноз на тираж t — по весам до t."""
    def calc():
        _, feats = f.feature_stack(sampled=True)
        n_feat = feats.shape[2]
        rng = np.random.default_rng(seed)
        w1 = rng.normal(0, 0.3, (n_feat, hidden))
        b1 = np.zeros(hidden)
        w2 = rng.normal(0, 0.3, hidden)
        b2 = float(np.log(f.p / (1 - f.p))) if 0 < f.p < 1 else 0.0
        s = np.zeros((f.T + 1, f.N), np.float32)
        for t in range(f.T + 1):
            xt = feats[t].astype(np.float64)
            h = np.tanh(xt @ w1 + b1)
            z = h @ w2 + b2
            prob = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
            s[t] = prob
            if t < f.T and t >= warmup:
                g = (prob - f.x[t]) / f.N                         # dL/dz
                gw2 = h.T @ g
                gh = np.outer(g, w2) * (1 - h * h)
                w1 -= lr * (xt.T @ gh + 1e-4 * w1)
                b1 -= lr * gh.sum(axis=0)
                w2 -= lr * (gw2 + 1e-4 * w2)
                b2 -= lr * float(g.sum())
        return s
    return f.memo(("mlp", hidden, lr), calc)


def _batched_classifier(f: Features, make, key: str, max_rows: int = 120_000, fits: int = 12,
                        min_every: int = 1000) -> np.ndarray:
    """Классификатор «выпадет ли число», переобучаемый fits раз за историю (не чаще раза в
    min_every тиражей) только на прошлых тиражах; прогноз на отрезок до следующего
    переобучения — одной пачкой."""
    def calc():
        _, feats = f.feature_stack(sampled=True)
        n_feat = feats.shape[2]
        s = np.full((f.T + 1, f.N), f.p, np.float32)
        start = min(max(300, f.T // 10), f.T)
        every = max(min_every, (f.T + 1 - start) // fits + 1)
        rng = np.random.default_rng(_seed(key))
        for t0 in range(start, f.T + 1, every):
            t1 = min(t0 + every, f.T + 1)
            rows = np.arange(50, t0)
            if len(rows) * f.N > max_rows:
                rows = np.sort(rng.choice(rows, size=max(1, max_rows // f.N), replace=False))
            y = f.x[rows].reshape(-1)
            if y.min() == y.max():
                continue
            model = make()
            model.fit(feats[rows].reshape(-1, n_feat), y)
            s[t0:t1] = model.predict_proba(feats[t0:t1].reshape(-1, n_feat))[:, 1].reshape(t1 - t0, f.N)
        # ничьи на разогреве разбиваются случайно
        return s + tie_noise(s.shape, _seed(key + "_tie")).astype(np.float32) * 1e-6
    return f.memo(("clf", key), calc)


def gbm_batch(f: Features) -> np.ndarray:
    from sklearn.ensemble import HistGradientBoostingClassifier
    return _batched_classifier(f, lambda: HistGradientBoostingClassifier(
        max_iter=80, learning_rate=0.06, max_leaf_nodes=15, l2_regularization=1.0, random_state=0), "gbm_batch")


def forest_batch(f: Features) -> np.ndarray:
    from sklearn.ensemble import ExtraTreesClassifier
    return _batched_classifier(f, lambda: ExtraTreesClassifier(
        n_estimators=40, max_depth=8, min_samples_leaf=40, random_state=0, n_jobs=1), "forest_batch",
        max_rows=80_000, fits=8)


# ── Эксперимент (зафиксирован 26.10.2026) ──────────────────────────────────

ECHO_DISTANCE = 3


def echo_scores(f: Features, d: int = ECHO_DISTANCE) -> np.ndarray:
    """«Эхо ±3»: числа, отстоящие ровно на 3 от чисел прошлого тиража (n−3 и n+3).

    Гипотеза выбрана перебором 25 закономерностей на реальных архивах 13 игр (17 полей,
    26.10.2026): отбор — первые 70% тиражей каждой игры, проверка — последние 30%. У «эха ±3»
    самый сильный общий сигнал на отборе среди гипотез, которые сохранили знак на проверке:
    z = +1,62 на отборе и +0,90 на проверке (сумма по полям). Параметры заморожены: дальше
    метод только записывает прогнозы в журнал и проверяется на новых тиражах."""
    def calc():
        last = f.last()
        s = np.zeros_like(last)
        if d < f.N:
            s[:, d:] += last[:, :-d]
            s[:, :-d] += last[:, d:]
        return s
    return f.memo(("echo", d), calc)


def experiment_model() -> Model:
    return Model("experiment_echo3", "Эксперимент: эхо ±3 от прошлого тиража", "experiment", echo_scores,
                 params={"distance": ECHO_DISTANCE})


def extra_models() -> list[Model]:
    """Новые методы для сравнения на странице игры (и в режиме Бога)."""
    return [
        Model("structure_100", "Структура тиража: десятки, чётность, половины (окно 100)", "structure",
              lambda f: structure_scores(f, 100), params={"window": 100}),
        Model("structure_500", "Структура тиража (окно 500)", "structure",
              lambda f: structure_scores(f, 500), params={"window": 500}),
        Model("center_50", "Центр тяжести тиража (окно 50)", "structure", lambda f: center_scores(f, 50),
              params={"window": 50}),
        Model("positions_300", "Позиции выпадения: любимая позиция числа (окно 300)", "position",
              lambda f: position_scores(f, 300), params={"window": 300}),
        Model("mlp", "Нейросеть, обучение онлайн", "ml", lambda f: online_mlp(f)),
        Model("gbm", "Градиентный бустинг (переобучение по истории)", "ml", gbm_batch),
        Model("forest", "Случайный лес (переобучение по истории)", "ml", forest_batch),
        experiment_model(),
    ]


# ── Ансамбль лидеров ───────────────────────────────────────────────────────


def leaders_ensemble(picks: list[list[np.ndarray]], hits_rows: np.ndarray, sizes: list[int], counts: list[int],
                     top: int = 3) -> list[np.ndarray]:
    """Голосование трёх лидеров: на каждый тираж t берутся три метода, угадавшие больше всех
    на тиражах < t, и числа с наибольшим числом их голосов (ничьи — в пользу первого лидера).
    picks[m][b] — (T+1)×k прогнозы метода m по блоку b; hits_rows — M×T угаданных."""
    m_count, t_len = hits_rows.shape
    cum = np.hstack([np.zeros((m_count, 1)), np.cumsum(hits_rows, axis=1)])   # M×(T+1): до тиража t
    noise = tie_noise((t_len + 1, m_count), 77) * 1e-6
    order = np.argsort(-(cum.T + noise), axis=1)[:, :top]                       # (T+1)×top
    out = []
    for b, (n, k) in enumerate(zip(sizes, counts)):
        res = np.zeros((t_len + 1, k), np.int64)
        for t in range(t_len + 1):
            votes = np.zeros(n)
            for rank, m in enumerate(order[t]):
                votes[picks[m][b][t]] += 1.0 + (top - rank) * 1e-3
            res[t] = np.argsort(-votes, kind="stable")[:k]
        out.append(res)
    return out
