"""«Находка» — заранее записанное правило, по которому метод считается отличимым от случайного выбора.

Без правила любой метод с +3 % за неделю выглядит как сигнал: методов и игр много, сравнений
десятки, и у кого-то отрыв найдётся всегда. Правило зафиксировано здесь и не подбирается под данные:

  1. Считаются только настоящие записи журнала — прогнозы, записанные ДО тиража и сверенные после
     (анализ за период и история прогнозов, посчитанные задним числом, не в счёт).
  2. Пара «игра + метод» должна набрать не меньше N_MIN сверенных прогнозов.
  3. Отрыв от случайного выбора в нужную сторону (у «наименее вероятных» — меньше выпавших) должен
     быть значим с поправкой Бонферрони на число пар: z ≥ z_crit, где z_crit — порог
     одностороннего уровня ALPHA / (число пар с хотя бы одним сверенным прогнозом).

Статусы пары: «подтверждено» — выполнены 2 и 3; «кандидат» — порог 3 пройден, но прогнозов меньше
N_MIN (рано судить); иначе находки нет. Проверка идёт каждый цикл, поэтому порог строгий: при 60
парах z_crit ≈ 3,1 — случайно его проходит одна пара из тысячи.

Результат — data/findings.json (сайт: «Статистика»; бот: «Состояние»). О новой подтверждённой
находке автозапуск пишет в Telegram один раз.
"""
from __future__ import annotations

import json
from datetime import datetime
from statistics import NormalDist

from .fsutil import write_text
from .games import data_dir, get_game
from .journal import ARCHIVED, LOWER, SOURCES, load
from .trust import score

N_MIN = 5000
ALPHA = 0.05
CLOSEST = 5


def path():
    return data_dir() / "findings.json"


def read() -> dict:
    try:
        return json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def z_crit(pairs: int) -> float:
    return NormalDist().inv_cdf(1 - ALPHA / max(1, pairs))


def build(slugs: list[str], now: datetime | None = None) -> dict:
    """Пересчитывает статусы всех пар «игра + метод» по журналу. Возвращает результат; в нём new —
    пары, впервые ставшие подтверждёнными (для сообщения в Telegram)."""
    now = now or datetime.now()
    rows = []
    for slug in slugs:
        game = get_game(slug)
        by: dict[str, list[dict]] = {}
        for e in load(slug)["entries"]:
            if e.get("status") == "checked" and e.get("source") in SOURCES and e.get("expected") is not None:
                by.setdefault(e["source"], []).append(e)
        for source, es in by.items():
            r = score(es, source in LOWER)
            good = -r["z"] if source in LOWER else r["z"]
            rows.append({"slug": slug, "title": game.title if game else slug, "source": source, "source_title": SOURCES[source],
                         "archived": source in ARCHIVED, "n": r["n"], "hits": r["hits"], "expected": r["expected"],
                         "excess_pct": r["excess_pct"], "z": round(good, 2)})
    crit = z_crit(len(rows))
    old = read()
    since = {f"{r['slug']}:{r['source']}": r.get("since") for r in old.get("confirmed", []) + old.get("candidates", [])}
    was = {f"{r['slug']}:{r['source']}" for r in old.get("confirmed", [])}
    confirmed, candidates = [], []
    for r in rows:
        if r["z"] >= crit:
            r["since"] = since.get(f"{r['slug']}:{r['source']}") or now.isoformat(timespec="minutes")
            (confirmed if r["n"] >= N_MIN else candidates).append(r)
    # ближе всего к порогу — чтобы было видно, насколько далеко до находки
    rest = sorted((r for r in rows if r["z"] < crit), key=lambda r: -r["z"])[:CLOSEST]
    for r in rest:
        # сколько прогнозов нужно, чтобы нынешний отрыв прошёл порог (и не меньше N_MIN)
        r["need"] = max(N_MIN, int(r["n"] * (crit / r["z"]) ** 2) + 1) if r["z"] > 0 else None
    out = {"updated_at": now.isoformat(timespec="seconds"),
           "rule": {"n_min": N_MIN, "alpha": ALPHA, "pairs": len(rows), "z_crit": round(crit, 2)},
           "confirmed": sorted(confirmed, key=lambda r: -r["z"]), "candidates": sorted(candidates, key=lambda r: -r["z"]),
           "closest": rest}
    write_text(path(), json.dumps(out, ensure_ascii=False, indent=1))
    return {**out, "new": [r for r in out["confirmed"] if f"{r['slug']}:{r['source']}" not in was]}


def summary(f: dict | None = None) -> str:
    """Одна-две строки для бота."""
    f = f if f is not None else read()
    rule = f.get("rule")
    if not rule:
        return "Находки: ещё не проверялись"
    if f.get("confirmed"):
        head = "Подтверждённые находки: " + "; ".join(
            f"{r['title']} — {r['source_title']} ({r['excess_pct']:+.1f} %, {r['n']} прогнозов)".replace(".", ",")
            for r in f["confirmed"])
    else:
        head = "Подтверждённых находок нет"
        if f.get("candidates"):
            head += "; кандидаты (мало прогнозов): " + "; ".join(f"{r['title']} — {r['source_title']}" for r in f["candidates"])
    crit = f"{rule['z_crit']:.2f}".replace(".", ",")
    return (f"{head}. Правило: не меньше {rule['n_min']} прогнозов журнала и z ≥ {crit} "
            f"(поправка на {rule['pairs']} пар «игра + метод»).")
