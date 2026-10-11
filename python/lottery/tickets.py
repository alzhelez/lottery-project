"""Генератор «непопулярных» комбинаций.

Шанс выиграть у любой комбинации одинаков. Но в категориях, где призовой фонд делится
между победителями (суперприз и часть призов в тиражных лотереях), сумма выигрыша зависит
от того, сколько людей выбрали те же числа. Игроки выбирают числа неслучайно: даты
(числа до 31 и до 12), ряды подряд, арифметические прогрессии, «рисунки», числа из
прошлого тиража. Генератор берёт равновероятные случайные комбинации и оставляет только
те, в которых таких признаков нет, — вероятность выигрыша не меняется, а ожидаемое число
соседей по выигрышу ниже.
"""
from __future__ import annotations

from math import comb

import numpy as np

from .drawfile import BlockSpec, GameData


POP_QUANTILE = 0.3


def load_popularity(slug: str) -> dict | None:
    import json
    from .games import results_dir
    try:
        return json.loads((results_dir(slug) / "popularity.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pop_score(model: dict, blocks: list[list[int]], names: list[str]) -> float:
    from .popularity import score as pscore
    return pscore(model, blocks, names)


def _ap_len(nums: list[int]) -> int:
    """Длина самой длинной арифметической прогрессии в отсортированном наборе."""
    s = set(nums)
    best = 1 if nums else 0
    for i, a in enumerate(nums):
        for b in nums[i + 1:]:
            step = b - a
            length, cur = 2, b
            while cur + step in s:
                cur += step
                length += 1
            best = max(best, length)
    return best


def flags(nums: list[int], spec: BlockSpec, last_draw: set[int] | None = None) -> list[dict]:
    """Признаки популярной комбинации для одного поля «k из N». Каждый признак — словарь
    с весом и объяснением. Пустой список — комбинация выглядит «случайной»."""
    nums = sorted(nums)
    k, hi = len(nums), spec.hi
    out = []

    def add(code: str, weight: float, text: str) -> None:
        out.append({"code": code, "weight": weight, "text": text})

    if hi > 31 and k >= 3:
        dates = sum(v <= 31 for v in nums)
        expected = k * min(31, hi) / spec.size
        if dates == k:
            add("dates", 3, "все числа не больше 31 — так выглядят даты рождения")
        elif dates >= expected + 2:
            add("dates", 1, f"{dates} из {k} чисел не больше 31 — перекос в сторону дат")
    if hi > 12 and k >= 3 and sum(v <= 12 for v in nums) >= max(3, k // 2 + 1):
        add("months", 1, "много чисел до 12 — похоже на месяцы")
    pairs = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
    longest, cur = 1, 1
    for a, b in zip(nums, nums[1:]):
        cur = cur + 1 if b == a + 1 else 1
        longest = max(longest, cur)
    if longest >= 3:
        add("runs", longest - 1, f"{longest} числа идут подряд")
    elif pairs >= 2:
        add("runs", 1, f"{pairs} пары соседних чисел")
    elif pairs == 1 and k <= 3:
        add("runs", 1, "два числа подряд")
    ap = _ap_len(nums)
    if k >= 4 and ap >= max(4, k - 1):
        word = "числа" if ap % 10 in (2, 3, 4) and ap % 100 not in (12, 13, 14) else "чисел"
        add("progression", 3, f"{ap} {word} образуют арифметическую прогрессию")
    elif k >= 3 and ap == k:
        add("progression", 2, "числа образуют арифметическую прогрессию")
    if k >= 3:
        digits = np.bincount([v % 10 for v in nums], minlength=10)
        if digits.max() >= 3:
            add("same_digit", 1, f"{digits.max()} числа оканчиваются на {int(digits.argmax())}")
        decades = np.bincount([(v - 1) // 10 for v in nums])
        if decades.max() >= max(3, k - 1) and spec.size > 20:
            add("cluster", 1, "почти все числа из одного десятка")
    for m in (5, 7, 10):
        if k >= 3 and all(v % m == 0 for v in nums):
            add("multiples", 2, f"все числа кратны {m}")
            break
    if last_draw:
        overlap = len(set(nums) & last_draw)
        if overlap >= max(2, k // 2):
            add("last_draw", 2, f"{overlap} числа из прошлого тиража — их часто ставят повторно")
    return out


def score(nums: list[int], spec: BlockSpec, last_draw: set[int] | None = None) -> float:
    return float(sum(f["weight"] for f in flags(nums, spec, last_draw)))


def applicable(data: GameData) -> tuple[bool, str]:
    if not data.fmt.supported:
        return False, data.fmt.reason
    if data.fmt.bingo:
        return False, "В бинго-играх числа на билете напечатаны заранее — выбирать их нельзя."
    return True, ""


def _last_draw_values(data: GameData, spec: BlockSpec) -> set[int]:
    if not data.draws:
        return set()
    vals = data.draws[-1].blocks[spec.source]
    return {vals[spec.position]} if spec.position is not None else set(vals)


def generate(data: GameData, count: int = 5, seed: int | None = None, max_overlap: int | None = None) -> dict:
    """count билетов: по каждому полю — случайная комбинация без признаков популярности.
    Билеты в наборе пересекаются не больше чем на max_overlap чисел основного поля."""
    ok, reason = applicable(data)
    base = {"slug": data.game.slug, "title": data.game.title}
    if not ok:
        return {**base, "supported": False, "reason": reason}
    rng = np.random.default_rng(seed)
    specs = data.fmt.blocks
    positional = all(s.mode == "position" for s in specs)
    pop = load_popularity(data.game.slug)
    names = [s.name for s in specs]
    pop_limit = None
    if pop and pop.get("significant") and not positional:
        # порог: комбинации не популярнее, чем 30% случайных
        sample = [_pop_score(pop, [sorted(rng.choice(np.arange(s.lo, s.hi + 1), size=s.count, replace=False).tolist())
                                   for s in specs], names) for _ in range(2000)]
        pop_limit = float(np.quantile(sample, POP_QUANTILE))
    tickets: list[dict] = []
    main = specs[0]
    limit = max_overlap if max_overlap is not None else max(1, main.count // 2)
    attempts = 0
    while len(tickets) < count and attempts < count * 5000:
        attempts += 1
        if positional:
            digits = [int(rng.integers(s.lo, s.hi + 1)) for s in specs]
            if len(set(digits)) == 1 or all(b - a == 1 for a, b in zip(digits, digits[1:])) \
                    or all(a - b == 1 for a, b in zip(digits, digits[1:])):
                continue
            if any(t["blocks"] == [[d] for d in digits] for t in tickets):
                continue
            tickets.append({"blocks": [[d] for d in digits], "notes": ["цифры не повторяются подряд и не образуют ряд"]})
            continue
        blocks, notes, fine = [], [], True
        for s in specs:
            nums = sorted(int(v) for v in rng.choice(np.arange(s.lo, s.hi + 1), size=s.count, replace=False))
            if s.count >= 3 and score(nums, s, _last_draw_values(data, s)) > 0:
                fine = False
                break
            blocks.append(nums)
        if not fine:
            continue
        if pop_limit is not None and _pop_score(pop, blocks, names) > pop_limit:
            continue
        if any(len(set(blocks[0]) & set(t["blocks"][0])) > limit for t in tickets):
            continue
        hi_share = sum(v > 31 for v in blocks[0])
        if main.hi > 31:
            notes.append(f"{hi_share} из {main.count} чисел больше 31 — вне «дат»")
        notes.append("нет рядов подряд, прогрессий, кратных и чисел из прошлого тиража")
        if pop_limit is not None:
            notes.append(f"по числу победителей в архиве — среди {int(POP_QUANTILE * 100)}% наименее популярных")
        tickets.append({"blocks": blocks, "notes": notes})
    share = acceptance_share(data, rng) if not positional else None
    return {
        **base,
        "supported": True,
        "popularity": None if not pop else {k: pop.get(k) for k in ("significant", "p_value", "verdict", "popular", "unpopular", "draws")},
        "tickets": tickets,
        "blocks": [{"name": s.name, "count": s.count, "lo": s.lo, "hi": s.hi} for s in specs],
        "accepted_share": share,
        "combinations": int(np.prod([comb(s.size, s.count) for s in specs])),
    }


def acceptance_share(data: GameData, rng: np.random.Generator, samples: int = 4000) -> float:
    """Какая доля всех комбинаций основного поля проходит фильтр (для объяснения в UI)."""
    s = data.fmt.blocks[0]
    if s.count < 3:
        return 1.0
    last = _last_draw_values(data, s)
    ok = 0
    for _ in range(samples):
        nums = sorted(int(v) for v in rng.choice(np.arange(s.lo, s.hi + 1), size=s.count, replace=False))
        ok += score(nums, s, last) == 0
    return ok / samples


def check(data: GameData, blocks: list[list[int]]) -> dict:
    """Разбор комбинации пользователя: какие признаки популярности в ней есть."""
    ok, reason = applicable(data)
    if not ok:
        return {"supported": False, "reason": reason}
    specs = data.fmt.blocks
    if len(blocks) != len(specs):
        return {"supported": True, "valid": False,
                "reason": f"нужно {len(specs)} пол{'е' if len(specs) == 1 else 'я'}: " +
                          "; ".join(f"{s.name} — {s.count} из {s.lo}–{s.hi}" for s in specs)}
    result = []
    for nums, s in zip(blocks, specs):
        if len(nums) != s.count or len(set(nums)) != len(nums) or not all(s.lo <= v <= s.hi for v in nums):
            return {"supported": True, "valid": False,
                    "reason": f"{s.name}: нужно {s.count} разных чисел от {s.lo} до {s.hi}"}
        f = flags(nums, s, _last_draw_values(data, s)) if s.count >= 3 else []
        result.append({"block": s.name, "flags": f})
    total = sum(f["weight"] for r in result for f in r["flags"])
    return {"supported": True, "valid": True, "blocks": result, "score": total,
            "verdict": "Комбинация выглядит случайной — признаков популярного выбора нет." if total == 0 else
            "Комбинация похожа на популярный выбор: при выигрыше в делимых категориях приз, вероятно, "
            "придётся делить с большим числом людей. Шанс выигрыша от этого не меняется."}
