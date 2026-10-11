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
from lottery.games import activity, all_games, draws_path, get_game, read_meta, results_dir  # noqa: E402

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


def journal_record(data, source: str, numbers, detail: str) -> None:
    """Прогноз в журнал — только для активной игры (иначе тираж не наступит)."""
    from lottery.journal import record
    if data.draws and game_activity(data)["active"]:
        record(data, source, numbers, detail)


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


def cmd_fetch(args) -> None:
    from lottery.stoloto import fetch_all
    slugs = args.game or None
    results = fetch_all(slugs, emit, workers=args.workers)
    emit({"type": "result", "results": results})
    done = [r for r in results.values() if r.get("status") == "done"]
    say(f"Загружено игр: {len(done)} из {len(results)}, тиражей всего: {sum(r.get('draws', 0) for r in done)}")


def cmd_scan(args) -> None:
    from lottery.scan import run_scan
    payload = run_scan(progress=lambda p: emit({"type": "progress", **p}))
    emit({"type": "result", "path": str(results_dir() / "scan.json"), "recomputed": payload["recomputed"]})
    for g in payload["games"]:
        say(f"{g['title']:<22} {g['draws']:>7} тир.  {g['verdict']}")
    say(f"Пересчитано игр: {payload['recomputed']} (остальные без изменений, взяты из прошлой проверки)")


def analyze_game(slug: str, progress=None) -> dict:
    """Тесты случайности + сравнение методов + прогноз в журнал. Возвращает сохранённый отчёт."""
    from lottery.evaluate import evaluate_game
    from lottery.journal import reconcile
    from lottery.stats import descriptive, finalize_scan, game_randomness
    data = load_game_data(get_game(slug))
    if not data.fmt.supported:
        raise SystemExit(f"Формат игры не поддерживается: {data.fmt.reason}")
    t0 = time.time()
    if progress:
        progress({"type": "progress", "stage": "tests", "done": 0, "total": 1})
    randomness = finalize_scan([game_randomness(data)])[0]
    reconcile(data.game)
    evaluation = evaluate_game(data, progress=(lambda p: progress({"type": "progress", **p})) if progress else None)
    if evaluation.get("status") == "ok":
        journal_record(data, "analysis_best", evaluation["next_prediction"]["numbers"],
                       evaluation["next_prediction"]["model"])
        journal_record(data, "analysis_consensus", evaluation["next_consensus"], "")
    from lottery.popularity import fit as fit_popularity
    popularity = fit_popularity(data)
    if popularity.get("available"):
        save_json(results_dir(slug) / "popularity.json", popularity)
    payload = {**meta(data), "seconds": round(time.time() - t0, 1), "randomness": randomness,
               "descriptive": descriptive(data), "evaluation": evaluation, "popularity": popularity}
    save_json(results_dir(slug) / "analysis.json", payload)
    return payload


def cmd_analyze(args) -> None:
    payload = analyze_game(args.game, progress=emit)
    path = results_dir(args.game) / "analysis.json"
    emit({"type": "result", "path": str(path)})
    evaluation, randomness = payload["evaluation"], payload["randomness"]
    say(f"\n{payload['title']}: {payload['format']}\nСлучайность: {randomness['verdict']}")
    if evaluation.get("status") == "ok":
        say(f"Методы: {evaluation['conclusion']}")
        say(f"Прогноз на тираж №{payload['last_draw_no'] + 1} («{evaluation['next_prediction']['model']}»): "
            f"{balls(evaluation['next_prediction']['numbers'])}")
        say(f"Консенсус методов: {balls(evaluation['next_consensus'])}")
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
    try:
        fetched = {} if args.skip_fetch else fetch_all(args.game or None, emit, workers=2)
        for slug, r in fetched.items():
            status["games"].setdefault(slug, {}).update(
                {"fetch": r.get("status"), "added": r.get("added", 0), "journal_checked": r.get("journal_checked", 0)})
            if r.get("status") == "error":
                log(f"{slug}: ошибка загрузки — {r.get('message')}")
        slugs = args.game or sorted(p.stem[len("draws_"):] for p in draws_path("x").parent.glob("draws_*.txt"))
        for slug in slugs:
            try:
                data = load_game_data(get_game(slug))
            except ValueError:
                continue
            g = status["games"].setdefault(slug, {})
            if not data.fmt.supported or not data.draws:
                g["skipped"] = "формат не поддерживается" if data.draws else "нет тиражей"
                continue
            if not game_activity(data)["active"]:
                g["skipped"] = "игра устарела"
                continue
            prev = _read_json(results_dir(slug) / "analysis.json")
            if prev and prev.get("last_draw_no") == data.draws[-1].no and prev.get("version") == __version__:
                g["skipped"] = "новых тиражей нет — прогноз уже в журнале"
                continue
            payload = analyze_game(slug)
            ev = payload["evaluation"]
            g["analyzed"] = ev.get("status") == "ok"
            g["next_no"] = data.draws[-1].no + 1
            if g["analyzed"]:
                predictions[slug] = {"title": data.game.title, "next_no": g["next_no"],
                                     "numbers": ev["next_prediction"]["numbers"]}
            log(f"{slug}: анализ готов, прогноз на тираж №{g['next_no']} записан в журнал")
            if args.godmode_budget > 0:
                from lottery.godmode import run_godmode
                folder = results_dir(slug)
                base = meta(data)

                def checkpoint(res, data=data, folder=folder, base=base):
                    save_json(folder / "godmode.json", {**base, **res})
                    journal_record(data, "godmode", res["next"]["numbers"], res["next"]["strategy"])
                gres = run_godmode(data, args.godmode_budget, on_checkpoint=checkpoint,
                                   state_path=folder / "godmode_state.npz")
                g["godmode"] = True
                notify.send(notify.godmode_message(data.game.title, gres), "godmode")
        if not args.skip_scan:
            cmd_scan_quiet()
        status["status"] = "done"
        log("Автозапуск: готово")
        notify.send(notify.auto_message(status, predictions), "auto")
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


def cmd_auto(args) -> None:
    from lottery.games import data_dir
    lock = data_dir() / "auto.lock"
    try:
        held = json.loads(lock.read_text(encoding="utf-8"))
        if pid_alive(int(held.get("pid", 0))):
            say("Автозапуск уже выполняется — пропускаю.")
            emit({"type": "result", "skipped": True})
            return
    except (OSError, ValueError):
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
    slugs = args.game and [args.game] or sorted(p.stem[len("draws_"):] for p in draws_path("x").parent.glob("draws_*.txt"))
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


def cmd_godmode(args) -> None:
    from lottery.godmode import run_godmode
    data = load_game_data(get_game(args.game))
    if not data.fmt.supported:
        raise SystemExit(f"Формат игры не поддерживается: {data.fmt.reason}")
    budget = min(max(args.budget, 1.0), 480.0)
    folder = results_dir(args.game)
    path = folder / "godmode.json"
    lock = folder / "godmode.lock"
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
        save_json(path, {**base, **res})
        journal_record(data, "godmode", res["next"]["numbers"],
                       f"{res['next']['strategy']}" + (f" → {res['next']['model']}" if res["next"]["model"] else ""))
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
    mapped = ([f"{c['label']}→{prizes_mod.category_key(c['label'], len(counts), counts) or '?'}"
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


def cmd_diagnose(args) -> None:
    from lottery.games import data_dir
    slugs = args.game or sorted(p.stem[len("draws_"):] for p in draws_path("x").parent.glob("draws_*.txt"))
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
              "events": sorted(cfg["events"]), "proxy": bool(cfg["proxy"])}
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
    p = sub.add_parser("godmode")
    p.add_argument("--game", required=True)
    p.add_argument("--budget", type=float, default=30.0, help="бюджет времени, минут (1–480)")
    p.add_argument("--resume", action="store_true", help="продолжить с сохранённого состояния")
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
    p.add_argument("--godmode-budget", type=float, default=0.0, help="минут режима Бога на игру (0 — не запускать)")
    p.add_argument("--every", type=float, default=0.0, help="повторять каждые N часов (для Docker)")
    p.add_argument("--skip-fetch", action="store_true")
    p.add_argument("--skip-scan", action="store_true")
    p = sub.add_parser("odds", help="шансы и ожидаемый возврат")
    p.add_argument("--game")
    p.add_argument("--set-prizes", help="JSON-файл {price, prizes: {\"4+4\": 1000000, ...}}")
    p = sub.add_parser("tickets", help="генератор непопулярных комбинаций")
    p.add_argument("--game", required=True)
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--seed", type=int)
    p.add_argument("--check", help="проверить свою комбинацию: \"1,2,3,4|5,6,7,8\"")
    p = sub.add_parser("export", help="экспорт в Excel или CSV")
    p.add_argument("--game", required=True)
    p.add_argument("--format", choices=["xlsx", "csv"], default="xlsx")
    p.add_argument("--what", default="all", help="all | draws | journal | methods | tests | godmode")
    p.add_argument("--out")
    args = parser.parse_args()
    handlers = {"fetch": cmd_fetch, "scan": cmd_scan, "analyze": cmd_analyze, "godmode": cmd_godmode,
                "info": cmd_info, "journal": cmd_journal, "auto": cmd_auto, "odds": cmd_odds,
                "tickets": cmd_tickets, "export": cmd_export, "diagnose": cmd_diagnose, "telegram": cmd_telegram}
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
