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
from pathlib import Path

from .fsutil import write_text
from .games import data_dir, draws_path

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
    k, v = _first(item, LABEL_KEYS)
    if isinstance(v, (str, int)):
        return str(v)
    if isinstance(v, list):
        return "+".join(str(x) for x in v)
    if isinstance(v, dict):
        nums = [x for x in v.values() if isinstance(x, (int, str))]
        return "+".join(str(x) for x in nums) if nums else None
    return None


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


def extract(raw: dict) -> dict | None:
    """Призы тиража из ответа API или None, если их там нет."""
    best = None
    for key, value in _walk({k: v for k, v in raw.items() if k not in ("combination", "winningCombination")}):
        if isinstance(value, list) and len(value) >= 2:
            cats = _categories(value)
            if cats and (best is None or len(cats) > len(best[1])):
                best = (key, cats)
    if best is None:
        return None
    out = {"no": raw.get("number"), "source": best[0], "categories": best[1]}
    for name, keys in (("sales", SALES_KEYS), ("price", PRICE_KEYS), ("super", SUPER_KEYS)):
        _, v = _first(raw, keys)
        if _num(v) is not None:
            out[name] = _num(v)
    return out


# ── Категория → ключ исхода билета ──────────────────────────────────────────

_PAIR = re.compile(r"(\d+)\s*(?:\+|и|/|-|из)\s*(\d+)")


def category_key(label: str, n_blocks: int, block_counts: list[int]) -> str | None:
    """«4+3», «4 и 3», «угадано 5», «5 из 36» → ключ исхода; None — не распознано."""
    if not label or label.startswith("#"):
        return None
    s = label.lower().replace("—", "-")
    if n_blocks >= 2:
        m = _PAIR.search(s)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= block_counts[0] and b <= block_counts[1]:
                return f"{a}+{b}"
        return None
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if " из " in s and len(nums) >= 2:      # «5 из 36» — первое число совпадения
        nums = nums[:1]
    if len(nums) == 1 and nums[0] <= block_counts[0]:
        return str(nums[0])
    return None


# ── Хранение ──────────────────────────────────────────────────────────────

def save(slug: str, records: dict[int, dict]) -> None:
    if not records:
        return
    lines = [json.dumps(records[k], ensure_ascii=False) for k in sorted(records)]
    write_text(prizes_file(slug), "\n".join(lines) + "\n")


def load(slug: str) -> dict[int, dict]:
    path = prizes_file(slug)
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            out[int(r["no"])] = r
        except (ValueError, KeyError, TypeError):
            continue
    return out


def save_samples(slug: str, raws: list[dict]) -> None:
    if raws:
        write_text(samples_file(slug), json.dumps(raws[-2:], ensure_ascii=False, indent=1))


def keyed_history(slug: str, block_counts: list[int]) -> dict[int, dict[str, dict]]:
    """По тиражу: ключ исхода → {winners, prize}. Нераспознанные категории пропускаются."""
    out = {}
    for no, r in load(slug).items():
        cats = {}
        for c in r["categories"]:
            key = category_key(c["label"], len(block_counts), block_counts)
            if key:
                cats[key] = {"winners": c["winners"], "prize": c["prize"]}
        if cats:
            out[no] = {"categories": cats, "price": r.get("price"), "sales": r.get("sales")}
    return out


def typical_prizes(slug: str, block_counts: list[int], last: int = 50) -> dict:
    """Медиана выплаты на победителя по каждой категории за последние `last` тиражей и цена
    билета, если API её сообщает."""
    import numpy as np
    hist = keyed_history(slug, block_counts)
    if not hist:
        return {"prizes": {}, "price": None, "draws": 0}
    recent = [hist[k] for k in sorted(hist)[-last:]]
    by_key: dict[str, list[float]] = {}
    for h in recent:
        for key, c in h["categories"].items():
            if c["prize"] and c["prize"] > 0:
                by_key.setdefault(key, []).append(c["prize"])
    prices = [h["price"] for h in recent if h.get("price")]
    return {"prizes": {k: float(np.median(v)) for k, v in by_key.items()},
            "price": float(np.median(prices)) if prices else None, "draws": len(recent)}
