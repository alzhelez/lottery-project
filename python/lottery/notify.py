"""Уведомления в Telegram.

Настройка (.env в папке проекта):
    TELEGRAM_BOT_TOKEN=123456:ABC...   токен бота от @BotFather
    TELEGRAM_CHAT_ID=123456789         куда писать (узнать: lp.bat telegram setup)
    TELEGRAM_EVENTS=journal,auto,godmode,errors,drift,ev   какие события присылать (по умолчанию все)
    TELEGRAM_EV_THRESHOLD=1   порог ожидаемого возврата ближайшего тиража для события ev
    TELEGRAM_PROXY=socks5://host:port  если api.telegram.org недоступен напрямую (нужен pip install pysocks)
    TELEGRAM_API_BASE=https://...      свой адрес Bot API (зеркало или локальный сервер)

Отправка никогда не прерывает основную работу: ошибки пишутся в data/logs/telegram.log
(токен в журнале скрывается). Если api.telegram.org не отвечает, сообщение не теряется: оно
ложится в очередь data/telegram_outbox.json и уходит при следующей отправке (не старше суток),
а следующие 10 минут программа не тратит время на попытки связаться.
"""
from __future__ import annotations

import html
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta

import requests

from .games import data_dir

EVENTS = ("journal", "auto", "godmode", "errors", "drift", "ev")
TIMEOUT = (10, 20)          # соединение, ответ
ATTEMPTS = 2
PAUSE_MIN = 10              # после неудачной попытки связи — столько минут не пытаемся снова
OUTBOX_MAX_AGE_H = 24
OUTBOX_MAX = 200
_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")
_lock = threading.RLock()
_down_until: datetime | None = None
_scrubbed = False


def config() -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    events = {e.strip() for e in os.environ.get("TELEGRAM_EVENTS", ",".join(EVENTS)).split(",") if e.strip()}
    return {
        "token": token,
        "chat_id": chat,
        "events": events,
        "base": os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/"),
        "proxy": os.environ.get("TELEGRAM_PROXY", "").strip() or None,
        "configured": bool(token and chat),
    }


def scrub(text: str) -> str:
    """Убирает токен бота из текста (адрес запроса попадает в текст ошибки requests)."""
    return _TOKEN_RE.sub("bot***", text)


def _log(text: str) -> None:
    global _scrubbed
    path = data_dir() / "logs" / "telegram.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        if not _scrubbed and path.exists():
            # журналы версий до 41.3.0 содержали токен в тексте ошибок — вычищаем один раз
            old = path.read_text(encoding="utf-8", errors="replace")
            clean = scrub(old)
            if clean != old:
                path.write_text(clean, encoding="utf-8")
        _scrubbed = True
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {scrub(text)}\n")


def _call(cfg: dict, method: str, **params) -> dict:
    proxies = {"https": cfg["proxy"], "http": cfg["proxy"]} if cfg["proxy"] else None
    last = None
    for attempt in range(ATTEMPTS):
        try:
            r = requests.post(f"{cfg['base']}/bot{cfg['token']}/{method}", json=params, timeout=TIMEOUT,
                              proxies=proxies)
            data = r.json()
            if data.get("ok"):
                return data
            last = data.get("description") or f"HTTP {r.status_code}"
            if r.status_code in (400, 401, 403, 404):
                raise Rejected(last)                    # неверный токен или чат — повтор не поможет
            if r.status_code == 429:
                time.sleep(min(int((data.get("parameters") or {}).get("retry_after", 2)), 30))
                continue
        except (requests.RequestException, ValueError) as exc:
            last = scrub(str(exc))
            if attempt + 1 < ATTEMPTS:
                time.sleep(1 + attempt)
            continue
        if attempt + 1 < ATTEMPTS:
            time.sleep(1 + attempt)
    raise RuntimeError(last or "нет ответа от Telegram")


class Rejected(RuntimeError):
    """Telegram отказал (неверный токен, чат, текст) — повтор не поможет."""


def _outbox_path():
    return data_dir() / "telegram_outbox.json"


def _load_outbox() -> list[dict]:
    try:
        return json.loads(_outbox_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_outbox(items: list[dict]) -> None:
    from .fsutil import write_text
    path = _outbox_path()
    if not items:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, json.dumps(items[-OUTBOX_MAX:], ensure_ascii=False))


def _deliver(cfg: dict, item: dict) -> None:
    text = item["text"]
    if item.get("queued_at") and item.get("delayed"):
        text = f"<i>Отложено с {esc(item['queued_at'][11:16])} — Telegram был недоступен</i>\n" + text
    for part in _chunks(text):
        _call(cfg, "sendMessage", chat_id=cfg["chat_id"], text=part, parse_mode="HTML",
              disable_web_page_preview=True)


def flush(cfg: dict | None = None) -> int:
    """Отправляет очередь неотправленных сообщений. Возвращает, сколько осталось."""
    global _down_until
    cfg = cfg or config()
    with _lock:
        items = _load_outbox()
        if not items or not cfg["configured"]:
            return len(items)
        if _down_until and datetime.now() < _down_until:
            return len(items)
        edge = (datetime.now() - timedelta(hours=OUTBOX_MAX_AGE_H)).isoformat(timespec="seconds")
        old = [i for i in items if i["queued_at"] < edge]
        if old:
            _log(f"очередь: {len(old)} сообщ. старше {OUTBOX_MAX_AGE_H} ч удалено")
        items = [i for i in items if i["queued_at"] >= edge]
        while items:
            try:
                _deliver(cfg, items[0])
            except Rejected as exc:
                _log(f"[{items[0]['event']}] не принято Telegram, удалено из очереди: {exc}")
            except RuntimeError as exc:
                _down_until = datetime.now() + timedelta(minutes=PAUSE_MIN)
                _log(f"[{items[0]['event']}] не отправлено (в очереди {len(items)}): {exc}")
                break
            items.pop(0)
        _save_outbox(items)
        return len(items)


def send(text: str, event: str = "auto", cfg: dict | None = None, force: bool = False) -> bool:
    """Отправляет сообщение (HTML). True — отправлено сейчас. False — не настроено, событие
    выключено или Telegram недоступен (тогда сообщение ждёт в очереди и уйдёт позже).
    force=True — отправить, даже если событие выключено в TELEGRAM_EVENTS (для теста; такое
    сообщение в очередь не ставится)."""
    global _down_until
    cfg = cfg or config()
    if not cfg["configured"] or (event not in cfg["events"] and not force):
        return False
    item = {"text": text, "event": event, "queued_at": datetime.now().isoformat(timespec="seconds")}
    with _lock:
        if flush(cfg) == 0 and not (_down_until and datetime.now() < _down_until):
            try:
                _deliver(cfg, item)
                return True
            except Rejected as exc:
                _log(f"[{event}] не отправлено: {exc}")
                return False
            except RuntimeError as exc:
                _down_until = datetime.now() + timedelta(minutes=PAUSE_MIN)
                _log(f"[{event}] не отправлено, сообщение в очереди: {exc}")
        if force:
            return False
        _save_outbox(_load_outbox() + [{**item, "delayed": True}])
        return False


def _chunks(text: str, limit: int = 3900) -> list[str]:
    """Telegram принимает до 4096 символов — длинное сообщение делим по строкам."""
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit and cur:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur)
    return out


def updates(cfg: dict | None = None) -> list[dict]:
    """Чаты, которые писали боту: [{id, title}] — для настройки TELEGRAM_CHAT_ID."""
    cfg = cfg or config()
    data = _call(cfg, "getUpdates", timeout=0)
    chats = {}
    for u in data.get("result", []):
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            title = chat.get("title") or " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) \
                or chat.get("username") or str(chat["id"])
            chats[chat["id"]] = {"id": chat["id"], "title": title, "type": chat.get("type")}
    return list(chats.values())


def me(cfg: dict | None = None) -> dict:
    cfg = cfg or config()
    return _call(cfg, "getMe")["result"]


# ── Тексты сообщений ──────────────────────────────────────────────────────

def esc(s) -> str:
    return html.escape(str(s))


def fmt_blocks(blocks) -> str:
    return " | ".join(" ".join(str(v) for v in b) for b in blocks)


def _rub(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def _dec(v: float, digits: int) -> str:
    return f"{v:.{digits}f}".replace(".", ",")


SHORT = {"analysis_best": "Л", "analysis_consensus": "К", "chaos": "Х", "godmode": "Б"}


def journal_digest(games: list[tuple[str, list[dict]]]) -> str | None:
    """Одно сообщение о сверке прогнозов по всем играм загрузки (вместо сообщения на игру):
    строка на тираж — выпавшие числа и сколько угадал каждый источник."""
    lines, n, hits, expected, won = [], 0, 0, 0.0, 0.0
    placed, placed_exp = 0, 0.0
    for title, entries in games:
        checked = [e for e in entries if e.get("status") == "checked"]
        if not checked:
            continue
        by_draw: dict[int, list[dict]] = {}
        for e in checked:
            by_draw.setdefault(e["draw_no"], []).append(e)
        for no in sorted(by_draw):
            group = by_draw[no]
            parts = []
            for e in group:
                w = f" ({_rub(e['won'])} ₽)" if e.get("won") else ""
                parts.append(f"{SHORT.get(e['source'], e['source_title'][:1])} {e['hits']}{w}")
                n += 1
                hits += e["hits"]
                expected += e["expected"]
                won += e.get("won") or 0
                placed += e.get("in_place") or 0
                placed_exp += e.get("in_place_expected") or 0.0
            lines.append(f"<b>{esc(title)}</b> №{no} <code>{esc(fmt_blocks(group[0]['actual']))}</code>: "
                         f"{esc(' · '.join(parts))} (ожидание {_dec(group[0]['expected'], 2)})")
    if not lines:
        return None
    head = (f"<b>Сверка прогнозов</b>: {n} шт., угадано {hits} при ожидаемых {_dec(expected, 1)}"
            + (f", выиграно {_rub(won)} ₽" if won else "")
            + (f"; на своём месте {placed} при ожидаемых {_dec(placed_exp, 1)}" if placed_exp else ""))
    legend = "Л — лучший метод, К — консенсус, Х — порядок из хаоса, Б — режим Бога"
    return "\n".join([head, *lines, f"<i>{legend}</i>"])


def journal_message(title: str, entries: list[dict]) -> str | None:
    checked = [e for e in entries if e.get("status") in ("checked", "late")]
    if not checked:
        return None
    by_draw: dict[int, list[dict]] = {}
    for e in checked:
        by_draw.setdefault(e["draw_no"], []).append(e)
    lines = [f"<b>{esc(title)}</b> — сверка прогнозов"]
    for no in sorted(by_draw):
        group = by_draw[no]
        lines.append(f"\nТираж №{no}: выпало <code>{esc(fmt_blocks(group[0]['actual']))}</code>")
        for e in group:
            won = ", выигрыш " + f"{e['won']:,.0f}".replace(",", " ") + " ₽" if e.get("won") else ""
            late = " (прогноз после тиража — не засчитан)" if e["status"] == "late" else ""
            lines.append(f"• {esc(e['source_title'])}: угадано {e['hits']} при ожидаемых "
                         f"{e['expected']:.2f}".replace(".", ",") + won + late)
    return "\n".join(lines)


def auto_message(status: dict, predictions: dict[str, dict]) -> str:
    games = status.get("games", {})
    added = sum(g.get("added", 0) or 0 for g in games.values())
    checked = sum(g.get("journal_checked", 0) or 0 for g in games.values())
    errors = [s for s, g in games.items() if g.get("fetch") == "error"]
    lines = [f"<b>Автозапуск</b> {esc(status.get('started_at', '').replace('T', ' ')[:16])}",
             f"Новых тиражей: {added}, сверено прогнозов: {checked}"]
    if errors:
        lines.append(f"Ошибки загрузки: {esc(', '.join(errors))}")
    if predictions:
        lines.append("\nПрогнозы на следующие тиражи:")
        for slug, p in predictions.items():
            lines.append(f"• {esc(p['title'])} №{p['next_no']}: <code>{esc(fmt_blocks(p['numbers']))}</code>")
            if p.get("chaos"):
                lines.append(f"  порядок из хаоса ({esc(p['chaos']['title'])}): "
                             f"<code>{esc(fmt_blocks(p['chaos']['numbers']))}</code>")
    return "\n".join(lines)


def godmode_message(title: str, res: dict) -> str:
    return (f"<b>{esc(title)}</b> — режим Бога: {esc(res['stage'].lower())}\n"
            f"{esc(res['verdict'])}\n"
            f"Прогноз на тираж №{res['next']['no']}: <code>{esc(fmt_blocks(res['next']['numbers']))}</code>")


def drift_message(title: str, alarms: list[dict]) -> str:
    lines = [f"<b>{esc(title)}</b> — возможный дрейф"]
    for a in alarms[:5]:
        lines.append(f"• {esc(a['title'])}, {esc(a['block'])}: {esc(a['check'])} — p={a['p_adjusted']:.4f}; "
                     f"{esc(a['detail'])}")
    lines.append("Это сигнал проверить, а не прогноз: тревога засчитывается, если повторится в следующих тиражах.")
    return "\n".join(lines)


def ev_message(items: list[dict]) -> str:
    lines = ["<b>Ближайшие тиражи с возвратом выше порога</b>"]
    for r in items:
        when = (r.get("date") or "").replace("T", " ")[:16]
        sp = f"{r['super_prize']:,.0f}".replace(",", " ")
        lines.append(f"• {esc(r['title'])} №{r['number']} ({esc(when)}): возврат {r['return']:.2f} "
                     f"на рубль, суперприз {sp} ₽".replace(".", ",", 1))
    lines.append("Ожидание в среднем по очень большому числу билетов; почти все билеты проигрывают.")
    return "\n".join(lines)
