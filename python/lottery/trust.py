"""Доверие к методам и «Финальное предсказание».

Доверие — шкала 0–100 для каждого источника прогнозов в каждой игре: насколько его результат
за выбранный период лучше случайного выбора. 50 — как случайный выбор, выше — угадывал больше
(для «наименее вероятных» — их числа выпадали реже: цель обратная), ниже — хуже случайного.
Считается по двум наборам сразу: «анализ за период» (ретро-проверка, retro.py: все методы на
каждом тираже периода) и настоящие прогнозы журнала за тот же период; на один тираж у источника
берётся одна запись — журнальная, если она есть.

    z = Σ(угадано − ожидалось) / √Σдисперсий        (для «наименее вероятных» — с обратным знаком)
    доверие = 100 · Φ(z · √(n / (n + 30)))

Множитель √(n/(n+30)) прижимает оценку к 50, пока прогнозов мало: десяток удачных тиражей не
делает метод «надёжным». Доверие — не вероятность выигрыша: в честной лотерее все методы в
среднем равны случайному выбору, и шкала показывает лишь, кому в этот период везло больше.

«Финальное предсказание» — голосование всех источников за числа ближайшего тиража с весами по
доверию: вес = 0,1 + max(0, доверие − 50) / 50; числа «наименее вероятных» получают штраф с
весом этого источника.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from .fsutil import write_text
from .games import data_dir
from .journal import FAMILIES, LOWER, SOURCES, load

PERIODS = (1, 3, 7, 14, 30)       # дней — выбор на вкладке «Статистика»
SHRINK_N = 30
FINAL = "final"
BASE_WEIGHT = 0.1


def trust_path():
    return data_dir() / "trust.json"


def _phi(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2))


Z_SIGNIFICANT = 1.96


def level(trust: float) -> str:
    if trust >= 90:
        return "высокое"
    if trust >= 65:
        return "повышенное"
    if trust >= 35:
        return "как у случайного выбора"
    return "низкое"


def _when(e: dict) -> datetime | None:
    for key, fmt in (("draw_date", "%d.%m.%Y %H:%M"), ("checked_at", None), ("made_at", None)):
        v = e.get(key)
        if not v:
            continue
        try:
            return datetime.strptime(v, fmt) if fmt else datetime.fromisoformat(v)
        except ValueError:
            continue
    return None


def score(entries: list[dict], lower: bool) -> dict:
    """Итог источника по сверенным прогнозам: число, угадано, ожидалось, превышение, z, доверие."""
    n = len(entries)
    hits = sum(e.get("hits") or 0 for e in entries)
    expected = sum(e.get("expected") or 0 for e in entries)
    variance = sum(e.get("variance") or 0 for e in entries)
    z = (hits - expected) / math.sqrt(variance) if variance > 0 else 0.0
    good = -z if lower else z
    trust = round(100 * _phi(good * math.sqrt(n / (n + SHRINK_N))), 1) if n else 50.0
    # честная рамка: mde_pct — отрыв от случайного выбора (в %), который на таком числе прогнозов уже
    # отличим от случайности (z = 1,96); need — сколько прогнозов нужно, чтобы отличить нынешний
    # отрыв, если он сохранится (None — отрыва в нужную сторону нет)
    mde = round(100 * Z_SIGNIFICANT * math.sqrt(variance) / expected, 2) if expected and variance > 0 else None
    need = math.ceil(n * (Z_SIGNIFICANT / good) ** 2) if good > 0 and n else None
    return {"n": n, "hits": hits, "expected": round(expected, 3), "mde_pct": mde, "need": need,
            "proven": good >= Z_SIGNIFICANT,
            "excess_pct": round(100 * (hits - expected) / expected, 2) if expected else 0.0,
            "z": round(z, 3), "trust": trust, "level": level(trust) if n >= SHRINK_N else "мало данных",
            "few": n < SHRINK_N}


def period_entries(slug: str, since: datetime) -> dict[str, list[dict]]:
    """Сверенные прогнозы игры за период по источникам: журнал + ретро, на тираж — одна запись."""
    by: dict[str, dict[int, dict]] = {}
    for retro in (True, False):                      # журнальная запись перекрывает ретро
        for e in load(slug, retro=retro)["entries"]:
            if e.get("status") != "checked":
                continue
            t = _when(e)
            if t is None or t < since:
                continue
            by.setdefault(e["source"], {})[e["draw_no"]] = e
    return {s: list(d.values()) for s, d in by.items()}


def game_trust(slug: str, since: datetime) -> dict:
    by = period_entries(slug, since)
    rows = {s: score(by[s], s in LOWER) for s in SOURCES if by.get(s)}
    ranked = sorted(rows, key=lambda s: (-rows[s]["trust"], -rows[s]["n"]))
    for i, s in enumerate(ranked):
        rows[s]["rank"] = i + 1
    return {"sources": rows, "ranking": ranked}


def build(slugs: list[str], days: int, now: datetime | None = None) -> dict:
    """Пересчитывает доверие по играм slugs за последние days дней и сохраняет data/trust.json."""
    now = now or datetime.now()
    since = now - timedelta(days=days)
    out = {"made_at": now.isoformat(timespec="seconds"), "days": days, "since": since.isoformat(timespec="minutes"),
           "games": {}}
    for slug in slugs:
        g = game_trust(slug, since)
        if g["sources"]:
            out["games"][slug] = g
    write_text(trust_path(), json.dumps(out, ensure_ascii=False, indent=1))
    return out


def load_trust() -> dict:
    try:
        return json.loads(trust_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def weights(slug: str, trust: dict | None = None) -> dict[str, float]:
    """Вес источника в финальном голосовании: 0,1 + max(0, доверие − 50)/50 (нет данных — 0,1)."""
    rows = ((trust if trust is not None else load_trust()).get("games") or {}).get(slug, {}).get("sources", {})
    return {s: BASE_WEIGHT + max(0.0, rows.get(s, {}).get("trust", 50.0) - 50.0) / 50.0 for s in SOURCES if s not in FAMILIES}


def final_numbers(by_source: dict[str, list[list[int]]], blocks: list[dict], w: dict[str, float],
                  final: str = FINAL) -> list[list[int]] | None:
    """Числа финального предсказания по прогнозам источников на один тираж. Источник отдаёт вес
    каждому своему числу, «наименее вероятные» — такой же штраф; при равенстве — число без штрафа,
    затем меньшее.
    Голосуют только источники своей версии (journal.FAMILIES[final]: для «Ф» — К и Б со штрафом Н,
    для «Ф2» — К2 и Б2 со штрафом Н2); архивные и чужие не в счёт. Один голосующий — итог повторяет
    его числа; None — голосующих нет."""
    by_source = {s: v for s, v in by_source.items() if s in FAMILIES[final]}
    voters = [s for s in by_source if s not in LOWER]
    if not voters:
        return None
    if len(voters) == 1:                    # голосует один метод (режима Бога на тираж нет) — Ф повторяет его
        return [sorted(b) for b in by_source[voters[0]]]
    out = []
    for b, spec in enumerate(blocks):
        score = {n: 0.0 for n in range(spec["lo"], spec["hi"] + 1)}
        penalized = set()
        for s, numbers in by_source.items():
            if b >= len(numbers):
                continue
            sign = -1.0 if s in LOWER else 1.0
            for n in numbers[b]:
                if n in score:
                    score[n] += sign * w.get(s, BASE_WEIGHT)
                    if s in LOWER:
                        penalized.add(n)
        count = max(len(by_source[s][b]) for s in voters if b < len(by_source[s]))
        # при равном счёте — сначала числа без штрафа, затем меньшее число
        out.append(sorted(sorted(score, key=lambda n: (-score[n], n in penalized, n))[:count]))
    return out


def final_detail(by_source: dict[str, list], w: dict[str, float], trust_rows: dict, final: str = FINAL) -> str:
    from .notify import SHORT
    parts = [f"{SHORT.get(s, s)} {trust_rows[s]['trust']:.0f}" if s in trust_rows else f"{SHORT.get(s, s)} —"
             for s in FAMILIES[final] if s in by_source]
    return "голосование по доверию: " + ", ".join(parts)
