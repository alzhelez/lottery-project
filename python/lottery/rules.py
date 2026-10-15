"""Правила игр со stoloto.ru: «Как проходят розыгрыши», таблица выигрышей, ближайший тираж.

Источники (те же, что использует страница https://www.stoloto.ru/<игра>/rules):
  * games/info-new — ближайший тираж каждой игры: номер, время, суперприз, цена ставки,
    процент призового фонда, гарантированный суперприз, трансляция (tvShow → лототрон);
  * games/<игра>/winning-table?drawNumber=N — официальная таблица выигрышей тиража:
    фиксированные призы, доли призового фонда, суперприз;
  * CMS api.stoloto.ru/cms/api/about-lottery-categories/<игра> — тексты страницы правил
    («Как проходят розыгрыши», «Вопрос — ответ» про суперприз, «Лотерея в цифрах»);
  * CMS winning-table-superprize/<игра> — что считается суперпризом.

Результат — data/rules/<игра>.json. Из текста «Как проходят розыгрыши» разбирается расписание:
какие тиражи проводятся на лототроне, какие — генератором случайных чисел (ГСЧ).
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime

from .fsutil import write_text
from .games import data_dir

CMS_BASE = os.environ.get("STOLOTO_CMS_BASE", "").rstrip("/")
MAX_AGE_H = 20          # тексты правил и таблицы перечитываются не чаще раза в сутки


def rules_dir():
    return data_dir() / "rules"


def rules_path(slug: str):
    return rules_dir() / f"{slug}.json"


def load_rules(slug: str) -> dict | None:
    try:
        return json.loads(rules_path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ── Разбор ────────────────────────────────────────────────────────────────

def html_to_text(s: str | None) -> str:
    """HTML из CMS → абзацы простого текста."""
    if not s:
        return ""
    s = re.sub(r"(?i)<\s*(br|/p|/h\d|/li)\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n")]
    return "\n".join(line for line in lines if line)


def _fill(text: str, draw: dict | None) -> str:
    """Подстановки CMS: {{lottery_winners_distribution_pers}}, {{lottery_jackpot_guaranteed}}."""
    draw = draw or {}
    pers = draw.get("winnersDistribitionPers")
    guar = draw.get("jackpotGuaranteed")
    text = text.replace("{{lottery_winners_distribution_pers}}", f"{pers:g}%" if pers else "—")
    text = text.replace("{{lottery_jackpot_guaranteed}}",
                        f"{guar:,.0f} ₽".replace(",", " ") if guar else "—")
    return re.sub(r"\{\{[^}]+\}\}", "—", text)


_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(\((?:лототрон|гсч)\))?", re.I)


def parse_schedule(text: str) -> dict:
    """Время розыгрышей и способ: «10:00 (лототрон), 11:07:30 (ГСЧ), 11:00, 14:25 (ГСЧ)».

    Время без пометки относится к способу, который в тексте указан для игры в целом:
    если упомянут только лототрон — к лототрону, если только ГСЧ — к ГСЧ, если оба — к
    лототрону (так на stoloto.ru: помечают именно тиражи ГСЧ, как в «6 из 45»). Учитывается
    только первое предложение со временем розыгрышей — не время окончания продаж."""
    low = text.lower()
    uses_l = "лототрон" in low
    uses_r = "гсч" in low or "генератор" in low
    out = {"lototron": uses_l, "rng": uses_r, "times": {}}
    # только фрагмент про время проведения: до «Продажи…»/«Билеты, купленные…»
    m = re.search(r"(проход\w*|проводят\w*)[^.]*?(\d{1,2}:\d{2}[^.]*)", text, re.I)
    if not m:
        return out
    fragment = m.group(2)
    default = "L" if uses_l else "R"
    for hh, mm, _ss, mark in _TIME.findall(fragment):
        kind = default if not mark else ("L" if "лото" in mark.lower() else "R")
        out["times"][f"{int(hh):02d}:{mm}"] = kind
    return out


def _table_rows(table: dict | None) -> list[dict]:
    rows = []
    for r in (table or {}).get("winningTable") or []:
        rows.append({"g1": r.get("guessNumber1"), "g2": r.get("guessNumber2"),
                     "prize": float(r.get("prize") or 0), "superprize": bool(r.get("superprize")),
                     "percent": r.get("percentprize"), "wc": r.get("wcnumber")})
    return rows


def parse(slug: str, info: dict | None, table: dict | None, cms: dict | None, superprize: dict | None) -> dict:
    """Ответы API → запись правил игры (без сетевых запросов — удобно тестировать)."""
    draw = (info or {}).get("draw") or {}
    contents = []
    for d in (cms or {}).get("data") or []:
        contents.extend(d.get("contents") or [])
    item = {c.get("collection"): c.get("item") or {} for c in contents}
    how = item.get("how_draws_work", {})
    how_text = html_to_text(_fill(how.get("text") or "", draw))
    if not how_text:                      # у части игр текст разбит на карточки
        parts = []
        for c in how.get("content") or []:
            for key in ("topText", "firstTitle", "firstText", "secondTitle", "secondText", "bottomText"):
                if c.get(key):
                    parts.append(html_to_text(_fill(str(c[key]), draw)))
        how_text = "\n".join(p for p in parts if p)
    faq = [{"question": q.get("question"), "answer": html_to_text(_fill(q.get("answer") or "", draw))}
           for q in (item.get("faq", {}).get("rulesFaqs") or [])
           if re.search(r"суперприз|призов|фонд", q.get("question") or "", re.I)]
    cards = [{"title": (c.get("title") or "").strip(), "text": _fill(str(c.get("text") or ""), draw).strip()}
             for c in (item.get("about_prize", {}).get("cards") or [])]
    sp_rows = []
    for d in (superprize or {}).get("data") or []:
        for g in d.get("guessNumbers") or []:
            sp_rows.append({"label": g.get("superprizeValue"), "g1": g.get("guessNumber1"),
                            "g2": g.get("guessNumber2"), "second": g.get("secondCount")})
    rows = _table_rows(table)
    sched = parse_schedule(how_text)
    return {
        "slug": slug,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "how": how_text,
        "schedule": sched,
        "faq": faq,
        "cards": cards,
        "table": rows,
        "table_error": ", ".join((table or {}).get("errors") or []) or None,
        "min_prize": (table or {}).get("minPrize"),
        "superprize_rows": sp_rows,
        "next_draw": {
            "number": draw.get("number"),
            "date": datetime.fromtimestamp(draw["date"]).isoformat(timespec="seconds") if draw.get("date") else None,
            "super_prize": draw.get("superPrize"),
            "jackpots": draw.get("jackpots") or [],
            "price": draw.get("betCost"),
            "lototron": draw.get("tvShow"),
            "prize_fund_pct": draw.get("winnersDistribitionPers"),
            "jackpot_guaranteed": draw.get("jackpotGuaranteed"),
            "rollover": draw.get("rollover"),
            "status": draw.get("status"),
        } if draw else None,
    }


# ── Таблица выигрышей → исходы билета ────────────────────────────────────

def official_prizes(rules: dict | None, n_blocks: int, counts: list[int]) -> dict:
    """Фиксированные призы из официальной таблицы в ключах калькулятора («4+3», «5»).

    Формы таблиц на stoloto.ru:
      * два поля (4 из 20, Охота, 5x2, Дважды два): g1 — совпало в поле 1, g2 — в поле 2;
      * поле + бонус (5 из 36 плюс, Рапидо): g2 — угадан ли бонус;
      * одно поле (6 из 45, 7 из 49): g2 = 0 или null;
      * 12 из 24: пара (12, 0), (11, 1)… — «угадано a или b»;
      * Кено: g1 — сколько чисел в ставке, g2 — сколько совпало.
    Возвращает {"prizes": {ключ: сумма}, "super": [ключи суперприза], "shares": {ключ: % фонда}}."""
    out = {"prizes": {}, "super": [], "shares": {}}
    if not rules:
        return out
    table = [r for r in rules.get("table") or [] if r["g1"] is not None]
    c = counts[0]
    from collections import Counter
    # Кено: одна и та же «ставка на g1 чисел» встречается в нескольких строках
    keno = n_blocks == 1 and any(n > 1 for n in Counter(r["g1"] for r in table if r["g2"] is not None).values())
    # 12 из 24: строки (11, 1), (10, 2)… — «угадано a или b»
    either = n_blocks == 1 and not keno and any(r["g2"] and r["g1"] + r["g2"] == c for r in table)
    for r in table:
        g1, g2 = r["g1"], r["g2"]
        keys: list[str] = []
        if n_blocks >= 2:
            if g2 is not None and g1 <= counts[0] and g2 <= counts[1]:
                keys = [f"{g1}+{g2}"]
        elif keno:
            if g1 == c and g2 is not None and g2 <= c:          # ставка на c чисел, угадано g2
                keys = [str(g2)]
        elif either:
            if g2 is not None and g1 + g2 == c:
                keys = list(dict.fromkeys([str(g1), str(g2)]))
        elif g2 in (None, 0) and g1 <= c:
            keys = [str(g1)]
        for k in keys:
            if r["superprize"]:
                out["super"].append(k)
            elif r["prize"] > 0:
                out["prizes"][k] = r["prize"]
            elif r["percent"]:
                out["shares"][k] = float(r["percent"])
    return out


def mechanism_of_time(rules: dict | None, hhmm: str) -> str | None:
    """Способ розыгрыша по времени тиража из расписания: "L", "R" или None (неизвестно)."""
    if not rules:
        return None
    s = rules.get("schedule") or {}
    if hhmm in (s.get("times") or {}):
        return s["times"][hhmm]
    if s.get("lototron") and not s.get("rng"):
        return "L"
    if s.get("rng") and not s.get("lototron"):
        return "R"
    return None


# ── Загрузка ─────────────────────────────────────────────────────────────

def fetch(slugs: list[str] | None = None, log=print, force: bool = False) -> dict:
    """Скачивает правила игр (по умолчанию — всех активных по API). Ближайший тираж
    обновляется всегда, тексты и таблицы — не чаще раза в MAX_AGE_H часов."""
    from . import stoloto
    info = stoloto.games_info(log=log)
    by_name = {g.get("name"): g for g in info}
    slugs = slugs or [n for n, g in by_name.items() if g.get("active")]
    from .games import is_excluded
    slugs = [s for s in slugs if not is_excluded(s)]
    cms_base = CMS_BASE or stoloto.cms_base()
    done, failed = [], []
    for slug in slugs:
        old = load_rules(slug)
        g = by_name.get(slug) or {}
        fresh = False
        if old and not force:
            try:
                age = (datetime.now() - datetime.fromisoformat(old["fetched_at"])).total_seconds() / 3600
                fresh = age < MAX_AGE_H
            except (KeyError, ValueError):
                pass
        draw_no = (g.get("draw") or {}).get("number")
        try:
            if fresh:
                rec = parse(slug, g, None, None, None)
                rec.update({k: old[k] for k in ("how", "schedule", "faq", "cards", "superprize_rows", "fetched_at")
                            if k in old})
                table = stoloto.winning_table(slug, draw_no, log=log) if draw_no else None
                if table:
                    rec["table"] = _table_rows(table)
                    rec["min_prize"] = table.get("minPrize")
                else:
                    rec["table"], rec["min_prize"] = old.get("table", []), old.get("min_prize")
            else:
                table = stoloto.winning_table(slug, draw_no, log=log) if draw_no else None
                cms = stoloto.cms_get(f"{cms_base}/about-lottery-categories/{slug}", log=log)
                sp = stoloto.cms_get(f"{cms_base}/winning-table-superprize/{slug}", log=log)
                rec = parse(slug, g, table, cms, sp)
            write_text(rules_path(slug), json.dumps(rec, ensure_ascii=False, indent=1))
            done.append(slug)
        except stoloto.ApiUnavailable as exc:
            log(f"{slug}: правила не загружены — {exc}")
            failed.append(slug)
    return {"done": done, "failed": failed}
