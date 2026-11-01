"""Специализированные методы для отдельных игр (по итогам анализа данных ветки).

ВАЖНО: в честной лотерее эти методы не повышают шансы — все комбинации равновероятны. Они
проверяются как все методы приложения: каждый тираж прогнозируется только по предыдущим,
в прогноз метод попадает, только если на истории лучше остальных.

Исправлено (01.11.2026):
  * модуль не импортировался — класса lottery.method в приложении нет, поэтому методы нигде
    не вызывались. Теперь это обычные модели (lottery.models.Model), подключённые к сравнению
    методов (evaluate_game) и к режиму Бога;
  * «мега-горячие» (5 из 36 плюс) и «кластеры» (Рапидо 2.0): горячим числам и «горячей зоне»
    доставался МЕНЬШИЙ вес, чем остальным (0,7/7 = 0,1 против 0,3 и 0,8/10 против 0,2) — метод
    выбирал противоположное задуманному;
  * «детектор аномалий» считал ожидание как «6 чисел» для любой игры — у 4 из 20 почти все числа
    выходили «аномальными»;
  * «горячие/холодные 60/40» брали только горячие: веса 0,06 у горячих против 0,04 у холодных,
    а прогноз — k чисел с наибольшим весом;
  * на бонусном поле «1 из 4» (5 из 36 плюс, Рапидо) методы падали (деление на ноль, пустое окно).
"""
from __future__ import annotations

import numpy as np

from .models import Features, Model

MIN_FIELD = 10   # методы рассчитаны на основное поле; на бонусном «1 из 4» — случайный выбор


def _top_mask(m: np.ndarray, n: int) -> np.ndarray:
    n = max(0, min(n, m.shape[1]))
    out = np.zeros(m.shape, dtype=bool)
    if n:
        np.put_along_axis(out, np.argsort(-m, axis=1, kind="stable")[:, :n], True, axis=1)
    return out


# ── 6 из 45 ───────────────────────────────────────────────────────────────

def hot_cold(f: Features) -> np.ndarray:
    """60% чисел прогноза — самые частые за всю историю, 40% — самые редкие."""
    n_hot = int(round(0.6 * f.k))
    hot = _top_mask(f.cum, n_hot)
    cold = _top_mask(-f.cum, f.k - n_hot) & ~hot
    return np.where(hot, 2.0, np.where(cold, 1.0, 0.0)).astype(np.float32)


def avoid_recent(f: Features) -> np.ndarray:
    """Исключить числа трёх последних тиражей (среди остальных — случайно)."""
    return np.where(f.window(3) > 0, 0.0, 1.0).astype(np.float32)


# ── 5 из 36 плюс ──────────────────────────────────────────────────────────

def mega_hot(f: Features) -> np.ndarray:
    """20% самых частых чисел за всю историю получают 70% веса."""
    n_hot = max(f.k, f.N // 5)
    hot = _top_mask(f.cum, n_hot)
    return np.where(hot, 0.7 / n_hot, 0.3 / max(1, f.N - n_hot)).astype(np.float32)


# ── Рапидо 2.0 ────────────────────────────────────────────────────────────

def high_repeat(f: Features) -> np.ndarray:
    """50% — числа прошлого тиража, 50% — числа с частотой выше медианы."""
    med = np.median(f.cum, axis=1, keepdims=True)
    return (0.5 * f.last() + 0.5 * (f.cum > med)).astype(np.float32)


def cluster(f: Features, window: int = 10) -> np.ndarray:
    """Зона из window соседних чисел с наибольшей частотой получает 80% веса."""
    window = min(window, f.N - 1)
    c = np.cumsum(np.hstack([np.zeros((f.T + 1, 1)), f.cum]), axis=1)
    start = np.argmax(c[:, window:] - c[:, :-window], axis=1)[:, None]
    idx = np.arange(f.N)[None, :]
    inside = (idx >= start) & (idx < start + window)
    return np.where(inside, 0.8 / window, 0.2 / max(1, f.N - window)).astype(np.float32)


# ── Кено 2.0, «Всё или ничего», Топ-3, 4 из 20 ────────────────────────────

def super_hot(f: Features) -> np.ndarray:
    """40% — 20 самых частых, 30% — остальные, затем 70/30 с числами прошлого тиража."""
    hot = _top_mask(f.cum, 20)
    p = np.where(hot, 0.4 / 20, 0.3 / max(1, f.N - 20))
    return (0.7 * p + 0.3 * f.last()).astype(np.float32)


def massive_repeat(f: Features) -> np.ndarray:
    """70% — числа прошлого тиража, 30% — 12 самых частых."""
    return (0.7 * f.last() + 0.3 * _top_mask(f.cum, 12)).astype(np.float32)


def position_freq(f: Features) -> np.ndarray:
    """Каждая позиция отдельно (поле — позиция): самая частая цифра."""
    return f.cum.astype(np.float32)


def two_fields(f: Features) -> np.ndarray:
    """Каждое поле отдельно: 10 самых частых чисел получают 70% веса."""
    hot = _top_mask(f.cum, 10)
    return np.where(hot, 0.7 / 10, 0.3 / max(1, f.N - 10)).astype(np.float32)


# ── Для всех игр ──────────────────────────────────────────────────────────

def anomaly(f: Features) -> np.ndarray:
    """Числа, частота которых отклоняется от ожидаемой больше чем на 2σ (по реальному числу
    выпадающих чисел игры); нет таких — случайный выбор."""
    t = np.arange(f.T + 1, dtype=np.float64)[:, None]
    p = f.kbar / f.N
    expected = t * p
    std = np.sqrt(np.maximum(expected * (1 - p), 1e-9))
    z = np.abs((f.cum - expected) / std)
    return np.where(z > 2.0, z, 0.0).astype(np.float32)


def conservative(f: Features) -> np.ndarray:
    """80% равномерно + 20% по частоте за всю историю (без сэмплирования)."""
    total = np.maximum(f.cum.sum(axis=1, keepdims=True), 1.0)
    return (0.8 / f.N + 0.2 * f.cum / total).astype(np.float32)


GAME = {
    "6x45": [("fb_hot_cold", "Горячие/холодные 60/40", hot_cold),
             ("fb_avoid_recent", "Исключить недавние", avoid_recent)],
    "5x36plus": [("fb_mega_hot", "Мега-горячие (20% чисел — 70% веса)", mega_hot)],
    "rapido2": [("fb_high_repeat", "Повторы + горячие", high_repeat),
                ("fb_cluster", "Кластер: самая частая зона из 10 чисел", cluster)],
    "keno2": [("fb_super_hot", "Супер-горячие + повторы", super_hot)],
    "vin": [("fb_massive_repeat", "Массивные повторы", massive_repeat)],
    "top-3": [("fb_position", "Позиционные частоты", position_freq)],
    "4x20": [("fb_two_fields", "Два поля раздельно", two_fields)],
}
UNIVERSAL = [("fb_anomaly", "Детектор аномалий", anomaly),
             ("fb_conservative", "Новая игра (консервативно)", conservative)]


def _main_field(fn, small_ok: bool):
    def wrapped(f: Features) -> np.ndarray:
        if f.N < MIN_FIELD and not small_ok:
            return np.zeros((f.T + 1, f.N), np.float32)
        return fn(f)
    return wrapped


def game_models(slug: str | None) -> list[Model]:
    """Методы игры slug и универсальные — кандидаты в сравнении методов и в режиме Бога."""
    out = [Model(k, t, "game", _main_field(fn, slug == "top-3")) for k, t, fn in GAME.get(slug or "", [])]
    out += [Model(k, t, "game", fn) for k, t, fn in UNIVERSAL]
    return out


def all_game_models() -> list[Model]:
    """Все методы всех игр (для восстановления лидера режима Бога по ключу)."""
    seen, out = set(), []
    for slug in list(GAME) + [None]:
        for m in game_models(slug):
            if m.key not in seen:
                seen.add(m.key)
                out.append(m)
    return out
