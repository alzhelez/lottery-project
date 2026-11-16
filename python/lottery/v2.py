"""Методы версии 2: те же идеи, что у К, Б и Н, но с быстрой адаптацией к последним тиражам.

Зачем. Методы первой версии судят о моделях по всей истории: «Консенсус» даёт каждой модели один
голос, «Режим Бога» ставит на лидера за всю историю, «Наименее вероятные» берут анти-метод, лучший
на отрезке отбора. Если розыгрыш изменился (другой лототрон, другой генератор), вся история до
перелома только мешает. Версия 2 отвечает на это одним приёмом — весами моделей по их результату
на ПОСЛЕДНИХ тиражах:

  форма модели перед тиражом t = экспоненциально сглаженное «угадано − ожидалось» по тиражам до t
  (полураспад HALF_LIFE тиражей), в единицах стандартного отклонения — z. Тираж t в z не входит.

  К2 «Консенсус v2»            — голос модели весит exp(z): кто попадал в последнее время — весомее;
  Б2 «Режим Бога v2»           — прогноз модели с лучшей формой (лидер последних тиражей, а не всей истории);
  Н2 «Наименее вероятные v2»   — то же взвешенное голосование среди анти-методов (форма анти-метода
                                 тем выше, чем РЕЖЕ выпадали его числа).
  Ф2 «Финальное предсказание v2» — голосование К2 и Б2 со штрафом Н2 (trust.final_numbers).

Заглядывания нет нигде: прогноз на тираж t использует только тиражи до t — на любом отрезке, без
деления на «отбор» и «контроль». Поэтому у v2 честный прогноз есть на каждый тираж после разгона.

Важно: это не обещание лучшего результата. Если тиражи случайны, v2 даст те же ≈0 %, что и v1;
выигрывает она, только если в розыгрыше есть закономерность, которая меняется во времени. Сравнение
v1 и v2 на одних и тех же тиражах — v2compare.py.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

from .models import top_k

HALF_LIFE = 150          # тиражей: вклад результата модели в её «форму» падает вдвое
Z_CLIP = 4.0             # вес голоса — от e^-4 до e^4
SEED = 71
SOURCES = ("consensus_v2", "godmode_v2", "least_v2")
TITLES = {"consensus_v2": "взвешенное голосование по результату на последних тиражах",
          "godmode_v2": "лидер последних тиражей", "least_v2": "взвешенное голосование анти-методов"}


def form(h: np.ndarray, mean0: np.ndarray, var0: np.ndarray, lower: bool = False) -> np.ndarray:
    """Форма моделей перед каждым тиражом. h — (моделей, T) угадано по тиражам; mean0, var0 —
    ожидание и дисперсия случайного выбора по тиражам. Возвращает z размером (моделей, T + 1):
    столбец t посчитан только по тиражам до t, последний — для будущего тиража."""
    lam = 0.5 ** (1.0 / HALF_LIFE)
    e = (np.asarray(h, np.float64) - mean0) / np.sqrt(np.maximum(var0, 1e-9))
    if lower:
        e = -e
    s = lfilter([1.0], [1.0, -lam], e, axis=1)                    # s[t] = Σ λ^(t−u)·e[u], u ≤ t
    n = np.arange(1, e.shape[1] + 1)
    norm = np.sqrt((1.0 - lam ** (2 * n)) / (1.0 - lam * lam))    # sd суммы при случайном розыгрыше
    z = s / norm
    return np.concatenate([np.zeros((e.shape[0], 1)), z], axis=1)  # сдвиг: тираж t видит только прошлые


def weighted_picks(picks: list[list[np.ndarray]], z: np.ndarray, specs) -> list[np.ndarray]:
    """Голосование моделей с весом exp(z): picks — по моделям списки блоков (T + 1)×k."""
    w = np.exp(np.clip(z, -Z_CLIP, Z_CLIP)).astype(np.float32)     # (моделей, T + 1)
    out = []
    for b, spec in enumerate(specs):
        rows = picks[0][b].shape[0]
        votes = np.zeros((rows, spec.size), np.float32)
        r = np.arange(rows)[:, None]
        for m, p in enumerate(picks):
            np.add.at(votes, (np.broadcast_to(r, p[b].shape), p[b]), np.broadcast_to(w[m][:, None], p[b].shape))
        out.append(top_k(votes, spec.count, seed=SEED + b))
    return out


def leader_picks(picks: list[list[np.ndarray]], z: np.ndarray) -> tuple[list[np.ndarray], np.ndarray]:
    """Прогноз модели с лучшей формой на каждый тираж. Возвращает (прогнозы, номер модели по тиражам)."""
    idx = z.argmax(axis=0)
    out = [p.copy() for p in picks[0]]
    for k in np.unique(idx):
        rows = np.nonzero(idx == k)[0]
        for b, p in enumerate(picks[int(k)]):
            out[b][rows] = p[rows]
    return out, idx


def build(ev, voter_picks: list[list[np.ndarray]], voter_hits: list[np.ndarray], voter_titles: list[str],
          anti_picks: list[list[np.ndarray]] | None) -> dict:
    """Прогнозы v2 на все тиражи (и на будущий) из уже посчитанных прогнозов моделей.
    ev — evaluate.Evaluator. Возвращает {picks: {источник: блоки}, detail: {источник: текст}}."""
    specs = ev.data.fmt.blocks
    z = form(np.stack(voter_hits), ev.mean0, ev.var0)
    picks = {"consensus_v2": weighted_picks(voter_picks, z, specs)}
    leader, idx = leader_picks(voter_picks, z)
    picks["godmode_v2"] = leader
    top = int(idx[-1])
    detail = {"consensus_v2": TITLES["consensus_v2"],
              "godmode_v2": f"{voter_titles[top]} — форма {z[top, -1]:+.1f}σ за последние тиражи"}
    if anti_picks:
        za = form(np.stack([ev.hits(p) for p in anti_picks]), ev.mean0, ev.var0, lower=True)
        picks["least_v2"] = weighted_picks(anti_picks, za, specs)
        detail["least_v2"] = TITLES["least_v2"]
    return {"picks": picks, "detail": detail}
