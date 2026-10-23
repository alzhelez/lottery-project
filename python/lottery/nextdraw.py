"""Ожидаемый возврат ближайшего тиража: стоит ли играть сейчас.

Выигрыши, кроме суперприза, в среднем возвращают постоянную долю ставки. Суперприз же
копится, пока его не выиграют, и ожидаемый возврат тиража растёт вместе с ним:

    E[выигрыш] = Σ P(исход) × приз(исход) + P(суперприз) × суперприз × доля,

где доля = (1 − e^(−λ)) / λ — сколько в среднем достанется одному победителю, если
суперприз угадают λ = продажи × P(суперприз) билетов (делят поровну).

Призы: фиксированные — из официальной таблицы выигрышей тиража (rules), делимые — медиана
реальных выплат из архива. Суперприз и цена — из данных ближайшего тиража (API Столото).
Расчёт приблизительный: продажи берутся медианой последних тиражей, а развёрнутые ставки
считаются как отдельные комбинации.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np

from .drawfile import GameData
from .games import data_dir, results_dir


def threshold() -> float:
    try:
        return float(os.environ.get("TELEGRAM_EV_THRESHOLD", "1").replace(",", "."))
    except ValueError:
        return 1.0


def _api_next(slug: str) -> dict | None:
    try:
        raw = json.loads((data_dir() / "api_games.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    g = next((g for g in raw.get("games", []) if g.get("name") == slug), None)
    d = (g or {}).get("draw")
    if not d:
        return None
    return {"number": d.get("number"),
            "date": datetime.fromtimestamp(d["date"]).isoformat(timespec="seconds") if d.get("date") else None,
            "super_prize": d.get("superPrize"), "price": d.get("betCost"), "lototron": d.get("tvShow"),
            "prize_fund_pct": d.get("winnersDistribitionPers"), "jackpot_guaranteed": d.get("jackpotGuaranteed")}


def expected_sales(slug: str, last: int = 30) -> float | None:
    from .prizes import _tail, clean
    recs = clean([r for r in _tail(slug, last * 2) if r.get("sales")])
    vals = [r["sales"] for r in recs][-last:]
    return float(np.median(vals)) if vals else None


def compute(data: GameData) -> dict | None:
    from .odds import odds_table
    from .prizes import archive_stats
    from .rules import load_rules, official_prizes
    slug = data.game.slug
    rules = load_rules(slug)
    nxt = (rules or {}).get("next_draw") or _api_next(slug)
    if not nxt or not nxt.get("price"):
        return None
    odds = odds_table(data)
    if not odds.get("supported"):
        return None
    counts = [b["count"] for b in odds["blocks"]]
    off = official_prizes(rules, len(counts), counts)
    top_keys = set(off["super"]) or {odds["jackpot"]["key"]}
    sales = expected_sales(slug)
    p_top = sum(r["p"] for r in odds["patterns"] if r["key"] in top_keys)
    lam = (sales or 0) * p_top
    share = (1 - np.exp(-lam)) / lam if lam > 1e-12 else 1.0
    sp = float(nxt.get("super_prize") or 0)
    ev_base = 0.0
    rows = []
    for r in odds["patterns"]:
        if r["key"] in top_keys:
            continue
        prize, src = off["prizes"].get(r["key"]), "rules"
        if not prize:
            prize, src = r.get("archive_prize"), "archive"
        if prize:
            ev_base += r["p"] * prize
            rows.append({"key": r["key"], "p": r["p"], "prize": prize, "source": src})
    ev_jack = p_top * sp * share
    price = float(nxt["price"])
    arch = archive_stats(slug)
    res = {
        "slug": slug, "title": data.game.title, "number": nxt.get("number"), "date": nxt.get("date"),
        "lototron": nxt.get("lototron"), "price": price, "super_prize": sp, "expected_sales": sales,
        "p_super": p_top, "share": float(share),
        "p_win": float(p_top + sum(r["p"] for r in rows)),
        "ev_base": ev_base, "ev_super": ev_jack, "expected_value": ev_base + ev_jack,
        "return": (ev_base + ev_jack) / price, "return_without_super": ev_base / price,
        "usual_return": arch["return"] if arch else None,
        "rows": rows,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
    }
    res["verdict"] = verdict(res)
    return res


def verdict(r: dict) -> str:
    from .stats import ru
    ret = r["return"]
    sp = f"{r['super_prize']:,.0f}".replace(",", " ")
    if ret >= 1:
        return ru(f"Ожидаемый возврат ближайшего тиража {ret:.2f} — больше ставки: суперприз {sp} ₽ "
                  f"перевешивает (так бывает примерно в 1% тиражей). Это всё равно лотерея: почти все "
                  f"билеты проигрывают, выгода — только в среднем на очень большом числе билетов.")
    usual = r.get("usual_return")
    more = f" (обычно {usual:.2f})" if usual else ""
    return ru(f"Ожидаемый возврат ближайшего тиража {ret:.2f}{more}: на рубль ставки в среднем "
              f"возвращается меньше рубля.")


def compute_all(slugs: list[str], loader) -> dict:
    """Ближайший тираж по всем играм → results/nextdraw.json. loader(slug) → GameData."""
    out = {}
    for slug in slugs:
        try:
            data = loader(slug)
            r = compute(data) if data.draws else None
        except (ValueError, KeyError):
            r = None
        if r:
            out[slug] = r
    from .fsutil import write_text
    path = results_dir() / "nextdraw.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                                 "threshold": threshold(), "games": out}, ensure_ascii=False, indent=1))
    return out


def to_notify(results: dict) -> list[dict]:
    """Тиражи, где возврат выше порога и о которых ещё не сообщали."""
    path = results_dir() / "nextdraw_notified.json"
    try:
        sent = set(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        sent = set()
    out = [r for r in results.values() if r["return"] >= threshold() and f"{r['slug']}:{r['number']}" not in sent]
    if out:
        from .fsutil import write_text
        sent |= {f"{r['slug']}:{r['number']}" for r in out}
        write_text(path, json.dumps(sorted(sent)[-500:], ensure_ascii=False))
    return out
