"""Способ розыгрыша (лототрон / ГСЧ), порядок шаров, повторяемость находок, чувствительность
тестов и наблюдение за дрейфом.

Идея: в честной лотерее предсказуемость может появиться только из-за физики (износ шаров,
неравномерный лототрон) или ошибки ГСЧ. Поэтому тиражи делятся по способу проведения,
каждый способ проверяется отдельно, а находка засчитывается, только если повторяется в
следующем периоде. Для каждой игры показывается, какое отклонение при таком объёме
архива уже было бы замечено («что исключено»).
"""
from __future__ import annotations

import json
from dataclasses import replace as dc_replace

import numpy as np
from scipy import stats as sps

from .drawfile import GameData
from .games import results_dir
from .stats import block_tests, holm, ru

MECH_TITLES = {"L": "лототрон", "R": "ГСЧ"}
MIN_PER_MECH = 200          # меньше — отдельный анализ способа не проводится
ORDER_MIN = 200
DRIFT_ALPHA = 0.01


# ── Способ розыгрыша каждого тиража ─────────────────────────────────────────

def classify(data: GameData) -> list[str | None]:
    """'L' (лототрон), 'R' (ГСЧ) или None по каждому тиражу.

    Порядок признаков:
      1. ответ API при загрузке: есть видеозапись → лототрон, время с секундами (:30) → ГСЧ;
      2. расписание из правил игры («10:00 (лототрон), 11:07:30 (ГСЧ)»);
      3. в смешанной игре время не на :00/:30 → ГСЧ (тиражи ГСЧ идут в 07, 22, 25, 37…),
         ровный час → лототрон;
      4. до первого тиража ГСЧ в смешанной игре — лототрон (ГСЧ появился позже: у «4 из 20» в 2025);
      5. игра с одним способом — этот способ; если в правилах способ не назван, а API у всех
         размеченных тиражей показывает один и тот же способ, — он же и у остальных (иначе
         в архиве оставался маленький «набор ГСЧ» из недавних тиражей, а старые терялись)."""
    from .prizes import mechanisms as stored
    from .rules import load_rules, mechanism_of_time
    rules = load_rules(data.game.slug)
    sched = (rules or {}).get("schedule") or {}
    mixed = bool(sched.get("lototron") and sched.get("rng"))
    single = "L" if sched.get("lototron") and not sched.get("rng") else (
        "R" if sched.get("rng") and not sched.get("lototron") else None)
    m_api = stored(data.game.slug)
    out: list[str | None] = []
    for d in data.draws:
        m = m_api.get(d.no)
        hhmm = d.date[-5:] if len(d.date) >= 16 else ""
        if m is None and hhmm:
            m = (sched.get("times") or {}).get(hhmm)
        if m is None and mixed and hhmm and hhmm[-2:] not in ("00", "30"):
            m = "R"
        if m is None and mixed and hhmm.endswith(":00"):
            m = "L"                      # ровный час в смешанной игре — лототрон (ГСЧ идут не ровно)
        if m is None and single:
            m = single
        out.append(m)
    if mixed:
        first_r = next((i for i, m in enumerate(out) if m == "R"), None)
        if first_r is not None:
            out = [("L" if m is None and i < first_r else m) for i, m in enumerate(out)]
    elif single is None:
        known = {m for m in out if m}
        if len(known) == 1:
            only = known.pop()
            out = [m or only for m in out]
    return out


def mechanism_of_draw(slug: str, no: int, date: str, rules: dict | None = None,
                      stored: dict | None = None) -> str | None:
    """Способ розыгрыша одного тиража (для журнала): ответ API → расписание → время."""
    from .prizes import mechanisms
    from .rules import load_rules
    stored = mechanisms(slug) if stored is None else stored
    if no in stored:
        return stored[no]
    rules = load_rules(slug) if rules is None else rules
    sched = (rules or {}).get("schedule") or {}
    hhmm = date[-5:] if len(date) >= 16 else ""
    if hhmm in (sched.get("times") or {}):
        return sched["times"][hhmm]
    if sched.get("lototron") and sched.get("rng") and hhmm:
        return "L" if hhmm.endswith(":00") else ("R" if hhmm[-2:] != "30" else None)
    if sched.get("lototron") != sched.get("rng"):
        return "L" if sched.get("lototron") else "R"
    return None


def subset(data: GameData, idx: np.ndarray) -> GameData:
    return dc_replace(data, draws=[data.draws[i] for i in idx], matrices=[m[idx] for m in data.matrices])


def split_by_mechanism(data: GameData) -> dict[str, GameData]:
    kinds = np.array([m or "" for m in classify(data)])
    out = {}
    for k in ("L", "R"):
        idx = np.nonzero(kinds == k)[0]
        if len(idx) >= MIN_PER_MECH:
            out[k] = subset(data, idx)
    return out


def mechanism_counts(data: GameData) -> dict:
    kinds = classify(data)
    return {"L": sum(k == "L" for k in kinds), "R": sum(k == "R" for k in kinds),
            "unknown": sum(k is None for k in kinds)}


# ── Порядок шаров ────────────────────────────────────────────────────────────

def _ordered_rows(data: GameData, spec) -> np.ndarray | None:
    """Числа поля в порядке выпадения (если файл хранит порядок, а не отсортированный список)."""
    if spec.mode not in ("set",) or spec.position is not None:
        return None
    rows = [d.blocks[spec.source] for d in data.draws]
    if not rows or any(len(r) != len(rows[0]) for r in rows):
        return None
    arr = np.array(rows)
    if arr.shape[1] < 2:
        return None
    ascending = np.mean(np.all(np.diff(arr, axis=1) > 0, axis=1))
    sorted_by_chance = 1 / np.prod(np.arange(1, arr.shape[1] + 1))   # 1/k!
    if ascending > max(0.5, 20 * sorted_by_chance):
        return None                                                  # хранится отсортированным
    return arr


def order_tests(data: GameData) -> list[dict]:
    """Равномерность числа на каждой позиции выпадения (1-й шар, 2-й шар…). У честного
    лототрона любой шар с равной вероятностью выходит первым; перекос — след механики
    (порядок загрузки шаров, неравные шары). Поправка Холма — по всем позициям всех полей."""
    if data.T < ORDER_MIN:
        return []
    tests = []
    for spec in data.fmt.blocks:
        arr = _ordered_rows(data, spec)
        if arr is None:
            continue
        for pos in range(arr.shape[1]):
            cnt = np.bincount(arr[:, pos] - spec.lo, minlength=spec.size)[: spec.size]
            chi = sps.chisquare(cnt)
            top = int(np.argmax(cnt)) + spec.lo
            tests.append({"block": spec.name, "position": pos + 1, "p_value": float(chi.pvalue),
                          "statistic": float(chi.statistic),
                          "detail": ru(f"чаще всего {top} ({cnt.max() / cnt.sum():.1%} при ожидаемых {1 / spec.size:.1%})")})
    for t, a in zip(tests, holm([t["p_value"] for t in tests])):
        t["p_adjusted"] = a
    return tests


def replicate_order(data: GameData, test: dict) -> bool:
    """Повторяется ли перекос позиции во второй половине истории в ту же сторону."""
    spec = next(s for s in data.fmt.blocks if s.name == test["block"])
    arr = _ordered_rows(data, spec)
    if arr is None:
        return False
    h = len(arr) // 2
    pos = test["position"] - 1
    c1 = np.bincount(arr[:h, pos] - spec.lo, minlength=spec.size)[: spec.size]
    c2 = np.bincount(arr[h:, pos] - spec.lo, minlength=spec.size)[: spec.size]
    if sps.chisquare(c2).pvalue >= 0.05:
        return False
    r, p = sps.pearsonr(c1 / c1.sum() - 1 / spec.size, c2 / c2.sum() - 1 / spec.size)
    return bool(r > 0 and p < 0.05)


# ── Повторяемость находок ─────────────────────────────────────────────────────

def replicate(data: GameData, test: dict, seed: int = 7) -> dict:
    """Находка засчитывается, только если тот же тест значим и во второй половине истории
    (а для частот — ещё и с теми же «любимыми» числами). Иначе это шум, найденный перебором."""
    spec = next((s for s in data.fmt.blocks if s.name == test.get("block")), None)
    if spec is None or data.T < 2 * 50:
        return {"replicated": False, "p_first": None, "p_second": None}
    i = data.fmt.blocks.index(spec)
    x = data.matrices[i]
    h = data.T // 2
    rng = np.random.default_rng(seed)
    first = next(t for t in block_tests(x[:h], spec, rng) if t["test"] == test["test"])
    second = next(t for t in block_tests(x[h:], spec, rng) if t["test"] == test["test"])
    ok = first["p_value"] < 0.05 and second["p_value"] < 0.05
    if ok and test["test"] == "freq":
        d1 = x[:h].mean(0) - x[:h].mean()
        d2 = x[h:].mean(0) - x[h:].mean()
        r, p = sps.pearsonr(d1, d2)
        ok = bool(r > 0 and p < 0.05)
    return {"replicated": bool(ok), "p_first": first["p_value"], "p_second": second["p_value"]}


# ── Чувствительность: что уже исключено ───────────────────────────────────────

def detectable(data: GameData, power: float = 0.8, alpha: float = 0.05) -> list[dict]:
    """Насколько чаще нормы должно выпадать одно число, чтобы тест частот это заметил
    (с вероятностью power, с поправкой на число чисел в поле). Чем больше архив, тем меньше
    исключённое смещение."""
    out = []
    for x, spec in zip(data.matrices, data.fmt.blocks):
        if spec.mode == "position":
            n_vals = spec.size
        else:
            n_vals = spec.size
        t = x.shape[0]
        p = float(x.sum() / (t * x.shape[1])) if t else 0.0
        if t == 0 or p <= 0 or p >= 1:
            continue
        z = sps.norm.ppf(1 - alpha / (2 * n_vals)) + sps.norm.ppf(power)
        delta = z * np.sqrt((1 - p) / (t * p))
        out.append({"block": spec.name, "draws": t, "relative_pct": float(delta * 100),
                    "text": ru(f"{spec.name}: если бы любое число выпадало хотя бы на {delta * 100:.1f}% чаще "
                               f"нормы, тесты заметили бы это с вероятностью {power:.0%}")})
    return out


def detectable_edge(hits_sd: float, n: int, mean: float, power: float = 0.8, alpha: float = 0.05) -> float | None:
    """На сколько процентов метод должен угадывать больше случайного выбора, чтобы проверка
    на контрольном отрезке (n тиражей) это увидела."""
    if n <= 0 or mean <= 0:
        return None
    z = sps.norm.ppf(1 - alpha / 2) + sps.norm.ppf(power)
    return float(z * hits_sd / np.sqrt(n) / mean * 100)


# ── Анализ по способам ───────────────────────────────────────────────────────

def mechanism_report(data: GameData) -> dict:
    """Тесты отдельно для лототрона и ГСЧ, сравнение частот между ними, порядок шаров."""
    from .stats import finalize_scan, game_randomness
    counts = mechanism_counts(data)
    parts = split_by_mechanism(data)
    rep: dict = {"counts": counts, "mixed": len(parts) == 2, "by_mechanism": {}, "comparison": [], "order": {}}
    for k, sub in parts.items():
        r = finalize_scan([game_randomness(sub)])[0]
        rep["by_mechanism"][k] = {"title": MECH_TITLES[k], "draws": sub.T, "verdict": r.get("verdict"),
                                  "level": r.get("level"), "p_game": r.get("p_game"),
                                  "significant": [t for t in r.get("tests", []) if t.get("significant")]}
        order = order_tests(sub)          # у ГСЧ — как контроль: перекоса быть не должно
        sig = [t for t in order if t["p_adjusted"] < 0.05]
        for t in sig:
            t["replicated"] = replicate_order(sub, t)
        rep["order"][k] = {"tests": order, "significant": sig,
                           "verdict": ("порядок выпадения шаров равномерный" if not sig else
                                       ("перекос порядка шаров повторяется во второй половине истории"
                                        if any(t["replicated"] for t in sig) else
                                        "перекос порядка шаров есть, но не повторяется — шум"))}
    if len(parts) == 2:
        for i, spec in enumerate(data.fmt.blocks):
            fl = parts["L"].matrices[i].sum(0)
            fr = parts["R"].matrices[i].sum(0)
            if fl.sum() and fr.sum():
                chi, p, _, _ = sps.chi2_contingency(np.vstack([fl, fr]) + 1e-9)
                rep["comparison"].append({"block": spec.name, "p_value": float(p), "statistic": float(chi),
                                          "detail": ru(f"частоты чисел лототрона и ГСЧ: χ²={chi:.1f}, p={p:.3f}")})
    return rep


def evaluate_by_mechanism(data: GameData) -> dict:
    """Сравнение методов отдельно на тиражах лототрона и ГСЧ (если обоих достаточно)."""
    from .evaluate import evaluate_game
    out = {}
    for k, sub in split_by_mechanism(data).items():
        if sub.T < 500:
            continue
        ev = evaluate_game(sub)
        if ev.get("status") != "ok":
            continue
        best = next((m for m in ev["models"] if m["key"] == ev["best_key"]), None)
        out[k] = {"title": MECH_TITLES[k], "draws": sub.T, "baseline": ev["baseline"],
                  "best": best and {"title": best.get("title"),
                                    "selection": {kk: best["selection"].get(kk) for kk in ("mean_hits", "excess_pct")},
                                    "holdout": {kk: best["holdout"].get(kk) for kk in ("mean_hits", "excess_pct", "p_adjusted")}},
                  "conclusion": ev.get("conclusion")}
    return out


# ── Дрейф ────────────────────────────────────────────────────────────────────

def drift(data: GameData) -> dict:
    """Наблюдение за дрейфом: последние W тиражей каждого способа против равномерности и
    против всей предыдущей истории. Тревога — если отклонение значимо после поправки на
    число проверок (p < 0,01). Это не прогноз: так замечают момент, когда физика начала
    влиять (износ шаров, замена лототрона, сбой ГСЧ)."""
    groups = split_by_mechanism(data) or {"all": data}
    if "L" not in groups and "R" not in groups:
        groups = {"all": data}
    checks = []
    for k, sub in groups.items():
        if sub.T < 2 * MIN_PER_MECH:
            continue
        w = int(np.clip(sub.T // 10, MIN_PER_MECH, 2000))
        for i, spec in enumerate(sub.fmt.blocks):
            x = sub.matrices[i]
            recent, before = x[-w:], x[:-w]
            f_recent = recent.sum(0)
            if f_recent.sum() == 0:
                continue
            p_uni = sps.chisquare(f_recent).pvalue
            chi, p_cmp, _, _ = sps.chi2_contingency(np.vstack([f_recent, before.sum(0)]) + 1e-9)
            top = int(np.argmax(f_recent)) + spec.lo
            for name, p in (("равномерность последних тиражей", p_uni), ("сравнение с прошлой историей", p_cmp)):
                checks.append({"mechanism": k, "title": MECH_TITLES.get(k, "все тиражи"), "block": spec.name,
                               "check": name, "window": w, "p_value": float(p),
                               "detail": ru(f"последние {w} тиражей; чаще всего {top}")})
        if k in ("L", "all"):
            for t in order_tests(subset(sub, np.arange(max(0, sub.T - 2000), sub.T))):
                checks.append({"mechanism": k, "title": MECH_TITLES.get(k, "все тиражи"), "block": t["block"],
                               "check": f"порядок: шар {t['position']}", "window": min(sub.T, 2000),
                               "p_value": t["p_value"], "detail": t["detail"]})
    for c, a in zip(checks, holm([c["p_value"] for c in checks])):
        c["p_adjusted"] = a
        c["alarm"] = a < DRIFT_ALPHA
    alarms = [c for c in checks if c["alarm"]]
    return {"last_draw_no": data.draws[-1].no if data.draws else None, "checks": checks, "alarms": alarms,
            "verdict": ("Дрейфа нет: последние тиражи не отличаются от честной лотереи и от прошлой истории."
                        if not alarms else
                        "Внимание: " + "; ".join(f"{a['title']}, {a['block']} — {a['check']} (p={a['p_adjusted']:.4f})"
                                                for a in alarms[:3]))}


def save_drift(data: GameData) -> dict:
    """Считает дрейф, сохраняет results/<игра>/drift.json и возвращает новые тревоги
    (которых не было в прошлый раз) — о них приходит уведомление."""
    path = results_dir(data.game.slug) / "drift.json"
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    res = drift(data)
    seen = {(a["mechanism"], a["block"], a["check"]) for a in prev.get("alarms", [])}
    res["new_alarms"] = [a for a in res["alarms"] if (a["mechanism"], a["block"], a["check"]) not in seen]
    from .fsutil import write_text
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, json.dumps(res, ensure_ascii=False, indent=1))
    return res


def method_edge(data: GameData, evaluation: dict) -> float | None:
    """«Что исключено» для методов: на сколько процентов метод должен угадывать больше
    случайного выбора, чтобы проверка на контрольном отрезке это увидела."""
    from .stats import hypergeom_moments
    try:
        split_no = evaluation["test"]["split"]
    except (KeyError, TypeError):
        return None
    idx = [i for i, d in enumerate(data.draws) if d.no >= split_no]
    if not idx:
        return None
    mean = np.zeros(len(idx))
    var = np.zeros(len(idx))
    for x, spec in zip(data.matrices, data.fmt.blocks):
        m, v = hypergeom_moments(spec.size, x[idx].sum(axis=1), spec.count)
        mean += m
        var += v
    return detectable_edge(float(np.sqrt(var.mean())), len(idx), float(mean.mean()))
