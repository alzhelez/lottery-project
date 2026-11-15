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


PEAK_DAYS = 180          # «максимум за полгода»
PEAK_MIN_DAYS = 14       # раньше наблюдений слишком мало, чтобы говорить о максимуме
PEAK_KEEP_DAYS = 200
PEAK_QUIET_DAYS = 7      # о новом максимуме одной игры — не чаще раза в неделю (серия растущих суперпризов)


def history_path():
    return data_dir() / "nextdraw_history.json"


def load_history() -> dict:
    try:
        return json.loads(history_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def track(results: dict, now: datetime | None = None) -> dict:
    """Запоминает возврат ближайших тиражей (data/nextdraw_history.json) и дописывает каждому
    результату peak: {days — сколько дней наблюдений, max — прежний максимум возврата за полгода,
    is_max — нынешний возврат выше него}. История копится с версии 42.11.0."""
    from .fsutil import write_text
    now = now or datetime.now()
    hist = load_history()
    for slug, r in results.items():
        rows = [x for x in hist.get(slug, []) if (now - datetime.fromisoformat(x["at"])).days <= PEAK_KEEP_DAYS]
        prev = [x for x in rows if x["no"] != r.get("number") and (now - datetime.fromisoformat(x["at"])).days <= PEAK_DAYS]
        days = (now - min(datetime.fromisoformat(x["at"]) for x in rows)).days if rows else 0
        top = max((x["return"] for x in prev), default=None)
        r["peak"] = {"days": days, "max": top,
                     "is_max": bool(top is not None and days >= PEAK_MIN_DAYS and r["return"] > top * 1.0001)}
        rows = [x for x in rows if x["no"] != r.get("number")]
        rows.append({"no": r.get("number"), "at": now.isoformat(timespec="minutes"), "return": round(r["return"], 4),
                     "super_prize": r.get("super_prize")})
        hist[slug] = rows
    write_text(history_path(), json.dumps(hist, ensure_ascii=False, separators=(",", ":")))
    return results


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
    track(out)
    from .fsutil import write_text
    path = results_dir() / "nextdraw.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                                 "threshold": threshold(), "games": out}, ensure_ascii=False, indent=1))
    return out


def to_notify(results: dict, now: datetime | None = None) -> list[dict]:
    """Тиражи, о которых стоит сообщить и ещё не сообщали: возврат выше порога или выше прежнего
    максимума за полгода (о максимуме одной игры — не чаще раза в PEAK_QUIET_DAYS дней)."""
    now = now or datetime.now()
    path = results_dir() / "nextdraw_notified.json"
    try:
        sent = set(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        sent = set()
    peaks = {}
    for key in sent:
        if key.startswith("peak:"):
            _, slug, day = key.split(":", 2)
            peaks[slug] = max(peaks.get(slug, ""), day)

    def peak_due(r: dict) -> bool:
        if not (r.get("peak") or {}).get("is_max"):
            return False
        last = peaks.get(r["slug"])
        return last is None or (now - datetime.fromisoformat(last)).days >= PEAK_QUIET_DAYS

    out, add = [], set()
    for r in results.values():
        fresh = f"{r['slug']}:{r['number']}" not in sent
        if fresh and (r["return"] >= threshold() or peak_due(r)):
            out.append(r)
            add.add(f"{r['slug']}:{r['number']}")
            if (r.get("peak") or {}).get("is_max"):
                add.add(f"peak:{r['slug']}:{now:%Y-%m-%d}")
    if out:
        from .fsutil import write_text
        sent |= add
        write_text(path, json.dumps(sorted(sent)[-800:], ensure_ascii=False))
    return out
