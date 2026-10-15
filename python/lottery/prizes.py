"""Призы и число победителей по категориям — из ответа API о тираже.

Точная структура этих полей в API Столото заранее неизвестна (из среды разработки сайт
недоступен), поэтому разбор поиском: в ответе о тираже ищутся списки объектов, где есть
число победителей и сумма выигрыша. Найденное сохраняется в data/draws/prizes_<игра>.jsonl
(одна строка — один тираж), а два последних сырых ответа API по каждой игре — в
data/api_samples/<игра>.json, чтобы проверить разбор командой `lp.bat diagnose`.

Категория приводится к ключу исхода билета, как в калькуляторе шансов: «4+3» — 4 совпадения
в первом поле и 3 во втором, «5» — 5 совпадений в однопольной игре.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from pathlib import Path

from .fsutil import write_text
from .games import data_dir, draws_path

VERSION = 2   # версия разбора: записи старых версий перечитываются из API один раз
# игры, у которых разбор выплат менялся позже: 40.5 — Кено 2.0 (группы категорий),
# Топ-3 (подзаголовки «2 одинаковых / 3 разных числа»)
GAME_VERSION = {"keno2": 3, "top-3": 3}


def required_version(slug: str) -> int:
    return GAME_VERSION.get(slug, VERSION)

WINNER_KEYS = ("winners", "winnersCount", "winnerCount", "winnersAmount", "participants", "count",
               "quantity", "ticketsCount", "winTickets")
PRIZE_KEYS = ("prize", "amount", "winAmount", "prizeAmount", "sum", "money", "value", "prizeValue", "win")
LABEL_KEYS = ("combination", "category", "name", "title", "description", "matches", "guessed", "categoryName")
SALES_KEYS = ("betsCount", "ticketsCount", "totalBets", "ticketCount", "betCount", "participantsCount")
PRICE_KEYS = ("betCost", "ticketPrice", "betPrice", "price", "ticketCost", "minBetCost")
SUPER_KEYS = ("superPrize", "superprize", "jackpot", "superPrizeAmount")


def prizes_file(slug: str) -> Path:
    return draws_path(slug).with_name(f"prizes_{slug}.jsonl")


def samples_file(slug: str) -> Path:
    return data_dir() / "api_samples" / f"{slug}.json"


def _num(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    if isinstance(v, dict):       # {"amount": 100, "currency": "RUB"}
        for k in ("amount", "value", "sum"):
            if k in v:
                return _num(v[k])
    return None


def _first(d: dict, keys) -> tuple[str | None, object]:
    for k in keys:
        if k in d and d[k] is not None:
            return k, d[k]
    return None, None


def _label(item: dict) -> str | None:
    base = _label_main(item)
    sub = item.get("subTitle")
    sub = sub.get("ru") if isinstance(sub, dict) else sub
    # «Любой порядок 3» бывает двух видов: «2 одинаковых числа» и «3 разных числа» (Топ-3)
    if base and isinstance(sub, str) and sub.strip() and sub.strip().lower() not in base.lower():
        return f"{base} ({sub.strip()})"
    return base


def _label_main(item: dict) -> str | None:
    k, v = _first(item, LABEL_KEYS)
    if isinstance(v, (str, int)):
        return str(v)
    if isinstance(v, list):
        return "+".join(str(x) for x in v)
    if isinstance(v, dict):
        # {"ru": "2 + 2", "en": "2 + 2"} — переводы одной подписи
        for lang in ("ru", "en"):
            if isinstance(v.get(lang), str):
                return v[lang]
        nums = [x for x in v.values() if isinstance(x, (int, str))]
        return "+".join(str(x) for x in nums) if nums else None
    return None


def _score(cats: list[dict]) -> tuple:
    """Какой из найденных списков — настоящие категории выигрышей. В ответе API их
    несколько: winCategories (подписи «2 + 2», суммы в рублях), winners (часто одни
    нули, категории только номерами), winningCategories (строка JSON, суммы в копейках)."""
    informative = sum(1 for c in cats if (c["winners"] or 0) > 0 or (c["prize"] or 0) > 0)
    labeled = sum(1 for c in cats if not c["label"].startswith("#") and not c["label"].strip().isdigit())
    return informative > 0, labeled / len(cats), informative, len(cats)


def _categories(items: list) -> list[dict] | None:
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return None
        _, w = _first(item, WINNER_KEYS)
        _, p = _first(item, PRIZE_KEYS)
        winners, prize = _num(w), _num(p)
        if winners is None and prize is None:
            return None
        out.append({"label": _label(item) or f"#{i + 1}", "winners": winners, "prize": prize})
    return out if out and any(c["winners"] is not None for c in out) else None


def _walk(obj, depth=0):
    if depth > 4:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from _walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:50]:
            yield from _walk(v, depth + 1)


def draw_mechanism(raw: dict) -> str | None:
    """Способ розыгрыша по ответу API: у тиражей на лототроне есть видеозапись трансляции,
    тиражи ГСЧ идут «с секундами» (11:07:30). Иначе — неизвестно (у старых тиражей
    лототрона видео в архиве нет)."""
    if raw.get("videoLink"):
        return "L"
    date = str(raw.get("date") or "")
    m = re.search(r"T\d{2}:\d{2}:(\d{2})", date)
    if m and m.group(1) != "00":
        return "R"
    return None


def extract(raw: dict) -> dict | None:
    """Призы тиража из ответа API или None, если их там нет."""
    status = str(raw.get("status") or "COMPLETED").upper()
    if status not in ("COMPLETED", "FINISHED", "CLOSED"):
        return None             # тираж ещё не закрыт (PLAYING): выплаты не посчитаны
    best = None
    groups = raw.get("groupedCategories")
    if isinstance(groups, list):
        # Кено 2.0: категории разбиты на группы (чётность, столбец, «k из K» для каждого K)
        merged = [c for g in groups if isinstance(g, dict) for c in (g.get("categories") or [])]
        cats = _categories(merged) if len(merged) >= 2 else None
        if cats:
            best = ("groupedCategories", cats)
    for key, value in _walk({k: v for k, v in raw.items() if k not in ("combination", "winningCombination",
                                                                         "groupedCategories")}):
        if isinstance(value, list) and len(value) >= 2:
            cats = _categories(value)
            if cats and (best is None or _score(cats) > _score(best[1])):
                best = (key, cats)
    if best is None or not _score(best[1])[0]:
        return None
    out = {"no": raw.get("number"), "source": best[0], "categories": best[1], "v": VERSION}
    m = draw_mechanism(raw)
    if m:
        out["m"] = m
    for name, keys in (("sales", SALES_KEYS), ("price", PRICE_KEYS), ("super", SUPER_KEYS)):
        _, v = _first(raw, keys)
        if _num(v) is not None:
            out[name] = _num(v)
    return out


# ── Категория → ключ исхода билета ──────────────────────────────────────────

_PAIR_X = re.compile(r"(\d+)\s*(?:\+|x|х|×|\*)\s*(\d+)")   # «4 + 3», «4 X 3» (латинская и русская х)
_PAIR_OLD = re.compile(r"(\d+)\s*(?:и|/|-)\s*(\d+)")           # «4 и 3», «4/3»
_NOT_OUTCOME = ("тур", "джекпот", "чётн", "четн", "нечётн", "нечетн", "поровну", "порядок", "комбо", "люб")


def category_keys(label: str, n_blocks: int, block_counts: list[int]) -> list[str]:
    """Подпись категории из API → ключи исходов билета («4+3» — 4 совпадения в первом поле
    и 3 во втором, «5» — 5 совпадений в однопольной игре). Пустой список — не исход по
    числу совпадений (тур бинго, ставка на чётность, порядок цифр и т. п.).

    Подписи из настоящего API: «4 X 3 и 3 X 4» (4 из 20: оба варианта — одна категория),
    «2 + 2», «5 + 1» и «5» (5 из 36 плюс: без бонуса), «4 из 6», «2 или 10» (12 из 24:
    угадано 2 или 10 — одна категория)."""
    if not label or label.startswith("#"):
        return []
    s = label.lower().replace("—", "-").strip()
    if any(w in s for w in _NOT_OUTCOME):
        return []
    # слова в подписи — только про совпадения; «Столбец 8», «Сектор 2» — другие ставки
    if re.search(r"[а-яёa-z]", s.replace(" из ", " ").replace(" или ", " ").replace(" и ", " ")
                 .replace("x", "").replace("х", "")) and not any(w in s for w in ("угад", "совпад", "числ")):
        return []
    out: list[str] = []
    if n_blocks >= 2:
        pairs = _PAIR_X.findall(s) or _PAIR_OLD.findall(s)
        if pairs:
            out = [f"{int(a)}+{int(b)}" for a, b in pairs
                   if int(a) <= block_counts[0] and int(b) <= block_counts[1]]
        elif re.fullmatch(r"\d+", s) and int(s) <= block_counts[0]:
            out = [f"{int(s)}+0"]                 # «5» в «5 из 36 плюс» — без бонусного числа
    else:
        nums = [int(x) for x in re.findall(r"\d+", s)]
        if " из " in s and len(nums) >= 2:      # «5 из 36», «4 из 6» — первое число совпадения
            # «5 из 9» в Кено — ставка на 9 чисел, а мы считаем билет на 10: не наш исход
            nums = nums[:1] if nums[1] >= block_counts[0] else []
        elif " или " in s:                       # «2 или 10» — одна категория на два исхода
            pass
        elif len(nums) != 1:
            nums = []
        out = [str(n) for n in nums if n <= block_counts[0]]
    return list(dict.fromkeys(out))


def category_key(label: str, n_blocks: int, block_counts: list[int]) -> str | None:
    """Первый ключ категории (для отчётов) или None."""
    keys = category_keys(label, n_blocks, block_counts)
    return keys[0] if keys else None


def describe_keys(label: str, n_blocks: int, block_counts: list[int]) -> str:
    keys = category_keys(label, n_blocks, block_counts)
    return ", ".join(keys) if keys else "?"


# ── Хранение ──────────────────────────────────────────────────────────────
#
# data/draws/prizes_<игра>.jsonl — строка на тираж. У частых игр (Рапидо, Дважды два)
# это сотни тысяч тиражей и сотни мегабайт, поэтому:
#   * строки пишутся компактно: {"no": 1, "src": "...", "p": цена, "s": продажи,
#     "c": [[подпись, победители, выплата], ...]} (старый формат тоже читается);
#   * новые тиражи дописываются в конец, файл целиком переписывается, только если
#     изменились уже сохранённые тиражи;
#   * при загрузке в памяти держатся не записи, а хеши строк — чтобы понять, изменилось ли что-то.

_NO = re.compile(r'"no":\s*(\d+)')


def _compact(rec: dict) -> dict:
    out = {"no": rec.get("no"), "src": rec.get("source"), "v": rec.get("v", VERSION),
           "c": [[c["label"], c["winners"], c["prize"]] for c in rec["categories"]]}
    for long, short in (("price", "p"), ("sales", "s"), ("super", "sp"), ("m", "m")):
        if rec.get(long) is not None:
            out[short] = rec[long]
    return out


def _expand(r: dict) -> dict:
    if "categories" in r:            # формат 40.3.0–40.3.2
        return r
    out = {"no": r["no"], "source": r.get("src"), "v": r.get("v"),
           "categories": [{"label": c[0], "winners": c[1], "prize": c[2]} for c in r.get("c", [])]}
    for long, short in (("price", "p"), ("sales", "s"), ("super", "sp"), ("m", "m")):
        if short in r:
            out[long] = r[short]
    return out


def record_line(rec: dict) -> str:
    return json.dumps(_compact(rec), ensure_ascii=False, separators=(",", ":"))


def _lines(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield line


def _line_no(line: str) -> int | None:
    m = _NO.search(line[:40])
    return int(m.group(1)) if m else None


def load(slug: str, nos: set[int] | None = None) -> dict[int, dict]:
    """Записи о выплатах по номеру тиража (все или только номера из `nos`)."""
    path = prizes_file(slug)
    if not path.exists():
        return {}
    out = {}
    for line in _lines(path):
        if nos is not None and _line_no(line) not in nos:
            continue
        try:
            r = _expand(json.loads(line))
            out[int(r["no"])] = r
        except (ValueError, KeyError, TypeError, IndexError):
            continue
    return out


def line_hashes(slug: str) -> dict[int, int]:
    """Номер тиража → хеш сохранённой строки (без разбора JSON)."""
    path = prizes_file(slug)
    if not path.exists():
        return {}
    out = {}
    for line in _lines(path):
        no = _line_no(line)
        if no is not None:
            out[no] = hash(line)
    return out


def write_records(slug: str, changed: dict[int, str], known: dict[int, int]) -> None:
    """Сохраняет строки `changed` (номер → строка). known — номера и хеши уже сохранённых."""
    if not changed:
        return
    path = prizes_file(slug)
    last = max(known) if known else -1
    if path.exists() and min(changed) > last:
        text = "\n".join(changed[k] for k in sorted(changed)) + "\n"
        for attempt in range(8):                     # Windows: файл может держать антивирус
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(text)
                return
            except PermissionError:
                time.sleep(0.25 * (attempt + 1))
    merged: dict[int, str] = {}
    if path.exists():
        for line in _lines(path):
            no = _line_no(line)
            if no is not None:
                if '"categories"' in line:           # старый формат — заодно уплотняем
                    try:
                        line = record_line(_expand(json.loads(line)))
                    except (ValueError, KeyError, TypeError):
                        pass
                merged[no] = line
    merged.update(changed)
    write_text(path, "\n".join(merged[k] for k in sorted(merged)) + "\n")


def save(slug: str, records: dict[int, dict]) -> None:
    """Записать набор тиражей целиком (тесты и инструменты)."""
    if records:
        write_text(prizes_file(slug), "\n".join(record_line(records[k]) for k in sorted(records)) + "\n")


def save_samples(slug: str, raws: list[dict]) -> None:
    if raws:
        write_text(samples_file(slug), json.dumps(raws[-2:], ensure_ascii=False, indent=1))


class Cat(tuple):
    """Категория тиража: (победители, выплата). Кортеж вместо словаря — в разы меньше памяти
    на больших архивах; обращение c["prize"] / c["winners"] оставлено для удобства."""
    __slots__ = ()

    def __getitem__(self, k):
        if k == "winners":
            return tuple.__getitem__(self, 0)
        if k == "prize":
            return tuple.__getitem__(self, 1)
        return tuple.__getitem__(self, k)

    def get(self, k, default=None):
        return self[k] if k in ("winners", "prize") else default


_cache: dict[tuple, dict] = {}


@lru_cache(maxsize=4096)
def _keys_cached(label: str, n_blocks: int, counts: tuple[int, ...]) -> tuple[str, ...]:
    return tuple(category_keys(label, n_blocks, list(counts)))


def keyed_history(slug: str, block_counts: list[int]) -> dict[int, dict]:
    """По тиражу: ключ исхода → (победители, выплата), плюс цена и продажи. Нераспознанные
    категории пропускаются. Результат кэшируется в процессе, пока файл не изменился."""
    path = prizes_file(slug)
    if not path.exists():
        return {}
    st = path.stat()
    sig = (slug, tuple(block_counts), st.st_mtime_ns, st.st_size)
    if sig in _cache:
        return _cache[sig]
    counts = tuple(block_counts)
    out = {}
    for line in _lines(path):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        cats_raw = r.get("c") if "c" in r else [[c["label"], c["winners"], c["prize"]]
                                                   for c in r.get("categories", [])]
        cats = {}
        for label, w, prize in cats_raw:
            keys = _keys_cached(label, len(counts), counts)
            for key in keys:
                # категория на несколько исходов («4 X 3 и 3 X 4»): выплата та же,
                # победители делятся поровну, чтобы сумма по исходам не удваивалась
                cats[key] = Cat((w / len(keys) if w is not None else None, prize))
        if cats:
            out[int(r["no"])] = {"categories": cats, "price": r.get("p", r.get("price")),
                                 "sales": r.get("s", r.get("sales"))}
    _cache.clear()                    # держим в памяти только последнюю игру
    _cache[sig] = out
    return out


def typical_prizes(slug: str, block_counts: list[int], last: int = 50) -> dict:
    """Медиана выплаты на победителя по каждой категории за последние `last` тиражей и цена
    билета, если API её сообщает."""
    import numpy as np
    from collections import deque
    path = prizes_file(slug)
    if not path.exists():
        return {"prizes": {}, "price": None, "draws": 0}
    counts = tuple(block_counts)
    tail: deque = deque(maxlen=last * 2)
    for line in _lines(path):                       # без разбора JSON — только хвост
        tail.append(line)
    recent = []
    parsed = []
    for line in sorted(tail, key=lambda s: _line_no(s) or 0):
        try:
            parsed.append(_expand(json.loads(line)))
        except (ValueError, KeyError):
            continue
    for r in clean(parsed):
        cats = {}
        for c in r["categories"]:
            for key in _keys_cached(c["label"], len(counts), counts):
                cats[key] = c["prize"]
        if cats:
            recent.append((cats, r.get("price")))
    recent = recent[-last:]
    if not recent:
        return {"prizes": {}, "price": None, "draws": 0}
    by_key: dict[str, list[float]] = {}
    for cats, _ in recent:
        for key, prize in cats.items():
            if prize and prize > 0:
                by_key.setdefault(key, []).append(prize)
    prices = [p for _, p in recent if p]
    return {"prizes": {k: float(np.median(v)) for k, v in by_key.items()},
            "price": float(np.median(prices)) if prices else None, "draws": len(recent)}


# ── Шансы по архиву ──────────────────────────────────────────────────────────

def _tail(slug: str, last: int) -> list[dict]:
    """Последние `last` записей файла выплат (разбирается только хвост)."""
    from collections import deque
    path = prizes_file(slug)
    if not path.exists():
        return []
    tail: deque = deque(maxlen=last)
    for line in _lines(path):
        tail.append(line)
    out = []
    for line in tail:
        try:
            out.append(_expand(json.loads(line)))
        except (ValueError, KeyError, TypeError):
            continue
    return sorted(out, key=lambda r: r.get("no") or 0)


def typical_by_label(slug: str, last: int = 50) -> dict[str, float]:
    """Медиана выплаты по подписи категории за последние тиражи (ненулевые выплаты)."""
    import numpy as np
    by: dict[str, list[float]] = {}
    for r in _tail(slug, last):
        for c in r["categories"]:
            if c["prize"] and c["prize"] > 0:
                by.setdefault(c["label"], []).append(c["prize"])
    return {k: float(np.median(v)) for k, v in by.items()}


def archive_stats(slug: str, last: int = 200) -> dict | None:
    """Шансы и возврат по реальным итогам последних тиражей — для любых игр, в том числе
    тех, где точный расчёт невозможен (туры бинго, ставки на порядок цифр, чётность).

    Шанс категории на одну ставку = победителей / проданных ставок (суммарно по тиражам);
    вклад в возврат = выплачено в категории / (ставок × цена). Это оценка по истории: в ней
    есть и популярность комбинаций, и множители ставок, если игроки их используют."""
    import numpy as np
    recs = clean([r for r in _tail(slug, last) if r.get("sales") and r.get("price")])
    if len(recs) < 10:
        return None
    spent = sum(r["sales"] * r["price"] for r in recs)
    bets = sum(r["sales"] for r in recs)
    rows: dict[str, dict] = {}
    order: list[str] = []
    for r in recs:
        for c in r["categories"]:
            row = rows.get(c["label"])
            if row is None:
                row = rows[c["label"]] = {"label": c["label"], "winners": 0.0, "paid": 0.0, "prizes": [], "draws": 0}
                order.append(c["label"])
            w, p = c["winners"] or 0.0, c["prize"] or 0.0
            row["winners"] += w
            row["paid"] += w * p
            row["draws"] += 1
            if p > 0 and w > 0:
                row["prizes"].append(p)
    cats = []
    for label in order:
        row = rows[label]
        chance = row["winners"] / bets if bets else 0.0
        cats.append({"label": label, "chance": chance, "one_in": (1 / chance) if chance > 0 else None,
                     "prize": float(np.median(row["prizes"])) if row["prizes"] else None,
                     "return": row["paid"] / spent if spent else 0.0, "winners": row["winners"]})
    total = sum(c["return"] for c in cats)
    return {"draws": len(recs), "from": recs[0]["no"], "to": recs[-1]["no"],
            "price": float(np.median([r["price"] for r in recs])),
            "bets_per_draw": bets / len(recs), "return": total,
            "p_any": min(1.0, sum(c["chance"] for c in cats)), "categories": cats}


_M = re.compile(r'"m":"([LR])"')


def mechanisms(slug: str) -> dict[int, str]:
    """Номер тиража → способ розыгрыша из сохранённых ответов API (без разбора JSON)."""
    path = prizes_file(slug)
    if not path.exists():
        return {}
    out = {}
    for line in _lines(path):
        m = _M.search(line)
        if m:
            no = _line_no(line)
            if no is not None:
                out[no] = m.group(1)
    return out


ANOMALY_SHARE = 0.1     # продажи меньше 10% от обычных — тираж-аномалия (сбой, тестовый тираж)


def clean(recs: list[dict]) -> list[dict]:
    """Убирает тиражи с аномально малыми продажами: по ним выплаты и возврат искажены
    (например, «6 из 45» №16382 — 2926 ставок при обычных сотнях тысяч)."""
    import numpy as np
    sales = [r["sales"] for r in recs if r.get("sales")]
    if len(sales) < 10:
        return recs
    out = []
    for i, r in enumerate(recs):
        lo, hi = max(0, i - 50), min(len(recs), i + 51)
        near = [x["sales"] for x in recs[lo:hi] if x.get("sales")]
        med = float(np.median(near)) if near else 0
        if r.get("sales") and med and r["sales"] < ANOMALY_SHARE * med:
            continue
        out.append(r)
    return out


def anomalies(slug: str) -> list[int]:
    """Номера тиражей с аномально малыми продажами (для diagnose)."""
    path = prizes_file(slug)
    if not path.exists():
        return []
    recs = []
    for line in _lines(path):
        m = re.search(r'"s":([0-9.]+)', line) or re.search(r'"sales":\s*([0-9.]+)', line)
        no = _line_no(line)
        if no is not None:
            recs.append({"no": no, "sales": float(m.group(1)) if m else None})
    kept = {r["no"] for r in clean(recs)}
    return [r["no"] for r in recs if r["no"] not in kept]
