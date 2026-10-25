#!/usr/bin/env python3
"""Командная строка движка. Все команды печатают события прогресса строками
``@@{json}`` в stdout (их читает Next.js), а результаты сохраняют в data/results.

  python python/lp.py fetch [--game 4x20 ...]     загрузить/обновить тиражи
  python python/lp.py scan                         тесты случайности по всем играм
  python python/lp.py analyze --game 4x20          сравнение методов на истории
  python python/lp.py godmode --game 4x20 --budget 30   «режим Бога», бюджет в минутах
  python python/lp.py info --game 4x20             сведения о данных игры
  python python/lp.py journal [--game 4x20]        сверить журнал прогнозов с тиражами
  python python/lp.py auto [--every 1]             загрузка + анализ активных игр (по расписанию)
  python python/lp.py odds [--game 4x20]           шансы и ожидаемый возврат
  python python/lp.py tickets --game 6x45          непопулярные комбинации
  python python/lp.py export --game 4x20           экспорт в Excel
  python python/lp.py diagnose [--api]             проверка формата и полноты данных
"""
from __future__ import annotations

import argparse
import json
import subprocess

import numpy as np
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def env_file() -> Path:
    """Файл настроек: .env в папке проекта (LOTTERY_ENV_FILE — другой путь, например в тестах)."""
    return Path(os.environ.get("LOTTERY_ENV_FILE") or Path(__file__).resolve().parents[1] / ".env")


def _load_dotenv() -> None:
    """Переменные из .env проекта (Next.js читает его сам, а при запуске из консоли — мы).
    Уже заданные переменные окружения не перезаписываются."""
    path = env_file()
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

from lottery import __version__  # noqa: E402
from lottery.drawfile import load_game_data  # noqa: E402
from lottery.games import local_slugs, activity, all_games, draws_path, get_game, read_meta, results_dir  # noqa: E402

if sys.stdout is None or sys.stderr is None:  # pythonw.exe (Планировщик без окна консоли)
    sys.stdout = sys.stdout or open(os.devnull, "w", encoding="utf-8")
    sys.stderr = sys.stderr or open(os.devnull, "w", encoding="utf-8")

try:  # Windows-консоль: принудительно UTF-8
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


_EMIT_LOCK = threading.Lock()


# В терминале — понятный текст, при запуске из приложения (вывод в канал) — события @@json.
PRETTY = sys.stdout.isatty() and os.environ.get("LOTTERY_JSON") != "1"
_last_progress = {"key": None, "at": 0.0}
GAME_STATUS = {"done": "готово", "no_data": "нет архива", "error": "ошибка"}


def _pretty(event: dict) -> str | None:
    kind = event.get("type")
    if kind == "log":
        return event.get("message")
    if kind == "error":
        return f"ОШИБКА: {event.get('message')}"
    if kind == "game" and event.get("status") in GAME_STATUS:
        line = f"  {event['game']:<16} {GAME_STATUS[event['status']]:<11} тиражей: {event.get('draws', 0)}"
        if event.get("added"):
            line += f" (+{event['added']})"
        if event.get("damaged"):
            line += f", неполных тиражей: {event['damaged']}"
        if event.get("legacy_conflicts"):
            line += f", расхождений со старыми файлами: {event['legacy_conflicts']}"
        if event.get("journal_checked"):
            line += f", сверено прогнозов: {event['journal_checked']}"
        if event["status"] != "done" and event.get("message"):
            line += f" — {event['message']}"
        return line
    if kind == "checkpoint":
        return f"  сохранён результат стадии «{event['stage']}»"
    if kind == "progress":
        key = event.get("stage") or event.get("game")
        now = time.time()
        if key == _last_progress["key"] and now - _last_progress["at"] < 10:
            return None
        _last_progress.update(key=key, at=now)
        done, total = event.get("done"), event.get("total")
        what = event.get("model") or event.get("note") or event.get("game") or ""
        stage = event.get("stage") or "проверка"
        count = f" {done}/{total}" if total else ""
        return f"  {stage}{count} {what}".rstrip()
    return None


def emit(event: dict) -> None:
    """Одно событие — одна строка. Блокировка обязательна: загрузка идёт в нескольких
    потоках, и без неё строки склеиваются (событие «готово» терялось)."""
    if PRETTY:
        text = _pretty(event)
        line = text + "\n" if text else ""
    else:
        line = "@@" + json.dumps(event, ensure_ascii=False, default=float) + "\n"
    if line:
        with _EMIT_LOCK:
            sys.stdout.write(line)
            sys.stdout.flush()


def say(text: str) -> None:
    """Итоговый текст для человека в терминале (в режиме событий не выводится)."""
    if PRETTY:
        print(text, flush=True)


def balls(blocks) -> str:
    return " | ".join(" ".join(str(v) for v in b) for b in blocks)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_json(path: Path, payload: dict) -> None:
    from lottery.fsutil import write_text
    write_text(path, json.dumps(payload, ensure_ascii=False, default=float))


def meta(data) -> dict:
    return {
        "version": __version__,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "game": data.game.slug,
        "title": data.game.title,
        "last_draw_no": data.draws[-1].no if data.draws else None,
        "format": data.fmt.describe(),
    }


def game_activity(data) -> dict:
    return activity(data.draws[-1].dt if data.draws else None, read_meta(data.game.slug).get("checked_at"))


def sorted_blocks(numbers) -> list[list[int]]:
    return [sorted(int(v) for v in b) for b in numbers]


def ordered_prediction(data, numbers, draw_no: int, mechanism: str | None = None) -> list[list[int]]:
    """Числа прогноза в предсказанном порядке выпадения (order.py); набор чисел не меняется."""
    from lottery import order
    try:
        return order.order_all(data, numbers, draw_no, mechanism)
    except Exception:  # noqa: BLE001 — порядок — эксперимент, прогноз важнее
        return numbers


def target_mechanism(data, target: dict) -> str | None:
    from lottery.mechanics import mechanism_of_draw
    if not target.get("date"):
        return None
    if target["date"].second:
        return "R"
    return mechanism_of_draw(data.game.slug, target["no"], target["date"].strftime("%d.%m.%Y %H:%M"))


def godmode_target(data, res: dict) -> None:
    """Прогноз режима Бога — на ближайший будущий тираж, числа — в порядке выпадения."""
    from lottery.journal import target_draw
    target = target_draw(data)
    mech = target_mechanism(data, target)
    res["next"].update({"no": target["no"], "mechanism": mech,
                        "numbers": ordered_prediction(data, res["next"]["numbers"], target["no"], mech)})


def journal_record(data, source: str, numbers, detail: str, draw_no: int | None = None,
                   mechanism: str | None = None, ordered: bool = True) -> None:
    """Прогноз в журнал — только для активной игры (иначе тираж не наступит). Номер тиража —
    ближайший будущий (journal.target_draw), если не задан; числа — в предсказанном порядке
    выпадения."""
    from lottery.journal import record, target_draw
    if data.draws and game_activity(data)["active"]:
        if draw_no is None:
            target = target_draw(data)
            draw_no, mechanism = target["no"], mechanism or target_mechanism(data, target)
        if ordered:
            numbers = ordered_prediction(data, numbers, draw_no, mechanism)
        record(data, source, [sorted(b) for b in numbers] if not ordered else numbers, detail,
               draw_no=draw_no, ordered=ordered)


def game_info(slug: str) -> dict:
    data = load_game_data(get_game(slug))
    draws = data.draws
    return {
        "activity": game_activity(data),
        "slug": slug,
        "title": data.game.title,
        "stoloto_url": data.game.stoloto_url,
        "draws_in_file": data.all_count,
        "draws_valid": data.T,
        "format": data.fmt.describe(),
        "supported": data.fmt.supported,
        "first": {"no": draws[0].no, "date": draws[0].date} if draws else None,
        "last": {"no": draws[-1].no, "date": draws[-1].date} if draws else None,
        "next_no": draws[-1].no + 1 if draws else None,
    }


def after_fetch(slugs: list[str] | None = None, log=None) -> dict:
    """После загрузки: правила игр и ближайшие тиражи, ожидаемый возврат, уведомления."""
    from lottery import notify
    from lottery import nextdraw, rules
    log = log or (lambda m: emit({"type": "log", "message": m}))
    try:
        rules.fetch(slugs, log=log)
    except Exception as exc:          # правила — дополнение, их сбой не должен ронять загрузку
        log(f"Правила игр не обновлены: {exc}")
    res = nextdraw.compute_all(slugs or local_slugs(), lambda s: load_game_data(get_game(s)))
    hot = nextdraw.to_notify(res)
    if hot:
        for r in hot:
            r["unpopular"] = unpopular_ticket(r["slug"])
        notify.send(notify.ev_message(hot), "ev")
    return res


def unpopular_ticket(slug: str) -> list[list[int]] | None:
    """Одна непопулярная комбинация для уведомления о высоком возврате (None — в игре не подобрать)."""
    from lottery.tickets import generate
    try:
        res = generate(load_game_data(get_game(slug)), count=1)
    except Exception:  # noqa: BLE001 — подсказка к уведомлению, не повод его не отправить
        return None
    return res["tickets"][0]["blocks"] if res.get("supported") and res.get("tickets") else None


def cmd_fetch(args) -> None:
    from lottery.stoloto import fetch_all
    slugs = args.game or None
    results = fetch_all(slugs, emit, workers=args.workers)
    emit({"type": "result", "results": results})
    done = [r for r in results.values() if r.get("status") == "done"]
    say(f"Загружено игр: {len(done)} из {len(results)}, тиражей всего: {sum(r.get('draws', 0) for r in done)}")
    nd = after_fetch(slugs)
    best = sorted(nd.values(), key=lambda r: -r["return"])[:3]
    if best:
        say("Ближайшие тиражи с наибольшим ожидаемым возвратом: " +
            "; ".join(f"{r['title']} №{r['number']} — {r['return']:.2f}" for r in best))


def cmd_rules(args) -> None:
    from lottery import rules
    res = rules.fetch(args.game or None, log=say, force=True)
    emit({"type": "result", **res})
    for slug in res["done"]:
        r = rules.load_rules(slug) or {}
        s = r.get("schedule") or {}
        kinds = " и ".join(k for k, v in (("лототрон", s.get("lototron")), ("ГСЧ", s.get("rng"))) if v) or "способ не указан"
        say(f"{slug:<16} {kinds}; таблица выигрышей: {len(r.get('table') or [])} строк"
            + (f" ({r['table_error']})" if r.get("table_error") else ""))
    say(f"Правила сохранены в data\\rules ({len(res['done'])} игр)" + (f", ошибки: {', '.join(res['failed'])}" if res["failed"] else ""))


def cmd_nextdraw(args) -> None:
    from lottery import nextdraw
    res = nextdraw.compute_all(args.game or local_slugs(), lambda s: load_game_data(get_game(s)))
    emit({"type": "result", "games": res})
    for r in sorted(res.values(), key=lambda r: -r["return"]):
        say(f"{r['title']:<22} №{r['number']}  возврат {r['return']:.2f}"
            f" (без суперприза {r['return_without_super']:.2f}), суперприз {r['super_prize']:,.0f} ₽".replace(",", " "))


def cmd_scan(args) -> None:
    from lottery.scan import run_scan
    payload = run_scan(progress=lambda p: emit({"type": "progress", **p}))
    emit({"type": "result", "path": str(results_dir() / "scan.json"), "recomputed": payload["recomputed"]})
    for g in payload["games"]:
        say(f"{g['title']:<22} {g['draws']:>7} тир.  {g['verdict']}")
    say(f"Пересчитано игр: {payload['recomputed']} (остальные без изменений, взяты из прошлой проверки)")


EVAL_MAX = 60_000
HEAVY_MAX_AGE_H = 12      # тесты случайности и проверки — не чаще, если архив почти не изменился
HEAVY_GROWTH = 0.02       # …и вырос меньше чем на 2%


def heavy_cache(slug: str, data) -> dict | None:
    """Прошлый отчёт, из которого можно взять тяжёлые проверки (тесты случайности, лототрон/ГСЧ,
    порядок, популярность, проверки хаоса): несколько новых тиражей к десяткам тысяч их не
    меняют, а пересчёт занимал до 2/3 времени анализа. Прогнозы считаются заново всегда."""
    prev = _read_json(results_dir(slug) / "analysis.json")
    heavy = (prev or {}).get("heavy") or {}
    if not prev or prev.get("version") != __version__ or not heavy.get("at"):
        return None
    try:
        age_h = (datetime.now() - datetime.fromisoformat(heavy["at"])).total_seconds() / 3600
    except ValueError:
        return None
    if age_h > HEAVY_MAX_AGE_H or not heavy["draws"] <= data.T <= heavy["draws"] * (1 + HEAVY_GROWTH):
        return None
    return prev


def analyze_game(slug: str, progress=None, full: bool = True) -> dict:
    """Тесты случайности + сравнение методов + прогноз в журнал. Возвращает сохранённый отчёт.
    full=False (автозапуск) — тяжёлые проверки берутся из прошлого отчёта, если архив почти
    не изменился (heavy_cache); прогнозы и их проверка на истории считаются всегда."""
    from lottery.evaluate import evaluate_game
    from lottery.journal import reconcile
    from lottery.stats import descriptive, finalize_scan, game_randomness
    data = load_game_data(get_game(slug))
    if not data.fmt.supported:
        raise SystemExit(f"Формат игры не поддерживается: {data.fmt.reason}")
    t0 = time.time()
    if progress:
        progress({"type": "progress", "stage": "tests", "done": 0, "total": 1})
    cache = None if full else heavy_cache(slug, data)
    from lottery import mechanics
    if cache:
        randomness = cache["randomness"]
        mech = randomness["mechanisms"]
        heavy = {**cache["heavy"], "reused": True}
    else:
        randomness = finalize_scan([game_randomness(data)])[0]
        mech = mechanics.mechanism_report(data)
        randomness["mechanisms"] = mech
        randomness["detectable"] = mechanics.detectable(data)
        heavy = {"draws": data.T, "at": datetime.now().isoformat(timespec="seconds"), "reused": False}
    drift = mechanics.save_drift(data)
    if drift.get("new_alarms"):
        from lottery import notify
        notify.send(notify.drift_message(data.game.title, drift["new_alarms"]), "drift")
    reconcile(data.game)
    # у быстрых игр до 190 тыс. тиражей: методы проверяются на последних EVAL_MAX — точности
    # проверки хватает с запасом (контрольный отрезок — 20 тыс. тиражей), а анализ втрое быстрее
    eval_data = data if data.T <= EVAL_MAX else mechanics.subset(data, np.arange(data.T - EVAL_MAX, data.T))
    evaluation = evaluate_game(eval_data, progress=(lambda p: progress({"type": "progress", **p})) if progress else None)
    if eval_data is not data:
        evaluation["limited_to"] = EVAL_MAX
    from lottery.journal import target_draw
    target = target_draw(data)
    mech_next = target_mechanism(data, target)
    if evaluation.get("status") == "ok":
        evaluation["target"] = {"no": target["no"], "how": target["how"], "mechanism": mech_next,
                                "date": target["date"].isoformat(timespec="minutes") if target["date"] else None}
        # прогнозы — в предсказанном порядке выпадения (тот же, что уйдёт в журнал)
        evaluation["next_prediction"]["numbers"] = ordered_prediction(
            data, evaluation["next_prediction"]["numbers"], target["no"], mech_next)
        evaluation["next_consensus"] = ordered_prediction(data, evaluation["next_consensus"], target["no"], mech_next)
        journal_record(data, "analysis_best", evaluation["next_prediction"]["numbers"],
                       evaluation["next_prediction"]["model"], draw_no=target["no"], mechanism=mech_next)
        journal_record(data, "analysis_consensus", evaluation["next_consensus"], "", draw_no=target["no"],
                       mechanism=mech_next)
        least = evaluation.get("least") or {}
        if least.get("status") == "ok":
            # наименее вероятные: порядок выпадения для них смысла не имеет — числа по возрастанию
            journal_record(data, "least", least["next_prediction"]["numbers"], least["next_prediction"]["model"],
                           draw_no=target["no"], mechanism=mech_next, ordered=False)
    if cache:
        popularity = cache.get("popularity") or {}
    else:
        from lottery.popularity import fit as fit_popularity
        popularity = fit_popularity(data)
        if popularity.get("available"):
            save_json(results_dir(slug) / "popularity.json", popularity)
    if evaluation.get("status") == "ok":
        evaluation["detectable_edge_pct"] = mechanics.method_edge(data, evaluation)
        if mech["mixed"]:
            if cache and (cache.get("evaluation") or {}).get("by_mechanism") is not None:
                evaluation["by_mechanism"] = cache["evaluation"]["by_mechanism"]
            else:
                if progress:
                    progress({"type": "progress", "stage": "mechanisms", "done": 0, "total": 1})
                evaluation["by_mechanism"] = mechanics.evaluate_by_mechanism(data)
    chaos_res = run_chaos(data, progress, target, reuse=(cache or {}).get("chaos"))
    from lottery import order
    if cache and cache.get("order_check") is not None:
        order_check = cache["order_check"]
    else:
        try:
            order_check = {m or "all": order.backtest(data, m) for m in (["L", "R"] if mech["mixed"] else [None])}
        except Exception as exc:  # noqa: BLE001
            order_check = {"error": str(exc)}
    from lottery import repeats
    if cache and cache.get("repeats") is not None:
        repeats_res = cache["repeats"]
    else:
        if progress:
            progress({"type": "progress", "stage": "repeats", "done": 0, "total": 1, "model": "повторы по позициям"})
        try:
            repeats_res = repeats.analyze(data)
        except Exception as exc:  # noqa: BLE001 — эксперимент не должен ронять анализ
            repeats_res = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    payload = {**meta(data), "seconds": round(time.time() - t0, 1), "randomness": randomness, "drift": drift,
               "descriptive": descriptive(data), "evaluation": evaluation, "popularity": popularity,
               "chaos": chaos_res, "order_check": order_check, "repeats": repeats_res, "heavy": heavy}
    save_json(results_dir(slug) / "analysis.json", payload)
    return payload


def run_chaos(data, progress=None, target: dict | None = None, reuse: dict | None = None) -> dict:
    """«Порядок из хаоса» по способам розыгрыша; прогноз на ближайший будущий тираж — в журнал."""
    from lottery import chaos
    from lottery.journal import target_draw
    target = target or target_draw(data)
    res = chaos.analyze(data, progress=(lambda p: progress({"type": "progress", **p})) if progress else None,
                        target=target, reuse=reuse)
    nxt = res.get("next") or {}
    if nxt.get("numbers"):
        mech = nxt.get("mechanism") if nxt.get("mechanism") in ("L", "R") else None
        nxt["numbers"] = ordered_prediction(data, nxt["numbers"], nxt["draw_no"], mech)
        if nxt.get("consensus"):
            nxt["consensus"] = ordered_prediction(data, nxt["consensus"], nxt["draw_no"], mech)
        journal_record(data, "chaos", nxt["numbers"], f"{nxt['model']} · {nxt['title']}", draw_no=nxt["draw_no"],
                       mechanism=mech)
    return res


def cmd_chaos(args) -> None:
    """Только «порядок из хаоса» (быстрее полного анализа); результат дописывается в analysis.json."""
    data = load_game_data(get_game(args.game))
    if not data.fmt.supported:
        raise SystemExit(f"Формат игры не поддерживается: {data.fmt.reason}")
    res = run_chaos(data, emit)
    path = results_dir(args.game) / "analysis.json"
    payload = _read_json(path) or {**meta(data), "evaluation": {"status": "none"}}
    payload["chaos"] = res
    save_json(path, payload)
    emit({"type": "result", "path": str(path)})
    say(f"\n{data.game.title} — порядок из хаоса\n{res['conclusion']}")
    for g in res["groups"].values():
        say(f"  {g['title']}: {g['verdict']}")
    nxt = res.get("next") or {}
    if nxt.get("numbers"):
        say(f"Прогноз на тираж №{nxt['draw_no']} ({nxt['title']}; {nxt['reason']}), «{nxt['model']}»: "
            f"{balls(nxt['numbers'])}")
    else:
        say(f"Прогноз на тираж №{nxt.get('draw_no')}: нет — {nxt.get('reason', '')}")


def cmd_repeats(args) -> None:
    """Гипотезы о повторах по позициям выпадения (все задержки и сдвиги)."""
    from lottery import repeats
    data = load_game_data(get_game(args.game))
    res = repeats.analyze(data)
    path = results_dir(args.game) / "analysis.json"
    payload = _read_json(path)
    if payload:
        payload["repeats"] = res
        save_json(path, payload)
    emit({"type": "result", "repeats": res})
    say(f"\n{data.game.title} — повторы по позициям выпадения")
    if not res.get("available"):
        say(res.get("reason", ""))
        return
    titles = {"L": "лототрон", "R": "ГСЧ", "all": "все тиражи"}
    for m, rows in res["groups"].items():
        for r in rows:
            say(f"  {titles[m]}, {r['block']}: {r['draws']} тиражей, проверено {r['tests']:,} пар (задержка, сдвиг)"
                .replace(",", " "))
            for h in r["hypotheses"]:
                shift = (f", сдвиг позиции {h['shift_pos']:+d}" if h["shift_pos"] else "") + \
                        (f", сдвиг числа {h['shift_num']:+d}" if h["shift_num"] else "")
                say(f"    {h['title']}: лучшая задержка {h['lag']}{shift} — {h['observed']} при ожидаемых "
                    f"{h['expected']:.1f}, p с поправкой {h['p_adjusted']:.3g}"
                    + (" — ПОВТОРЯЕТСЯ" if h["replicated"] else ""))
    say(res["verdict"])


def cmd_analyze(args) -> None:
    payload = analyze_game(args.game, progress=emit)
    path = results_dir(args.game) / "analysis.json"
    emit({"type": "result", "path": str(path)})
    evaluation, randomness = payload["evaluation"], payload["randomness"]
    say(f"\n{payload['title']}: {payload['format']}\nСлучайность: {randomness['verdict']}")
    if evaluation.get("status") == "ok":
        say(f"Методы: {evaluation['conclusion']}")
        say(f"Прогноз на тираж №{(evaluation.get('target') or {}).get('no') or payload['last_draw_no'] + 1} "
            f"(«{evaluation['next_prediction']['model']}»): "
            f"{balls(evaluation['next_prediction']['numbers'])}")
        say(f"Консенсус методов: {balls(evaluation['next_consensus'])}")
    ch = (payload.get("chaos") or {}).get("next") or {}
    if ch.get("numbers"):
        say(f"Порядок из хаоса ({ch['title']}, «{ch['model']}»): {balls(ch['numbers'])}")
    else:
        say(evaluation.get("message", ""))
    say(f"Полный отчёт: {path}")


# ── Автозапуск ─────────────────────────────────────────────────────────────

def pid_alive(pid: int) -> bool:
    """Жив ли процесс. На Windows os.kill(pid, 0) ЗАВЕРШАЕТ процесс, поэтому через WinAPI."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def auto_once(args) -> dict:
    """Один цикл: загрузка тиражей → сверка журнала → анализ активных игр (прогноз в журнал)
    → при необходимости режим Бога → проверка игр на случайность."""
    from lottery.games import data_dir
    from lottery.stoloto import fetch_all
    status_path = data_dir() / "auto_status.json"
    log_path = data_dir() / "logs" / "auto.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(text: str) -> None:
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        emit({"type": "log", "message": text})

    from lottery import notify
    predictions: dict[str, dict] = {}
    started = datetime.now().isoformat(timespec="seconds")
    status = {"started_at": started, "finished_at": None, "status": "running", "pid": os.getpid(), "games": {}}
    save_json(status_path, status)
    log("Автозапуск: начало")
    status["backup"] = housekeeping(log)

    def stage(text: str, game: str | None = None) -> None:
        """Что цикл делает сейчас — видно на главной и по auto_status.json, если цикл завис."""
        status["current"] = {"stage": text, "game": game, "since": datetime.now().isoformat(timespec="seconds")}
        save_json(status_path, status)

    try:
        stage("загрузка тиражей")
        fetched = {} if args.skip_fetch else fetch_all(args.game or None, emit, workers=2)
        for slug, r in fetched.items():
            status["games"].setdefault(slug, {}).update(
                {"fetch": r.get("status"), "added": r.get("added", 0), "journal_checked": r.get("journal_checked", 0)})
            if r.get("status") == "error":
                log(f"{slug}: ошибка загрузки — {r.get('message')}")
        if not args.skip_fetch:
            stage("правила игр и ближайшие тиражи")
            nd = after_fetch(args.game or None, log=log)
            status["nextdraw"] = {s: round(r["return"], 3) for s, r in nd.items()}
        status["my_tickets"] = settle_my_tickets(log)
        slugs = args.game or local_slugs()
        from lottery.drawfile import same_draws
        seen: dict[str, list] = {}
        for slug in slugs:
            try:
                data = load_game_data(get_game(slug))
            except ValueError:
                continue
            g = status["games"].setdefault(slug, {})
            twin = next((s for s, d in seen.items() if same_draws(d, data.draws)), None)
            seen[slug] = data.draws
            if twin:
                g["skipped"] = f"те же тиражи, что у {twin}"
                continue
            if not data.fmt.supported or not data.draws:
                g["skipped"] = "формат не поддерживается" if data.draws else "нет тиражей"
                continue
            if not game_activity(data)["active"]:
                g["skipped"] = "игра устарела"
                continue
            if data.T < MIN_AUTO_DRAWS:
                # прогнозы всех методов (Л, К, Х, Б) нужны хотя бы 300 тиражей — игру не анализируем
                g["skipped"] = f"мало тиражей ({data.T} < {MIN_AUTO_DRAWS})"
                continue
            prev = _read_json(results_dir(slug) / "analysis.json")
            if prev and prev.get("last_draw_no") == data.draws[-1].no and prev.get("version") == __version__:
                g["skipped"] = "новых тиражей нет — прогноз уже в журнале"
                continue
            stage("анализ", slug)
            t_game = time.time()
            payload = analyze_game(slug, full=False)
            ev = payload["evaluation"]
            g["analyzed"] = ev.get("status") == "ok"
            g["seconds"] = round(time.time() - t_game, 1)
            g["next_no"] = (ev.get("target") or {}).get("no") or data.draws[-1].no + 1
            if g["analyzed"]:
                predictions[slug] = {"title": data.game.title, "next_no": g["next_no"],
                                     "numbers": ev["next_prediction"]["numbers"],
                                     "consensus": ev["next_consensus"]}
                if (ev.get("least") or {}).get("status") == "ok":
                    predictions[slug]["least"] = sorted_blocks(ev["least"]["next_prediction"]["numbers"])
                ch = (payload.get("chaos") or {}).get("next") or {}
                if ch.get("numbers"):
                    predictions[slug]["chaos"] = {"numbers": ch["numbers"], "title": ch["title"]}
            if g["analyzed"]:
                log(f"{slug}: анализ готов за {g['seconds']:.0f} с, прогноз на тираж №{g['next_no']} записан в журнал")
            else:
                log(f"{slug}: анализ готов, прогноза нет — {ev.get('message', 'мало тиражей')}")
        if args.godmode_budget > 0 and predictions:
            auto_godmode(args, predictions, stage, log)
        if not args.skip_scan:
            stage("проверка игр на случайность")
            cmd_scan_quiet()
        status.pop("current", None)
        status["seconds"] = round((datetime.now() - datetime.fromisoformat(started)).total_seconds())
        status["status"] = "done"
        log("Автозапуск: готово")
        notify.send(notify.auto_message(status, predictions, recommend(predictions)), "auto")
    except Exception as exc:  # статус ошибки должен попасть в файл, иначе интерфейс покажет «идёт»
        status["status"] = "error"
        status["error"] = f"{type(exc).__name__}: {exc}"
        log(f"Автозапуск: ошибка — {status['error']}")
        notify.send(f"<b>Автозапуск: ошибка</b>\n{notify.esc(status['error'])}", "errors")
        raise
    finally:
        status["finished_at"] = datetime.now().isoformat(timespec="seconds")
        save_json(status_path, status)
    return status


STUCK_HOURS = 3
from lottery.games import MIN_FORECAST_DRAWS as MIN_AUTO_DRAWS  # noqa: E402
GODMODE_PER_CYCLE = 6       # режим Бога: не больше стольких игр за цикл (по 2 одновременно)
GODMODE_MAX_DRAWS = 60_000


def auto_godmode(args, predictions: dict, stage, log) -> None:
    """Режим Бога в автозапуске: для игр с новыми тиражами, у которых прошлый запуск старше
    args.godmode_every часов (самые давние — первыми, не больше GODMODE_PER_CYCLE за цикл, по
    два процесса одновременно), args.godmode_budget минут на игру. Для остальных — прогноз
    модели-лидера прошлого запуска на новые тиражи (без перебора), чтобы у каждой игры был
    прогноз Б."""
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from lottery.godmode import auto_run, predict_leader
    from lottery.mechanics import subset
    due = []
    now = datetime.now()
    busy = godmode_all_running()
    if busy:
        log("режим Бога: идёт всеобъемлющий режим — новые запуски пропускаю, прогноз Б — лидер прошлого запуска")
    for slug in predictions:
        if busy or _lock_alive(results_dir(slug) / "godmode.lock"):
            continue
        gm = _read_json(results_dir(slug) / "godmode.json") or {}
        try:
            age_h = (now - datetime.fromisoformat(gm["generated_at"])).total_seconds() / 3600
        except (KeyError, ValueError, TypeError):
            age_h = float("inf")
        if age_h >= args.godmode_every or gm.get("version") != __version__:
            due.append((age_h, slug))
    run_now = [s for _, s in sorted(due, reverse=True)[:GODMODE_PER_CYCLE]]
    results: dict[str, dict] = {}
    if run_now:
        stage("режим Бога", ", ".join(run_now))
        with ProcessPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(auto_run, s, args.godmode_budget, GODMODE_MAX_DRAWS): s for s in run_now}
            for fut in as_completed(futures):
                slug = futures[fut]
                try:
                    results[slug] = fut.result()
                except Exception as exc:  # noqa: BLE001 — одна игра не должна ронять цикл
                    log(f"{slug}: режим Бога — ошибка {type(exc).__name__}: {exc}")
    for slug, p in predictions.items():
        data = load_game_data(get_game(slug))
        res = results.get(slug)
        if res:
            numbers, detail = res["next"]["numbers"], (f"{res['next']['strategy']}"
                                                        + (f" → {res['next']['model']}" if res["next"]["model"] else ""))
            log(f"{slug}: режим Бога за {res['elapsed_seconds']:.0f} с, экспертов {res['experts']}, "
                f"прогноз на тираж №{p['next_no']} записан в журнал")
        else:
            gm = _read_json(results_dir(slug) / "godmode.json") or {}
            leader = (gm.get("next") or {}).get("leader")
            part = data if data.T <= GODMODE_MAX_DRAWS else subset(data, np.arange(data.T - GODMODE_MAX_DRAWS, data.T))
            try:
                numbers = predict_leader(part, leader)
            except Exception:  # noqa: BLE001
                numbers = None
            if not numbers:
                continue
            detail = f"лидер за всю историю «{leader['title']}» (режим Бога {gm['generated_at'][5:16].replace('T', ' ')})"
        target = {"no": p["next_no"]}
        mech = (_read_json(results_dir(slug) / "analysis.json") or {}).get("evaluation", {}).get("target", {}).get("mechanism")
        numbers = ordered_prediction(data, numbers, target["no"], mech)
        if res:
            res["next"].update({"no": target["no"], "numbers": numbers, "mechanism": mech})
            save_json(results_dir(slug) / "godmode.json", {**meta(data), **res, "auto": True})
        journal_record(data, "godmode", numbers, detail, draw_no=target["no"], mechanism=mech)
        p["godmode"] = numbers


def housekeeping(log) -> dict:
    """Раз в сутки — архив журнала и билетов; файлы убранных из программы игр — удалить
    (их журнал и билеты сначала в архив). Сбой здесь не останавливает цикл."""
    from lottery import backup, notify
    try:
        made = backup.daily()
        if made:
            log(f"Резервная копия журнала: {made['path']} ({made['bytes'] / 1e6:.1f} МБ)"
                + (f", удалены старые: {', '.join(made['removed'])}" if made["removed"] else ""))
    except Exception as exc:  # noqa: BLE001
        log(f"Резервная копия не сделана: {type(exc).__name__}: {exc}")
        notify.send(f"<b>Резервная копия журнала не сделана</b>\n{notify.esc(f'{type(exc).__name__}: {exc}')}", "errors")
    try:
        gone = backup.remove_excluded()
        if gone["games"]:
            mb = sum(gone["games"].values()) / 1e6
            log(f"Удалены файлы убранных игр ({', '.join(gone['games'])}): {mb:.0f} МБ"
                + (f"; их журнал и билеты — в {gone['archive']}" if gone["archive"] else ""))
    except Exception as exc:  # noqa: BLE001
        log(f"Файлы убранных игр не удалены: {type(exc).__name__}: {exc}")
    try:
        return backup.info()
    except OSError:
        return {}


def settle_my_tickets(log) -> dict:
    """Сверка купленных билетов с загруженными тиражами и сообщение в Telegram о сверенных."""
    from lottery import mytickets, notify
    fresh: list[tuple[str, list[dict]]] = []
    for slug in mytickets.slugs():
        try:
            got = mytickets.settle(get_game(slug))
        except Exception as exc:  # noqa: BLE001 — одна игра не должна ронять цикл
            log(f"{slug}: мои билеты не сверены — {type(exc).__name__}: {exc}")
            continue
        if got:
            fresh.append((get_game(slug).title, got))
            won = sum(t["won"] or 0 for t in got)
            log(f"{slug}: сверено моих билетов {len(got)}, выигрыш {won:,.0f} ₽".replace(",", " "))
    total = mytickets.summary([t for s in mytickets.slugs() for t in mytickets.load(s)["tickets"]])
    if fresh:
        msg = notify.tickets_message(fresh, total)
        if msg:
            notify.send(msg, "tickets")
    return {"checked_now": sum(len(t) for _, t in fresh), **{k: total[k] for k in ("total", "pending", "spent", "won")}}


def recommend(predictions: dict, top: int = 3) -> list[dict]:
    """Рекомендации для рассылки: игры с лучшим ожидаемым возвратом ближайшего тиража (и шанс
    выиграть хоть что-то), числа — метода, который по журналу этой игры устойчиво лучше
    случайного выбора (последовательное p < 0,05), иначе консенсус; проверка на непопулярность."""
    from lottery import journal, tickets
    nd = (_read_json(results_dir() / "nextdraw.json") or {}).get("games", {})
    rows = []
    for slug, p in predictions.items():
        r = nd.get(slug)
        if not r:
            continue
        rows.append((r["return"], slug, r))
    out = []
    for ret, slug, r in sorted(rows, reverse=True)[:top]:
        p = predictions[slug]
        best = journal.proven_source(slug)
        key = best["source"] if best else "analysis_consensus"
        numbers = {"analysis_best": p.get("numbers"), "analysis_consensus": p.get("consensus"),
                   "chaos": (p.get("chaos") or {}).get("numbers"), "godmode": p.get("godmode")}.get(key) \
            or p.get("consensus") or p.get("numbers")
        try:
            check = tickets.check(load_game_data(get_game(slug)), [sorted(b) for b in numbers])
            popular = bool(check.get("valid") and check.get("score", 0) > 0)
        except Exception:  # noqa: BLE001
            popular = None
        out.append({"slug": slug, "title": p["title"], "next_no": p["next_no"], "return": ret,
                    "usual_return": r.get("usual_return"), "p_win": r.get("p_win"), "source": key,
                    "proven": best, "numbers": numbers, "popular": popular})
    return out


def auto_log(text: str) -> None:
    from lottery.games import data_dir
    path = data_dir() / "logs" / "auto.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}\n")


def stop_stuck(pid: int) -> bool:
    """Останавливает зависший цикл автозапуска — только если это действительно lp.py (номер
    процесса мог достаться другой программе)."""
    try:
        if os.name == "nt":
            cmd = (f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine")
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                                 capture_output=True, text=True, timeout=30).stdout
            if "lp.py" not in out or " auto" not in out:
                return False
            return subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                                  timeout=20).returncode == 0
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").replace("\0", " ")
        if "lp.py" not in cmdline or " auto" not in cmdline:
            return False
        os.kill(pid, 15)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def cmd_auto(args) -> None:
    from lottery.games import data_dir
    lock = data_dir() / "auto.lock"
    try:
        held = json.loads(lock.read_text(encoding="utf-8"))
        pid = int(held.get("pid", 0))
        if pid_alive(pid):
            started = held.get("started_at")
            age_h = (datetime.now() - datetime.fromisoformat(started)).total_seconds() / 3600 if started else 0.0
            if age_h < STUCK_HOURS or args.every:
                auto_log(f"Автозапуск: предыдущий цикл (процесс {pid}) ещё идёт — пропускаю")
                say("Автозапуск уже выполняется — пропускаю.")
                emit({"type": "result", "skipped": True})
                return
            # цикл идёт дольше STUCK_HOURS часов — завис (например, после сна компьютера)
            stopped = stop_stuck(pid)
            auto_log(f"Автозапуск: предыдущий цикл (процесс {pid}) идёт {age_h:.1f} ч — считаю зависшим"
                     + (", процесс остановлен" if stopped else ", остановить не удалось"))
    except (OSError, ValueError, KeyError):
        pass
    save_json(lock, {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds")})
    try:
        while True:
            status = auto_once(args)
            done = [s for s, g in status["games"].items() if g.get("analyzed")]
            say(f"Готово: прогнозы для {len(done)} активных игр записаны в журнал.")
            if not args.every:
                break
            nxt = datetime.now() + timedelta(hours=args.every)
            say(f"Следующий запуск: {nxt:%d.%m.%Y %H:%M}")
            time.sleep(args.every * 3600)
    finally:
        lock.unlink(missing_ok=True)
    emit({"type": "result", "status": status})


def cmd_scan_quiet() -> None:
    from lottery.scan import run_scan
    run_scan()


# ── Шансы, билеты, экспорт ─────────────────────────────────────────────────

def cmd_odds(args) -> None:
    from lottery.odds import odds_table, save_prizes
    if args.set_prizes:
        raw = json.loads(Path(args.set_prizes).read_text(encoding="utf-8"))
        save_prizes(args.game, raw.get("price"), raw.get("prizes") or {})
    slugs = args.game and [args.game] or local_slugs()
    tables = {}
    for slug in slugs:
        try:
            data = load_game_data(get_game(slug))
        except ValueError:
            continue
        if not data.draws:
            continue
        t = odds_table(data)
        t["active"] = game_activity(data)["active"]
        tables[slug] = t
    emit({"type": "result", "odds": tables})
    for t in tables.values():
        if not t["supported"]:
            say(f"{t['title']}: {t['reason']}")
            continue
        line = f"{t['title']:<20} главный приз ({t['jackpot']['key']}): 1 из {t['jackpot']['one_in']:,.0f}".replace(",", " ")
        if t["return_per_ruble"] is not None:
            line += f"; возврат с рубля по введённым призам: {t['return_per_ruble']:.2f}"
        say(line)


def cmd_tickets(args) -> None:
    from lottery.tickets import check, generate
    data = load_game_data(get_game(args.game))
    if args.check:
        blocks = [[int(v) for v in part.replace(" ", "").split(",") if v] for part in args.check.split("|")]
        res = check(data, blocks)
        emit({"type": "result", "check": res})
        if res.get("valid"):
            for b in res["blocks"]:
                for f in b["flags"]:
                    say(f"  {b['block']}: {f['text']}")
            say(res["verdict"])
        else:
            say(res.get("reason", ""))
        return
    res = generate(data, count=args.count, seed=args.seed)
    emit({"type": "result", "tickets": res})
    if not res["supported"]:
        say(res["reason"])
        return
    for i, t in enumerate(res["tickets"], 1):
        say(f"{i:>2}. {balls(t['blocks'])}")
    if res.get("accepted_share") is not None:
        say(f"Фильтр проходит {res['accepted_share']:.0%} комбинаций. Шанс выигрыша у них тот же, что у любых других.")


def cmd_mytickets(args) -> None:
    """Мои билеты: list | add | remove | won."""
    from lottery import mytickets
    if args.action == "list":
        res = mytickets.overview([args.game] if args.game else None)
        if args.game:
            data = load_game_data(get_game(args.game))
            from lottery.journal import target_draw
            res["form"] = {"next_no": target_draw(data)["no"] if data.draws else None,
                           "price": mytickets.current_price(data),
                           "blocks": [{"name": s.name, "count": s.count, "lo": s.lo, "hi": s.hi, "mode": s.mode,
                                       "flexible": s.mode == "set" and s.drawn > s.count} for s in data.fmt.blocks]}
        emit({"type": "result", **res})
        t = res["summary"]
        say(f"Билетов: {t['total']}, сверено {t['checked']}, ждут тиража {t['pending']}; потрачено "
            f"{t['spent']:,.0f} ₽, выиграно {t['won']:,.0f} ₽".replace(",", " ")
            + (f", возврат {t['return']:.2f} с рубля" if t["return"] is not None else ""))
        for g in res["games"]:
            for x in g["tickets"][:20]:
                won = mytickets.won_of(x)
                state = ("ждёт тиража" if x["status"] == "pending" else
                         f"угадано {x['hits']}, " + ("выплата неизвестна" if won is None else f"выигрыш {won:,.0f} ₽".replace(",", " ")))
                say(f"  {g['title']} №{x['draw_no']}: {balls(x['numbers'])} — {state}")
        return
    if not args.game:
        raise SystemExit("укажите --game")
    if args.action == "add":
        data = load_game_data(get_game(args.game))
        try:
            added = mytickets.add(data, mytickets.parse(args.numbers or ""), draw_no=args.draw, draws=args.draws,
                                  price=args.price, note=args.note or "")
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        emit({"type": "result", "added": added})
        say(f"Внесено билетов: {len(added)}, тиражи №{added[0]['draw_no']}–{added[-1]['draw_no']}")
        return
    if not args.id:
        raise SystemExit("укажите --id")
    if args.action == "remove":
        ok = mytickets.remove(args.game, args.id)
        if not ok:
            raise SystemExit("билет не найден")
        emit({"type": "result", "removed": args.id})
        say("Билет удалён")
        return
    try:
        t = mytickets.set_won(args.game, args.id, None if args.won is None or args.won < 0 else args.won)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not t:
        raise SystemExit("билет не найден")
    emit({"type": "result", "ticket": t})
    say("Выигрыш записан")


def cmd_backup(args) -> None:
    """Резервные копии журнала и билетов: list | make | restore; cleanup — файлы убранных игр."""
    from lottery import backup
    if args.action == "make":
        p = backup.make()
        backup.rotate()
        emit({"type": "result", "path": str(p)})
        say(f"Архив: {p}")
    elif args.action == "restore":
        if not args.name:
            raise SystemExit("укажите имя архива: lp.bat backup restore lottery-backup-ГГГГ-ММ-ДД.zip")
        try:
            res = backup.restore(args.name)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        emit({"type": "result", **res})
        say(f"Восстановлено файлов: {len(res['restored'])}. Прежнее состояние сохранено в {res['before']}")
    elif args.action == "cleanup":
        res = backup.remove_excluded()
        emit({"type": "result", **res})
        say("Файлов убранных игр нет" if not res["games"] else
            f"Удалено {sum(res['games'].values()) / 1e6:.0f} МБ: {', '.join(res['games'])}"
            + (f"; журнал и билеты этих игр — в {res['archive']}" if res["archive"] else ""))
    else:
        items = backup.listing()
        emit({"type": "result", "dir": str(backup.backup_dir()), "items": items})
        say(f"Папка: {backup.backup_dir()}")
        for i in items:
            say(f"  {i['name']}  {i['bytes'] / 1e6:.1f} МБ  {i['modified'].replace('T', ' ')}")


def cmd_export(args) -> None:
    from lottery.export import KINDS, to_csv, to_xlsx
    game = get_game(args.game)
    out = Path(args.out) if args.out else results_dir(args.game) / (
        f"{args.game}.xlsx" if args.format == "xlsx" else f"{args.game}_{args.what}.csv")
    try:
        if args.format == "xlsx":
            to_xlsx(game, out, None if args.what == "all" else [args.what])
        else:
            if args.what == "all":
                raise ValueError("Для CSV укажите одну таблицу: --what " + "|".join(KINDS))
            to_csv(game, args.what, out)
    except ValueError as exc:
        raise SystemExit(str(exc))
    emit({"type": "result", "path": str(out)})
    say(f"Сохранено: {out}")


def _write_json_quiet(path: Path, payload: dict) -> None:
    try:
        save_json(path, payload)
    except OSError:
        pass


MAX_GODMODE_MIN = 480.0     # режим Бога работает до исчерпания перебора, но не дольше 8 часов


def cmd_godmode(args) -> None:
    from lottery.godmode import run_godmode
    data = load_game_data(get_game(args.game))
    if not data.fmt.supported:
        raise SystemExit(f"Формат игры не поддерживается: {data.fmt.reason}")
    budget = min(max(args.budget, 1.0), MAX_GODMODE_MIN)
    folder = results_dir(args.game)
    path = folder / "godmode.json"
    lock = folder / "godmode.lock"
    if _lock_alive(lock):
        held = _read_json(lock) or {}
        raise SystemExit("По этой игре уже идёт " + ("всеобъемлющий режим Бога" if held.get("comprehensive")
                                                     else "режим Бога") + " — дождитесь окончания или остановите его")
    progress_file = folder / "godmode.progress.json"
    base = meta(data)
    folder.mkdir(parents=True, exist_ok=True)
    save_json(lock, {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds"),
                     "budget": budget, "resume": bool(args.resume)})
    last_write = [0.0]

    def on_progress(p: dict) -> None:
        emit({"type": "progress", **p})
        if time.time() - last_write[0] > 2:      # для интерфейса, если запуск идёт вне приложения
            _write_json_quiet(progress_file, {**p, "updated_at": datetime.now().isoformat(timespec="seconds")})
            last_write[0] = time.time()

    from lottery.journal import reconcile
    reconcile(data.game)

    def checkpoint(res: dict) -> None:
        godmode_target(data, res)
        save_json(path, {**base, **res})
        journal_record(data, "godmode", res["next"]["numbers"],
                       f"{res['next']['strategy']}" + (f" → {res['next']['model']}" if res["next"]["model"] else ""),
                       draw_no=res["next"]["no"], mechanism=res["next"].get("mechanism"))
        emit({"type": "checkpoint", "stage": res["stage"], "complete": res["complete"]})

    try:
        res = run_godmode(data, budget, on_progress=on_progress, on_checkpoint=checkpoint,
                          state_path=folder / "godmode_state.npz", resume=args.resume)
    except ValueError as exc:
        raise SystemExit(str(exc))
    finally:
        for f in (lock, progress_file):
            f.unlink(missing_ok=True)
    emit({"type": "result", "path": str(path)})
    from lottery import notify
    notify.send(notify.godmode_message(data.game.title, res), "godmode")
    say(f"\n{res['verdict']}\nПрогноз на тираж №{res['next']['no']}: {balls(res['next']['numbers'])}"
        f"\nЭкспертов: {res['experts']}, время: {res['elapsed_seconds']:.0f} с"
        + (" (перебор исчерпан)" if res.get("exhausted") else " (можно продолжить: --resume)")
        + f". Отчёт: {path}")


GODMODE_ALL_FROM = 1000


def godmode_all_file() -> Path:
    return results_dir() / "godmode_all.json"


def _lock_alive(path: Path) -> int | None:
    """PID из lock-файла, если процесс жив и это не мы."""
    held = _read_json(path) or {}
    try:
        pid = int(held.get("pid", 0))
    except (TypeError, ValueError):
        return None
    return pid if pid and pid != os.getpid() and pid_alive(pid) else None


def godmode_all_running() -> bool:
    from lottery.games import data_dir
    return _lock_alive(data_dir() / "godmode_all.lock") is not None


def godmode_all_plan(from_draw: int) -> tuple[list[str], dict, dict]:
    """Игры для всеобъемлющего режима: формат поддерживается, тиражей больше from_draw + 60
    (проверке нужен хотя бы короткий отрезок), без копий одних и тех же тиражей. Сначала
    короткие архивы — первые итоги появятся быстрее."""
    from lottery.drawfile import same_draws
    order, info, skipped, seen = [], {}, {}, {}
    for slug in local_slugs():
        try:
            data = load_game_data(get_game(slug))
        except ValueError as exc:
            skipped[slug] = str(exc)
            continue
        twin = next((s for s, d in seen.items() if same_draws(d, data.draws)), None)
        seen[slug] = data.draws
        title = data.game.title
        if twin:
            skipped[slug] = f"{title}: те же тиражи, что у «{get_game(twin).title}»"
        elif not data.fmt.supported:
            skipped[slug] = f"{title}: формат не поддерживается"
        elif data.T < from_draw + 60:
            skipped[slug] = f"{title}: тиражей {data.T}, нужно больше {from_draw + 60}"
        else:
            order.append(slug)
            info[slug] = {"title": data.game.title, "draws": data.T, "status": "queued"}
    order.sort(key=lambda s: info[s]["draws"])
    return order, info, skipped


def cmd_godmode_all(args) -> None:
    """Всеобъемлющий режим Бога: все игры по очереди, эксперты проверяются на каждом тираже
    с from-го (каждый — только по предыдущим) до последнего, без ограничения длины истории.
    До budget минут на игру. --resume — продолжить остановленный проход: готовые игры не
    пересчитываются, прерванная продолжает с сохранения (если не пришли новые тиражи)."""
    from lottery import notify
    from lottery.games import data_dir
    from lottery.godmode import drop_state, run_godmode
    lock = data_dir() / "godmode_all.lock"
    if _lock_alive(lock):
        raise SystemExit("Всеобъемлющий режим Бога уже идёт")
    path = godmode_all_file()
    budget = min(max(args.budget, 1.0), MAX_GODMODE_MIN)
    state = _read_json(path) if args.resume else None
    if not state or state.get("status") == "done" or not state.get("order"):
        order, info, skipped = godmode_all_plan(args.from_draw)
        state = {"started_at": datetime.now().isoformat(timespec="seconds"), "from": args.from_draw,
                 "budget": budget, "order": order, "games": info, "skipped": skipped}
    state.update({"status": "running", "pid": os.getpid(), "resumed_at": datetime.now().isoformat(timespec="seconds")
                  if args.resume else None, "finished_at": None})
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(lock, {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds")})
    save_json(path, state)
    emit({"type": "games", "games": state["order"]})
    if not state["order"]:
        say("Нет игр, где тиражей больше " + str(state["from"] + 60))
    last_write = [0.0]
    try:
        for slug in state["order"]:
            g = state["games"][slug]
            if g["status"] == "done":
                emit({"type": "game", "game": slug, **g})
                continue
            g.pop("error", None)
            data = load_game_data(get_game(slug))
            eval_from = min(state["from"] - 1, data.T - 60)
            folder = results_dir(slug)
            folder.mkdir(parents=True, exist_ok=True)
            state_path = folder / "godmode_all_state.npz"
            game_lock = folder / "godmode.lock"
            progress_file = folder / "godmode.progress.json"
            resume = bool(g.get("partial")) and state_path.exists()
            g.update({"status": "running", "started_at": g.get("started_at") or datetime.now().isoformat(timespec="seconds"),
                      "from_no": data.draws[eval_from].no, "to_no": data.draws[-1].no, "draws": data.T})
            state["current"] = slug
            save_json(path, state)
            emit({"type": "game", "game": slug, **g})
            save_json(game_lock, {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds"),
                                  "budget": budget, "comprehensive": True})

            def on_progress(p: dict, slug=slug, g=g) -> None:
                emit({"type": "progress", "game": slug, **p})
                if time.time() - last_write[0] > 5:
                    stamp = datetime.now().isoformat(timespec="seconds")
                    _write_json_quiet(progress_file, {**p, "updated_at": stamp, "comprehensive": True})
                    g["progress"] = {k: p.get(k) for k in ("stage", "done", "total", "experts", "total_elapsed", "note")}
                    _write_json_quiet(path, state)
                    last_write[0] = time.time()

            def checkpoint(res: dict, data=data, slug=slug, g=g) -> None:
                godmode_target(data, res)
                res["comprehensive"] = {"from": state["from"], "from_no": data.draws[eval_from].no}
                save_json(results_dir(slug) / "godmode.json", {**meta(data), **res})
                journal_record(data, "godmode", res["next"]["numbers"],
                               f"всеобъемлющий: {res['next']['strategy']}"
                               + (f" → {res['next']['model']}" if res["next"]["model"] else ""),
                               draw_no=res["next"]["no"], mechanism=res["next"].get("mechanism"))
                g.update({"partial": True, "stage": res["stage"], "experts": res["experts"]})
                save_json(path, state)

            t_game = time.time()
            try:
                try:
                    res = run_godmode(data, budget, on_progress=on_progress, on_checkpoint=checkpoint,
                                      state_path=state_path, resume=resume, eval_from=eval_from)
                except ValueError:
                    # сохранение не подходит (пришли новые тиражи) — эту игру заново
                    drop_state(state_path)
                    res = run_godmode(data, budget, on_progress=on_progress, on_checkpoint=checkpoint,
                                      state_path=state_path, resume=False, eval_from=eval_from)
            except Exception as exc:  # noqa: BLE001 — одна игра не должна останавливать проход
                g.update({"status": "error", "error": f"{type(exc).__name__}: {exc}",
                          "finished_at": datetime.now().isoformat(timespec="seconds")})
                say(f"{data.game.title}: ошибка — {g['error']}")
            else:
                second = next(x["second"] for x in res["strategies"] if x["key"] == res["chosen"])
                g.update({"status": "done", "finished_at": datetime.now().isoformat(timespec="seconds"),
                          "seconds": round(time.time() - t_game), "elapsed_total": res["elapsed_seconds"],
                          "experts": res["experts"], "exhausted": bool(res.get("exhausted")),
                          "mean_hits": second["mean_hits"], "baseline": second["baseline"],
                          "excess_pct": second["excess_pct"], "p_better": second["p_better"],
                          "verdict": res["verdict"], "next": res["next"]["numbers"], "next_no": res["next"]["no"]})
                g.pop("progress", None)
                say(f"{data.game.title}: {res['verdict']}")
            finally:
                for f in (game_lock, progress_file):
                    f.unlink(missing_ok=True)
            emit({"type": "game", "game": slug, **g})
            save_json(path, state)
        state.update({"status": "done", "current": None, "finished_at": datetime.now().isoformat(timespec="seconds")})
        save_json(path, state)
        notify.send(notify.godmode_all_message(state), "godmode")
        emit({"type": "result", "path": str(path)})
    except BaseException:
        if state.get("status") == "running":
            state["status"] = "stopped"
            _write_json_quiet(path, state)
        raise
    finally:
        lock.unlink(missing_ok=True)


def cmd_journal(args) -> None:
    from lottery.journal import journal_path, reconcile, view
    slugs = args.game or sorted(p.stem for p in journal_path("x").parent.glob("*.json"))
    checked = {s: reconcile(get_game(s)) for s in slugs}
    journals = {s: view(s) for s in slugs}
    emit({"type": "result", "checked": checked, "journals": journals})
    if not slugs:
        say("Журнал пуст: запустите analyze или godmode для активной игры.")
    for s, j in journals.items():
        say(f"{get_game(s).title}: сверено сейчас {checked[s]}")
        for row in j["summary"]:
            line = f"  {row['title']:<24} сверено {row['checked']:>4}, ждут {row['pending']}"
            if "mean_hits" in row:
                line += f", угадано в среднем {row['mean_hits']:.3f} при {row['expected']:.3f} у случайного выбора"
            say(line)


def diagnose_game(slug: str) -> dict:
    """Всё, что нужно, чтобы по тексту понять, правильно ли разобрана игра."""
    from collections import Counter
    from lottery.drawfile import load_game_draws, split_bonus
    from lottery.stoloto import damaged
    game = get_game(slug)
    raw = load_game_draws(game)
    data = load_game_data(game)
    act = game_activity(data) if data.draws else activity(raw[-1].dt if raw else None, read_meta(slug).get("checked_at"))
    shapes = Counter("+".join(str(len(b)) for b in d.blocks) for d in raw)
    split = split_bonus(raw, game)[1]
    ranges = []
    for i in range(max((len(d.blocks) for d in raw), default=0)):
        vals = [v for d in raw if len(d.blocks) > i for v in d.blocks[i]]
        if vals:
            ranges.append(f"{min(vals)}–{max(vals)}")
    lines = []
    path = draws_path(slug)
    if path.exists():
        text = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        lines = text[:2] + (["…"] if len(text) > 4 else []) + text[-2:] if len(text) > 4 else text
    from lottery import prizes as prizes_mod
    prize_recs = prizes_mod.load(slug)
    last_prize = prize_recs[max(prize_recs)] if prize_recs else None
    counts = [s.count for s in data.fmt.blocks] if data.fmt.supported else []
    mapped = ([f"{c['label']}→{prizes_mod.describe_keys(c['label'], len(counts), counts)}"
               for c in last_prize["categories"]] if last_prize and counts else [])
    sample_keys = []
    try:
        sample = json.loads(prizes_mod.samples_file(slug).read_text(encoding="utf-8"))
        sample_keys = sorted(sample[-1].keys()) if sample else []
    except (OSError, ValueError):
        pass
    return {
        "prizes": {"draws": len(prize_recs), "source": last_prize and last_prize.get("source"),
                   "categories": mapped, "price": last_prize and last_prize.get("price")},
        "api_keys": sample_keys,
        "anomalies": prizes_mod.anomalies(slug),
        "mechanisms": _mech_counts(data),
        "rules": _rules_brief(slug),
        "slug": slug, "title": game.title, "in_registry": bool(game.counts or game.labels or game.title != slug),
        "draws": len(raw), "valid": data.T,
        "numbers": f"№{raw[0].no}–{raw[-1].no}" if raw else "—",
        "missing": sum(b.no - a.no - 1 for a, b in zip(raw, raw[1:])),
        "damaged": len(damaged(game, raw)),
        "dates": f"{raw[0].date} — {raw[-1].date}" if raw else "—",
        "active": act["active"], "days_since_last": act["days_since_last"],
        "shapes": ", ".join(f"{k}: {v / len(raw):.1%}" for k, v in shapes.most_common(3)) if raw else "—",
        "ranges": " | ".join(ranges) or "—",
        "split_bonus": split,
        "format": data.fmt.describe(),
        "supported": data.fmt.supported,
        "lines": lines,
    }


def _mech_counts(data) -> dict | None:
    try:
        from lottery.mechanics import mechanism_counts
        return mechanism_counts(data) if data.draws else None
    except Exception:
        return None


def _rules_brief(slug: str) -> str:
    from lottery.rules import load_rules
    r = load_rules(slug)
    if not r:
        return "не загружены (lp.bat rules)"
    s = r.get("schedule") or {}
    kinds = " и ".join(k for k, v in (("лототрон", s.get("lototron")), ("ГСЧ", s.get("rng"))) if v) or "способ не указан"
    return f"{kinds}; таблица выигрышей: {len(r.get('table') or [])} строк; загружены {r.get('fetched_at', '?')[:16]}"


def cmd_diagnose(args) -> None:
    from lottery.games import data_dir
    slugs = args.game or local_slugs()
    report = []
    for slug in slugs:
        try:
            report.append(diagnose_game(slug))
        except ValueError:
            continue
    samples = {}
    api_lines: list[str] = []
    if args.api:
        from lottery import prizes as prizes_mod
        from lottery.games import all_games
        from lottery.stoloto import ApiUnavailable, archive_page, discover_games
        api_slugs = [r["slug"] for r in report]
        if not api_slugs:   # тиражи ещё не загружены — берём игры из API (или из реестра)
            say("Тиражей на диске нет — запрашиваю у API список игр…")
            api_slugs = args.game or discover_games(log=lambda m: None) or [g.slug for g in all_games()]
        for slug in api_slugs:
            say(f"  ответ API: {slug}")
            try:
                draws, _ = archive_page(get_game(slug), datetime.now() - timedelta(days=60), datetime.now(), 1,
                                        count=2, log=lambda m: None)
            except (ApiUnavailable, ValueError) as exc:
                samples[slug] = {"error": str(exc)}
                api_lines.append(f"!! {slug}: ошибка API — {exc}")
                continue
            samples[slug] = draws
            if not draws:
                api_lines.append(f"   {slug}: за 60 дней тиражей нет")
                continue
            found = prizes_mod.extract(draws[-1]) if isinstance(draws[-1], dict) else None
            keys = ", ".join(sorted(draws[-1].keys())) if isinstance(draws[-1], dict) else "?"
            if found:
                cats = ", ".join(f"{c['label']}: {c['winners']:.0f} поб. × {c['prize'] or 0:,.0f} ₽".replace(",", " ")
                                 for c in found["categories"][:8] if c["winners"] is not None)
                api_lines.append(f"OK {slug}: выплаты найдены (поле «{found['source']}», цена {found.get('price', 'нет')}) — {cats}")
            else:
                api_lines.append(f"!! {slug}: выплаты не найдены; поля тиража: {keys}")
        save_json(data_dir() / "api_samples.json", samples)
    out = [f"Диагностика {__version__}, {datetime.now():%d.%m.%Y %H:%M}", ""]
    # разные имена в API, а тиражи одни и те же (например, «Дважды два» и «Охота: вызов»)
    from lottery.drawfile import load_game_draws, same_draws
    loaded = {r["slug"]: load_game_draws(get_game(r["slug"])) for r in report if r["draws"]}
    groups: list[list[str]] = []
    for slug, draws in loaded.items():
        for grp in groups:
            if same_draws(loaded[grp[0]], draws):
                grp.append(slug)
                break
        else:
            groups.append([slug])
    for same in (g for g in groups if len(g) > 1):
        out += [f"Одинаковые тиражи у игр {', '.join(same)}: API отдаёт один розыгрыш под разными именами "
                f"(автозапуск анализирует только {same[0]}).", ""]
    if not report:
        out += ["Тиражи ещё не загружены (в data\\draws нет файлов). Сначала выполните: lp.bat fetch", ""]
    if api_lines:
        out += ["Ответы API (последний тираж каждой игры):", *api_lines, ""]
    for r in report:
        mark = "OK " if r["supported"] and not r["damaged"] else "!! "
        out.append(f"{mark}{r['slug']} — {r['title']}" + ("" if r["in_registry"] else " (нет в реестре)"))
        out.append(f"   тиражей: {r['draws']} (подходят под формат: {r['valid']}), {r['numbers']}, "
                   f"пропусков {r['missing']}, неполных {r['damaged']}")
        out.append(f"   даты: {r['dates']}; " + ("активная" if r["active"] else f"устаревшая ({r['days_since_last']} дн.)"))
        out.append(f"   формы строк: {r['shapes']}; диапазоны по полям: {r['ranges']}"
                   + ("; бонус отделён автоматически" if r["split_bonus"] else ""))
        out.append(f"   формат: {r['format']}")
        pz = r["prizes"]
        if pz["draws"]:
            out.append(f"   выплаты: {pz['draws']} тиражей (поле «{pz['source']}»), цена билета: {pz['price'] or 'нет в ответе'}; "
                       f"категории: {', '.join(pz['categories'][:12])}")
        else:
            out.append("   выплаты: в ответах API не найдены")
        if r.get("anomalies"):
            out.append(f"   тиражи с аномально малыми продажами (исключены из расчётов в рублях): "
                       f"{len(r['anomalies'])} — №{', №'.join(map(str, r['anomalies'][:10]))}")
        if r.get("mechanisms"):
            m = r["mechanisms"]
            out.append(f"   способ розыгрыша: лототрон {m['L']}, ГСЧ {m['R']}, не определено {m['unknown']}")
        out.append(f"   правила: {r['rules']}")
        if r["api_keys"]:
            out.append(f"   поля ответа API: {', '.join(r['api_keys'])}")
        for line in r["lines"]:
            out.append(f"     {line[:150]}")
        out.append("")
    if args.api:
        out.append(f"Сырые ответы API (по 2 последних тиража): {data_dir() / 'api_samples.json'}")
    out.append(f"Сырые ответы API по каждой игре (сохраняются при загрузке): {data_dir() / 'api_samples'}")
    text = "\n".join(out)
    from lottery.fsutil import write_text
    write_text(data_dir() / "diagnose.txt", text)
    emit({"type": "result", "games": report, "path": str(data_dir() / "diagnose.txt")})
    say(text)
    say(f"Сохранено: {data_dir() / 'diagnose.txt'}")


def set_env_var(key: str, value: str) -> Path:
    """Записывает KEY=value в .env проекта (заменяет строку, если ключ уже есть)."""
    from lottery.fsutil import write_text
    path = env_file()
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    out, done = [], False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    write_text(path, "\n".join(out) + "\n")
    os.environ[key] = value
    return path


def cmd_telegram(args) -> None:
    from lottery import notify
    cfg = notify.config()
    status = {"configured": cfg["configured"], "has_token": bool(cfg["token"]), "has_chat": bool(cfg["chat_id"]),
              "events": sorted(cfg["events"]), "proxy": bool(cfg["proxy"]), **notify.outbox_info()}
    if args.action == "status":
        emit({"type": "result", "telegram": status})
        say("Telegram: " + ("настроен" if cfg["configured"] else
                            "не настроен — " + ("нет TELEGRAM_CHAT_ID (lp.bat telegram setup)" if cfg["token"]
                                                 else "нет TELEGRAM_BOT_TOKEN в .env")))
        return
    if not cfg["token"]:
        raise SystemExit("В .env нет TELEGRAM_BOT_TOKEN. Создайте бота у @BotFather и впишите токен (см. README).")
    try:
        bot = notify.me(cfg)
    except RuntimeError as exc:
        raise SystemExit(f"Telegram не отвечает или токен неверный: {exc}. Если api.telegram.org недоступен, "
                         "задайте TELEGRAM_PROXY в .env.")
    if args.action == "setup":
        chats = notify.updates(cfg)
        emit({"type": "result", "bot": bot.get("username"), "chats": chats})
        say(f"Бот: @{bot.get('username')}")
        if not chats:
            say("Чатов пока нет. Откройте бота в Telegram, нажмите «Запустить» (или напишите любое сообщение) "
                "и выполните команду ещё раз.")
            return
        for c in chats:
            say(f"  чат {c['id']}: {c['title']} ({c['type']})")
        if len(chats) == 1 or args.chat:
            chat = args.chat or str(chats[0]["id"])
            path = set_env_var("TELEGRAM_CHAT_ID", chat)
            say(f"TELEGRAM_CHAT_ID={chat} записан в {path}. Проверка: lp.bat telegram test")
        else:
            say("Чатов несколько — укажите нужный: lp.bat telegram setup --chat <id>")
        return
    if args.action == "test":
        if not cfg["chat_id"]:
            raise SystemExit("Нет TELEGRAM_CHAT_ID: выполните lp.bat telegram setup")
        ok = notify.send(f"Лотерейный анализатор {__version__}: уведомления работают ✅", "auto", cfg, force=True)
        emit({"type": "result", "sent": ok})
        if not ok:
            raise SystemExit("Сообщение не отправлено — подробности в data\\logs\\telegram.log")
        say("Тестовое сообщение отправлено.")


def cmd_info(args) -> None:
    info = game_info(args.game)
    emit({"type": "result", "info": info})
    if info["last"]:
        act = info["activity"]
        say(f"{info['title']} ({info['stoloto_url']})\nТиражей: {info['draws_valid']}, "
            f"№{info['first']['no']}–{info['last']['no']}, {info['first']['date']} — {info['last']['date']}\n"
            f"Формат: {info['format']}\n"
            + (f"Следующий тираж: №{info['next_no']}" if act["active"]
               else f"Игра устарела: тиражей нет {act['days_since_last']:.0f} дн."))
    else:
        say(f"{info['title']}: тиражи не загружены")


def main() -> None:
    parser = argparse.ArgumentParser(description="Движок анализа лотерей")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("--game", action="append")
    p.add_argument("--workers", type=int, default=2)
    sub.add_parser("scan")
    p = sub.add_parser("analyze")
    p.add_argument("--game", required=True)
    p = sub.add_parser("repeats", help="повторы по позициям выпадения: все задержки и сдвиги")
    p.add_argument("--game", required=True)
    p = sub.add_parser("chaos", help="порядок из хаоса: динамика тиражей отдельно по лототрону и ГСЧ")
    p.add_argument("--game", required=True)
    p = sub.add_parser("godmode")
    p.add_argument("--game", required=True)
    p.add_argument("--budget", type=float, default=480.0,
                   help="предел времени, минут (1–480); по умолчанию — до исчерпания перебора, не дольше 8 ч")
    p.add_argument("--resume", action="store_true", help="продолжить с сохранённого состояния")
    p = sub.add_parser("godmode-all", help="всеобъемлющий режим Бога: все игры по очереди с 1000-го тиража")
    p.add_argument("--from", dest="from_draw", type=int, default=GODMODE_ALL_FROM,
                   help="с какого по счёту тиража проверять экспертов (по умолчанию 1000)")
    p.add_argument("--budget", type=float, default=float(os.environ.get("LOTTERY_GODMODE_ALL_BUDGET", 480)),
                   help="минут на игру (1–480; по умолчанию 480 или LOTTERY_GODMODE_ALL_BUDGET)")
    p.add_argument("--resume", action="store_true", help="продолжить остановленный проход")
    p = sub.add_parser("info")
    p.add_argument("--game", required=True)
    p = sub.add_parser("journal")
    p.add_argument("--game", action="append")
    p = sub.add_parser("telegram", help="уведомления: status | setup | test")
    p.add_argument("action", choices=["status", "setup", "test"])
    p.add_argument("--chat", help="id чата для setup, если чатов несколько")
    p = sub.add_parser("diagnose", help="проверка формата и полноты данных по каждой игре")
    p.add_argument("--game", action="append")
    p.add_argument("--api", action="store_true", help="сохранить по 2 сырых ответа API на игру")
    p = sub.add_parser("auto", help="загрузка + анализ активных игр + журнал (для Планировщика)")
    p.add_argument("--game", action="append")
    p.add_argument("--godmode-budget", type=float, default=5.0, help="минут режима Бога на игру (0 — не запускать)")
    p.add_argument("--godmode-every", type=float, default=3.0, help="часов между запусками режима Бога для игры")
    p.add_argument("--every", type=float, default=0.0, help="повторять каждые N часов (для Docker)")
    p.add_argument("--skip-fetch", action="store_true")
    p.add_argument("--skip-scan", action="store_true")
    p = sub.add_parser("rules", help="правила игр со stoloto.ru: как проходят розыгрыши, таблица выигрышей")
    p.add_argument("--game", action="append")
    p = sub.add_parser("nextdraw", help="ожидаемый возврат ближайших тиражей")
    p.add_argument("--game", action="append")
    p = sub.add_parser("odds", help="шансы и ожидаемый возврат")
    p.add_argument("--game")
    p.add_argument("--set-prizes", help="JSON-файл {price, prizes: {\"4+4\": 1000000, ...}}")
    p = sub.add_parser("tickets", help="генератор непопулярных комбинаций")
    p.add_argument("--game", required=True)
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--seed", type=int)
    p.add_argument("--check", help="проверить свою комбинацию: \"1,2,3,4|5,6,7,8\"")
    p = sub.add_parser("mytickets", help="мои купленные билеты: list | add | remove | won")
    p.add_argument("action", choices=["list", "add", "remove", "won"])
    p.add_argument("--game")
    p.add_argument("--numbers", help="\"1,2,3,4|5,6,7,8\"")
    p.add_argument("--draw", type=int, help="номер тиража (по умолчанию — ближайший)")
    p.add_argument("--draws", type=int, default=1, help="на сколько тиражей подряд")
    p.add_argument("--price", type=float, help="цена билета на один тираж, ₽")
    p.add_argument("--note")
    p.add_argument("--id")
    p.add_argument("--won", type=float, help="выигрыш вручную, ₽ (меньше 0 — вернуть расчёт)")
    p = sub.add_parser("backup", help="резервные копии журнала и билетов: list | make | restore | cleanup")
    p.add_argument("action", choices=["list", "make", "restore", "cleanup"], nargs="?", default="list")
    p.add_argument("name", nargs="?")
    p = sub.add_parser("export", help="экспорт в Excel или CSV")
    p.add_argument("--game", required=True)
    p.add_argument("--format", choices=["xlsx", "csv"], default="xlsx")
    p.add_argument("--what", default="all", help="all | draws | journal | methods | tests | godmode")
    p.add_argument("--out")
    args = parser.parse_args()
    handlers = {"fetch": cmd_fetch, "scan": cmd_scan, "analyze": cmd_analyze, "godmode": cmd_godmode,
                "info": cmd_info, "journal": cmd_journal, "auto": cmd_auto, "odds": cmd_odds,
                "tickets": cmd_tickets, "export": cmd_export, "diagnose": cmd_diagnose, "telegram": cmd_telegram,
                "rules": cmd_rules, "nextdraw": cmd_nextdraw, "chaos": cmd_chaos,
                "repeats": cmd_repeats, "mytickets": cmd_mytickets, "backup": cmd_backup,
                "godmode-all": cmd_godmode_all}
    try:
        handlers[args.cmd](args)
    except SystemExit as exc:
        if exc.code not in (0, None):
            emit({"type": "error", "message": str(exc.code)})
            sys.exit(2)
    except Exception as exc:
        traceback.print_exc()
        emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
