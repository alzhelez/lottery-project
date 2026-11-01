"""Методы под конкретные игры — идеи из ветки improvements/ai-analysis-fixes (Fable), переписанные
так, чтобы они реально работали в приложении.

В той ветке модуль не импортировался (класса lottery.method нет), поэтому приложение их не
вызывало, а в двух методах веса были перепутаны: «мега-горячим» 5 из 36 и «горячей зоне» Рапидо
доставался меньший вес, чем остальным числам. Здесь:
  * каждый метод — обычная модель (как в models.py): строка t оценок использует только тиражи
    < t, поэтому их честно проверяет и сравнение методов, и режим Бога;
  * веса исправлены по замыслу из описаний;
  * «детектор аномалий» считает ожидание по реальному числу выпадающих чисел игры (в ветке было
    жёстко «6 чисел» для любой игры);
  * «консервативный» метод (80% равномерно + 20% частоты) выбирает числа строго по частоте за
    всю историю, без сэмплирования Томпсона, которым «горячие» приложения разбавляют случайные
    перекосы. Он оставлен как отдельный кандидат: на «Охоте» (поле 2) частоты последних тиражей
    действительно неравны, и на контрольном отрезке он угадывал на 1,7% больше случайного.

Попадают ли они в прогноз, решает отбор на истории, как для всех методов.
"""
from __future__ import annotations

import numpy as np

from .models import Features, Model


def _top_mask(m: np.ndarray, n: int) -> np.ndarray:
    n = max(0, min(n, m.shape[1]))
    out = np.zeros(m.shape, dtype=bool)
    if n:
        idx = np.argsort(-m, axis=1, kind="stable")[:, :n]
        np.put_along_axis(out, idx, True, axis=1)
    return out


def hot_cold_mix(f: Features, hot_share: float = 0.6) -> np.ndarray:
    """6 из 45: ~60% чисел прогноза — самые частые за всю историю, остальные — самые редкие."""
    def calc():
        k = f.k
        n_hot = int(round(hot_share * k))
        hot = _top_mask(f.cum, n_hot)
        cold = _top_mask(-f.cum, k - n_hot) & ~hot
        return np.where(hot, 2.0, np.where(cold, 1.0, 0.0)).astype(np.float32)
    return f.memo(("gs_hotcold", hot_share), calc)


def avoid_recent(f: Features, window: int = 3) -> np.ndarray:
    """Числа, которых не было в последних window тиражах (среди них — ничьи, выбор случайный)."""
    return f.memo(("gs_avoid", window), lambda: np.where(f.window(window) > 0, 0.0, 1.0).astype(np.float32))


def hot_group(f: Features, share: float = 0.2) -> np.ndarray:
    """Доля share самых частых чисел за всю историю — одной группой (внутри — случайно)."""
    return f.memo(("gs_hotgroup", share), lambda: _top_mask(f.cum, max(f.k, int(f.N * share))).astype(np.float32))


def repeat_plus_hot(f: Features, w_last: float = 0.5) -> np.ndarray:
    """Числа прошлого тиража + числа с частотой выше медианы."""
    def calc():
        med = np.median(f.cum, axis=1, keepdims=True)
        return (w_last * f.last() + (1 - w_last) * (f.cum > med)).astype(np.float32)
    return f.memo(("gs_repeathot", w_last), calc)


def hot_zone(f: Features, window: int = 10) -> np.ndarray:
    """Отрезок из window соседних чисел с наибольшей частотой за всю историю; внутри — по частоте."""
    def calc():
        c = np.cumsum(np.hstack([np.zeros((f.T + 1, 1)), f.cum]), axis=1)
        sums = c[:, window:] - c[:, :-window]
        start = np.argmax(sums, axis=1)[:, None]
        idx = np.arange(f.N)[None, :]
        inside = (idx >= start) & (idx < start + window)
        rate = f.cum / np.maximum(f.cum.max(axis=1, keepdims=True), 1)
        return (inside * 2.0 + rate).astype(np.float32)
    return f.memo(("gs_zone", window), calc)


def hot_in_last(f: Features, hot_n: int = 20) -> np.ndarray:
    """Кено: числа прошлого тиража, сначала — входящие в hot_n самых частых."""
    def calc():
        hot = _top_mask(f.cum, hot_n)
        return (0.7 * np.where(hot, 0.4 / hot_n, 0.3 / f.N) + 0.3 * f.last()).astype(np.float32)
    return f.memo(("gs_hotlast", hot_n), calc)


def frequency_fixed(f: Features) -> np.ndarray:
    """Частота за всю историю без сэмплирования (метод «новая игра (консервативно)» ветки Fable):
    0,8 · равномерно + 0,2 · доля выпадений — порядок чисел тот же, что у чистой частоты."""
    def calc():
        total = np.maximum(f.cum.sum(axis=1, keepdims=True), 1.0)
        return (0.8 / f.N + 0.2 * f.cum / total).astype(np.float32)
    return f.memo("gs_freqfixed", calc)


def anomaly(f: Features, z_limit: float = 2.0) -> np.ndarray:
    """Числа, частота которых отклоняется от ожидаемой больше чем на z_limit сигм (в любую
    сторону); если таких нет — ничьи (случайный выбор)."""
    def calc():
        t = np.arange(f.T + 1, dtype=np.float64)[:, None]
        p = f.kbar / f.N
        expected = t * p
        std = np.sqrt(np.maximum(expected * (1 - p), 1e-9))
        z = np.abs((f.cum - expected) / std)
        return np.where(z > z_limit, z, 0.0).astype(np.float32)
    return f.memo(("gs_anomaly", z_limit), calc)


GAME_METHODS: dict[str, list[tuple[str, str, callable]]] = {
    "6x45": [("gs_hot_cold", "6 из 45: горячие и холодные 60/40", hot_cold_mix),
             ("gs_avoid_recent", "6 из 45: без чисел трёх последних тиражей", avoid_recent)],
    "5x36plus": [("gs_hot_group", "5 из 36 плюс: группа самых частых (20%)", hot_group)],
    "rapido2": [("gs_repeat_hot", "Рапидо 2.0: прошлый тираж + частые", repeat_plus_hot),
                ("gs_hot_zone", "Рапидо 2.0: самая частая зона из 10 чисел", hot_zone)],
    "keno2": [("gs_hot_in_last", "Кено: частые среди чисел прошлого тиража", hot_in_last)],
    "vin": [("gs_repeat_hot_vin", "Всё или ничего: прошлый тираж + частые", lambda f: repeat_plus_hot(f, 0.7))],
    "4x20": [("gs_hot_group_4x20", "4 из 20: группа 10 самых частых в каждом поле", lambda f: hot_group(f, 0.5))],
}


MIN_FIELD = 10   # методы рассчитаны на основное поле; бонусное поле «1 из 4» — случайный выбор


def _main_field(fn):
    def wrapped(f: Features) -> np.ndarray:
        if f.N < MIN_FIELD:
            return np.zeros((f.T + 1, f.N), np.float32)
        return fn(f)
    return wrapped


def game_models(slug: str | None) -> list[Model]:
    """Методы для игры slug (если есть) и универсальный детектор аномалий."""
    out = [Model(k, t, "game", _main_field(fn)) for k, t, fn in GAME_METHODS.get(slug or "", [])]
    out.append(Model("gs_anomaly", "Детектор аномальных частот (|z| > 2)", "game", anomaly))
    out.append(Model("gs_freq_fixed", "Частота за всю историю без сэмплирования", "game", frequency_fixed))
    return out
