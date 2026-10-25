"""Мои билеты: билеты, которые пользователь действительно купил, сверка с тиражами и денежный
итог.

Журнал прогнозов отвечает на вопрос «угадывает ли метод», а здесь — «сколько я потратил и
сколько выиграл». Билет вносится до или после тиража (номер тиража по умолчанию — ближайший
будущий); билет на несколько тиражей записывается отдельной строкой на каждый тираж. Когда
тираж загружен, билет сверяется: сколько чисел угадано и выплата по таблице призов этого
тиража из архива Столото. Если таблицы нет (или игра с позиционными полями), выигрыш можно
вписать вручную.

Файлы: data/my_tickets/<игра>.json — по файлу на игру, чтобы внесение билета в интерфейсе и
сверка в автозапуске реже писали один и тот же файл.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from .drawfile import BlockSpec, Draw, GameData, block_values, load_game_draws
from .fsutil import write_text
from .games import Game, data_dir, is_excluded

MAX_DRAWS_AHEAD = 100      # билет «на несколько тиражей» — не больше стольких
MAX_PER_GAME = 5000


def folder():
    return data_dir() / "my_tickets"


def path(slug: str):
    return folder() / f"{slug}.json"


def load(slug: str) -> dict:
    try:
        return json.loads(path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"game": slug, "tickets": []}


def save(slug: str, rec: dict) -> None:
    write_text(path(slug), json.dumps(rec, ensure_ascii=False, indent=1))


def slugs() -> list[str]:
    """Игры, по которым есть внесённые билеты (кроме убранных из программы)."""
    if not folder().exists():
        return []
    return sorted(p.stem for p in folder().glob("*.json") if not is_excluded(p.stem))


def parse(text: str) -> list[list[int]]:
    """«1, 2, 3 | 4» → [[1, 2, 3], [4]]."""
    blocks = []
    for part in text.split("|"):
        nums = [v.strip() for v in part.replace(";", ",").replace(" ", ",").split(",") if v.strip()]
        try:
            blocks.append([int(v) for v in nums])
        except ValueError as exc:
            raise ValueError("числа через запятую, поля через «|»") from exc
    return blocks


def validate(data: GameData, blocks: list[list[int]]) -> str | None:
    """Текст ошибки или None. В полях «k из N» можно отметить меньше чисел, только если в игре
    выбирают часть выпадающих (Кено: от 1 до 10 из 20 выпавших)."""
    specs = data.fmt.blocks
    if not data.fmt.supported or not specs:
        return "формат этой игры не поддерживается"
    if len(blocks) != len(specs):
        return (f"нужно {len(specs)} пол{'е' if len(specs) == 1 else 'я'}, через «|»: "
                + "; ".join(f"{s.name} — {s.count} из {s.lo}–{s.hi}" for s in specs))
    for nums, s in zip(blocks, specs):
        if s.mode not in ("set", "position"):
            return "в этой игре числа не выбираются"
        if len(set(nums)) != len(nums) or not all(s.lo <= v <= s.hi for v in nums):
            return f"{s.name}: разные числа от {s.lo} до {s.hi}"
        flexible = s.mode == "set" and s.drawn > s.count
        if flexible and not 1 <= len(nums) <= s.count:
            return f"{s.name}: от 1 до {s.count} чисел"
        if not flexible and len(nums) != s.count:
            return f"{s.name}: нужно {s.count} {'число' if s.count == 1 else 'чисел'} от {s.lo} до {s.hi}"
    return None


def current_price(data: GameData) -> float | None:
    """Цена ставки: из ближайшего тиража по данным Столото, иначе из последней таблицы призов."""
    try:
        from .rules import load_rules
        p = ((load_rules(data.game.slug) or {}).get("next_draw") or {}).get("price")
        if p:
            return float(p)
    except Exception:  # noqa: BLE001 — правила необязательны
        pass
    from . import prizes as prizes_mod
    hist = prizes_mod.keyed_history(data.game.slug, [s.count for s in data.fmt.blocks])
    for no in sorted(hist, reverse=True)[:20]:
        if hist[no].get("price"):
            return float(hist[no]["price"])
    return None


def add(data: GameData, blocks: list[list[int]], draw_no: int | None = None, draws: int = 1,
        price: float | None = None, note: str = "", now: datetime | None = None) -> list[dict]:
    """Вносит билет: по строке на каждый из `draws` тиражей, начиная с draw_no (по умолчанию —
    ближайший будущий). Возвращает добавленные строки."""
    err = validate(data, blocks)
    if err:
        raise ValueError(err)
    if not 1 <= draws <= MAX_DRAWS_AHEAD:
        raise ValueError(f"тиражей — от 1 до {MAX_DRAWS_AHEAD}")
    now = now or datetime.now()
    if draw_no is None:
        from .journal import target_draw
        draw_no = target_draw(data, now)["no"] if data.draws else 1
    if price is None:
        price = current_price(data)
    if price is not None and not 0 <= price <= 1_000_000:
        raise ValueError("цена — от 0 до 1 000 000 ₽")
    from .tickets import check
    pop = None
    try:
        c = check(data, [sorted(b) for b in blocks])
        if c.get("valid"):
            pop = {"popular": c["score"] > 0,
                   "flags": [f"{b['block']}: {f['text']}" for b in c["blocks"] for f in b["flags"]]}
    except Exception:  # noqa: BLE001 — проверка популярности — подсказка, не условие
        pop = None
    rec = load(data.game.slug)
    if len(rec["tickets"]) + draws > MAX_PER_GAME:
        raise ValueError(f"в игре уже {len(rec['tickets'])} билетов — больше {MAX_PER_GAME} не храним")
    group = uuid.uuid4().hex[:8]
    added = []
    for i in range(draws):
        t = {"id": uuid.uuid4().hex[:12], "group": group, "draw_no": int(draw_no) + i,
             "numbers": [[int(v) for v in b] for b in blocks],
             "blocks": [s.to_dict() for s in data.fmt.blocks],
             "price": price, "note": note[:200], "added_at": now.isoformat(timespec="seconds"),
             "status": "pending", **({"popularity": pop} if pop else {})}
        added.append(t)
    rec["tickets"].extend(added)
    save(data.game.slug, rec)
    settle(data.game, now=now)
    return [next(x for x in load(data.game.slug)["tickets"] if x["id"] == t["id"]) for t in added]


def remove(slug: str, ticket_id: str) -> bool:
    rec = load(slug)
    keep = [t for t in rec["tickets"] if t["id"] != ticket_id]
    if len(keep) == len(rec["tickets"]):
        return False
    rec["tickets"] = keep
    save(slug, rec)
    return True


def set_won(slug: str, ticket_id: str, won: float | None) -> dict | None:
    """Выигрыш вручную (например, когда таблицы призов в архиве нет); None — вернуть расчёт."""
    rec = load(slug)
    for t in rec["tickets"]:
        if t["id"] == ticket_id:
            if won is None:
                t.pop("won_manual", None)
            else:
                if not 0 <= won <= 1e10:
                    raise ValueError("выигрыш — от 0 ₽")
                t["won_manual"] = float(won)
            save(slug, rec)
            return t
    return None


def _hits(specs: list[BlockSpec], numbers: list[list[int]], draw: Draw) -> list[int]:
    out = []
    for s, mine in zip(specs, numbers):
        act = block_values(draw, s)
        out.append(int(mine[0] == act[0]) if s.mode == "position" else len(set(mine) & set(act)))
    return out


def _payout(t: dict, hits_by_block: list[int], table: dict | None) -> float | None:
    if not table or any(b.get("mode", "set") != "set" for b in t["blocks"]):
        return None
    c = table["categories"].get("+".join(str(h) for h in hits_by_block))
    return float(c["prize"]) if c and c.get("prize") else 0.0


def settle(game: Game, now: datetime | None = None) -> list[dict]:
    """Сверяет билеты с загруженными тиражами; дописывает выплату, если таблица призов
    появилась в архиве позже тиража. Возвращает впервые сверенные билеты."""
    rec = load(game.slug)
    todo = [t for t in rec["tickets"] if t["status"] == "pending" or (t["status"] == "checked" and t.get("won") is None)]
    if not todo:
        return []
    now = now or datetime.now()
    by_no = {d.no: d for d in load_game_draws(game)}
    from . import prizes as prizes_mod
    tables: dict[tuple, dict] = {}
    fresh, changed = [], False
    for t in todo:
        d = by_no.get(t["draw_no"])
        if d is None:
            continue
        counts = tuple(len(b) for b in t["numbers"])
        if counts not in tables:
            tables[counts] = prizes_mod.keyed_history(game.slug, list(counts))
        table = tables[counts].get(t["draw_no"])
        if t["status"] == "pending":
            specs = [BlockSpec.from_dict(b) for b in t["blocks"]]
            try:
                hb = _hits(specs, t["numbers"], d)
            except (IndexError, TypeError):
                t.update({"status": "invalid", "note": "формат тиража не совпадает с билетом"})
                changed = True
                continue
            t.update({"status": "checked", "checked_at": now.isoformat(timespec="seconds"), "draw_date": d.date,
                      "actual": [list(block_values(d, s)) for s in specs], "hits_by_block": hb,
                      "hits": int(sum(hb)), "won": _payout(t, hb, table)})
            if t.get("price") is None and table and table.get("price"):
                t["price"] = float(table["price"])
            fresh.append(t)
            changed = True
        elif table is not None:
            t["won"] = _payout(t, t["hits_by_block"], table)
            changed = changed or t["won"] is not None
    if changed:
        # перечитываем файл перед записью: пока шла сверка, в интерфейсе могли внести билет
        cur = load(game.slug)
        upd = {t["id"]: t for t in todo}
        cur["tickets"] = [{**t, **{k: v for k, v in upd[t["id"]].items() if k != "won_manual"}}
                          if t["id"] in upd else t for t in cur["tickets"]]
        save(game.slug, cur)
    return fresh


def won_of(t: dict) -> float | None:
    return t["won_manual"] if t.get("won_manual") is not None else t.get("won")


def summary(tickets: list[dict]) -> dict:
    """Итог по билетам: потрачено (по сверенным с известной ценой), выиграно, возврат."""
    checked = [t for t in tickets if t["status"] == "checked"]
    pending = [t for t in tickets if t["status"] == "pending"]
    priced = [t for t in checked if t.get("price") is not None]
    spent = float(sum(t["price"] for t in priced))
    known = [t for t in checked if won_of(t) is not None]
    won = float(sum(won_of(t) for t in known))
    winners = sum(1 for t in known if won_of(t) > 0)
    return {"total": len(tickets), "checked": len(checked), "pending": len(pending),
            "pending_spent": float(sum(t["price"] for t in pending if t.get("price") is not None)),
            "spent": spent, "won": won, "won_known": len(known), "winners": winners,
            "unknown_prize": len(checked) - len(known),
            "balance": won - spent, "return": won / spent if spent else None,
            "best": max((won_of(t) for t in known), default=0.0)}


def overview(only: list[str] | None = None) -> dict:
    """Все игры: билеты (свежие сверены), итог по каждой игре и общий."""
    from .games import get_game
    games, everything = [], []
    for slug in only or slugs():
        try:
            game = get_game(slug)
        except (KeyError, ValueError):
            continue
        settle(game)
        ts = load(slug)["tickets"]
        if not ts and not only:
            continue
        everything += ts
        games.append({"slug": slug, "title": game.title, "summary": summary(ts),
                      "tickets": sorted(ts, key=lambda t: (t["draw_no"], t["added_at"]), reverse=True)})
    return {"games": games, "summary": summary(everything)}
