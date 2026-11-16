"""Сравнение методов первой и второй версии на одних и тех же тиражах.

Для каждой игры и каждой пары (Ф ↔ Ф2, К ↔ К2, Б ↔ Б2, Н ↔ Н2) берутся тиражи, на которые есть
прогноз ОБЕИХ версий, и считается парная разница «угадано v2 − угадано v1» (у «наименее вероятных»
наоборот: меньше выпало — лучше). Парное сравнение убирает общий шум тиража, поэтому оно точнее,
чем сравнение двух процентов.

Два набора данных:
  history — все тиражи: история прогнозов на весь архив (расчёт задним числом, без заглядывания)
            + журнал; большая выборка, по ней виден эффект в доли процента;
  journal — только прогнозы, записанные в журнал ДО тиража: строгая проверка, но копится медленно.

Вердикт пары — по history, с поправкой Бонферрони на число сравнений (игры × пары):
  «v2 лучше» / «v2 хуже» — |z| ≥ z_crit; иначе «не отличаются». Порог записан заранее, как и правило
  находок (findings.py): методов и игр много, и без поправки кто-нибудь «выиграет» всегда.

Результат — data/v2_compare.json; сайт: «Статистика», бот: меню игры и «Состояние».
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from statistics import NormalDist

from . import botstats
from .fsutil import write_text
from .games import data_dir, get_game
from .journal import LOWER, SOURCES, V2_PAIRS, load

ALPHA = 0.05
MIN_DRAWS = 100          # меньше общих тиражей — сравнивать рано


def path():
    return data_dir() / "v2_compare.json"


def read() -> dict:
    try:
        return json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def paired(a: dict[int, float], b: dict[int, float], lower: bool) -> dict | None:
    """Парная разница v2 − v1 по общим тиражам: a, b — {тираж: угадано}. diff > 0 — v2 лучше."""
    common = sorted(set(a) & set(b))
    n = len(common)
    if n == 0:
        return None
    d = [(a[no] - b[no]) if lower else (b[no] - a[no]) for no in common]
    mean = sum(d) / n
    var = sum((x - mean) ** 2 for x in d) / (n - 1) if n > 1 else 0.0
    z = mean / math.sqrt(var / n) if var > 0 else 0.0
    h1, h2 = sum(a[no] for no in common), sum(b[no] for no in common)
    return {"n": n, "v1_hits": round(h1), "v2_hits": round(h2), "diff_per_draw": round(mean, 4),
            "diff_pct": round(100 * (h2 - h1) / h1, 2) if h1 else 0.0, "z": round(z, 2)}


def build(slugs: list[str], now: datetime | None = None) -> dict:
    now = now or datetime.now()
    games = []
    for slug in slugs:
        game = get_game(slug)
        if game is None:
            continue
        rows = botstats.scored(slug, datetime(2000, 1, 1))["rows"]         # история + анализ за период + журнал
        hist = {s: {no: v[1] for no, v in r.items()} for s, r in rows.items()}
        jour: dict[str, dict[int, float]] = {}
        for e in load(slug)["entries"]:
            if e.get("status") == "checked":
                jour.setdefault(e["source"], {})[e["draw_no"]] = e.get("hits") or 0
        pairs = []
        for v1, v2 in V2_PAIRS:
            lower = v1 in LOWER
            h = paired(hist.get(v1, {}), hist.get(v2, {}), lower)
            if h is None:
                continue
            pairs.append({"v1": v1, "v2": v2, "title": SOURCES[v1], "lower": lower, "history": h,
                          "journal": paired(jour.get(v1, {}), jour.get(v2, {}), lower)})
        if pairs:
            games.append({"slug": slug, "title": game.title, "pairs": pairs})
    tests = sum(1 for g in games for p in g["pairs"] if p["history"]["n"] >= MIN_DRAWS)
    crit = NormalDist().inv_cdf(1 - ALPHA / (2 * max(1, tests)))            # двусторонний: v2 может быть и хуже
    tally = {"better": 0, "worse": 0, "same": 0, "early": 0}
    for g in games:
        for p in g["pairs"]:
            h = p["history"]
            p["verdict"] = ("early" if h["n"] < MIN_DRAWS else "better" if h["z"] >= crit
                            else "worse" if h["z"] <= -crit else "same")
            tally[p["verdict"]] += 1
    out = {"updated_at": now.isoformat(timespec="seconds"),
           "rule": {"alpha": ALPHA, "tests": tests, "z_crit": round(crit, 2), "min_draws": MIN_DRAWS},
           "tally": tally, "games": sorted(games, key=lambda g: g["title"])}
    write_text(path(), json.dumps(out, ensure_ascii=False, indent=1))
    return out


VERDICTS = {"better": "v2 лучше", "worse": "v2 хуже", "same": "не отличаются", "early": "рано судить"}


def summary(c: dict | None = None, slug: str | None = None) -> str:
    """Текст для бота: общий счёт или пары одной игры."""
    c = c if c is not None else read()
    if not c.get("games"):
        return "Версия 2: сравнение появится после анализа за период (история прогнозов с методами v2)."
    if slug is None:
        t = c["tally"]
        return (f"Версия 2 против первой (пар «игра + метод»): v2 лучше — {t['better']}, хуже — {t['worse']}, "
                f"не отличаются — {t['same']}" + (f", рано судить — {t['early']}" if t["early"] else "") + ".")
    g = next((g for g in c["games"] if g["slug"] == slug), None)
    if g is None:
        return "Версия 2: по этой игре сравнения ещё нет — проведите анализ за период."
    from .notify import SHORT
    lines = ["<b>Версия 2 против первой</b> — на одних и тех же тиражах"]
    for p in g["pairs"]:
        h = p["history"]
        sign = f"{h['diff_pct']:+.1f}".replace(".", ",").replace("-", "−")
        lines.append(f"{SHORT[p['v1']]} → {SHORT[p['v2']]}: {VERDICTS[p['verdict']]} "
                     f"({h['n']} тиражей, {'выпало' if p['lower'] else 'угадано'} {sign} %)")
    return "\n".join(lines)
