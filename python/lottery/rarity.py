"""Редкость комбинаций: насколько прогноз похож на то, что любят ставить игроки.

Шанс выигрыша у любой комбинации одинаков, но в категориях, где приз делится между победителями
(суперприз и часть призов тиражных лотерей), сумма зависит от того, сколько людей выбрали те же
числа. Для каждого прогноза журнала на будущие тиражи считаются признаки популярного выбора
(tickets.flags: даты, ряды подряд, прогрессии, числа прошлого тиража) и подбирается одна «редкая
комбинация» без таких признаков (tickets.generate) — она не прогноз и в журнал не пишется.

Результат — data/results/<игра>/rarity.json; его показывает «Обзор» (карточка ближайшего тиража).
"""
from __future__ import annotations

import json
from datetime import datetime

from . import tickets
from .drawfile import GameData
from .fsutil import write_text
from .games import results_dir
from .journal import LOWER, load


def path(slug: str):
    return results_dir(slug) / "rarity.json"


def read(slug: str) -> dict | None:
    try:
        return json.loads(path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def rate(data: GameData, numbers: list[list[int]]) -> dict | None:
    """{score, flags: [текст]} для прогноза; None — комбинацию нельзя оценить (не тот формат)."""
    res = tickets.check(data, [sorted(int(v) for v in b) for b in numbers])
    if not res.get("supported") or not res.get("valid"):
        return None
    flags = list(dict.fromkeys(f["text"] for b in res["blocks"] for f in b["flags"]))     # без повторов по полям
    return {"score": res["score"], "flags": flags}


def build(data: GameData) -> dict:
    """Пересчитывает редкость прогнозов на будущие тиражи. Редкая комбинация подбирается один раз
    на состояние архива (зависит от прошлого тиража) и между пересчётами не меняется."""
    slug = data.game.slug
    ok, reason = tickets.applicable(data)
    last = data.draws[-1].no if data.draws else 0
    out: dict = {"game": slug, "applicable": ok, "reason": reason, "based_on": last, "draws": {},
                 "updated_at": datetime.now().isoformat(timespec="seconds")}
    if ok and data.draws:
        for e in load(slug)["entries"]:
            if e["status"] != "pending" or e["draw_no"] <= last or e["source"] in LOWER:
                continue
            r = rate(data, e["numbers"])
            if r is not None:
                out["draws"].setdefault(str(e["draw_no"]), {})[e["source"]] = r
        old = read(slug) or {}
        if old.get("based_on") == last and old.get("rare"):
            out["rare"] = old["rare"]
        else:
            gen = tickets.generate(data, count=1, seed=last)
            if gen.get("supported") and gen.get("tickets"):
                t = gen["tickets"][0]
                out["rare"] = {"numbers": t["blocks"], "notes": t["notes"], "accepted_share": gen.get("accepted_share")}
    path(slug).parent.mkdir(parents=True, exist_ok=True)
    write_text(path(slug), json.dumps(out, ensure_ascii=False, indent=1))
    return out
