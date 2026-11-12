"""42.5.0: прогноз на все тиражи до следующего цикла, «Золотая середина», призы Кено 2.0 из
правил, ретро-проверка за неделю, сводка сверки в Telegram и «Л = К»."""
import json
from datetime import datetime, timedelta

import numpy as np
from conftest import random_lotto, write_lotto_file

from lottery import journal, notify
from lottery.drawfile import Draw, load_game_data, write_draws
from lottery.games import draws_path, get_game


def _fast_game(minutes=15, count=400, last_ago_min=20, slug="5x36"):
    now = datetime(2026, 10, 17, 3, 20)
    last = now - timedelta(minutes=last_ago_min)
    rng = np.random.default_rng(3)
    write_draws(draws_path(slug), [
        Draw(i + 1, (last - timedelta(minutes=minutes * (count - 1 - i))).strftime("%d.%m.%Y %H:%M"),
             (tuple(sorted(int(v) + 1 for v in rng.choice(36, 5, replace=False))),)) for i in range(count)])
    return load_game_data(get_game(slug)), now


def test_target_draws_cover_horizon():
    """Тираж каждые 15 минут: горизонт 75 минут — пять тиражей подряд, номера по порядку."""
    data, now = _fast_game()
    ts = journal.target_draws(data, now, horizon_s=75 * 60, max_n=12)
    assert [t["no"] for t in ts] == [402, 403, 404, 405, 406]
    assert all(t["date"] > now for t in ts)
    assert len(journal.target_draws(data, now, horizon_s=75 * 60, max_n=2)) == 2
    # без горизонта — один ближайший, как раньше
    assert [t["no"] for t in journal.target_draws(data, now)] == [402]


def test_record_many_replaces_only_pending_of_same_source():
    data, now = _fast_game()
    journal.record_many(data, "analysis_best", [(402, [[1, 2, 3, 4, 5]]), (403, [[1, 2, 3, 4, 5]])], now=now)
    journal.record_many(data, "chaos", [(402, [[6, 7, 8, 9, 10]])], now=now)
    journal.record_many(data, "analysis_best", [(403, [[11, 12, 13, 14, 15]]), (404, [[1, 2, 3, 4, 6]])], now=now)
    es = journal.load("5x36")["entries"]
    best = {e["draw_no"]: e["numbers"] for e in es if e["source"] == "analysis_best"}
    assert best == {402: [[1, 2, 3, 4, 5]], 403: [[11, 12, 13, 14, 15]], 404: [[1, 2, 3, 4, 6]]}
    assert sum(e["source"] == "chaos" for e in es) == 1


def test_journal_record_writes_all_draws_until_next_cycle(monkeypatch):
    import lp
    data, now = _fast_game()
    monkeypatch.setattr(lp, "game_activity", lambda d: {"active": True})
    monkeypatch.setattr(journal, "datetime", type("D", (datetime,), {"now": classmethod(lambda cls: now)}))
    lp.journal_record(data, "analysis_consensus", [[1, 2, 3, 4, 5]], "", ordered=False)
    nos = sorted(e["draw_no"] for e in journal.load("5x36")["entries"])
    assert nos == list(range(402, 411))            # горизонт 130 минут — два цикла автозапуска


def test_golden_excludes_least_and_keeps_best():
    from lottery.evaluate import evaluate_game
    write_lotto_file(draws_path("6x45"), [random_lotto(900, 45, 6, seed=4)])
    ev = evaluate_game(load_game_data(get_game("6x45")), keep_picks=True)
    g = ev["golden"]
    assert g["title"] == "Золотая середина" and g["holdout"]["n"] > 0
    p = ev.pop("_picks")
    best, least, gold = p["analysis_best"][0], p["least"][0], p["golden"][0]
    for row in range(0, best.shape[0], 37):
        b, l, z = set(best[row]), set(least[row]), set(gold[row])
        assert len(z) == 6 and not (z & l)
        assert b - l <= z                      # числа лучшего метода, не попавшие в «наименее вероятные», остаются
    assert ev["golden"]["next"] == [sorted(int(v) + 1 for v in gold[-1])]
    json.dumps(ev, default=float)              # без _picks результат сохраняется как JSON (как в lp.save_json)


def test_keno_payout_from_rules_table():
    from lottery import rules
    rules.rules_dir().mkdir(parents=True, exist_ok=True)
    rules.rules_path("keno2").write_text(json.dumps({
        "next_draw": {"price": 100},
        "table": [{"g1": 10, "g2": 10, "prize": 10_000_000, "superprize": False, "percent": None},
                  {"g1": 10, "g2": 5, "prize": 250, "superprize": False, "percent": None},
                  {"g1": 10, "g2": 0, "prize": 200, "superprize": False, "percent": None},
                  {"g1": 9, "g2": 5, "prize": 300, "superprize": False, "percent": None}]}), encoding="utf-8")
    t = journal.rules_prize_table("keno2", [10])
    assert t["price"] == 100 and t["categories"]["5"]["prize"] == 250 and "4" not in t["categories"]
    entry = {"source": "analysis_best", "blocks": [{"mode": "set"}]}
    assert journal._payout(entry, [5], t) == 250 and journal._payout(entry, [0], t) == 200
    assert journal._payout(entry, [3], t) == 0.0
    assert journal.rules_prize_table("6x45", [6]) is None     # только игры с фиксированными призами


def test_retro_is_honest_and_separate():
    """Ретро: прогноз на каждый тираж недели, без пометки «после тиража», отдельно от журнала;
    прогноз на тираж t не зависит от тиражей после t."""
    from lottery import retro
    data, now = _fast_game(minutes=60, count=700, last_ago_min=10)
    st = retro.run(["5x36"], days=2, godmode_budget=0, now=now, log=lambda m: None)
    assert st["status"] == "done" and not retro.due(now + timedelta(days=1))
    rj = journal.load("5x36", retro=True)
    assert rj["retro"] and not journal.load("5x36")["entries"]
    es = rj["entries"]
    by_source = st["games"]["5x36"]["by_source"]
    week = sum(1 for d in data.draws if d.dt >= now - timedelta(days=2))
    for s in ("analysis_best", "analysis_consensus", "least", "golden", "chaos"):
        assert by_source[s] == week, s
    assert all(e["status"] == "checked" and e["retro"] for e in es)
    first = min(e["draw_no"] for e in es)
    # те же тиражи, но всё после первого тиража недели — другое: прогноз на первый не меняется
    rng = np.random.default_rng(99)
    draws = [d if d.no <= first else Draw(d.no, d.date, (tuple(sorted(int(v) + 1 for v in rng.choice(36, 5, replace=False))),))
             for d in data.draws]
    write_draws(draws_path("5x36"), draws)
    retro.run(["5x36"], days=2, godmode_budget=0, now=now, log=lambda m: None)
    again = {(e["source"], e["draw_no"]): e["numbers"] for e in journal.load("5x36", retro=True)["entries"]}
    for e in es:
        if e["draw_no"] == first and e["source"] in ("analysis_best", "analysis_consensus", "golden"):
            assert again[(e["source"], first)] == e["numbers"], e["source"]


def test_digest_groups_many_draws_and_same_lk():
    def entry(source, no, hits):
        return {"source": source, "source_title": source, "status": "checked", "draw_no": no, "hits": hits,
                "expected": 1.0, "numbers": [[1, 2, 3, 4, 5]], "actual": [[1, 2, 9, 10, 11]], "won": 100.0 if hits > 2 else 0}
    many = [entry(s, no, h) for no in (10, 11, 12) for s, h in (("analysis_best", 2), ("golden", 3), ("least", 1))]
    text = notify.journal_digest([("Рапидо", many)])
    assert "№10–12 (3 тиража" in text and "Л: 6 из 15" in text and "З: 9 из 15" in text and "Н: выпало 3 из 15" in text
    assert text.count("Рапидо") == 1
    one = notify.journal_digest([("6 из 45", [entry("analysis_best", 7, 2)])])
    assert "№7 (выпало" in one
    msg = notify.auto_message({"games": {}}, {"g": {"title": "Игра", "next_no": 5, "numbers": [[3, 1, 2]],
                                                    "consensus": [[1, 2, 3]], "golden": [[1, 2, 4]]}})
    assert "Л = К: " in msg and "  К:" not in msg and "З: " in msg
