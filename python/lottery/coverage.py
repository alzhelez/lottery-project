"""Автоанализ игры: у всех ли тиражей архива есть предсказания каждого метода — журнал, «анализ
за период» и история прогнозов на весь архив (history.py). То же считает сайт
(src/lib/predictions.ts); здесь — для бота.

Пропуск — тираж, на который метод мог дать прогноз, а его нет: новый тираж, ещё не попавший в
историю, или «дыра» у методов анализа (Л, К, Н, З, Ф) внутри истории. Чего быть не может
(разгон, первая часть архива у режима Бога и «порядка из хаоса»), пропуском не считается."""
from __future__ import annotations

from . import history
from .drawfile import load_game_draws
from .games import get_game
from .journal import load

METHODS = [("final", "ФП"), ("analysis_best", "ЛМА"), ("analysis_consensus", "КМ"), ("chaos", "ПиХ"),
           ("godmode", "РБ"), ("golden", "ЗС"), ("least", "НВ")]


def analysis_days() -> int:
    """Период «анализа за период», который пересчитывается вместе с историей (как в прошлый раз)."""
    from .trust import load_trust
    days = load_trust().get("days")
    return days if days in (1, 3, 7, 14, 30) else 7


ALWAYS = {"final", "analysis_best", "analysis_consensus", "golden", "least"}    # считают каждый тираж истории


def coverage(slug: str) -> dict:
    nos = [d.no for d in load_game_draws(get_game(slug))]
    h = history.load(slug)
    have: dict[str, set[int]] = {}
    for retro in (True, False):
        for e in load(slug, retro=retro)["entries"]:
            if e.get("status") == "checked":
                have.setdefault(e["source"], set()).add(e["draw_no"])
    if h is None:
        return {"built": False, "draws": len(nos), "missing": {}, "complete": False}
    last, first = h["last_no"], h.get("first_no") or 0
    missing = {}
    for source, short in METHODS:
        if source not in h["sources"]:
            continue
        got = have.get(source, set()) | set(h["sources"][source]["nos"])
        missing[short] = sum(1 for no in nos if no not in got and (no > last or (source in ALWAYS and no >= first)))
    covered = set().union(*(set(v["nos"]) for v in h["sources"].values()), *have.values()) if h["sources"] else set()
    return {"built": True, "draws": len(nos), "with_predictions": sum(1 for no in nos if no in covered),
            "missing": {k: v for k, v in missing.items() if v}, "complete": bool(nos) and not any(missing.values())}


def summary(slug: str) -> tuple[str, bool]:
    """Строка автоанализа для бота и нужен ли пересчёт."""
    c = coverage(slug)
    if not c["draws"]:
        return "Автоанализ: тиражей в архиве нет.", False
    if not c["built"]:
        return (f"⚠️ Автоанализ: в архиве {c['draws']} тиражей, предсказания на весь архив ещё не посчитаны.", True)
    head = f"в архиве {c['draws']} тиражей, предсказания есть у {c['with_predictions']}"
    if c["complete"]:
        return f"✅ Автоанализ: {head} — у самых ранних их быть не может (методам нужна история до тиража; анализ берёт последние 60 000). Пропусков нет.", False
    gaps = ", ".join(f"{k} — {v}" for k, v in c["missing"].items())
    return f"⚠️ Автоанализ: {head}. Не хватает предсказаний: {gaps}.", True
