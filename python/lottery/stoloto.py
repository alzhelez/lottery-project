"""Загрузка архива тиражей с stoloto.ru.

Алгоритм обновления игры:
  1. legacy-файлы (data/tirazh*.txt) сливаются в data/draws (данные API приоритетнее);
  2. файла нет → определяем дату первого тиража бинарным поиском и качаем всё по годам;
  3. файл есть → докачиваем тиражи с даты последнего, заполняем пропуски в нумерации
     (запросом окна дат между соседними известными тиражами) и ранние тиражи;
  4. прогресс сохраняется на диск каждые несколько страниц — прерывание не теряет данные.
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

from .drawfile import Draw, load_game_draws, merge_legacy, write_draws
from . import prizes as prizes_mod
from .fsutil import cleanup_stale_tmp, write_text
from .games import Game, all_games, data_dir, draws_path, get_game, read_meta, write_meta

API_BASE = os.environ.get("STOLOTO_API_BASE", "https://www.stoloto.ru/p/api/mobile/api/v35/service").rstrip("/")
PAGE_SIZE = 50
WINDOW_DAYS = 365
EPOCH = datetime(2009, 1, 1)
REQUEST_DELAY = float(os.environ.get("STOLOTO_DELAY", "0.2"))
FLUSH_EVERY_S = 30         # файл переписывается не чаще раза в 30 с (и в конце загрузки)
FLUSH_MAX_PAGES = 40       # …или каждые 40 страниц (2000 тиражей), если API отвечает быстро
REPAIR_LIMIT = 2000        # больше испорченных тиражей — перекачиваем весь период целиком

_DEFAULT_COOKIE = (
    "ga=7ec1530511-3a8b64-498989-81db45-c10b0c6087d137; accept_cookies=true; gosloto_locale=ru"
)
HEADERS = {
    "accept": "*/*",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/x-www-form-urlencoded",
    "device-platform": "DESKTOP",
    "device-type": "STOLOTO",
    "gosloto-partner": "bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg",
    "gosloto-token": os.environ.get("STOLOTO_TOKEN", "7ec1530511-3a8b64-498989-81db45-c10b0c6087d137"),
    "referer": "https://www.stoloto.ru/4x20/archive",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"),
    "Cookie": os.environ.get("STOLOTO_COOKIE", _DEFAULT_COOKIE),
}
GAMES_TOKEN = os.environ.get("STOLOTO_GAMES_TOKEN", "161aa1be13-07d882-41dd32-8fa380-de2eea7bf30a66")

# Не больше двух одновременных запросов к API — иначе HTTP 429
_API_SEMAPHORE = threading.BoundedSemaphore(2)

# Прокси системы мешают прямому доступу к stoloto.ru
for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)


class ApiUnavailable(RuntimeError):
    def __init__(self, message: str, network: bool = False):
        super().__init__(message)
        self.network = network  # True — сервер не отвечает вовсе (нет сети, DNS, отказ соединения)


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")


def fmt_datetime(iso: str) -> str:
    """'2026-04-10T15:30:00.000+03:00' → '10.04.2026 15:30'."""
    try:
        return datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return ""


# ── Разбор ответа API ─────────────────────────────────────────────────────

def _int_list(raw) -> list[int]:
    """Целые неотрицательные числа. Ноль — законное значение (цифровые игры вроде «Топ-3»):
    раньше нули отбрасывались для всех игр, кроме отмеченных в реестре, и данные портились,
    если имя игры в API отличалось от реестра (top-3 вместо top3)."""
    out = []
    for v in raw:
        try:
            n = int(v)
        except (ValueError, TypeError):
            continue
        if n >= 0:
            out.append(n)
    return out


def _split(nums: list[int], counts: tuple[int, ...]) -> list[list[int]]:
    """Делит плоский список по подсказке counts; если длина не совпадает — один блок."""
    if counts and sum(counts) == len(nums):
        out, pos = [], 0
        for c in counts:
            out.append(nums[pos:pos + c])
            pos += c
        return out
    if counts and len(counts) > 1 and len(nums) > sum(counts) >= counts[0]:
        # лишние числа (например, служебные) — берём ожидаемое количество
        out, pos = [], 0
        for c in counts:
            out.append(nums[pos:pos + c])
            pos += c
        return out
    return [nums] if nums else []


def extract_blocks(draw: dict, game: Game) -> list[list[int]]:
    """Числа тиража из ответа API. Поддерживаемые форматы combination.structured:

    A) [22, 10, 44, 2, 7, 35]                     — плоский список
    B) {"played": [...], "notPlayed": [...]}      — два блока
    C) {"notPlayed": [...]}                       — один блок
    D) [{"first": [7, 9, 1], "second": [1]}]      — два блока
    E) {"played": [...], "parity": ..., ...}      — played
    Запасные поля: winningCombination, numbers, drawnNumbers, playedNumbers.
    """
    comb = draw.get("combination") or {}
    structured = comb.get("structured") if isinstance(comb, dict) else None

    if isinstance(structured, list) and structured and isinstance(structured[0], dict):
        d = structured[0]
        blocks = [_int_list(d.get(key) or []) for key in ("first", "second")]
        blocks = [b for b in blocks if b]
        if blocks:
            return blocks
    if isinstance(structured, dict):
        played = _int_list(structured.get("played") or [])
        not_played = _int_list(structured.get("notPlayed") or [])
        if played and not_played:
            both = played + not_played
            if (len(both) >= 20 and len(set(both)) == len(both)
                    and sorted(both) == list(range(min(both), max(both) + 1))):
                # бинго: выпавшие + невыпавшие = весь диапазон; невыпавшие выводятся из выпавших
                return [played]
            return [played, not_played]
        if played:
            return _split(played, game.counts)
        if not_played:
            return [not_played]
    if isinstance(structured, list) and structured:
        nums = _int_list(structured)
        if nums:
            return _split(nums, game.counts)
    wc = draw.get("winningCombination")
    if isinstance(wc, list) and wc:
        nums = _int_list(wc)
        if nums:
            return _split(nums, game.counts)
    for key in ("numbers", "drawnNumbers", "playedNumbers"):
        raw = draw.get(key)
        if isinstance(raw, list) and raw:
            nums = _int_list(raw)
            if nums:
                return _split(nums, game.counts)
    return []


def api_draw_to_draw(raw: dict, game: Game) -> Draw | None:
    date = fmt_datetime(raw.get("date", ""))
    try:
        no = int(raw.get("number"))
    except (TypeError, ValueError):
        return None
    blocks = extract_blocks(raw, game)
    if not date or not blocks:
        return None  # тираж без чисел бесполезен для анализа — останется пропуском
    return Draw(no=no, date=date, blocks=tuple(tuple(b) for b in blocks))


# ── HTTP ──────────────────────────────────────────────────────────────────

def _get(url: str, params: dict, headers: dict | None = None, retries: int = 5, log=print) -> dict | None:
    """GET с ретраями. None — данных нет (400/404). ApiUnavailable — сеть/сервер недоступны."""
    last_err = ""
    network_fails = 0
    for attempt in range(retries + 1):
        try:
            with _API_SEMAPHORE:
                resp = requests.get(url, headers=headers or HEADERS, params=params, timeout=30)
            if resp.status_code == 429:
                wait = min(2 ** (attempt + 1), 60)
                log(f"HTTP 429 (лимит запросов), пауза {wait} с")
                time.sleep(wait)
                continue
            if resp.status_code in (400, 404):
                return None
            if resp.status_code in (401, 403):
                raise ApiUnavailable(
                    f"API Столото отказало в доступе (HTTP {resp.status_code}). Обновите STOLOTO_COOKIE "
                    "и STOLOTO_TOKEN в файле .env значениями из браузера (см. README).")
            if resp.status_code >= 500:
                last_err = f"HTTP {resp.status_code}"
                time.sleep(min(2 ** (attempt + 1), 30))
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_err = str(exc)
            network_fails += 1
            if network_fails >= 3:   # нет соединения — не тратим минуты на ретраи
                raise ApiUnavailable(f"Нет связи с API Столото: {last_err}", network=True) from exc
            time.sleep(2 * network_fails)
        except (requests.RequestException, ValueError) as exc:
            last_err = str(exc)
            if attempt < retries:
                time.sleep(min(2 ** (attempt + 1), 30))
    raise ApiUnavailable(f"API Столото недоступно: {last_err or 'превышен лимит повторов'}")


def archive_page(game: Game, date_from: datetime, date_to: datetime, page: int, count: int = PAGE_SIZE,
                 log=print) -> tuple[list[dict], bool]:
    data = _get(f"{API_BASE}/draws/archive", {
        "game": game.slug, "date_from": fmt_date(date_from), "date_to": fmt_date(date_to),
        "count": count, "page": page,
    }, log=log)
    if not isinstance(data, dict):
        return [], False
    draws = data.get("draws") or []
    has_more = bool(data.get("hasMore", len(draws) >= count))
    return draws, has_more


def has_draws(game: Game, date_from: datetime, date_to: datetime, log=print) -> bool:
    data = _get(f"{API_BASE}/draws/archive", {
        "game": game.slug, "date_from": fmt_date(date_from), "date_to": fmt_date(date_to),
        "count": 1, "page": 1,
    }, log=log)
    if not isinstance(data, dict):
        return False
    if data.get("draws"):
        return True
    total = data.get("totalCount", data.get("total", 0))
    return isinstance(total, (int, float)) and total > 0


TITLE_KEYS = ("title", "displayName", "gameTitle", "fullName", "caption", "label", "shortName", "nameRu")


def _api_title(game: dict) -> str | None:
    """Русское название игры из ответа API (имя поля в API заранее неизвестно)."""
    for key in TITLE_KEYS:
        v = game.get(key)
        if isinstance(v, str) and any("а" <= ch.lower() <= "я" or ch in "ёЁ" for ch in v):
            return v.strip()
    for v in game.values():   # любое строковое поле на кириллице
        if isinstance(v, str) and 2 < len(v) < 60 and any("а" <= ch.lower() <= "я" for ch in v):
            return v.strip()
    return None


def discover_games(log=print) -> list[str]:
    """Активные игры по данным API; при ошибке — пустой список. Список с названиями
    сохраняется в data/api_games.json (его читают реестр игр и интерфейс)."""
    headers = dict(HEADERS)
    headers["gosloto-token"] = GAMES_TOKEN
    try:
        data = _get(f"{API_BASE}/games/info-new", {}, headers=headers, retries=2, log=log)
    except ApiUnavailable as exc:
        log(f"Список игр из API не получен: {exc}")
        return []
    games = (data or {}).get("games", []) if isinstance(data, dict) else []
    active = [g for g in games if isinstance(g, dict) and g.get("active") and g.get("name")]
    if active:
        payload = {
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "games": [{"name": g["name"], "title": _api_title(g), "keys": sorted(g.keys())} for g in active],
        }
        write_text(data_dir() / "api_games.json", json.dumps(payload, ensure_ascii=False, indent=1))
    return [g["name"] for g in active]


# ── Обновление файла игры ───────────────────────────────────────────────────

def _last_day_of_month(y: int, m: int) -> datetime:
    return datetime(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)


def detect_first_draw_date(game: Game, log=print) -> datetime | None:
    """Дата первого тиража. Предикат «есть тиражи с EPOCH по конец периода» монотонен,
    поэтому бинарный поиск корректен даже для закрытых игр (в старой версии
    проверялся отдельный год, и поиск ломался, если игра уже не проводится)."""
    today = datetime.today()
    if not has_draws(game, EPOCH, today, log=log):
        return None

    def search(units, end_of):
        lo, hi = 0, len(units) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if has_draws(game, EPOCH, min(end_of(units[mid]), today), log=log):
                hi = mid
            else:
                lo = mid + 1
            time.sleep(REQUEST_DELAY)
        return units[lo]

    year = search(list(range(EPOCH.year, today.year + 1)), lambda y: datetime(y, 12, 31))
    month = search(list(range(1, 13)), lambda m: _last_day_of_month(year, m))
    last = _last_day_of_month(year, month).day
    day = search(list(range(1, last + 1)), lambda d: datetime(year, month, d))
    return datetime(year, month, day)


class DrawStore:
    """Накопитель тиражей с периодической записью на диск."""

    def __init__(self, game: Game, existing: list[Draw]):
        self.game = game
        self.by_no = {d.no: d for d in existing}
        self.prizes = prizes_mod.load(game.slug)      # призы и победители по тиражам
        self._prizes_changed = False
        self.latest_raw: list[dict] = []              # сырые ответы API — для диагностики
        self.added = 0
        self._dirty_pages = 0
        self._last_flush = time.time()
        self._changed = False

    def add(self, raw_draws: list[dict]) -> None:
        for raw in raw_draws:
            d = api_draw_to_draw(raw, self.game)
            if d is None:
                continue
            rec = prizes_mod.extract(raw)
            if rec and self.prizes.get(d.no) != rec:
                self.prizes[d.no] = rec
                self._prizes_changed = True
            if not self.latest_raw or d.no >= max(int(r.get("number", 0)) for r in self.latest_raw):
                self.latest_raw = (self.latest_raw + [raw])[-2:]
            old = self.by_no.get(d.no)
            if old is None:
                self.added += 1
            if old != d:
                self._changed = True
            self.by_no[d.no] = d  # данные API перекрывают legacy
        self._dirty_pages += 1
        # Каждая запись переписывает весь файл: при частой записи больших архивов Windows
        # (антивирус) не успевает отпустить файл. Пишем по времени, а не каждые 5 страниц.
        if self._dirty_pages >= FLUSH_MAX_PAGES or time.time() - self._last_flush >= FLUSH_EVERY_S:
            self.flush()

    def flush(self) -> None:
        # переписываем файл, только если что-то изменилось: меньше записей — меньше
        # конфликтов с антивирусом и не сбрасывается кэш проверки на случайность
        if self.by_no and self._changed:
            write_draws(draws_path(self.game.slug), list(self.by_no.values()))
        if self._prizes_changed:
            prizes_mod.save(self.game.slug, self.prizes)
            self._prizes_changed = False
        if self.latest_raw:
            prizes_mod.save_samples(self.game.slug, self.latest_raw)
        self._dirty_pages = 0
        self._changed = False
        self._last_flush = time.time()


def fetch_range(game: Game, store: DrawStore, date_from: datetime, date_to: datetime, log=print,
                on_page=None) -> None:
    """Все тиражи за период: окна по году, внутри окна — по страницам."""
    start = date_from
    while start <= date_to:
        end = min(start + timedelta(days=WINDOW_DAYS - 1), date_to)
        page = 1
        while True:
            draws, has_more = archive_page(game, start, end, page, log=log)
            if draws:
                store.add(draws)
            if on_page:
                on_page(start, end, page, len(draws))
            if not draws or not has_more or len(draws) < PAGE_SIZE:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        start = end + timedelta(days=1)
        time.sleep(REQUEST_DELAY)


def _read_meta(game: Game) -> dict:
    return read_meta(game.slug)


def _write_meta(game: Game, meta: dict) -> None:
    write_meta(game.slug, **meta)


def expected_shape(game: Game, draws: list[Draw]) -> tuple[int, ...] | None:
    """Сколько чисел должно быть в каждом поле: из реестра, иначе — преобладающая форма
    (если у 90%+ тиражей она одинакова). None — форма переменная (бинго), чинить нечего."""
    if game.counts:
        return tuple(game.counts)
    if not draws:
        return None
    from collections import Counter
    shape, n = Counter(tuple(len(b) for b in d.blocks) for d in draws).most_common(1)[0]
    return shape if n / len(draws) >= 0.9 else None


def damaged(game: Game, draws: list[Draw]) -> list[Draw]:
    """Тиражи, в которых чисел меньше, чем должно быть (например, выброшенные нули)."""
    shape = expected_shape(game, draws)
    if shape is None:
        return []
    total = sum(shape)
    return [d for d in draws if tuple(len(b) for b in d.blocks) != shape and sum(len(b) for b in d.blocks) < total]


def _date_ranges(dates: list[datetime], join_days: int = 3) -> list[tuple[datetime, datetime]]:
    days = sorted({datetime(d.year, d.month, d.day) for d in dates})
    out: list[list[datetime]] = []
    for d in days:
        if out and (d - out[-1][1]).days <= join_days:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [(a, b) for a, b in out]


def _gap_ranges(draws: list[Draw]) -> list[tuple[int, int, datetime, datetime]]:
    """Пропуски нумерации и окна дат между соседними известными тиражами."""
    out = []
    for a, b in zip(draws, draws[1:]):
        if b.no - a.no > 1 and a.dt and b.dt:
            out.append((a.no + 1, b.no - 1, a.dt, b.dt))
    return out


def update_game(game: Game, log=print, on_status=None) -> dict:
    """Загружает или обновляет файл тиражей игры. Возвращает сводку."""
    t0 = time.time()
    legacy_added, legacy_conflicts = merge_legacy(game)
    existing = load_game_draws(game)
    store = DrawStore(game, existing)
    today = datetime.today()

    def status(msg: str) -> None:
        log(msg)
        if on_status:
            on_status({"message": msg, "draws": len(store.by_no)})

    def page_note(start, end, page, n):
        if on_status:
            on_status({"message": f"{fmt_date(start)}–{fmt_date(end)}, стр. {page}: {n} тиражей",
                       "draws": len(store.by_no)})

    if not existing:
        status("Определяю дату первого тиража…")
        first = detect_first_draw_date(game, log=log)
        if first is None:
            write_meta(game.slug, checked_at=datetime.now().isoformat(timespec="seconds"))
            return {"status": "no_data", "draws": 0, "added": 0, "message": "В архиве нет тиражей этой игры"}
        _write_meta(game, {"first_date": fmt_date(first), "repaired_v2": True})
        status(f"Первый тираж: {fmt_date(first)}. Загружаю архив…")
        fetch_range(game, store, first, today, log=log, on_page=page_note)
    else:
        last = max(existing, key=lambda d: d.no)
        last_dt = last.dt or today
        status(f"В файле {len(existing)} тиражей, докачиваю с {fmt_date(last_dt)}…")
        fetch_range(game, store, datetime(last_dt.year, last_dt.month, last_dt.day), today, log=log, on_page=page_note)

        first = min(existing, key=lambda d: d.no)
        meta = _read_meta(game)
        if first.no > 1 and first.dt and not meta.get("first_date"):
            real_first = detect_first_draw_date(game, log=log)
            if real_first:
                _write_meta(game, {**meta, "first_date": fmt_date(real_first)})
            if real_first and real_first.date() < first.dt.date():
                status(f"Догружаю ранние тиражи с {fmt_date(real_first)}…")
                fetch_range(game, store, real_first, first.dt, log=log, on_page=page_note)

        # Ремонт: тиражи, сохранённые старой версией с потерей чисел, перекачиваются один раз
        bad = damaged(game, list(store.by_no.values()))
        if bad and not meta.get("repaired_v2"):
            dated = [d.dt for d in bad if d.dt]
            ranges = ([(min(dated), max(dated))] if len(bad) > REPAIR_LIMIT
                      else _date_ranges(dated))
            for i, (d_from, d_to) in enumerate(ranges):
                status(f"Исправляю тиражи с неполными данными: {len(bad)} шт. ({i + 1}/{len(ranges)})")
                fetch_range(game, store, d_from, d_to, log=log)
        _write_meta(game, {**_read_meta(game), "repaired_v2": True})

        current = sorted(store.by_no.values(), key=lambda d: d.no)
        gaps = _gap_ranges(current)
        for i, (lo, hi, d_from, d_to) in enumerate(gaps[:200]):
            status(f"Заполняю пропуск №{lo}–{hi} ({i + 1}/{min(len(gaps), 200)})")
            fetch_range(game, store, d_from, d_to, log=log)
    store.flush()

    cleanup_stale_tmp(draws_path(game.slug).parent)
    if store.added:
        # после новых тиражей продолжить режим Бога нельзя — сохранение только занимает место
        from .godmode import drop_state
        from .games import results_dir
        drop_state(results_dir(game.slug) / "godmode_state.npz")
    final = sorted(store.by_no.values(), key=lambda d: d.no)
    missing = sum(b.no - a.no - 1 for a, b in zip(final, final[1:]))
    still_bad = len(damaged(game, final))
    write_meta(game.slug, checked_at=datetime.now().isoformat(timespec="seconds"))
    from . import notify
    from .journal import reconcile
    checked_entries: list[dict] = []
    journal_checked = reconcile(game, collect=checked_entries)
    if checked_entries:
        msg = notify.journal_message(game.title, checked_entries)
        if msg:
            notify.send(msg, "journal")
    return {
        "journal_checked": journal_checked,
        "status": "done" if final else "no_data",
        "draws": len(final),
        "added": store.added + legacy_added,
        "legacy_conflicts": legacy_conflicts,
        "damaged": still_bad,
        "missing": missing,
        "first_no": final[0].no if final else None,
        "last_no": final[-1].no if final else None,
        "seconds": round(time.time() - t0, 1),
        "message": "Готово" if final else "В архиве нет тиражей",
    }


def fetch_all(slugs: list[str] | None, emit, workers: int = 2) -> dict:
    """Загрузка всех игр (по 2 параллельно). emit(event) — события прогресса."""
    if not slugs:
        discovered = discover_games(log=lambda m: emit({"type": "log", "message": m}))
        local = sorted(p.stem[len("draws_"):] for p in draws_path("x").parent.glob("draws_*.txt"))
        if discovered:
            # активные по данным API + уже скачанные (чтобы обновлялись и они)
            slugs = discovered + [s for s in local if s not in discovered]
        else:
            registry = [g.slug for g in all_games()]
            slugs = registry + [s for s in local if s not in registry]
        emit({"type": "log", "message": f"Игр к загрузке: {len(slugs)}" +
              (f" (активных по API: {len(discovered)})" if discovered else " (список из реестра — API игр недоступно)")})
    emit({"type": "games", "games": slugs})
    results: dict[str, dict] = {}
    down: list[str] = []

    def one(slug: str) -> None:
        try:
            game = get_game(slug)
        except ValueError as exc:
            results[slug] = {"status": "error", "message": str(exc), "draws": 0}
            emit({"type": "game", "game": slug, **results[slug]})
            return
        if down:
            res = {"status": "error", "message": "Пропущено: нет связи с API Столото", "draws": len(load_game_draws(game))}
            results[slug] = res
            emit({"type": "game", "game": slug, **res})
            return
        emit({"type": "game", "game": slug, "status": "running", "message": "Начало загрузки"})
        try:
            res = update_game(
                game,
                log=lambda m: None,
                on_status=lambda s: emit({"type": "game", "game": slug, "status": "running", **s}),
            )
        except ApiUnavailable as exc:
            if exc.network:
                down.append(str(exc))
            res = {"status": "error", "message": str(exc), "draws": len(load_game_draws(game))}
        except Exception as exc:  # одна игра не должна ронять загрузку остальных
            res = {"status": "error", "message": f"{type(exc).__name__}: {exc}", "draws": len(load_game_draws(game))}
        results[slug] = res
        emit({"type": "game", "game": slug, **res})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, slugs))
    from .games import results_dir
    from .godmode import cleanup_states
    cleanup_states(results_dir())
    return results
