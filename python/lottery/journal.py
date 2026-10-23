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
    "chaos": "Порядок из хаоса",
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


TARGET_MARGIN_S = 90      # прогноз должен быть записан хотя бы за полторы минуты до тиража
STALE_DAYS = 3            # архив старше — номер тиража по времени не угадать


def target_draw(data: GameData, now: datetime | None = None) -> dict:
    """Ближайший тираж, который точно ещё не прошёл к моменту записи прогноза.

    У быстрых игр (тираж каждые несколько минут) «последний загруженный + 1» обычно уже
    сыгран, пока идёт анализ всех игр, — такие прогнозы журнал не засчитывает. Поэтому:
      1. если API знает ближайший тираж (номер и время) и до него больше TARGET_MARGIN_S — он;
      2. иначе номер считается от последнего известного тиража (из API или архива): по
         расписанию игры, если оно есть в правилах («10:00, 11:07, …»), или с шагом —
         10-й процентиль интервалов между последними тиражами (чтобы скорее перескочить
         вперёд, чем опоздать; ночной перерыв даёт лишь более далёкий, но будущий тираж).
    Возвращает {no, date (ожидаемое время или None), how}."""
    import math
    from datetime import timedelta
    now = now or datetime.now()
    edge = now + timedelta(seconds=TARGET_MARGIN_S)
    last = data.draws[-1]
    anchor_no, anchor_dt = last.no, last.dt
    stale = {"no": last.no + 1, "date": None,
             "how": "архив давно не обновлялся — следующий за последним загруженным"}
    try:
        from .rules import load_rules
        rules_rec = load_rules(data.game.slug) or {}
    except Exception:  # noqa: BLE001 — правила необязательны
        rules_rec = {}
    nd = rules_rec.get("next_draw") or {}
    if nd.get("number") and nd.get("date") and int(nd["number"]) > last.no:
        try:
            dt = datetime.fromisoformat(str(nd["date"])[:19])
        except ValueError:
            dt = None
        if dt is not None:
            if dt >= edge:
                return {"no": int(nd["number"]), "date": dt, "how": "ближайший тираж по данным Столото"}
            anchor_no, anchor_dt = int(nd["number"]), dt
    if anchor_dt is None:
        return {"no": last.no + 1, "date": None, "how": "следующий за последним загруженным"}
    if anchor_dt < now - timedelta(days=STALE_DAYS):
        return stale
    sched = sorted(((rules_rec.get("schedule") or {}).get("times") or {}))
    if sched:
        no, dt = anchor_no, anchor_dt
        for _ in range(5000):
            hhmm = dt.strftime("%H:%M")
            nxt = next((t for t in sched if t > hhmm), None)
            day = dt if nxt else dt + timedelta(days=1)
            h, m = map(int, (nxt or sched[0]).split(":"))
            dt = day.replace(hour=h, minute=m, second=0, microsecond=0)
            no += 1
            if dt >= edge:
                return {"no": no, "date": dt, "how": "ближайший будущий тираж по расписанию"}
    times = [d.dt for d in data.draws[-61:]]
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:]) if a and b and b > a]
    if not gaps:
        return {"no": last.no + 1, "date": None, "how": "следующий за последним загруженным"}
    step = float(np.percentile(gaps, 10))
    k = max(1, math.ceil((edge - anchor_dt).total_seconds() / step))
    return {"no": anchor_no + k, "date": anchor_dt + timedelta(seconds=k * step),
            "how": "ближайший будущий тираж по интервалу между тиражами"}


def record(data: GameData, source: str, numbers: list[list[int]], detail: str = "",
           now: datetime | None = None, draw_no: int | None = None, ordered: bool = False) -> dict:
    """Записывает прогноз на тираж draw_no (по умолчанию — ближайший будущий, target_draw).
    Повторный прогноз того же источника на тот же тираж заменяет прежний, пока тираж не
    сыгран."""
    now = now or datetime.now()
    draw_no = draw_no or target_draw(data, now)["no"]
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
        **({"ordered": True} if ordered else {}),
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


def _price(prize_table: dict | None) -> float | None:
    """Цена билета (одной ставки) в этом тираже — чтобы сравнить выигрыш с затратами."""
    try:
        return float(prize_table["price"]) if prize_table and prize_table.get("price") else None
    except (TypeError, ValueError):
        return None


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
    in_place, in_place_exp = 0, 0.0
    for s, pred, act in zip(specs, entry["numbers"], actual):
        hits_by_block.append(len(set(pred) & set(act)))
        m, v = hypergeom_moments(s.size, len(act), len(pred))
        expected += float(m)
        variance += float(v)
        if entry.get("ordered") and s.mode == "set":
            # «на своём месте»: число прогноза на той же позиции, что и в тираже
            in_place += sum(1 for a, b in zip(pred, act) if a == b)
            in_place_exp += min(len(pred), len(act)) / s.size
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
        "spent": _price(prize_table),
        **({"in_place": in_place, "in_place_expected": in_place_exp} if entry.get("ordered") else {}),
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
    from .mechanics import mechanism_of_draw
    from .rules import load_rules
    rules = load_rules(game.slug)
    stored = None
    for i, e in enumerate(journal["entries"]):
        if e["status"] == "pending" and e["draw_no"] in by_no:
            if tables is None:
                counts = [b["count"] for b in e["blocks"]]
                tables = prizes_mod.keyed_history(game.slug, counts)
                stored = prizes_mod.mechanisms(game.slug)
            d = by_no[e["draw_no"]]
            journal["entries"][i] = {**_check(e, d, now, tables.get(e["draw_no"])),
                                     "mechanism": mechanism_of_draw(game.slug, d.no, d.date, rules, stored)}
            if collect is not None:
                collect.append(journal["entries"][i])
            changed += 1
        elif e["status"] in ("checked", "late") and e.get("won") is not None and "spent" not in e:
            # записи до 41.5.0: цены билета не было — дописываем из архива выплат
            if tables is None:
                tables = prizes_mod.keyed_history(game.slug, [b["count"] for b in e["blocks"]])
            journal["entries"][i] = {**e, "spent": _price(tables.get(e["draw_no"]))}
            changed += 1
        elif e["status"] in ("checked", "late") and e.get("won") is None:
            # выплаты могли появиться в архиве позже самого тиража
            if tables is None:
                tables = prizes_mod.keyed_history(game.slug, [b["count"] for b in e["blocks"]])
            if e["draw_no"] in tables and e.get("hits_by_block") is not None:
                journal["entries"][i] = {**e, "won": _payout(e, e["hits_by_block"], tables[e["draw_no"]]),
                                         "spent": _price(tables[e["draw_no"]])}
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
            ordered = [e for e in done if "in_place" in e]
            if ordered:
                row.update({"ordered_checked": len(ordered), "in_place": int(sum(e["in_place"] for e in ordered)),
                            "in_place_expected": float(sum(e["in_place_expected"] for e in ordered))})
            paid = [e for e in done if e.get("won") is not None]
            if paid:
                row.update({"money_checked": len(paid), "won": float(sum(e["won"] for e in paid))})
                priced = [e for e in paid if e.get("spent")]
                if priced:
                    spent = float(sum(e["spent"] for e in priced))
                    row.update({"spent": spent, "won_priced": float(sum(e["won"] for e in priced)),
                                "return": float(sum(e["won"] for e in priced)) / spent if spent else None})
        out.append(row)
    return out


def view(slug: str) -> dict:
    journal = load(slug)
    entries = sorted(journal["entries"], key=lambda e: (e["draw_no"], e["made_at"]), reverse=True)
    by_mech = {}
    for m, title in (("L", "лототрон"), ("R", "ГСЧ")):
        part = [e for e in entries if e.get("mechanism") == m]
        if part:
            by_mech[m] = {"title": title, "summary": summary(part)}
    return {"game": slug, "entries": entries, "summary": summary(entries),
            "by_mechanism": by_mech if len(by_mech) > 1 else {}}


def sequential_p(entries: list[dict]) -> float | None:
    """«Всегда верное» p (смесь Роббинса), как в приложении (src/lib/journalStats.ts): его
    можно смотреть после каждого тиража, ложной тревоги всё равно не чаще заявленного."""
    done = [e for e in entries if e.get("status") == "checked"]
    if len(done) < MIN_FOR_P:
        return None
    s = float(sum(e["hits"] - e["expected"] for e in done))
    v = float(sum(e["variance"] for e in done))
    if v <= 0 or s <= 0:
        return 1.0
    rho = 1.0 / (500 * v / len(done))
    log_lambda = -0.5 * math.log(1 + rho * v) + rho * s * s / (2 * (1 + rho * v))
    return float(min(1.0, math.exp(-log_lambda)))


def proven_source(slug: str) -> dict | None:
    """Источник, который по журналу этой игры устойчиво лучше случайного выбора
    (последовательное p < 0,05); None — такого нет."""
    entries = load(slug)["entries"]
    best = None
    for source, title in SOURCES.items():
        p = sequential_p([e for e in entries if e["source"] == source])
        if p is not None and p < 0.05 and (best is None or p < best["p"]):
            best = {"source": source, "title": title, "p": p}
    return best
