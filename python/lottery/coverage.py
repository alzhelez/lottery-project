"""Автоанализ игры: у всех ли тиражей периода есть сверенные предсказания каждого метода
(журнал + анализ за период). То же считает сайт (src/lib/predictions.ts); здесь — для бота."""
from __future__ import annotations

from datetime import datetime, timedelta

from .drawfile import load_game_draws
from .games import get_game
from .journal import load
from .trust import load_trust

METHODS = [("final", "ФП"), ("analysis_best", "ЛМА"), ("analysis_consensus", "КМ"), ("chaos", "ПиХ"),
           ("godmode", "РБ"), ("golden", "ЗС"), ("least", "НВ")]


def analysis_days() -> int:
    days = load_trust().get("days")
    return days if days in (1, 3, 7, 14, 30) else 7


def coverage(slug: str, days: int | None = None, now: datetime | None = None) -> dict:
    days = days or analysis_days()
    since = (now or datetime.now()) - timedelta(days=days)
    nos = [d.no for d in load_game_draws(get_game(slug)) if d.dt is not None and d.dt >= since]
    have: dict[str, set[int]] = {}
    for retro in (True, False):
        for e in load(slug, retro=retro)["entries"]:
            if e.get("status") == "checked":
                have.setdefault(e["source"], set()).add(e["draw_no"])
    missing = {short: sum(1 for no in nos if no not in have.get(source, ())) for source, short in METHODS}
    return {"days": days, "draws": len(nos), "missing": {k: v for k, v in missing.items() if v},
            "complete": bool(nos) and not any(missing.values())}


def summary(slug: str) -> tuple[str, bool]:
    """Строка автоанализа для бота и нужен ли пересчёт."""
    c = coverage(slug)
    if not c["draws"]:
        return f"Автоанализ: за {c['days']} дн. тиражей не было.", False
    if c["complete"]:
        return f"✅ Автоанализ: за {c['days']} дн. {c['draws']} тиражей — у каждого есть предсказания всех методов.", False
    gaps = ", ".join(f"{k} — {v}" for k, v in c["missing"].items())
    return f"⚠️ Автоанализ: за {c['days']} дн. {c['draws']} тиражей, не хватает предсказаний: {gaps}.", True
