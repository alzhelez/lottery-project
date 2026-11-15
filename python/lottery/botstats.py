"""Статистика игры для Telegram-бота: таблица методов за месяц и лидеры по месяцам за полгода.

Источник — все сверенные предсказания игры: история прогнозов на весь архив (history.py —
что дал бы каждый метод на каждый тираж, только по тиражам до него), поверх неё «анализ за
период» и настоящие записи журнала; на один тираж у метода — одна запись, журнальная, если она
есть. Истории ещё нет — считается только по журналу и анализу за период.

Таблицы — моноширинным текстом (<pre>): других таблиц в сообщениях Telegram нет. Ширина — до
30 знаков, чтобы строки не переносились на телефоне.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import history
from .drawfile import load_game_draws
from .games import get_game
from .journal import LOWER, SOURCES, load
from .notify import SHORT, _dec, _draws_word
from .stats import hypergeom_moments
from .trust import SHRINK_N, _when, score

MONTH_DAYS = 30
HALF_YEAR_MONTHS = 6
ORDER = ("final", "analysis_consensus", "godmode", "least")          # активные методы; архивные — на сайте
LEGEND = ("Ф — финальное предсказание, К — консенсус, Б — режим Бога, "
          "Н — наименее вероятные (у них меньше — лучше)")

_cache: dict[str, tuple[tuple, dict]] = {}


def _stamp(slug: str) -> tuple:
    from .games import data_dir, draws_path
    out = []
    for p in (history.path(slug), data_dir() / "journal" / f"{slug}.json",
              data_dir() / "journal_retro" / f"{slug}.json", draws_path(slug)):
        try:
            st = p.stat()
            out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append(None)
    return tuple(out)


def scored(slug: str, since: datetime) -> dict:
    """{built, rows: {метод: {тираж: (время, угадано, ожидалось, дисперсия)}}} — тиражи с since."""
    key = (_stamp(slug), since)
    hit = _cache.get(slug)
    if hit and hit[0] == key:
        return hit[1]
    rows: dict[str, dict[int, tuple]] = {}
    h = history.load(slug)
    if h is not None:
        when = {d.no: d.dt for d in load_game_draws(get_game(slug))}
        sizes = [b["hi"] - b["lo"] + 1 for b in h["blocks"]]
        actual, moments = {}, {}
        for no, text in zip(h["draws"]["nos"], h["draws"]["actual"]):
            t = when.get(no)
            if t is not None and t >= since:
                actual[no] = (t, [set(b) for b in history.dec(text)])
        for source, v in h["sources"].items():
            out = rows.setdefault(source, {})
            for no, text in zip(v["nos"], v["numbers"]):
                if no not in actual:
                    continue
                t, act = actual[no]
                hits, mean, var = 0, 0.0, 0.0
                for size, pred, a in zip(sizes, history.dec(text), act):
                    hits += len(a.intersection(pred))
                    k = (size, len(a), len(pred))
                    if k not in moments:
                        m, s2 = hypergeom_moments(*k)
                        moments[k] = (float(m), float(s2))
                    mean += moments[k][0]
                    var += moments[k][1]
                out[no] = (t, hits, mean, var)
    for retro in (True, False):                       # журнальная запись перекрывает остальные
        for e in load(slug, retro=retro)["entries"]:
            t = _when(e) if e.get("status") == "checked" else None
            if t is not None and t >= since:
                rows.setdefault(e["source"], {})[e["draw_no"]] = (t, e.get("hits") or 0, e.get("expected") or 0,
                                                                  e.get("variance") or 0)
    res = {"built": h is not None, "rows": rows}
    _cache[slug] = (key, res)
    return res


def window(rows: dict, start: datetime, end: datetime) -> dict[str, dict]:
    """Итог каждого метода по тиражам [start, end) — как trust.score."""
    out = {}
    for source in ORDER:
        es = [{"hits": h, "expected": m, "variance": v} for t, h, m, v in rows.get(source, {}).values() if start <= t < end]
        if es:
            out[source] = score(es, source in LOWER)
    return out


def _pct(v: float) -> str:
    return f"{v:+.1f}".replace(".", ",").replace("-", "−")


def month_table(stats: dict[str, dict]) -> str:
    """Таблица методов: тиражей, угадано, ожидалось при случайном выборе, разница в %, доверие."""
    lines = [" М   Тир  Угад  Ожид    ±%  Дов"]
    for source, r in sorted(stats.items(), key=lambda x: (x[0] in LOWER, -x[1]["trust"])):
        mark = "~" if r["few"] else " "
        lines.append(f"{mark}{SHORT[source]} {r['n']:>5} {r['hits']:>5} {r['expected']:>5.0f} {_pct(r['excess_pct']):>6} {r['trust']:>4.0f}")
    return "\n".join(lines)


def leader(stats: dict[str, dict]) -> tuple[str, dict] | None:
    """Метод с самым высоким доверием («наименее вероятные» не в счёт: это числа, которые не брать)."""
    cand = [(s, r) for s, r in stats.items() if s not in LOWER]
    return max(cand, key=lambda x: (x[1]["trust"], x[1]["n"])) if cand else None


def leaders_table(rows: dict, now: datetime) -> tuple[str, tuple[str, dict] | None]:
    """Лидер каждого из шести 30-дневных отрезков (от давнего к последнему) и лидер за всё полугодие."""
    lines = ["  Период     Лид    ±%  Дов"]
    for i in range(HALF_YEAR_MONTHS, 0, -1):
        start, end = now - timedelta(days=MONTH_DAYS * i), now - timedelta(days=MONTH_DAYS * (i - 1))
        top = leader(window(rows, start, end if i > 1 else now + timedelta(days=1)))
        span = f"{start:%d.%m}–{end:%d.%m}"
        if top is None:
            lines.append(f"{span}    —     —    —")
        else:
            s, r = top
            lines.append(f"{span}  {'~' if r['few'] else ' '}{SHORT[s]}  {_pct(r['excess_pct']):>6} {r['trust']:>4.0f}")
    whole = leader(window(rows, now - timedelta(days=MONTH_DAYS * HALF_YEAR_MONTHS), now + timedelta(days=1)))
    return "\n".join(lines), whole


def game_report(slug: str, now: datetime | None = None) -> str:
    """Текст для бота: таблица за месяц и лидеры за полгода."""
    now = now or datetime.now()
    # с начала суток — чтобы повторное нажатие брало готовый расчёт (ключ кэша не меняется)
    data = scored(slug, (now - timedelta(days=MONTH_DAYS * HALF_YEAR_MONTHS)).replace(hour=0, minute=0, second=0, microsecond=0))
    rows = data["rows"]
    month = window(rows, now - timedelta(days=MONTH_DAYS), now + timedelta(days=1))
    parts = [f"<b>Статистика за месяц</b> ({now - timedelta(days=MONTH_DAYS):%d.%m}–{now:%d.%m})"]
    if not month:
        parts.append("сверенных предсказаний за месяц нет")
    else:
        parts.append(f"<pre>{month_table(month)}</pre>")
    table, whole = leaders_table(rows, now)
    parts.append("\n<b>Лидеры за полгода</b> — у кого доверие выше в каждом месяце")
    if whole is None:
        parts.append("сверенных предсказаний за полгода нет")
    else:
        s, r = whole
        parts.append(f"<pre>{table}</pre>")
        parts.append(f"За все полгода: <b>{SHORT[s]} {SOURCES[s]}</b> — {_draws_word(r['n'])}, {_pct(r['excess_pct'])} % "
                     f"к случайному выбору, доверие {_dec(r['trust'], 0)}" + (" (мало данных)" if r["few"] else ""))
    notes = ["Тир — тиражей с предсказанием; Угад — угадано чисел; Ожид — столько дал бы случайный выбор; "
             "±% — разница; Дов — доверие 0–100 (50 — как случайный выбор)."]
    if any(r["few"] for r in month.values()) or "~" in table:
        notes.append(f"~ — меньше {SHRINK_N} тиражей, оценка ненадёжна.")
    notes.append(LEGEND + ".")
    if not data["built"]:
        notes.append("⚠️ Предсказания на весь архив ещё не посчитаны — здесь только журнал и анализ за период.")
    parts.append("\n" + "\n".join(notes))
    return "\n".join(parts)
