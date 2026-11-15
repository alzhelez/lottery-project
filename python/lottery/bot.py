"""Telegram-бот с кнопками: отдельный процесс (lp.py bot, bot.bat), который слушает бота.

Работает независимо от сайта — поэтому может честно ответить, доступно ли приложение.
Отвечает только чату TELEGRAM_CHAT_ID. Меню — кнопками под одним сообщением (оно
редактируется, чат не засоряется):

    Сверка прогнозов: вкл/выкл      — приходят ли сообщения о сверке (сама сверка идёт всегда)
    Автозапуск: вкл/выкл            — приходят ли итоги автозапуска (сам автозапуск идёт всегда)
    Проверить статус приложения     — отвечает ли сайт, когда был последний цикл автозапуска
    Выбор игры → игра               — таблицы: методы за месяц и лидеры по месяцам за полгода;
                                      ближайший тираж: возврат, общие числа Ф, К, Б, редкая комбинация;
                                      «Запустить архивные методы» — их числа придут сообщением
              → метод               — время до ближайшего тиража и числа этого метода

Настройки кнопок — data/telegram_settings.json (их читает notify.send).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta

import requests

from . import notify
from .fsutil import write_text
from .games import data_dir, get_game
from .journal import ARCHIVED, LOWER, SOURCES, load

MUTABLE = {"journal": "Сверка прогнозов", "auto": "Автозапуск"}
POLL_S = 25
APP_URL_ENV = "LOTTERY_APP_URL"


def settings_path():
    return data_dir() / "telegram_settings.json"


def muted() -> set[str]:
    try:
        return set(json.loads(settings_path().read_text(encoding="utf-8")).get("muted", []))
    except (OSError, ValueError):
        return set()


def set_muted(event: str, off: bool) -> set[str]:
    m = muted()
    (m.add if off else m.discard)(event)
    write_text(settings_path(), json.dumps({"muted": sorted(m)}, ensure_ascii=False))
    return m


# ── Данные для ответов ─────────────────────────────────────────────────────

def app_status() -> str:
    url = os.environ.get(APP_URL_ENV, "http://localhost:3000").rstrip("/")
    try:
        ok = requests.get(f"{url}/api/games", timeout=5).status_code == 200
    except requests.RequestException:
        ok = False
    lines = [f"✅ Приложение доступно: {notify.esc(url)}" if ok
             else f"❌ Приложение недоступно ({notify.esc(url)} не отвечает) — запустите start.bat"]
    try:
        st = json.loads((data_dir() / "auto_status.json").read_text(encoding="utf-8"))
        when = (st.get("finished_at") or st.get("started_at") or "").replace("T", " ")[:16]
        state = {"done": "завершён", "running": "идёт", "error": "ошибка"}.get(st.get("status"), st.get("status") or "?")
        lines.append(f"Автозапуск: последний цикл {when} — {state}")
        if st.get("current"):
            lines.append(f"Сейчас: {notify.esc(st['current'].get('stage', ''))}")
    except (OSError, ValueError):
        lines.append("Автозапуск ещё не запускался")
    try:
        from . import findings
        lines.append(notify.esc(findings.summary()))
    except Exception:  # noqa: BLE001 — строка о находках не должна ломать ответ
        pass
    lines.append(f"Проверено {datetime.now():%d.%m %H:%M}")
    return "\n".join(lines)


def games() -> list[tuple[str, str]]:
    """Игры, по которым есть журнал прогнозов: [(slug, название)]."""
    from .games import is_excluded
    out = []
    d = data_dir() / "journal"
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        slug = p.stem
        g = get_game(slug)
        if g is not None and not is_excluded(slug) and load(slug)["entries"]:
            out.append((slug, g.title))
    return sorted(out, key=lambda x: x[1])


def game_stats(slug: str, now: datetime | None = None) -> tuple[str, list[str]]:
    """Статистика методов игры таблицами — за месяц и лидеры за полгода (botstats.py) — и
    источники, у которых есть прогноз на ближайшие тиражи."""
    from .botstats import game_report
    title = get_game(slug).title
    has = [s for s in SOURCES if any(e["source"] == s and e["status"] == "pending" for e in load(slug)["entries"])]
    return f"<b>{notify.esc(title)}</b>\n{game_report(slug, now)}", has


def _left(delta: timedelta) -> str:
    m = int(delta.total_seconds() // 60)
    if m < 0:
        return "тираж уже начался"
    if m < 60:
        return f"через {m} мин"
    h, m = divmod(m, 60)
    return f"через {h} ч {m} мин" if h < 48 else f"через {h // 24} дн."


def method_forecast(slug: str, source: str, now: datetime | None = None) -> str:
    """Время до ближайшего тиража и числа метода на него (из журнала)."""
    from .drawfile import load_game_data
    from .journal import target_draw
    now = now or datetime.now()
    title = get_game(slug).title
    head = f"<b>{notify.esc(title)}</b> — {notify.SHORT.get(source, '')} {notify.esc(SOURCES.get(source, source))}"
    pending = sorted((e for e in load(slug)["entries"] if e["source"] == source and e["status"] == "pending"),
                     key=lambda e: e["draw_no"])
    try:
        target = target_draw(load_game_data(get_game(slug)), now)
    except (ValueError, OSError):
        target = {"no": None, "date": None}
    entry = next((e for e in pending if target["no"] is None or e["draw_no"] >= target["no"]), None)
    lines = [head]
    if target.get("date"):
        lines.append(f"Ближайший тираж №{target['no']} — {_left(target['date'] - now)} ({target['date']:%d.%m %H:%M})")
    else:
        lines.append("Время ближайшего тиража неизвестно")
    if entry is None:
        lines.append("Прогноза этого метода на ближайший тираж нет — он появится после следующего автозапуска.")
    else:
        note = " — эти числа лучше не брать" if source in LOWER else ""
        lines.append(f"Числа на №{entry['draw_no']}: <code>{notify.esc(notify.fmt_blocks(entry['numbers']))}</code>{note}")
        if entry.get("detail"):
            lines.append(notify.esc(entry["detail"]))
        lines.append(f"прогноз записан {entry['made_at'].replace('T', ' ')[:16]}")
    return "\n".join(lines)


# ── Меню ───────────────────────────────────────────────────────────────────

def _kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


def main_menu() -> tuple[str, dict]:
    m = muted()
    rows = [[(f"{'🔕' if e in m else '🔔'} {title}: {'выкл' if e in m else 'вкл'}", f"mute:{e}")] for e, title in MUTABLE.items()]
    rows += [[("Проверить статус приложения", "status")], [("Выбор игры", "games")],
             [("Провести анализ за …", "analyze")]]
    return ("<b>Лотерейный анализатор</b>\nКнопки «вкл/выкл» управляют сообщениями: сама сверка и автозапуск "
            "продолжают работать.", _kb(rows))


def games_menu() -> tuple[str, dict]:
    gs = games()
    rows = [[(t, f"g:{s}") for s, t in gs[i:i + 2]] for i in range(0, len(gs), 2)]
    return ("Список доступных игр:" if gs else "Игр с прогнозами пока нет.", _kb(rows + [[("← Меню", "menu")]]))


def nearest(slug: str, now: datetime | None = None) -> tuple[int | None, datetime | None, dict[str, dict]]:
    """Ближайший тираж игры: (номер, время, {метод: запись журнала с прогнозом на него})."""
    from .drawfile import load_game_data
    from .journal import target_draw
    now = now or datetime.now()
    try:
        target = target_draw(load_game_data(get_game(slug)), now)
    except (ValueError, OSError):
        target = {"no": None, "date": None}
    pending = sorted((e for e in load(slug)["entries"] if e["status"] == "pending"
                      and (target["no"] is None or e["draw_no"] >= target["no"])), key=lambda e: e["draw_no"])
    # номер — тиража, на который есть прогнозы (он может быть дальше расчётного ближайшего)
    first = pending[0]["draw_no"] if pending else None
    no = first if first is not None else target["no"]
    return no, target.get("date") if no == target["no"] else None, {e["source"]: e for e in pending if e["draw_no"] == first}


def next_draw_block(slug: str, now: datetime | None = None) -> str:
    """То же, что карточка ближайшего тиража в «Обзоре» сайта: ожидаемый возврат, числа, общие для
    Ф, К и Б, и «редкая комбинация»."""
    from . import rarity
    from .games import results_dir
    now = now or datetime.now()
    no, when, by = nearest(slug, now)
    if no is None:
        return ""
    lines = [f"<b>Ближайший тираж №{no}</b>" + (f" — {_left(when - now)} ({when:%d.%m %H:%M})" if when else "")]
    try:
        money = json.loads((results_dir() / "nextdraw.json").read_text(encoding="utf-8")).get("games", {}).get(slug)
    except (OSError, ValueError):
        money = None
    if money and money.get("number") == no:
        peak = money.get("peak") or {}
        line = f"Ожидаемый возврат: {notify._dec(money['return'], 2)} на рубль"
        if money.get("usual_return") is not None:
            line += f" (обычно {notify._dec(money['usual_return'], 2)})"
        if peak.get("is_max"):
            line += f" — максимум за {peak['days']} дн. наблюдений"
        lines.append(line)
    voters = [by[s]["numbers"] for s in ("final", "analysis_consensus", "godmode") if s in by]
    if "analysis_consensus" in by and "godmode" in by:
        common = [sorted(n for n in voters[0][b] if all(n in v[b] for v in voters)) for b in range(len(voters[0]))]
        shown = " | ".join(" ".join(str(n) for n in b) or "—" for b in common)
        lines.append("Есть у каждого метода (Ф, К, Б): " + (f"<code>{shown}</code>" if any(common) else "таких чисел нет"))
    r = rarity.read(slug) or {}
    last = max((e["based_on"] for e in by.values() if e.get("based_on") is not None), default=None)
    if r.get("rare") and r.get("based_on") == last:
        lines.append(f"Редкая комбинация (не прогноз — числа, которые редко ставят): "
                     f"<code>{notify.esc(notify.fmt_blocks(r['rare']['numbers']))}</code>")
    return "\n".join(lines)


def start_archive(slug: str) -> str:
    """Разовый запуск архивных методов (Л, З, Х) отдельным процессом — lp.py archive --notify."""
    import subprocess
    import sys
    from pathlib import Path
    lp = Path(__file__).resolve().parents[1] / "lp.py"
    flags = {"creationflags": 0x08000000} if os.name == "nt" else {"start_new_session": True}   # без окна
    subprocess.Popen([sys.executable, str(lp), "archive", "--game", slug, "--notify"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **flags)
    return (f"Архивные методы «{notify.esc(get_game(slug).title)}» запущены: лучший метод, золотая середина и порядок "
            "из хаоса. Это несколько минут — пришлю их числа, когда посчитаются.")


def archive_done_message(slug: str, now: datetime | None = None) -> str:
    """Числа архивных методов на ближайший тираж — после запуска кнопкой бота."""
    from .journal import ARCHIVED
    no, when, by = nearest(slug, now)
    lines = [f"<b>{notify.esc(get_game(slug).title)}</b> — архивные методы" + (f", тираж №{no}" if no else "")]
    got = [s for s in SOURCES if s in ARCHIVED and s in by]
    for s in got:
        lines.append(f"  {notify.SHORT[s]} {notify.esc(SOURCES[s])}: <code>{notify.esc(notify.fmt_blocks(by[s]['numbers']))}</code>")
    if not got:
        lines.append("Прогнозов нет: игра неактивна или в архиве мало тиражей.")
    else:
        lines.append("Прогнозы записаны в журнал и будут сверены; в «Финальном предсказании» не участвуют.")
    return "\n".join(lines)


def game_menu(slug: str) -> tuple[str, dict]:
    from .coverage import summary
    text, has = game_stats(slug)
    try:
        block = next_draw_block(slug)
    except Exception:  # noqa: BLE001 — блок ближайшего тиража не должен ломать меню игры
        block = ""
    if block:
        text = f"{text}\n\n{block}"
    try:
        check, need_fix = summary(slug)
    except (ValueError, OSError):
        check, need_fix = "", False
    if check:
        text = f"{text}\n\n{check}"
    text += "\n\nВыберите метод — пришлю его числа на ближайший тираж."
    buttons = [(f"{notify.SHORT.get(s, '?')} {SOURCES[s]}", f"m:{slug}:{s}") for s in has]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    if need_fix:
        rows.insert(0, [("Пересчитать предсказания", f"fix:{slug}")])
    rows.append([("Запустить архивные методы (Л, З, Х)", f"arch:{slug}")])
    return text, _kb(rows + [[("← Игры", "games"), ("← Меню", "menu")]])


PERIODS = {1: "сутки", 3: "3 дня", 7: "неделю", 14: "2 недели", 30: "месяц"}


def analyze_menu() -> tuple[str, dict]:
    rows = [[(f"за {t}", f"run:{d}") for d, t in list(PERIODS.items())[i:i + 3]] for i in range(0, len(PERIODS), 3)]
    return ("<b>Провести анализ за …</b>\nВсе методы на каждом тираже периода по всем играм; после него "
            "обновятся доверие и «По методам». Когда закончится — пришлю итог.", _kb(rows + [[("← Меню", "menu")]]))


def start_analysis(days: int, slug: str | None = None) -> str:
    """Запускает «анализ за период» отдельным процессом (lp.py retro --notify): бот не ждёт его."""
    import subprocess
    import sys
    from pathlib import Path
    lock = data_dir() / "retro.lock"
    try:
        import psutil                 # не os.kill(pid, 0): на Windows он завершает процесс
        if psutil.pid_exists(int(json.loads(lock.read_text(encoding="utf-8")).get("pid"))):
            return "Анализ уже идёт — дождитесь сообщения о завершении."
    except (OSError, ValueError, TypeError, ImportError):
        pass
    lp = Path(__file__).resolve().parents[1] / "lp.py"
    flags = {"creationflags": 0x08000000} if os.name == "nt" else {"start_new_session": True}   # без окна
    subprocess.Popen([sys.executable, str(lp), "retro", "--days", str(days), "--notify"] + (["--game", slug] if slug else []),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **flags)
    if slug:
        return (f"Пересчёт предсказаний «{notify.esc(get_game(slug).title)}» за {PERIODS[days]} запущен — пришлю итог, "
                "когда закончится.")
    return (f"Анализ за {PERIODS[days]} запущен: все методы на каждом тираже периода, режим Бога по 3 минуты "
            "на игру. Это от получаса до нескольких часов — пришлю итог, когда закончится.")


def analysis_done_message(days: int, trust_table: dict) -> str:
    """Итог анализа для Telegram: по каждой игре — метод с самым высоким доверием."""
    lines = [f"<b>Анализ за {PERIODS.get(days, f'{days} дн.')} завершён</b>", "Выше всех доверие:"]
    for slug, g in sorted((trust_table.get("games") or {}).items(), key=lambda x: get_game(x[0]).title if get_game(x[0]) else x[0]):
        ranking = [s for s in g.get("ranking") or [] if s not in ARCHIVED]      # лидер — среди активных методов
        if not ranking or get_game(slug) is None:
            continue
        top = ranking[0]
        r = g["sources"][top]
        lines.append(f"{notify.esc(get_game(slug).title)}: {notify.SHORT.get(top, '')} {notify.esc(SOURCES.get(top, top))} — "
                     f"{r['trust']:.0f}" + (" (мало данных)" if r.get("few") else ""))
    return "\n".join(lines)


def route(data: str) -> tuple[str, dict]:
    """Ответ на нажатие кнопки: (текст, клавиатура)."""
    if data.startswith("mute:") and data[5:] in MUTABLE:
        set_muted(data[5:], data[5:] not in muted())
        return main_menu()
    if data == "status":
        return app_status(), _kb([[("Проверить ещё раз", "status")], [("← Меню", "menu")]])
    if data == "games":
        return games_menu()
    if data == "analyze":
        return analyze_menu()
    if data.startswith("run:") and data[4:].isdigit() and int(data[4:]) in PERIODS:
        return start_analysis(int(data[4:])), _kb([[("← Меню", "menu")]])
    if data.startswith("g:") and get_game(data[2:]) is not None:
        return game_menu(data[2:])
    if data.startswith("arch:") and get_game(data[5:]) is not None:
        return start_archive(data[5:]), _kb([[("← К игре", f"g:{data[5:]}"), ("← Меню", "menu")]])
    if data.startswith("fix:") and get_game(data[4:]) is not None:
        from .coverage import analysis_days
        return start_analysis(analysis_days(), data[4:]), _kb([[("← К игре", f"g:{data[4:]}"), ("← Меню", "menu")]])
    if data.startswith("m:"):
        _, slug, source = (data.split(":", 2) + ["", ""])[:3]
        if get_game(slug) is not None and source in SOURCES:
            return method_forecast(slug, source), _kb([[("Обновить", data)], [("← К игре", f"g:{slug}"), ("← Меню", "menu")]])
    return main_menu()


# ── Цикл ───────────────────────────────────────────────────────────────────

class Api:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def call(self, method: str, read_timeout: float = 20, **params) -> dict:
        proxies = {"https": self.cfg["proxy"], "http": self.cfg["proxy"]} if self.cfg["proxy"] else None
        r = requests.post(f"{self.cfg['base']}/bot{self.cfg['token']}/{method}", json=params,
                          timeout=(10, read_timeout), proxies=proxies)
        return r.json()


def handle(update: dict, api, chat_id: str) -> None:
    """Обрабатывает одно обновление. Чужие чаты игнорируются."""
    cb = update.get("callback_query")
    if cb:
        msg = cb.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != str(chat_id):
            return
        text, kb = route(cb.get("data") or "")
        api.call("answerCallbackQuery", callback_query_id=cb["id"])
        res = api.call("editMessageText", chat_id=chat_id, message_id=msg.get("message_id"), text=text,
                       parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        # «message is not modified» — нажали ту же кнопку: это не ошибка
        if not res.get("ok") and "not modified" not in str(res.get("description", "")):
            api.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=kb,
                     disable_web_page_preview=True)
        return
    msg = update.get("message")
    if msg and str((msg.get("chat") or {}).get("id")) == str(chat_id):
        text, kb = main_menu()
        api.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=kb)


def run(stop=lambda: False, api=None, log=print) -> None:
    """Слушает бота (long polling), пока stop() не вернёт True."""
    cfg = notify.config()
    if not cfg["configured"]:
        raise RuntimeError("Telegram не настроен: задайте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env")
    api = api or Api(cfg)
    try:
        api.call("setMyCommands", commands=[{"command": "menu", "description": "Меню: статус, игры, уведомления"}])
    except requests.RequestException:
        pass
    offset = None
    log("Бот слушает Telegram. Напишите ему /menu")
    while not stop():
        try:
            res = api.call("getUpdates", read_timeout=POLL_S + 15, timeout=POLL_S, **({"offset": offset} if offset else {}),
                           allowed_updates=["message", "callback_query"])
        except (requests.RequestException, ValueError) as exc:
            log(f"нет связи с Telegram: {notify.scrub(str(exc))}")
            time.sleep(10)
            continue
        if not res.get("ok"):
            log(f"Telegram: {res.get('description')}")
            time.sleep(10)
            continue
        for u in res.get("result", []):
            offset = u["update_id"] + 1
            try:
                handle(u, api, cfg["chat_id"])
            except Exception as exc:  # noqa: BLE001 — одно нажатие не должно ронять бота
                log(f"ошибка обработки: {type(exc).__name__}: {notify.scrub(str(exc))}")
