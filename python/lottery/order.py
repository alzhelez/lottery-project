"""Порядок выпадения: в какой последовательности, скорее всего, выйдут предсказанные числа.

Архив хранит числа в порядке выпадения (лототрон и ГСЧ выдают их не по возрастанию). Для
выигрыша порядок не важен — важно, какие числа выпали, — но его можно предсказывать
отдельно и проверять: «на своём месте» — число прогноза совпало с числом тиража на той же
позиции.

Как ставится порядок. По истории (только тиражи того же способа розыгрыша, если в игре их
два) для каждого числа считается, на какой позиции оно выходило: счётчики C[число, позиция].
Для каждого тиража берётся правдоподобное распределение позиций из апостериорного
распределения Дирихле (сэмплирование Томпсона, как у частотных методов: где история не
различает позиции, порядок меняется от тиража к тиражу), и числа расставляются по позициям
так, чтобы суммарное правдоподобие было наибольшим (венгерский алгоритм).

Честная проверка: для последних тиражей порядок выпавших чисел предсказывается только по
предыдущим тиражам и сравнивается с настоящим; у честного розыгрыша доля «на месте» — 1/k.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as sps
from scipy.optimize import linear_sum_assignment

from .drawfile import GameData
from .models import tie_noise

BACKTEST = 2000


def ordered_blocks(data: GameData) -> dict[int, np.ndarray]:
    """{индекс блока: массив T×k чисел в порядке выпадения} — для блоков, где порядок хранится."""
    from .mechanics import _ordered_rows
    out = {}
    for i, spec in enumerate(data.fmt.blocks):
        arr = _ordered_rows(data, spec)
        if arr is not None:
            out[i] = arr
    return out


def _rows_for(data: GameData, mechanism: str | None) -> np.ndarray:
    """Индексы тиражей, по которым считается порядок: того же способа, если он известен и
    таких тиражей достаточно."""
    if mechanism in ("L", "R"):
        from .mechanics import classify
        kinds = np.array([k or "" for k in classify(data)])
        idx = np.nonzero(kinds == mechanism)[0]
        if len(idx) >= 200:
            return idx
    return np.arange(data.T)


def position_counts(arr: np.ndarray, lo: int, size: int) -> np.ndarray:
    """size×k: сколько раз число выходило на каждой позиции."""
    k = arr.shape[1]
    c = np.zeros((size, k), np.float64)
    for pos in range(k):
        np.add.at(c[:, pos], arr[:, pos] - lo, 1.0)
    return c


def _assign(numbers: list[int], logp: np.ndarray, lo: int) -> list[int]:
    """Расстановка чисел по позициям с наибольшим суммарным log-правдоподобием; числа
    возвращаются в порядке позиций."""
    m = logp[[n - lo for n in numbers]]                 # len(numbers) × k
    rows, cols = linear_sum_assignment(-m)
    return [numbers[r] for _, r in sorted(zip(cols, rows))]


def order_numbers(data: GameData, block: int, numbers: list[int], draw_no: int,
                  mechanism: str | None = None) -> list[int]:
    """Числа блока в предсказанном порядке выпадения (если порядок в архиве есть)."""
    blocks = ordered_blocks(data)
    if block not in blocks or not numbers:
        return list(numbers)
    spec = data.fmt.blocks[block]
    arr = blocks[block][_rows_for(data, mechanism)]
    k = arr.shape[1]
    if len(numbers) > k:
        return list(numbers)
    c = position_counts(arr, spec.lo, spec.size) + 1.0  # Дирихле(1) на позиции каждого числа
    # сэмплирование Дирихле через гамма-распределение, воспроизводимо по номеру тиража
    u = np.clip(tie_noise((spec.size, k), 7000 + block + 31 * (draw_no % 100_003)), 1e-12, 1 - 1e-12)
    g = sps.gamma.ppf(u, c)
    p = g / g.sum(axis=1, keepdims=True)
    return _assign([int(v) for v in numbers], np.log(np.maximum(p, 1e-12)), spec.lo)


def order_all(data: GameData, numbers: list[list[int]], draw_no: int, mechanism: str | None = None) -> list[list[int]]:
    return [order_numbers(data, i, b, draw_no, mechanism) for i, b in enumerate(numbers)]


def in_place(pred: list[int], actual: list[int]) -> int:
    return sum(1 for a, b in zip(pred, actual) if a == b)


def backtest(data: GameData, mechanism: str | None = None, last: int = BACKTEST) -> list[dict]:
    """Можно ли угадать порядок: для последних тиражей выпавшие числа расставляются по
    позициям только по предыдущим тиражам (средние вероятности, без сэмплирования) и
    сравниваются с настоящим порядком. Ожидание у честного розыгрыша — 1/k на позицию."""
    out = []
    rows = _rows_for(data, mechanism)
    for b, arr_all in ordered_blocks(data).items():
        spec = data.fmt.blocks[b]
        arr = arr_all[rows]
        t = len(arr)
        if t < 300:
            continue
        start = max(200, t - last)
        c = position_counts(arr[:start], spec.lo, spec.size)
        k = arr.shape[1]
        hits = 0
        n = 0
        for i in range(start, t):
            logp = np.log((c + 1.0) / (c.sum(axis=1, keepdims=True) + k))
            actual = [int(v) for v in arr[i]]
            pred = _assign(sorted(actual), logp, spec.lo)
            hits += in_place(pred, actual)
            n += k
            for pos, v in enumerate(actual):
                c[v - spec.lo, pos] += 1
        rate = hits / n if n else 0.0
        p = float(sps.binomtest(hits, n, 1.0 / k, alternative="greater").pvalue) if n else 1.0
        out.append({"block": spec.name, "draws": t - start, "positions": k, "in_place": hits, "total": n,
                    "rate": rate, "expected": 1.0 / k, "p_value": p,
                    "excess_pct": (rate * k - 1.0) * 100 if n else 0.0})
    return out


def expected_in_place(spec_size: int, count: int) -> float:
    """Сколько чисел прогноза в среднем окажутся «на своём месте» при случайном порядке и
    случайном наборе: на каждой из count позиций — шанс 1/size."""
    return count / spec_size if spec_size else 0.0

