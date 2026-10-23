"""«Порядок из хаоса»: прогноз не по частоте чисел, а по динамике тиражей.

Детерминированный хаос выглядит случайным, но следующее состояние системы определяется
текущим. Тогда по последовательности наблюдений можно восстановить фазовое пространство
(теорема Такенса), и похожие состояния в прошлом подсказывают, что будет дальше (метод
аналогов Лоренца, симплекс-прогноз Сугихары–Мэя). Порядок проявляется и в форме ряда —
какие «узоры» подъёмов и спадов встречаются чаще (порядковые паттерны Бандта–Помпе) и как
часто траектория возвращается к уже пройденным состояниям (рекуррентный анализ).

Хаос у каждого способа розыгрыша свой: лототрон — физическая система (шары, воздух,
камера), ГСЧ — алгоритм. Поэтому всё считается отдельно на тиражах лототрона и на тиражах
ГСЧ: у каждого способа своя история, свои аналоги и свой прогноз. Прогноз на следующий тираж
берётся из того набора, к которому относится этот тираж.

Честная лотерея устроена так, чтобы порядка не было: лототрон перемешивает шары заново,
ГСЧ не зависит от прошлого. Поэтому каждая находка проверяется:
  * проверки «есть ли порядок» сравнивают ряд с его же перемешанными копиями (у
    перемешанного ряда динамики нет по построению) или с нулевой корреляцией;
  * методы проверяются как остальные: каждый тираж прогнозируется только по предыдущим,
    лучший выбирается на отрезке отбора и проверяется на контрольном.

Состояние тиража — 5 чисел: среднее выпавшее число, размах, доля нечётных, доля чисел из
нижней половины поля, сколько чисел повторилось из прошлого тиража.
"""
from __future__ import annotations

import math
from datetime import datetime

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy import stats as sps

from .drawfile import GameData
from .models import Features, Model, _rand
from .stats import holm, ru

MIN_DRAWS = 300        # меньше — анализ способа не проводится
MAX_DRAWS = 20_000     # методы проверяются на последних тиражах способа (быстрые игры — до 190 тысяч)
LIB = 4000             # аналоги ищутся среди последних LIB состояний
CHUNK = 256
FEATURES = ("среднее число", "размах", "доля нечётных", "доля малых", "повторы с прошлым тиражом")
MECH_TITLES = {"L": "лототрон", "R": "ГСЧ", "all": "все тиражи"}


# ── Состояние тиража ─────────────────────────────────────────────────────────

def draw_features(x: np.ndarray, lo: int = 1) -> np.ndarray:
    """T×5: среднее число, размах, доля нечётных, доля малых, повторы с прошлым тиражом."""
    t, n = x.shape
    x = x.astype(np.float32, copy=False)
    cnt = np.maximum(x.sum(1), 1.0)
    values = np.arange(n, dtype=np.float32) + lo
    mean = x @ values / cnt
    present = x > 0
    has = present.any(1)
    first = np.where(has, present.argmax(1), 0)
    last = np.where(has, n - 1 - present[:, ::-1].argmax(1), 0)
    spread = (last - first).astype(np.float32)
    odd = x[:, (values % 2) == 1].sum(1) / cnt
    low = x[:, : n // 2].sum(1) / cnt
    rep = np.zeros(t, np.float32)
    rep[1:] = (x[1:] * x[:-1]).sum(1)
    return np.stack([mean, spread, odd, low, rep], 1).astype(np.float32)


def embed(z: np.ndarray, e: int) -> np.ndarray:
    """(T+1)×(e·D): строка u — состояние перед тиражом u, т. е. z[u−1], z[u−2], …, z[u−e]
    (по тиражам < u). Строки u < e не определены (нули)."""
    if z.ndim == 1:
        z = z[:, None]
    t, d = z.shape
    q = np.zeros((t + 1, e * d), np.float32)
    for j in range(e):
        q[j + 1:, j * d:(j + 1) * d] = z[: t - j]
    return q


def _expanding_inv_var(z: np.ndarray, reps: int) -> np.ndarray:
    """(T+1)×(reps·D): 1/дисперсия каждого признака по тиражам < u (масштаб расстояний без
    заглядывания в будущее). Нулевая дисперсия — вес 0."""
    t, d = z.shape
    n = np.arange(1, t + 1, dtype=np.float64)[:, None]
    m = np.cumsum(z, 0, dtype=np.float64) / n
    v = np.cumsum(z.astype(np.float64) ** 2, 0) / n - m ** 2
    w = np.zeros((t + 1, d), np.float32)
    w[1:] = np.where(v > 1e-12, 1.0 / np.maximum(v, 1e-12), 0.0)
    return np.tile(w, (1, reps))


# ── Поиск аналогов ───────────────────────────────────────────────────────────

def knn_predict(q: np.ndarray, y: np.ndarray, start: int, k: int, kind: str = "dist",
                w: np.ndarray | None = None, rows: np.ndarray | None = None, lib: int = LIB) -> np.ndarray:
    """Прогноз по аналогам.

    q — (T+1)×D состояния (строка u — перед тиражом u), y — T×M то, что случилось в тираже u.
    Для строки t ищутся k ближайших состояний u ∈ [max(start, t−lib), t−1] — только прошлое —
    и берётся взвешенное среднее y[u]. kind='dot' — близость = скалярное произведение (число
    общих чисел), веса e^(близость − max); kind='dist' — евклидово расстояние с весами
    признаков w[t], веса симплекса e^(−d/d_min). Возвращает (T+1)×M, NaN — аналогов нет."""
    t_total, m_out = y.shape
    out = np.full((t_total + 1, m_out), np.nan, np.float32)
    rows = np.arange(start + 1, t_total + 1) if rows is None else np.asarray(rows)
    rows = rows[rows > start]
    for c0 in range(0, len(rows), CHUNK):
        tt = rows[c0:c0 + CHUNK]
        l0 = max(start, int(tt[0]) - lib)
        l1 = int(tt[-1])
        if l1 <= l0:
            continue
        u = np.arange(l0, l1)
        a, b = q[tt], q[u]
        if kind == "dot":
            c = a @ b.T
        else:
            wt = np.ones_like(a) if w is None else w[tt]
            d2 = (a * a * wt).sum(1)[:, None] + wt @ (b * b).T - 2.0 * (a * wt) @ b.T
            c = -np.maximum(d2, 0.0)
        valid = (u[None, :] < tt[:, None]) & (u[None, :] >= tt[:, None] - lib)
        # при равной близости предпочитаем более свежие состояния
        c = np.where(valid, c + 1e-6 * (u - l0)[None, :] / max(len(u), 1), -np.inf)
        kk = int(min(k, len(u)))
        idx = np.argpartition(-c, kk - 1, axis=1)[:, :kk]
        ck = np.take_along_axis(c, idx, axis=1)
        ok = np.isfinite(ck)
        if kind == "dot":
            top = np.where(ok, ck, -np.inf).max(1, keepdims=True)
            wts = np.where(ok, np.exp(np.where(ok, ck, 0.0) - np.where(np.isfinite(top), top, 0.0)), 0.0)
        else:
            d = np.sqrt(np.where(ok, np.maximum(-ck, 0.0), np.inf))
            dmin = np.where(ok, d, np.inf).min(1, keepdims=True)
            wts = np.where(ok, np.exp(-d / np.maximum(dmin, 1e-6)), 0.0)
            wts = np.where(ok & (dmin <= 1e-6), (d <= 1e-6).astype(np.float32), wts)   # точные совпадения
        tot = wts.sum(1)
        good = tot > 0
        if not good.any():
            continue
        yy = y[u[idx]]                                      # chunk × k × M
        pred = (wts[:, :, None] * yy).sum(1) / np.where(good, tot, 1.0)[:, None]
        out[tt[good]] = pred[good]
    return out


def _fill(s: np.ndarray, f: Features) -> np.ndarray:
    return np.where(np.isfinite(s), s, f.p).astype(np.float32)


def analog_scores(f: Features, m: int, k: int = 30) -> np.ndarray:
    """Метод аналогов: в прошлом ищутся моменты, когда последние m тиражей были больше всего
    похожи на последние m тиражей сейчас (по общим числам), и берётся, что выпало после них."""
    return f.memo(("chaos_analog", m, k), lambda: _fill(knn_predict(embed(f.x, m), f.x, m, k, "dot"), f))


def phase_scores(f: Features, e: int, k: int = 25) -> np.ndarray:
    """Фазовое пространство (Такенс): состояние — 5 признаков e последних тиражей; аналоги —
    ближайшие состояния в этом пространстве; прогноз — что выпадало после них."""
    def calc():
        z = draw_features(f.x)
        return _fill(knn_predict(embed(z, e), f.x, e, k, "dist", w=_expanding_inv_var(z, e)), f)
    return f.memo(("chaos_phase", e, k), calc)


def ordinal_codes(y: np.ndarray, d: int) -> np.ndarray:
    """Номер порядкового паттерна каждого окна из d значений (Бандт–Помпе)."""
    win = sliding_window_view(y, d)
    ranks = np.argsort(win, axis=1, kind="stable")
    return (ranks * (d ** np.arange(d))).sum(1)


def ordinal_scores(f: Features, d: int, prior: float = 20.0) -> np.ndarray:
    """Порядковые паттерны: «узор» подъёмов и спадов среднего числа в последних d тиражах;
    оценка числа — как часто оно выпадало после такого же узора в прошлом."""
    def calc():
        x = f.x
        t = f.T
        y = draw_features(x)[:, 0]
        s = np.full((t + 1, f.N), f.p, np.float32)
        if t < d:
            return s
        pat = np.full(t + 1, -1, np.int64)
        pat[d:] = ordinal_codes(y, d)                       # состояние перед тиражом u = окно y[u−d..u−1]
        for code in np.unique(pat[d:]):
            us = np.nonzero(pat == code)[0]
            succ = us[us < t]
            cum = np.vstack([np.zeros((1, f.N), np.float64), np.cumsum(x[succ], 0, dtype=np.float64)])
            kk = np.arange(len(us))
            s[us] = ((cum[kk] + prior * f.p) / (kk[:, None] + prior)).astype(np.float32)
        return s
    return f.memo(("chaos_ordinal", d, prior), calc)


def chaos_models() -> list[Model]:
    """Методы «порядка из хаоса» (признаки — в номерах чисел поля: сдвиг нумерации не меняет
    расстояний, а доли нечётных и чётных дополняют друг друга)."""
    m = [Model("random", "Случайный выбор (контроль)", "control", _rand(7), control=True)]
    for k in (1, 2):
        m.append(Model(f"analog_{k}", f"Аналоги {'последнего тиража' if k == 1 else 'двух последних тиражей'}",
                       "analog", (lambda k: lambda f: analog_scores(f, k))(k), params={"m": k}))
    for e in (1, 2, 3):
        m.append(Model(f"phase_{e}", f"Фазовое пространство, размерность {e}", "phase",
                       (lambda e: lambda f: phase_scores(f, e))(e), params={"E": e, "k": 25}))
    m.append(Model("simplex_3", "Симплекс-прогноз (Сугихара–Мэй), E=3", "phase",
                   lambda f: phase_scores(f, 3, k=4), params={"E": 3, "k": 4}))
    for d in (3, 4):
        m.append(Model(f"ordinal_{d}", f"Порядковые паттерны из {d} тиражей", "ordinal",
                       (lambda d: lambda f: ordinal_scores(f, d))(d), params={"d": d}))
    return m


# ── Есть ли порядок ──────────────────────────────────────────────────────────

def predictability(y: np.ndarray, e_max: int = 5, n_test: int = 3000) -> dict:
    """Нелинейная предсказуемость (Сугихара–Мэй): симплекс-прогноз следующего значения ряда
    по E прошлым. У детерминированного хаоса корреляция прогноза с фактом заметно больше
    нуля; у независимых тиражей прогноз зависит только от прошлого, факт — нет, и корреляция
    ≈ 0 (её p-value — обычный t-тест; по E — поправка Бонферрони)."""
    y = np.asarray(y, np.float32)
    t = len(y)
    rows = np.arange(max(e_max + 30, t - n_test), t)
    best = None
    by_e = []
    for e in range(1, e_max + 1):
        pred = knn_predict(embed(y, e), y[:, None], e, e + 1, "dist", rows=rows)[rows, 0]
        ok = np.isfinite(pred)
        n = int(ok.sum())
        if n < 30 or np.std(pred[ok]) == 0 or np.std(y[rows][ok]) == 0:
            by_e.append({"E": e, "rho": 0.0, "p_value": 1.0, "n": n})
            continue
        r = float(np.corrcoef(pred[ok], y[rows][ok])[0, 1])
        tstat = r * math.sqrt((n - 2) / max(1e-12, 1 - r * r))
        p = float(sps.t.sf(tstat, n - 2))
        by_e.append({"E": e, "rho": r, "p_value": p, "n": n})
    best = min(by_e, key=lambda b: b["p_value"])
    return {"rho": best["rho"], "E": best["E"], "n": best["n"],
            "p_value": min(1.0, best["p_value"] * e_max), "by_E": by_e}


def perm_entropy(y: np.ndarray, d: int = 4) -> float:
    codes = ordinal_codes(np.asarray(y), d)
    _, cnt = np.unique(codes, return_counts=True)
    p = cnt / cnt.sum()
    return float(-(p * np.log(p)).sum() / math.log(math.factorial(d)))


def entropy_test(y: np.ndarray, d: int = 4, n_sur: int = 199, seed: int = 0, max_len: int = 20_000) -> dict:
    """Энтропия перестановок (Бандт–Помпе): насколько разнообразны «узоры» ряда. Порядок
    делает одни узоры частыми, а энтропию — ниже, чем у перемешанных копий ряда."""
    y = np.asarray(y)[-max_len:]
    h = perm_entropy(y, d)
    rng = np.random.default_rng(seed)
    hs = np.array([perm_entropy(rng.permutation(y), d) for _ in range(n_sur)])
    return {"entropy": h, "surrogate_mean": float(hs.mean()),
            "p_value": float((1 + (hs <= h).sum()) / (n_sur + 1))}


def _det(states: np.ndarray, rate: float) -> float:
    sq = (states ** 2).sum(1)
    d2 = np.maximum(sq[:, None] + sq[None, :] - 2 * states @ states.T, 0)
    n = len(states)
    off = ~np.eye(n, dtype=bool)
    eps = np.quantile(d2[np.triu(off, 1)], rate)
    r = (d2 <= eps) & off
    prev = np.zeros_like(r)
    prev[1:, 1:] = r[:-1, :-1]
    nxt = np.zeros_like(r)
    nxt[:-1, :-1] = r[1:, 1:]
    total = r.sum()
    return float((r & (prev | nxt)).sum() / total) if total else 0.0


def recurrence_test(z: np.ndarray, e: int = 3, n: int = 1000, rate: float = 0.1, n_sur: int = 99,
                    seed: int = 0) -> dict:
    """Рекуррентный анализ: детерминизм DET — доля возвращений к прошлым состояниям, которые
    продолжаются вдоль той же траектории (диагональные линии). Сравнение с перемешанными
    копиями тех же тиражей."""
    z = np.asarray(z, np.float32)[-(n + e):]
    sd = z.std(0)
    z = (z - z.mean(0)) / np.where(sd > 0, sd, 1)

    def states(zz):
        return embed(zz, e)[e:]

    det = _det(states(z), rate)
    rng = np.random.default_rng(seed)
    ds = np.array([_det(states(z[rng.permutation(len(z))]), rate) for _ in range(n_sur)])
    return {"det": det, "surrogate_mean": float(ds.mean()),
            "p_value": float((1 + (ds >= det).sum()) / (n_sur + 1))}


def _block_checks(x: np.ndarray, lo: int, seed: int) -> list[dict]:
    z = draw_features(x, lo)
    y = z[:, 0]
    pr = predictability(y)
    en = entropy_test(y, seed=seed)
    rq = recurrence_test(z, seed=seed)
    return [
        {"test": "predictability", "title": "Нелинейная предсказуемость", "p_value": pr["p_value"],
         "value": pr["rho"],
         "detail": ru(f"симплекс-прогноз среднего числа следующего тиража: корреляция с фактом "
                      f"{pr['rho']:+.3f} (лучшая размерность E={pr['E']}, {pr['n']} тиражей); "
                      f"у независимых тиражей ≈ 0")},
        {"test": "entropy", "title": "Порядковые паттерны (энтропия)", "p_value": en["p_value"],
         "value": en["entropy"],
         "detail": ru(f"энтропия узоров из 4 тиражей {en['entropy']:.4f} при {en['surrogate_mean']:.4f} у "
                      f"перемешанных копий (1 — все узоры равновероятны)")},
        {"test": "recurrence", "title": "Рекуррентный анализ (детерминизм)", "p_value": rq["p_value"],
         "value": rq["det"],
         "detail": ru(f"DET {rq['det']:.3f} при {rq['surrogate_mean']:.3f} у перемешанных копий — "
                      f"насколько возвращения к прошлым состояниям продолжаются той же траекторией")},
    ]


def diagnostics(data: GameData, seed: int = 0) -> list[dict]:
    """Проверки «есть ли порядок» по каждому полю; поправка Холма; значимая находка
    засчитывается, только если повторяется в обеих половинах истории."""
    out = []
    for i, (x, spec) in enumerate(zip(data.matrices, data.fmt.blocks)):
        for c in _block_checks(x, spec.lo, seed + i):
            c["block"] = spec.name
            out.append(c)
    for c, a in zip(out, holm([c["p_value"] for c in out])):
        c["p_adjusted"] = a
        c["replicated"] = None
        c["significant"] = False
    for c in out:
        if c["p_adjusted"] < 0.05:
            i = next(j for j, s in enumerate(data.fmt.blocks) if s.name == c["block"])
            x, lo = data.matrices[i], data.fmt.blocks[i].lo
            h = x.shape[0] // 2
            halves = [next(r for r in _block_checks(part, lo, seed) if r["test"] == c["test"])
                      for part in (x[:h], x[h:])]
            c["replicated"] = all(r["p_value"] < 0.05 for r in halves)
            c["significant"] = bool(c["replicated"])
    return out


# ── По способам розыгрыша ────────────────────────────────────────────────────

def _groups(data: GameData) -> dict[str, GameData]:
    from .mechanics import split_by_mechanism
    parts = split_by_mechanism(data)
    return parts or {"all": data}


def next_mechanism(data: GameData, available: list[str], target: dict | None = None) -> tuple[str | None, str]:
    """Способ розыгрыша тиража, на который пишется прогноз (target — journal.target_draw),
    и откуда это известно."""
    from .mechanics import mechanism_of_draw
    from .rules import load_rules
    if len(available) == 1:
        return available[0], "в игре один способ розыгрыша" if available[0] != "all" else "способ розыгрыша не определён"
    rules = load_rules(data.game.slug) or {}
    if target and target.get("date") and target.get("no"):
        dt = target["date"]
        if dt.second:
            return "R", f"тираж №{target['no']} в {dt:%H:%M:%S} — время с секундами, ГСЧ"
        m = mechanism_of_draw(data.game.slug, target["no"], dt.strftime("%d.%m.%Y %H:%M"), rules)
        if m and "интервал" not in target.get("how", ""):
            return m, f"тираж №{target['no']} в {dt:%H:%M} по расписанию"
    nd = rules.get("next_draw") or {}
    last = data.draws[-1]
    if nd.get("number") == last.no + 1 and nd.get("date"):
        try:
            dt = datetime.fromisoformat(str(nd["date"])[:19])
        except ValueError:
            dt = None
        if dt:
            if dt.second:
                return "R", "время ближайшего тиража с секундами — ГСЧ"
            m = mechanism_of_draw(data.game.slug, last.no + 1, dt.strftime("%d.%m.%Y %H:%M"), rules)
            if m:
                return m, f"ближайший тираж в {dt:%H:%M} по расписанию"
    times = sorted(((rules.get("schedule") or {}).get("times") or {}).items())
    hhmm = last.date[-5:]
    if times:
        later = [kv for kv in times if kv[0] > hhmm]
        when, m = (later or times)[0]
        return m, f"следующий тираж после №{last.no} по расписанию — в {when}"
    return None, "способ ближайшего тиража неизвестен"


def evaluate_group(sub: GameData, progress=None) -> dict:
    from .evaluate import evaluate_game
    from .mechanics import subset
    if sub.T > MAX_DRAWS:
        sub = subset(sub, np.arange(sub.T - MAX_DRAWS, sub.T))
    return evaluate_game(sub, progress=progress, models=chaos_models())


def analyze(data: GameData, progress=None, target: dict | None = None, reuse: dict | None = None) -> dict:
    """Проверки и методы «порядка из хаоса» отдельно по каждому способу розыгрыша, прогноз на
    тираж target (по умолчанию — следующий) из набора его способа."""
    groups = {k: g for k, g in _groups(data).items() if g.T >= MIN_DRAWS}
    if not groups and data.T >= MIN_DRAWS:
        groups = {"all": data}         # способы не определены или каждого слишком мало
    out: dict = {"groups": {}, "min_draws": MIN_DRAWS, "max_draws": MAX_DRAWS}
    for gi, (k, sub) in enumerate(groups.items()):
        title = MECH_TITLES[k]
        cb = (lambda p, title=title: progress({**p, "model": f"{title}: {p.get('model', '')}"})) if progress else None
        if progress:
            progress({"stage": "chaos", "done": 0, "total": 1, "model": f"{title}: проверки порядка"})
        old = ((reuse or {}).get("groups") or {}).get(k)
        if old and old.get("checks") and old["draws"] <= sub.T <= old["draws"] * 1.02:
            checks = old["checks"]          # проверки «есть ли порядок» — из прошлого отчёта (см. lp.heavy_cache)
        else:
            checks = diagnostics(sub)
        ev = evaluate_group(sub, cb)
        found = [c for c in checks if c["significant"]]
        noise = [c for c in checks if c["p_adjusted"] < 0.05 and not c["significant"]]
        if found:
            verdict = ("Найден порядок: " + "; ".join(f"{c['block']} — {c['title'].lower()}" for c in found)
                       + ". Он повторяется в обеих половинах истории.")
        elif noise:
            verdict = ("Есть отклонение (" + "; ".join(c["title"].lower() for c in noise)
                       + "), но оно не повторяется в обеих половинах истории — это шум.")
        else:
            verdict = ("Порядка не найдено: тиражи ведут себя как независимые — их динамика не "
                       "отличается от перемешанной истории.")
        best = None
        if ev.get("status") == "ok":
            best = next((m for m in ev["models"] if m["key"] == ev["best_key"]), None)
        out["groups"][k] = {
            "key": k, "title": title, "draws": sub.T, "checks": checks, "verdict": ru(verdict),
            "evaluation": ev,
            "best": best and {"key": best["key"], "title": best["title"],
                              "holdout": {kk: best["holdout"].get(kk) for kk in
                                          ("mean_hits", "baseline", "excess_pct", "p_better", "p_adjusted", "n")}},
        }
    mech, why = next_mechanism(data, list(out["groups"]), target)
    draw_no = (target or {}).get("no") or data.draws[-1].no + 1
    g = out["groups"].get(mech) if mech else None
    if g is None and len(out["groups"]) == 1:
        g = next(iter(out["groups"].values()))
        why += f"; для другого способа тиражей мало — прогноз по набору «{g['title']}»"
    if g and g["evaluation"].get("status") == "ok":
        ev = g["evaluation"]
        out["next"] = {"draw_no": draw_no, "mechanism": g["key"], "title": g["title"],
                       "reason": ru(why), "model": ev["next_prediction"]["model"],
                       "numbers": ev["next_prediction"]["numbers"], "consensus": ev["next_consensus"]}
    else:
        out["next"] = {"draw_no": draw_no, "mechanism": mech, "reason": ru(why), "numbers": None}
    out["conclusion"] = ru(conclusion(out))
    return out


def conclusion(res: dict) -> str:
    gs = list(res["groups"].values())
    if not gs:
        return f"Для анализа нужно хотя бы {MIN_DRAWS} тиражей одного способа розыгрыша."
    parts = []
    for g in gs:
        ev = g["evaluation"]
        found = any(c["significant"] for c in g["checks"])
        b = g.get("best")
        if b and b["holdout"].get("p_adjusted") is not None and b["holdout"]["p_adjusted"] < 0.05:
            meth = (f"лучший метод «{b['title']}» на контроле угадывает на {b['holdout']['excess_pct']:+.1f}% "
                    f"больше случайного выбора (p={b['holdout']['p_adjusted']:.3f})")
        elif b:
            meth = (f"лучший на отборе метод «{b['title']}» на контроле "
                    f"{b['holdout']['excess_pct']:+.1f}% к случайному выбору — в пределах случайности")
        else:
            meth = ev.get("message", "методы не проверены")
        parts.append(f"{g['title'][0].upper() + g['title'][1:]} ({g['draws']} тиражей): "
                     f"{'порядок найден' if found else 'порядка не найдено'}; {meth}.")
    return " ".join(parts)
