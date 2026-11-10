"""Ретро-проверка: что дал бы каждый источник журнала на каждый тираж последней недели.

Обычный журнал записывает прогноз ДО тиража, но успевает не на каждый тираж: автозапуск идёт
раз в час, а быстрые игры разыгрываются каждые 5–15 минут. Ретро-проверка восстанавливает
прогнозы задним числом на все тиражи недели — честно: прогноз на тираж t строится только по
тиражам до t (методы считают оценки пошагово), а сам метод выбирается на отрезке отбора,
который заканчивается задолго до этой недели. Поэтому выбор «лучшего» не видел ни одного
тиража недели.

Это всё же не то же самое, что прогноз, записанный заранее: так считает текущая версия
программы, а не та, что работала в тот день. Поэтому ретро-прогнозы хранятся отдельно
(data/journal_retro/<игра>.json) и в «Статистике» показываются своей таблицей.

Источники: Л, К, Н, З — из одного сравнения методов (evaluate_game), Х — «порядок из хаоса»
по способу розыгрыша каждого тиража, Б — «лидер за всю историю» режима Бога (короткий
запуск, эксперты отобраны по первой половине истории), Ф — «Финальное предсказание»: голосование
этих источников с весами по доверию, накопленному к каждому тиражу.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

import numpy as np

from .drawfile import GameData, load_game_data
from .fsutil import write_text
from .games import data_dir, get_game
from .journal import SOURCES, PrizeLookup, _check, _entry, save

RETRO_VERSION = 2          # меняется, когда меняется расчёт, — тогда ретро пересчитывается
RETRO_DAYS = 7
EVAL_MAX = 60_000          # как в анализе (lp.analyze_game)
GODMODE_MAX_DRAWS = 60_000
REFRESH_DAYS = 7           # автозапуск пересчитывает ретро раз в неделю


def status_path():
    return data_dir() / "journal_retro" / "status.json"


def load_status() -> dict:
    try:
        return json.loads(status_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def due(now: datetime | None = None) -> bool:
    """Пора ли пересчитать: ещё не считали, расчёт изменился или прошлый старше недели."""
    st = load_status()
    if st.get("retro_version") != RETRO_VERSION or st.get("status") != "done":
        return True
    try:
        return (now or datetime.now()) - datetime.fromisoformat(st["finished_at"]) >= timedelta(days=REFRESH_DAYS)
    except (KeyError, ValueError, TypeError):
        return True


def _numbers(picks: list[np.ndarray], specs, row: int) -> list[list[int]]:
    return [sorted(int(v) + s.lo for v in p[row]) for p, s in zip(picks, specs)]


def week_rows(data: GameData, since: datetime) -> list[int]:
    return [t for t, d in enumerate(data.draws) if d.dt is not None and d.dt >= since]


def from_evaluation(data: GameData, since: datetime) -> tuple[dict[str, list[tuple[int, list[list[int]], str]]], dict]:
    """Л, К, Э, Н, З на каждый тираж недели из одного сравнения методов."""
    from .evaluate import evaluate_game
    from .mechanics import subset
    part = data if data.T <= EVAL_MAX else subset(data, np.arange(data.T - EVAL_MAX, data.T))
    rows = week_rows(part, since)
    out: dict[str, list] = {}
    if not rows:
        return out, {"rows": 0}
    ev = evaluate_game(part, keep_picks=True)
    if ev.get("status") != "ok":
        return out, {"rows": len(rows), "skipped": ev.get("message", "мало тиражей")}
    picks = ev.pop("_picks")
    split = picks["split"]
    honest = [t for t in rows if t >= split]          # выбор метода не видел этих тиражей
    detail = {"analysis_best": ev["next_prediction"]["model"], "analysis_consensus": "",
              "least": (ev.get("least") or {}).get("next_prediction", {}).get("model", ""),
              "golden": (ev.get("golden") or {}).get("detail", "")}
    for source in ("analysis_best", "analysis_consensus", "least", "golden"):
        p = picks.get(source)
        if p is None:
            continue
        out[source] = [(part.draws[t].no, _numbers(p, part.fmt.blocks, t), detail[source]) for t in honest]
    return out, {"rows": len(rows), "honest": len(honest), "best": ev["next_prediction"]["model"]}


def from_chaos(data: GameData, since: datetime) -> list[tuple[int, list[list[int]], str]]:
    """«Порядок из хаоса»: тираж прогнозирует лучший метод набора его способа розыгрыша."""
    from . import chaos
    from .evaluate import evaluate_game
    from .mechanics import subset
    groups = {k: g for k, g in chaos._groups(data).items() if g.T >= chaos.MIN_DRAWS}
    if not groups and data.T >= chaos.MIN_DRAWS:
        groups = {"all": data}
    out = []
    for key, sub in groups.items():
        if sub.T > chaos.MAX_DRAWS:
            sub = subset(sub, np.arange(sub.T - chaos.MAX_DRAWS, sub.T))
        rows = week_rows(sub, since)
        if not rows:
            continue
        ev = evaluate_game(sub, models=chaos.chaos_models(), keep_picks=True)
        if ev.get("status") != "ok":
            continue
        picks = ev.pop("_picks")
        title = f"{ev['next_prediction']['model']} · {chaos.MECH_TITLES[key]}"
        out += [(sub.draws[t].no, _numbers(picks["analysis_best"], sub.fmt.blocks, t), title)
                for t in rows if t >= picks["split"]]
    return out


def _entries(data: GameData, items: dict[str, list], now: datetime) -> list[dict]:
    """Ретро-записи журнала, сразу сверенные с тиражами."""
    from .mechanics import mechanism_of_draw
    from .prizes import mechanisms
    from .rules import load_rules
    by_no = {d.no: (t, d) for t, d in enumerate(data.draws)}
    prizes = PrizeLookup(data.game.slug, [s.count for s in data.fmt.blocks])
    rules = load_rules(data.game.slug)
    stored = mechanisms(data.game.slug)
    out = []
    for source, rows in items.items():
        for no, numbers, detail in rows:
            if no not in by_no:
                continue
            t, d = by_no[no]
            e = _entry(data, source, numbers, detail, now, no, ordered=False)
            e.update({"retro": True, "based_on": data.draws[t - 1].no if t else None})
            checked = _check(e, d, now, prizes.get(no))
            checked["mechanism"] = mechanism_of_draw(data.game.slug, d.no, d.date, rules, stored)
            out.append(checked)
    return out


def final_rows(data: GameData, entries: list[dict]) -> list[tuple[int, list[list[int]], str]]:
    """«Финальное предсказание» на каждый тираж периода: голосование источников с весами по
    доверию, накопленному к этому тиражу (только по более ранним тиражам периода) — без
    заглядывания: тираж не влияет на веса, с которыми на него строится прогноз."""
    import math

    from . import trust
    from .journal import LOWER
    by_no: dict[int, dict[str, dict]] = {}
    for e in entries:
        by_no.setdefault(e["draw_no"], {})[e["source"]] = e
    blocks = [s.to_dict() for s in data.fmt.blocks]
    acc: dict[str, list[float]] = {}                 # источник → [Σ(угадано − ожидалось), Σдисперсий, n]
    out = []
    for no in sorted(by_no):
        w = {}
        for s, (diff, var, n) in acc.items():
            z = diff / math.sqrt(var) if var > 0 else 0.0
            tr = 100 * trust._phi((-z if s in LOWER else z) * math.sqrt(n / (n + trust.SHRINK_N)))
            w[s] = trust.BASE_WEIGHT + max(0.0, tr - 50.0) / 50.0
        numbers = trust.final_numbers({s: e["numbers"] for s, e in by_no[no].items()}, blocks, w)
        if numbers:
            out.append((no, numbers, "голосование по доверию, накопленному к этому тиражу"))
        for s, e in by_no[no].items():
            a = acc.setdefault(s, [0.0, 0.0, 0])
            a[0] += (e.get("hits") or 0) - (e.get("expected") or 0)
            a[1] += e.get("variance") or 0
            a[2] += 1
    return out


def run(slugs: list[str], days: int = RETRO_DAYS, godmode_budget: float = 3.0, log=print,
        now: datetime | None = None, workers: int = 2) -> dict:
    """Ретро-проверка игр slugs за последние days дней. Журнал каждой игры
    (data/journal_retro/<игра>.json) пересчитывается целиком."""
    now = now or datetime.now()
    since = now - timedelta(days=days)
    status = {"retro_version": RETRO_VERSION, "status": "running", "started_at": now.isoformat(timespec="seconds"),
              "finished_at": None, "days": days, "since": since.isoformat(timespec="minutes"), "games": {}}
    write_text(status_path(), json.dumps(status, ensure_ascii=False, indent=1))
    datas: dict[str, GameData] = {}
    items: dict[str, dict[str, list]] = {}
    for slug in slugs:
        t0 = time.time()
        try:
            data = load_game_data(get_game(slug))
        except ValueError:
            continue
        if not week_rows(data, since):
            status["games"][slug] = {"skipped": "за неделю тиражей нет"}
            continue
        try:
            ev_items, info = from_evaluation(data, since)
            ev_items["chaos"] = from_chaos(data, since)
        except Exception as exc:  # noqa: BLE001 — одна игра не должна ронять пересчёт
            status["games"][slug] = {"error": f"{type(exc).__name__}: {exc}"}
            log(f"{slug}: ретро-проверка — ошибка {type(exc).__name__}: {exc}")
            continue
        datas[slug], items[slug] = data, ev_items
        status["games"][slug] = {**info, "seconds": round(time.time() - t0, 1)}
        log(f"{slug}: ретро — {info.get('honest', 0)} тиражей за {days} дн., методы анализа и порядок из хаоса")
    # Б — режим Бога: короткий запуск на игру, по два процесса (как в автозапуске)
    if godmode_budget > 0 and datas:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor, as_completed

        from .godmode import auto_run
        first_no = {s: next(d.no for d in datas[s].draws if d.dt is not None and d.dt >= since) for s in datas}
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = {pool.submit(auto_run, s, godmode_budget, GODMODE_MAX_DRAWS, first_no[s]): s for s in datas}
            for fut in as_completed(futures):
                slug = futures[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001
                    log(f"{slug}: ретро режима Бога — ошибка {type(exc).__name__}: {exc}")
                    continue
                leader = (res.get("next") or {}).get("strategy") or "Лидер за всю историю"
                items[slug]["godmode"] = [(r["no"], r["predicted"], leader) for r in res.get("retro") or []]
                status["games"][slug]["godmode_experts"] = res.get("experts")
    for slug, data in datas.items():
        entries = _entries(data, items[slug], now)
        entries += _entries(data, {"final": final_rows(data, entries)}, now)
        save(slug, {"game": slug, "retro": True, "made_at": now.isoformat(timespec="seconds"), "days": days,
                    "since": since.isoformat(timespec="minutes"), "retro_version": RETRO_VERSION,
                    "entries": entries}, retro=True)
        status["games"][slug]["entries"] = len(entries)
        status["games"][slug]["by_source"] = {s: sum(e["source"] == s for e in entries) for s in SOURCES}
    status.update({"status": "done", "finished_at": datetime.now().isoformat(timespec="seconds")})
    write_text(status_path(), json.dumps(status, ensure_ascii=False, indent=1))
    return status
