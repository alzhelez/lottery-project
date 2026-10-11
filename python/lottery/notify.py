"""Уведомления в Telegram.

Настройка (.env в папке проекта):
    TELEGRAM_BOT_TOKEN=123456:ABC...   токен бота от @BotFather
    TELEGRAM_CHAT_ID=123456789         куда писать (узнать: lp.bat telegram setup)
    TELEGRAM_EVENTS=journal,auto,godmode,errors   какие события присылать (по умолчанию все)
    TELEGRAM_PROXY=socks5://host:port  если api.telegram.org недоступен напрямую (нужен pip install pysocks)
    TELEGRAM_API_BASE=https://...      свой адрес Bot API (зеркало или локальный сервер)

Отправка никогда не прерывает основную работу: ошибки пишутся в data/logs/telegram.log.
"""
from __future__ import annotations

import html
import os
import time
from datetime import datetime

import requests

from .games import data_dir

EVENTS = ("journal", "auto", "godmode", "errors")
TIMEOUT = 15


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


def _log(text: str) -> None:
    path = data_dir() / "logs" / "telegram.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}\n")


def _call(cfg: dict, method: str, **params) -> dict:
    proxies = {"https": cfg["proxy"], "http": cfg["proxy"]} if cfg["proxy"] else None
    last = None
    for attempt in range(3):
        try:
            r = requests.post(f"{cfg['base']}/bot{cfg['token']}/{method}", json=params, timeout=TIMEOUT,
                              proxies=proxies)
            data = r.json()
            if data.get("ok"):
                return data
            last = data.get("description") or f"HTTP {r.status_code}"
            if r.status_code in (400, 401, 403, 404):
                break                                   # неверный токен или чат — повтор не поможет
            if r.status_code == 429:
                time.sleep(min(int((data.get("parameters") or {}).get("retry_after", 2)), 30))
                continue
        except (requests.RequestException, ValueError) as exc:
            last = str(exc)
        time.sleep(1 + attempt)
    raise RuntimeError(last or "нет ответа от Telegram")


def send(text: str, event: str = "auto", cfg: dict | None = None, force: bool = False) -> bool:
    """Отправляет сообщение (HTML). False — не настроено, событие выключено или ошибка.
    force=True — отправить, даже если событие выключено в TELEGRAM_EVENTS (для теста)."""
    cfg = cfg or config()
    if not cfg["configured"] or (event not in cfg["events"] and not force):
        return False
    try:
        for part in _chunks(text):
            _call(cfg, "sendMessage", chat_id=cfg["chat_id"], text=part, parse_mode="HTML",
                  disable_web_page_preview=True)
        return True
    except RuntimeError as exc:
        _log(f"[{event}] не отправлено: {exc}")
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
    return "\n".join(lines)


def godmode_message(title: str, res: dict) -> str:
    return (f"<b>{esc(title)}</b> — режим Бога: {esc(res['stage'].lower())}\n"
            f"{esc(res['verdict'])}\n"
            f"Прогноз на тираж №{res['next']['no']}: <code>{esc(fmt_blocks(res['next']['numbers']))}</code>")
