"""Журнал прогнозов: прогноз записывается ДО тиража и сверяется, когда тираж загружен.

Это единственная проверка без какой-либо подгонки: модель ещё не видела тиража,
на котором её оценивают. Засчитываются только прогнозы, сделанные раньше времени
тиража (время берётся из архива); прогноз, сделанный по устаревшим данным уже после
тиража, помечается «после тиража» и в статистику не идёт.

Файл: data/journal/<игра>.json
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime

import numpy as np
from scipy import stats as sps

from .drawfile import BlockSpec, Draw, GameData, block_values, load_game_draws
from .fsutil import write_text
from .games import Game, data_dir
from .stats import hypergeom_moments

MIN_FOR_P = 30   # меньше сверенных прогнозов — p-value не показываем, это шум

SOURCES = {
    "analysis_best": "Лучший метод анализа",
    "analysis_consensus": "Консенсус методов",
    "godmode": "Режим Бога",
}


def journal_path(slug: str):
    return data_dir() / "journal" / f"{slug}.json"


def load(slug: str) -> dict:
    try:
        return json.loads(journal_path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"game": slug, "entries": []}


def save(slug: str, journal: dict) -> None:
    write_text(journal_path(slug), json.dumps(journal, ensure_ascii=False, indent=1))


def record(data: GameData, source: str, numbers: list[list[int]], detail: str = "",
           now: datetime | None = None) -> dict:
    """Записывает прогноз на следующий тираж. Повторный прогноз того же источника на тот же
    тираж заменяет прежний, пока тираж не сыгран."""
    now = now or datetime.now()
    draw_no = data.draws[-1].no + 1
    journal = load(data.game.slug)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "draw_no": draw_no,
        "source": source,
        "source_title": SOURCES.get(source, source),
        "detail": detail,
        "made_at": now.isoformat(timespec="seconds"),
        "based_on": data.draws[-1].no,
        "blocks": [s.to_dict() for s in data.fmt.blocks],
        "numbers": [[int(v) for v in b] for b in numbers],
        "status": "pending",
    }
    entries = [e for e in journal["entries"]
               if not (e["draw_no"] == draw_no and e["source"] == source and e["status"] == "pending")]
    entries.append(entry)
    journal["entries"] = entries
    save(data.game.slug, journal)
    return entry


def _payout(entry: dict, hits_by_block: list[int], prize_table: dict | None) -> float | None:
    """Выплата по реальной таблице призов тиража (None — таблицы нет или формат не тот)."""
    if not prize_table or any(b.get("mode", "set") != "set" for b in entry["blocks"]):
        return None
    key = "+".join(str(h) for h in hits_by_block)
    c = prize_table["categories"].get(key)
    return float(c["prize"]) if c and c.get("prize") else 0.0


def _check(entry: dict, draw: Draw, now: datetime, prize_table: dict | None = None) -> dict:
    specs = [BlockSpec.from_dict(b) for b in entry["blocks"]]
    made = datetime.fromisoformat(entry["made_at"])
    draw_dt = draw.dt
    try:
        actual = [list(block_values(draw, s)) for s in specs]
    except (IndexError, TypeError):
        return {**entry, "status": "invalid", "checked_at": now.isoformat(timespec="seconds"),
                "note": "формат тиража не совпадает с форматом прогноза"}
    hits_by_block, expected, variance = [], 0.0, 0.0
    for s, pred, act in zip(specs, entry["numbers"], actual):
        hits_by_block.append(len(set(pred) & set(act)))
        m, v = hypergeom_moments(s.size, len(act), len(pred))
        expected += float(m)
        variance += float(v)
    late = draw_dt is not None and made >= draw_dt
    return {
        **entry,
        "status": "late" if late else "checked",
        "checked_at": now.isoformat(timespec="seconds"),
        "draw_date": draw.date,
        "actual": actual,
        "hits_by_block": hits_by_block,
        "hits": int(sum(hits_by_block)),
        "expected": expected,
        "variance": variance,
        "won": _payout(entry, hits_by_block, prize_table),
    }


def reconcile(game: Game, now: datetime | None = None, collect: list | None = None) -> int:
    """Сверяет ждущие прогнозы с загруженными тиражами. Возвращает число сверенных."""
    journal = load(game.slug)
    if not journal["entries"]:
        return 0
    now = now or datetime.now()
    by_no = {d.no: d for d in load_game_draws(game)}
    from . import prizes as prizes_mod
    tables = None
    changed = 0
    for i, e in enumerate(journal["entries"]):
        if e["status"] == "pending" and e["draw_no"] in by_no:
            if tables is None:
                counts = [b["count"] for b in e["blocks"]]
                tables = prizes_mod.keyed_history(game.slug, counts)
            journal["entries"][i] = _check(e, by_no[e["draw_no"]], now, tables.get(e["draw_no"]))
            if collect is not None:
                collect.append(journal["entries"][i])
            changed += 1
        elif e["status"] in ("checked", "late") and e.get("won") is None:
            # выплаты могли появиться в архиве позже самого тиража
            if tables is None:
                tables = prizes_mod.keyed_history(game.slug, [b["count"] for b in e["blocks"]])
            if e["draw_no"] in tables and e.get("hits_by_block") is not None:
                journal["entries"][i] = {**e, "won": _payout(e, e["hits_by_block"], tables[e["draw_no"]])}
                changed += 1
    if changed:
        save(game.slug, journal)
    return changed


def summary(entries: list[dict]) -> list[dict]:
    """Итог по каждому источнику: сколько угадано против ожидания случайного выбора."""
    out = []
    for source, title in SOURCES.items():
        done = [e for e in entries if e["source"] == source and e["status"] == "checked"]
        pending = sum(1 for e in entries if e["source"] == source and e["status"] == "pending")
        late = sum(1 for e in entries if e["source"] == source and e["status"] == "late")
        if not done and not pending and not late:
            continue
        row = {"source": source, "title": title, "checked": len(done), "pending": pending, "late": late}
        if done:
            hits = np.array([e["hits"] for e in done], float)
            exp = np.array([e["expected"] for e in done], float)
            var = float(sum(e["variance"] for e in done))
            z = float((hits.sum() - exp.sum()) / math.sqrt(var)) if var > 0 else 0.0
            row.update({
                "mean_hits": float(hits.mean()),
                "expected": float(exp.mean()),
                "excess_pct": float((hits.mean() - exp.mean()) / exp.mean() * 100) if exp.mean() else 0.0,
                "z": z,
                "p_better": float(sps.norm.sf(z)) if len(done) >= MIN_FOR_P else None,
            })
            paid = [e for e in done if e.get("won") is not None]
            if paid:
                row.update({"money_checked": len(paid), "won": float(sum(e["won"] for e in paid))})
        out.append(row)
    return out


def view(slug: str) -> dict:
    journal = load(slug)
    entries = sorted(journal["entries"], key=lambda e: (e["draw_no"], e["made_at"]), reverse=True)
    return {"game": slug, "entries": entries, "summary": summary(entries)}
