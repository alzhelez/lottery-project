"""История прогнозов: что дал бы каждый метод на КАЖДЫЙ тираж архива (data/history/<игра>.json).

Журнал записывает прогноз до тиража, но не на каждый тираж (компьютер выключен, цикл задержался),
а «анализ за период» покрывает только выбранные дни. История закрывает весь архив: прогноз на
тираж t строится только по тиражам до t, выбор метода тоже не видит тиража (см. retro.py).

Чего в истории быть не может — и это не пропуск:
  - первых тиражей игры (разгон: методам нужна история) и тиражей старше EVAL_MAX последних;
  - «Режима Бога» и «Порядка из хаоса» на первой части архива: по ней они отбирают экспертов и
    метод, честный прогноз у них есть только на остальную часть.

Файл компактный (у быстрых игр — десятки тысяч тиражей): по источнику — номера тиражей и числа
строкой «1,6,12,14|1,4» (блоки через «|»); выпавшие числа — один раз на тираж. Полная сборка —
retro.run («анализ за период», «Пересчитать предсказания»); новые тиражи дописывает fill() в
каждом цикле автозапуска: сверенный прогноз журнала, а где его нет — расчёт задним числом.
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np

from .drawfile import GameData, block_values
from .fsutil import write_text
from .games import data_dir
from .stats import hypergeom_moments

HISTORY_VERSION = 1
EVAL_SOURCES = ("analysis_best", "analysis_consensus", "least", "golden")
ORDER = ("analysis_best", "analysis_consensus", "least", "golden", "chaos", "godmode", "final")

Rows = dict[str, dict[int, str]]          # источник → номер тиража → числа строкой


def path(slug: str):
    return data_dir() / "history" / f"{slug}.json"


def enc(numbers) -> str:
    return "|".join(",".join(str(int(v)) for v in sorted(b)) for b in numbers)


def dec(text: str) -> list[list[int]]:
    return [[int(v) for v in b.split(",") if v] for b in text.split("|")]


def load(slug: str) -> dict | None:
    try:
        h = json.loads(path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return h if h.get("version") == HISTORY_VERSION else None


def rows_of(h: dict) -> Rows:
    return {s: dict(zip(v["nos"], v["numbers"])) for s, v in h.get("sources", {}).items()}


def _numbers(picks: list[np.ndarray], specs, row: int) -> str:
    return "|".join(",".join(str(v) for v in sorted(int(x) + s.lo for x in p[row])) for p, s in zip(picks, specs))


def eval_part(data: GameData) -> GameData:
    from .mechanics import subset
    from .retro import EVAL_MAX
    return data if data.T <= EVAL_MAX else subset(data, np.arange(data.T - EVAL_MAX, data.T))


def eval_rows(data: GameData, nos: set[int] | None = None) -> tuple[Rows, dict[str, str], dict]:
    """Л, К, Н, З на тиражи nos (None — на все после разгона) из одного сравнения методов."""
    from .evaluate import evaluate_game
    part = eval_part(data)
    ev = evaluate_game(part, keep_picks=True)
    if ev.get("status") != "ok":
        return {}, {}, {"skipped": ev.get("message", "мало тиражей")}
    picks = ev.pop("_picks")
    detail = {"analysis_best": ev["next_prediction"]["model"], "analysis_consensus": "",
              "least": (ev.get("least") or {}).get("next_prediction", {}).get("model", ""),
              "golden": (ev.get("golden") or {}).get("detail", "")}
    rows: Rows = {}
    ts = [t for t in range(picks["warm"], part.T) if nos is None or part.draws[t].no in nos]
    for source in EVAL_SOURCES:
        p = picks["full"].get(source)
        if p is not None:
            rows[source] = {part.draws[t].no: _numbers(p, part.fmt.blocks, t) for t in ts}
    return rows, detail, {"rows": len(ts), "best": detail["analysis_best"], "split_no": part.draws[picks["split"]].no}


def chaos_rows(data: GameData, nos: set[int] | None = None) -> tuple[dict[int, str], str]:
    """«Порядок из хаоса»: тираж прогнозирует лучший метод набора его способа розыгрыша — на
    контрольном отрезке набора (выбор метода этих тиражей не видел)."""
    from . import chaos
    from .evaluate import evaluate_game
    from .mechanics import subset
    groups = {k: g for k, g in chaos._groups(data).items() if g.T >= chaos.MIN_DRAWS}
    if not groups and data.T >= chaos.MIN_DRAWS:
        groups = {"all": data}
    out: dict[int, str] = {}
    titles = []
    for key, sub in groups.items():
        if sub.T > chaos.MAX_DRAWS:
            sub = subset(sub, np.arange(sub.T - chaos.MAX_DRAWS, sub.T))
        ev = evaluate_game(sub, models=chaos.chaos_models(), keep_picks=True)
        if ev.get("status") != "ok":
            continue
        picks = ev.pop("_picks")
        titles.append(f"{ev['next_prediction']['model']} · {chaos.MECH_TITLES[key]}")
        for t in range(picks["split"], sub.T):
            if nos is None or sub.draws[t].no in nos:
                out[sub.draws[t].no] = _numbers(picks["analysis_best"], sub.fmt.blocks, t)
    return out, "; ".join(titles)


def leader_rows(data: GameData, nos: set[int]) -> tuple[dict[int, str], str]:
    """Режим Бога на новые тиражи без перебора: модель-лидер прошлого запуска (как в журнале
    между запусками) — на каждый тираж по тиражам до него."""
    from .evaluate import Evaluator
    from .games import results_dir
    from .godmode import model_by_key
    from .mechanics import subset
    from .retro import GODMODE_MAX_DRAWS
    try:
        gm = json.loads((results_dir(data.game.slug) / "godmode.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, ""
    leader = (gm.get("next") or {}).get("leader")
    m = model_by_key(leader.get("key", ""), leader.get("params")) if leader else None
    if m is None:
        return {}, ""
    part = data if data.T <= GODMODE_MAX_DRAWS else subset(data, np.arange(data.T - GODMODE_MAX_DRAWS, data.T))
    picks = Evaluator(part).picks(m)
    return ({d.no: _numbers(picks, part.fmt.blocks, t) for t, d in enumerate(part.draws) if d.no in nos},
            f"лидер за всю историю «{leader.get('title', '')}»")


class Scorer:
    """Выпавшие числа и «угадано / ожидалось / дисперсия» прогноза — по номеру тиража."""

    def __init__(self, data: GameData):
        self.specs = data.fmt.blocks
        self.by_no = {d.no: d for d in data.draws}
        self._actual: dict[int, list[tuple[int, ...]] | None] = {}
        self._moments: dict[tuple, tuple[float, float]] = {}

    def actual(self, no: int) -> list[tuple[int, ...]] | None:
        if no not in self._actual:
            try:
                self._actual[no] = [tuple(block_values(self.by_no[no], s)) for s in self.specs]
            except (KeyError, IndexError, TypeError):
                self._actual[no] = None
        return self._actual[no]

    def score(self, no: int, numbers: list[list[int]]) -> tuple[int, float, float]:
        act = self.actual(no) or []
        hits, mean, var = 0, 0.0, 0.0
        for s, pred, a in zip(self.specs, numbers, act):
            hits += len(set(pred) & set(a))
            key = (s.size, len(a), len(pred))
            if key not in self._moments:
                m, v = hypergeom_moments(*key)
                self._moments[key] = (float(m), float(v))
            mean += self._moments[key][0]
            var += self._moments[key][1]
        return hits, mean, var


def add_final(rows: Rows, scorer: Scorer, acc: dict[str, list[float]], nos: list[int],
              keep: dict[int, str] | None = None) -> None:
    """«Финальное предсказание» на тиражи nos (по возрастанию): голосование источников с весами по
    доверию, накопленному к тиражу, — acc копит «угадано − ожидалось» только по уже пройденным.
    keep — готовые Ф (из журнала): их числа не пересчитываются."""
    from . import trust
    from .retro import final_weights
    blocks = [s.to_dict() for s in scorer.specs]
    final = rows.setdefault("final", {})
    for no in nos:
        by_source = {s: dec(r[no]) for s, r in rows.items() if s != "final" and no in r}
        if not by_source:
            continue
        if keep and no in keep:
            final[no] = keep[no]
        else:
            numbers = trust.final_numbers(by_source, blocks, final_weights(acc))
            if numbers:
                final[no] = enc(numbers)
        for s, numbers in by_source.items():
            hits, mean, var = scorer.score(no, numbers)
            a = acc.setdefault(s, [0.0, 0.0, 0])
            a[0] += hits - mean
            a[1] += var
            a[2] += 1


def save(data: GameData, rows: Rows, details: dict[str, str], acc: dict, scorer: Scorer,
         made_at: str | None = None, now: datetime | None = None) -> dict:
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    nos = sorted({no for r in rows.values() for no in r if scorer.actual(no) is not None})
    h = {
        "game": data.game.slug, "version": HISTORY_VERSION, "made_at": made_at or stamp, "updated_at": stamp,
        "first_no": nos[0] if nos else None, "last_no": data.draws[-1].no,
        "blocks": [s.to_dict() for s in data.fmt.blocks],
        "draws": {"nos": nos, "actual": [enc(scorer.actual(no)) for no in nos]},
        "sources": {s: {"detail": details.get(s, ""), "nos": (ns := sorted(n for n in rows[s] if scorer.actual(n) is not None)),
                        "numbers": [rows[s][n] for n in ns]} for s in ORDER if rows.get(s)},
        "final_acc": acc,
    }
    write_text(path(data.game.slug), json.dumps(h, ensure_ascii=False, separators=(",", ":")))
    return h


def build(data: GameData, godmode: list[dict] | None = None, godmode_title: str = "",
          now: datetime | None = None) -> tuple[dict, dict]:
    """Полная сборка истории игры. godmode — прогнозы «лидера за всю историю» режима Бога
    ([{no, predicted}], godmode.auto_run c retro_from_no). Возвращает (история, сведения)."""
    rows, details, info = eval_rows(data)
    if not rows:
        return {}, info
    ch, ch_title = chaos_rows(data)
    if ch:
        rows["chaos"], details["chaos"] = ch, ch_title
    if godmode:
        rows["godmode"] = {int(r["no"]): enc(r["predicted"]) for r in godmode}
        details["godmode"] = godmode_title
    scorer = Scorer(data)
    acc: dict[str, list[float]] = {}
    add_final(rows, scorer, acc, sorted({no for r in rows.values() for no in r}))
    details["final"] = "голосование по доверию, накопленному к этому тиражу"
    return save(data, rows, details, acc, scorer, now=now), info


def journal_checked(slug: str) -> Rows:
    from .journal import load as load_journal
    out: Rows = {}
    for e in load_journal(slug)["entries"]:
        if e.get("status") == "checked":
            out.setdefault(e["source"], {})[int(e["draw_no"])] = enc(e["numbers"])
    return out


def fill(data: GameData, log=None) -> dict:
    """Дописывает в историю тиражи, сыгранные после прошлого обновления: сверенный прогноз журнала,
    а где его нет — расчёт задним числом (сравнение методов запускается, только если есть что
    восстанавливать). Истории ещё нет — ничего не делает: её целиком собирает retro.run."""
    slug = data.game.slug
    h = load(slug)
    if h is None:
        return {"status": "no_history"}
    new = [d.no for d in data.draws if d.no > h["last_no"]]
    if not new:
        return {"status": "up_to_date", "added": 0}
    rows = rows_of(h)
    details = {s: v.get("detail", "") for s, v in h["sources"].items()}
    jr = journal_checked(slug)
    wanted = [s for s in rows if s != "final"]
    need = {s: {no for no in new if no not in jr.get(s, {})} for s in wanted}
    restored = 0
    if any(need[s] for s in EVAL_SOURCES if s in need):
        calc, _, _ = eval_rows(data, set().union(*(need[s] for s in EVAL_SOURCES if s in need)))
    else:
        calc = {}
    if need.get("chaos"):
        calc["chaos"] = chaos_rows(data, need["chaos"])[0]
    if need.get("godmode"):
        calc["godmode"] = leader_rows(data, need["godmode"])[0]
    for s in wanted:
        for no in new:
            text = jr.get(s, {}).get(no)
            if text is None:
                text = calc.get(s, {}).get(no)
                restored += text is not None
            if text is not None:
                rows[s][no] = text
    scorer = Scorer(data)
    for no, text in zip(h["draws"]["nos"], h["draws"]["actual"]):    # старые тиражи — как записаны
        scorer._actual[no] = [tuple(b) for b in dec(text)]
    acc = h.get("final_acc") or {}
    add_final(rows, scorer, acc, new, keep=jr.get("final"))
    save(data, rows, details, acc, scorer, made_at=h.get("made_at"))
    if log and restored:
        log(f"{slug}: {len(new)} новых тиражей, восстановлено прогнозов задним числом — {restored}")
    return {"status": "filled", "added": len(new), "restored": restored}
