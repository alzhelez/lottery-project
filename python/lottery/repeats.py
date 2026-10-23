"""Гипотезы о повторах по позициям выпадения (эксперимент).

Архив хранит числа в порядке выпадения: позиция 1 — первый шар, позиция 2 — второй и т. д.
Проверяются гипотезы:

  H1  через L тиражей на той же позиции выходит то же число:
      шар №j тиража t = шар №j тиража t+L;
  H2a через L тиражей то же число выходит на позиции, сдвинутой на s:
      шар №j тиража t = шар №(j+s) тиража t+L;
  H2b через L тиражей на той же позиции выходит число, сдвинутое на d:
      шар №j тиража t + d = шар №j тиража t+L;
  H2c сдвигаются и позиция, и число: шар №j тиража t + d = шар №(j+s) тиража t+L.

L — от 1 до всей длины архива, s и d — все возможные сдвиги; для каждой игры (и для лототрона
и ГСЧ отдельно) ищутся свои L и сдвиг. У честного розыгрыша на каждой позиции любое число
выходит с вероятностью 1/N, поэтому ожидаемое число совпадений известно точно.

Совпадения для всех L и сдвигов сразу считаются через двумерное быстрое преобразование
Фурье (автокорреляция индикаторов «число × тираж» по каждой позиции и «позиция × тираж» по
каждому числу). Значимость — точный хвост распределения Пуассона, поправка Бонферрони на
число всех проверенных пар (L, сдвиг) — их миллионы, без поправки «находка» гарантирована.
Найденное засчитывается, только если повторяется в каждой половине истории.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import fft as sfft
from scipy import stats as sps

from .drawfile import GameData

ALPHA = 0.05
CHUNK = 4000          # строк L за раз при расчёте p-value (ограничение памяти)
COMBINED_BYTES = 600e6  # память под спектры H2c; не хватает — берутся последние тиражи


def _autocorr(z: np.ndarray, nt: int, nv: int) -> np.ndarray:
    f = sfft.rfft2(z, s=(nt, nv))
    return (f.real ** 2 + f.imag ** 2)


def counts(arr: np.ndarray, lo: int, size: int) -> tuple[np.ndarray, np.ndarray]:
    """C_num[L, d + N − 1] и C_pos[L, s + k − 1] для L = 0…T−1 (строка 0 не используется)."""
    t, k = arr.shape
    n = size
    vals = arr - lo
    nt = sfft.next_fast_len(2 * t)
    nv = sfft.next_fast_len(2 * n)
    power = None
    for j in range(k):
        z = np.zeros((t, n), np.float64)
        z[np.arange(t), vals[:, j]] = 1.0
        p = _autocorr(z, nt, nv)
        power = p if power is None else power + p
    c = sfft.irfft2(power, s=(nt, nv))
    shifts_d = np.arange(-(n - 1), n)
    c_num = np.rint(c[:t, shifts_d % nv]).astype(np.int64)
    del c, power
    nk = sfft.next_fast_len(2 * k)
    power = None
    for v in range(n):
        w = np.zeros((t, k), np.float64)
        tt, jj = np.nonzero(vals == v)
        w[tt, jj] = 1.0
        if not w.any():
            continue
        p = _autocorr(w, nt, nk)
        power = p if power is None else power + p
    shifts_s = np.arange(-(k - 1), k)
    if power is None:
        c_pos = np.zeros((t, len(shifts_s)), np.int64)
    else:
        c = sfft.irfft2(power, s=(nt, nk))
        c_pos = np.rint(c[:t, shifts_s % nk]).astype(np.int64)
    return c_num, c_pos


def expected(arr: np.ndarray, lo: int, size: int) -> tuple[np.ndarray, np.ndarray]:
    """Ожидаемое число совпадений у честного розыгрыша (та же форма, что у counts)."""
    t, k = arr.shape
    n = size
    vals = arr - lo
    shifts_d = np.arange(-(n - 1), n)
    # m[t, d] — сколько чисел тиража t после сдвига на d остаются в поле
    shifted = vals[:, :, None] + shifts_d[None, None, :]
    m = ((shifted >= 0) & (shifted < n)).sum(axis=1)             # T × (2N−1)
    cum = np.vstack([np.zeros((1, m.shape[1]), np.int64), np.cumsum(m, axis=0)])
    lags = np.arange(t)
    e_num = cum[t - lags] / n                                     # пары (t, t+L): t < T−L
    shifts_s = np.arange(-(k - 1), k)
    valid_j = np.array([sum(1 for j in range(k) if 0 <= j + s < k) for s in shifts_s])
    e_pos = (t - lags)[:, None] * valid_j[None, :] / n
    return e_num, e_pos


def _best(c: np.ndarray, e: np.ndarray, mask_cols: np.ndarray) -> tuple[float, int, int]:
    """Наименьший хвост Пуассона P(X ≥ C) по ячейкам L ≥ 1 и разрешённым сдвигам."""
    best = (1.0, 0, 0)
    t = c.shape[0]
    for a in range(1, t, CHUNK):
        cc = c[a:a + CHUNK][:, mask_cols]
        ee = e[a:a + CHUNK][:, mask_cols]
        sel = cc > ee
        if not sel.any():
            continue
        p = np.ones(cc.shape)
        p[sel] = sps.poisson.sf(cc[sel] - 1, ee[sel])
        i = np.unravel_index(int(np.argmin(p)), p.shape)
        if p[i] < best[0]:
            best = (float(p[i]), a + int(i[0]), int(np.flatnonzero(mask_cols)[i[1]]))
    return best


def count_one(arr: np.ndarray, lag: int, s: int, d: int, lo: int, size: int) -> tuple[int, float]:
    """Совпадения и их ожидание для одной пары (L, сдвиг) — для проверки по половинам."""
    t, k = arr.shape
    if lag < 1 or lag >= t:
        return 0, 0.0
    a, b = arr[: t - lag], arr[lag:]
    obs, pairs = 0, 0
    for j in range(k):
        j2 = j + s
        if not 0 <= j2 < k:
            continue
        shifted = a[:, j] + d
        ok = (shifted >= lo) & (shifted < lo + size)
        obs += int(np.sum(b[:, j2][ok] == shifted[ok]))
        pairs += int(ok.sum())
    return obs, pairs / size


def combined_best(arr: np.ndarray, lo: int, size: int) -> dict | None:
    """H2c: сдвиг и позиции (s ≠ 0), и числа (d ≠ 0) — все L, s, d. Спектры позиций хранятся
    одновременно, поэтому при нехватке памяти берутся последние тиражи (draws_used)."""
    t, k = arr.shape
    n = size
    if k < 2 or n < 2:
        return None
    nv = sfft.next_fast_len(2 * n)
    per_row = (nv // 2 + 1) * 8 * k
    t_use = int(min(t, max(200, COMBINED_BYTES / per_row / 2)))
    a = arr[-t_use:] - lo
    nt = sfft.next_fast_len(2 * t_use)
    spectra = []
    for j in range(k):
        z = np.zeros((t_use, n), np.float32)
        z[np.arange(t_use), a[:, j]] = 1.0
        spectra.append(sfft.rfft2(z, s=(nt, nv)).astype(np.complex64))
    shifts_d = np.arange(-(n - 1), n)
    lags = np.arange(t_use)
    best = (1.0, 0, 0, 0, 0, 0.0)
    for s in range(-(k - 1), k):
        if s == 0:
            continue
        js = [j for j in range(k) if 0 <= j + s < k]
        acc = np.zeros_like(spectra[0])
        for j in js:
            acc += np.conj(spectra[j]) * spectra[j + s]
        c = np.rint(sfft.irfft2(acc, s=(nt, nv))[:t_use, shifts_d % nv]).astype(np.int64)
        # ожидание у честного розыгрыша: пары × доля чисел, которые после сдвига остаются в поле
        e = ((t_use - lags)[:, None] * len(js) * (n - np.abs(shifts_d))[None, :] / (n * n))
        p, lag, ci = _best(c, e, shifts_d != 0)
        if p < best[0]:
            best = (p, lag, s, int(shifts_d[ci]), int(c[lag, ci]), float(e[lag, ci]))
    return {"draws_used": t_use, "tests": int((t_use - 1) * (2 * k - 2) * (2 * n - 2)),
            "p": best[0], "lag": best[1], "s": best[2], "d": best[3], "observed": best[4], "expected": best[5]}


def analyze_block(arr: np.ndarray, lo: int, size: int, name: str) -> dict:
    t, k = arr.shape
    n = size
    c_num, c_pos = counts(arr, lo, size)
    e_num, e_pos = expected(arr, lo, size)
    shifts_d = np.arange(-(n - 1), n)
    shifts_s = np.arange(-(k - 1), k)
    comb = combined_best(arr, lo, size)
    tests = (t - 1) * (len(shifts_d) + len(shifts_s) - 1) + (comb["tests"] if comb else 0)
    out = {"block": name, "draws": t, "positions": k, "numbers": n, "tests": int(tests), "hypotheses": [],
           "combined_draws": comb["draws_used"] if comb else None}

    def finding(key: str, title: str, p: float, lag: int, s: int, d: int, obs: int, exp: float) -> dict:
        adj = min(1.0, p * tests)
        h = t // 2
        halves = []
        for part in (arr[:h], arr[h:]):
            o, e = count_one(part, lag, s, d, lo, n)
            halves.append({"observed": o, "expected": e,
                           "p_value": float(sps.poisson.sf(o - 1, e)) if e > 0 and o > e else 1.0})
        replicated = adj < ALPHA and all(x["p_value"] < ALPHA for x in halves)
        return {"key": key, "title": title, "lag": int(lag), "shift_pos": int(s), "shift_num": int(d),
                "observed": int(obs), "expected": float(exp), "ratio": float(obs / exp) if exp else None,
                "p_value": p, "p_adjusted": adj, "halves": halves, "replicated": bool(replicated),
                "significant": bool(replicated)}

    # H1 — тот же номер на той же позиции (d = 0, s = 0)
    col0 = np.zeros(len(shifts_d), bool)
    col0[n - 1] = True
    p, lag, ci = _best(c_num, e_num, col0)
    out["hypotheses"].append(finding("same", "То же число на той же позиции", p, lag, 0, 0,
                                     c_num[lag, ci] if lag else 0, e_num[lag, ci] if lag else 0.0))
    # H2a — сдвиг позиции (s ≠ 0, d = 0)
    cols = shifts_s != 0
    if cols.any():
        p, lag, ci = _best(c_pos, e_pos, cols)
        out["hypotheses"].append(finding("pos_shift", "То же число со сдвигом позиции", p, lag, int(shifts_s[ci]), 0,
                                         c_pos[lag, ci] if lag else 0, e_pos[lag, ci] if lag else 0.0))
    # H2b — сдвиг числа (s = 0, d ≠ 0)
    cols = shifts_d != 0
    p, lag, ci = _best(c_num, e_num, cols)
    out["hypotheses"].append(finding("num_shift", "Сдвинутое число на той же позиции", p, lag, 0, int(shifts_d[ci]),
                                     c_num[lag, ci] if lag else 0, e_num[lag, ci] if lag else 0.0))
    # H2c — сдвигаются и позиция, и число
    if comb:
        out["hypotheses"].append(finding("both_shift", "Сдвинутое число на сдвинутой позиции", comb["p"], comb["lag"],
                                         comb["s"], comb["d"], comb["observed"], comb["expected"]))
    # что исключено: на ближайших задержках (L = 1) перекос какой силы был бы замечен
    e1 = float(e_num[1, n - 1]) if t > 1 else 0.0
    if e1 > 0:
        z = sps.norm.isf(ALPHA / tests) + sps.norm.isf(0.2)
        out["detectable_ratio"] = float(1 + z / math.sqrt(e1))
    out["found"] = [h for h in out["hypotheses"] if h["significant"]]
    return out


def predict(arr: np.ndarray, lo: int, hi: int, finding: dict) -> list[int | None]:
    """Прогноз по найденному повтору: на позицию j — число с позиции j−s тиража T−L плюс d."""
    t, k = arr.shape
    lag, s, d = finding["lag"], finding["shift_pos"], finding["shift_num"]
    out: list[int | None] = []
    for j in range(k):
        src = j - s
        if t - lag < 0 or not 0 <= src < k:
            out.append(None)
            continue
        v = int(arr[t - lag, src]) + d
        out.append(v if lo <= v <= hi else None)
    return out


def analyze(data: GameData) -> dict:
    """Все упорядоченные поля игры, отдельно по способам розыгрыша (если их два)."""
    from .mechanics import classify
    from .order import ordered_blocks
    blocks = ordered_blocks(data)
    if not blocks:
        return {"available": False, "reason": "архив не хранит порядок выпадения (или поле позиционное)"}
    kinds = np.array([m or "" for m in classify(data)])
    groups = {m: np.nonzero(kinds == m)[0] for m in ("L", "R") if (kinds == m).sum() >= 300}
    if len(groups) < 2:
        groups = {"all": np.arange(data.T)}
    out = {"available": True, "groups": {}}
    for m, idx in groups.items():
        res = []
        for b, arr in blocks.items():
            spec = data.fmt.blocks[b]
            part = arr[idx]
            r = analyze_block(part, spec.lo, spec.size, spec.name)
            for f in r["found"]:
                f["next"] = predict(part, spec.lo, spec.hi, f)
            res.append(r)
        out["groups"][m] = res
    found = [(m, r["block"], f) for m, rs in out["groups"].items() for r in rs for f in r["found"]]
    out["verdict"] = ("Найдены повторяющиеся закономерности: " + "; ".join(
        f"{m}, {blk}: {f['title'].lower()} через {f['lag']} тир." for m, blk, f in found)
        if found else "Повторов по позициям сверх случайных не найдено ни для одной задержки и сдвига.")
    return out
