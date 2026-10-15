"""Правила игр (ответы stoloto.ru, октябрь 2026), лототрон/ГСЧ, порядок шаров, повторяемость
находок, «что исключено», дрейф и ожидаемый возврат ближайшего тиража."""
import json
from pathlib import Path

import numpy as np
import pytest
from conftest import random_lotto

from lottery import mechanics, nextdraw, prizes, rules
from lottery.drawfile import load_game_data
from lottery.games import draws_path, get_game

REAL = json.loads((Path(__file__).parent / "fixtures" / "rules_real.json").read_text(encoding="utf-8"))


def _rules(slug):
    f = REAL[slug]
    cms = {"data": [{"contents": [
        {"collection": "how_draws_work", "item": {"text": f["how"], "content": []}},
        {"collection": "faq", "item": {"rulesFaqs": f["faq"]}},
        {"collection": "about_prize", "item": {"cards": f["cards"]}}]}]}
    return rules.parse(slug, {"draw": f["draw"]}, f["table"], cms, f["superprize"])


def _save_rules(slug):
    rec = _rules(slug)
    rules.rules_dir().mkdir(parents=True, exist_ok=True)
    rules.rules_path(slug).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return rec


def test_schedule_4x20_lototron_and_rng():
    r = _rules("4x20")
    s = r["schedule"]
    assert s["lototron"] and s["rng"]
    assert s["times"]["10:00"] == "L" and s["times"]["22:00"] == "L"
    assert s["times"]["11:07"] == "R" and s["times"]["23:37"] == "R"
    assert "09:55" not in s["times"]                     # время окончания продаж — не тираж
    assert "Тиражи лотереи проходят" in r["how"] and "&laquo;" not in r["how"]
    assert "67%" in r["faq"][0]["answer"] and "100 000 000 ₽" in r["faq"][0]["answer"]
    assert r["next_draw"]["super_prize"] == 418062296 and r["next_draw"]["price"] == 350
    assert r["next_draw"]["prize_fund_pct"] == 67 and r["next_draw"]["lototron"] is False


def test_schedule_6x45_unmarked_times_are_lototron():
    s = _rules("6x45")["schedule"]
    assert s["times"]["11:00"] == "L" and s["times"]["12:30"] == "L" and s["times"]["23:59"] == "L"
    assert s["times"]["14:25"] == "R" and s["times"]["19:55"] == "R"


def test_schedule_rng_only():
    s = _rules("5x36plus")["schedule"]
    assert s["rng"] and not s["lototron"]
    assert rules.mechanism_of_time(_rules("5x36plus"), "12:34") == "R"


@pytest.mark.parametrize("slug,n,counts,expect", [
    ("4x20", 2, [4, 4], {"prizes": {"2+1": 350.0}, "super": ["4+4"], "share": ("2+0", 25.0)}),
    ("6x45", 1, [6], {"prizes": {"5": 140000.0, "2": 70.0}, "super": ["6"]}),
    ("5x36plus", 2, [5, 1], {"prizes": {"4+0": 7500.0}, "super": ["5+1", "5+0"]}),
    ("crazycombo", 1, [12], {"prizes": {"11": 750.0, "1": 750.0, "8": 20.0, "4": 20.0}, "super": ["12", "0"]}),
    ("keno2", 1, [10], {"prizes": {"10": 10000000.0, "6": 750.0, "0": 200.0}, "super": []}),
])
def test_official_prizes(slug, n, counts, expect):
    off = rules.official_prizes(_rules(slug), n, counts)
    for k, v in expect["prizes"].items():
        assert off["prizes"][k] == v
    assert sorted(off["super"]) == sorted(expect["super"])
    if "share" in expect:
        assert off["shares"][expect["share"][0]] == expect["share"][1]


def test_bingo_table_error_is_kept():
    r = _rules("gzhl")
    assert r["table"] == [] and r["table_error"] == "not valid request" and r["next_draw"]["lototron"] is True


# ── лототрон / ГСЧ ───────────────────────────────────────────────────────────

def _mixed_4x20(t=1200, biased_first_ball=False, seed=0):
    """Тиражи «4 из 20»: старые — лототрон (до появления ГСЧ), новые — чередуются."""
    rng = np.random.default_rng(seed)
    lines = []
    for i in range(t):
        rng_era = i >= t // 3
        kind = "R" if rng_era and i % 2 else "L"
        hh, mm = (11, "07") if kind == "R" else (22, "00")
        f1 = rng.choice(np.arange(1, 21), 4, replace=False).tolist()
        f2 = rng.choice(np.arange(1, 21), 4, replace=False).tolist()
        if biased_first_ball and kind == "L" and 7 not in f1 and rng.random() < 0.5:
            f1 = [7] + f1[1:]
        day = 1 + i // 2
        lines.append(f"{1 + day % 28:02d}.{1 + (day // 28) % 12:02d}.{2010 + day // 336} {hh}:{mm}||{i + 1}||"
                     f"{', '.join(map(str, f1))}||{', '.join(map(str, f2))}")
    draws_path("4x20").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_game_data(get_game("4x20"))


def test_classify_by_schedule_and_era():
    _save_rules("4x20")
    data = _mixed_4x20()
    kinds = mechanics.classify(data)
    assert kinds[0] == "L" and kinds[-1] in ("L", "R")
    c = mechanics.mechanism_counts(data)
    assert c["L"] > 700 and c["R"] == 400 and c["unknown"] == 0


def test_api_mechanism_beats_time():
    _save_rules("4x20")
    data = _mixed_4x20()
    rec = {"no": data.draws[0].no, "source": "w", "categories": [{"label": "2 X 1", "winners": 1, "prize": 350}],
           "m": "R"}
    prizes.save("4x20", {rec["no"]: rec})
    assert mechanics.classify(data)[0] == "R"
    assert prizes.draw_mechanism({"date": "2026-10-14T23:37:30+0300"}) == "R"
    assert prizes.draw_mechanism({"date": "2020-03-11T22:00:00", "videoLink": "https://x"}) == "L"
    assert prizes.draw_mechanism({"date": "2020-03-11T22:00:00"}) is None


def test_mechanism_report_finds_order_bias_only_for_lototron():
    _save_rules("4x20")
    data = _mixed_4x20(t=3000, biased_first_ball=True, seed=3)
    rep = mechanics.mechanism_report(data)
    assert rep["mixed"] and set(rep["by_mechanism"]) == {"L", "R"}
    sig_l = rep["order"]["L"]["significant"]
    assert any(t["position"] == 1 and t["block"] == "Поле 1" for t in sig_l)
    assert any(t["replicated"] for t in sig_l)               # перекос устойчивый — повторяется
    assert not rep["order"]["R"]["significant"]
    assert rep["comparison"] and all("p_value" in c for c in rep["comparison"])


def test_fair_mixed_game_has_no_order_bias():
    _save_rules("4x20")
    rep = mechanics.mechanism_report(_mixed_4x20(t=2000, seed=11))
    assert not any(t.get("replicated") for k in rep["order"] for t in rep["order"][k]["significant"])


# ── повторяемость, чувствительность, дрейф ────────────────────────────────────

def test_one_off_noise_is_not_replicated(data_dir):
    """Отклонение только в первой половине истории — не находка."""
    from lottery.stats import game_randomness
    x1 = random_lotto(1500, 20, 4, seed=1)
    x1[:750, 0] = 1.0                                         # число 1 выпадало всегда — но только раньше
    from conftest import write_lotto_file
    write_lotto_file(draws_path("6x45"), [random_lotto(1500, 45, 6, seed=2)])
    write_lotto_file(draws_path("5x36"), [x1])
    data = load_game_data(get_game("5x36"))
    r = game_randomness(data)
    freq = next(t for t in r["tests"] if t["test"] == "freq")
    assert freq["p_adjusted"] < 0.05 and freq["replicated"] is False and not freq["significant"]


def test_detectable_shrinks_with_more_draws(data_dir):
    from conftest import write_lotto_file
    write_lotto_file(draws_path("6x45"), [random_lotto(500, 45, 6, seed=2)])
    small = mechanics.detectable(load_game_data(get_game("6x45")))[0]["relative_pct"]
    write_lotto_file(draws_path("6x45"), [random_lotto(8000, 45, 6, seed=2)])
    big = mechanics.detectable(load_game_data(get_game("6x45")))[0]["relative_pct"]
    assert big < small / 3 and 0 < big < 20
    assert mechanics.detectable_edge(1.0, 400, 2.0) == pytest.approx((1.959964 + 0.841621) / 20 / 2 * 100, rel=1e-3)


def test_drift_alarm_on_recent_bias(data_dir):
    from conftest import write_lotto_file
    x = random_lotto(4000, 20, 4, seed=5)
    rng = np.random.default_rng(9)
    for t in range(3700, 4000):                               # последние 300 тиражей: число 5 «прилипло»
        if x[t, 4] == 0 and rng.random() < 0.6:
            on = np.nonzero(x[t])[0]
            x[t, on[0]] = 0
            x[t, 4] = 1
    write_lotto_file(draws_path("5x36"), [x])
    data = load_game_data(get_game("5x36"))
    res = mechanics.save_drift(data)
    assert res["alarms"] and res["new_alarms"]
    again = mechanics.save_drift(data)
    assert again["alarms"] and not again["new_alarms"]        # о той же тревоге второй раз не сообщаем
    write_lotto_file(draws_path("6x45"), [random_lotto(4000, 45, 6, seed=6)])
    assert not mechanics.drift(load_game_data(get_game("6x45")))["alarms"]


# ── ближайший тираж ───────────────────────────────────────────────────────────

def _six45(t=400):
    from conftest import write_lotto_file
    write_lotto_file(draws_path("6x45"), [random_lotto(t, 45, 6, seed=4)])
    recs = {}
    for no in range(1, t + 1):
        recs[no] = {"no": no, "source": "winCategories", "price": 70.0, "sales": 300000.0 if no != 50 else 900.0,
                    "categories": [{"label": "6 из 6", "winners": 0, "prize": 0},
                                   {"label": "5 из 6", "winners": 15, "prize": 140000},
                                   {"label": "4 из 6", "winners": 700, "prize": 3500},
                                   {"label": "3 из 6", "winners": 9000, "prize": 560},
                                   {"label": "2 из 6", "winners": 50000, "prize": 70}]}
    prizes.save("6x45", recs)
    return load_game_data(get_game("6x45"))


def test_next_draw_return_grows_with_superprize():
    from scipy import stats as sps
    data = _six45()
    _save_rules("6x45")
    r = nextdraw.compute(data)
    pmf = sps.hypergeom(45, 6, 6).pmf(np.arange(7))
    base = (pmf[5] * 140000 + pmf[4] * 3500 + pmf[3] * 560 + pmf[2] * 70) / 70
    assert r["return_without_super"] == pytest.approx(base, rel=1e-9)
    lam = 300000 * pmf[6]
    assert r["return"] == pytest.approx(base + pmf[6] * 49548548 * (1 - np.exp(-lam)) / lam / 70, rel=1e-6)
    assert r["number"] == 19091 and r["return"] < 1
    # суперприз в миллиард — возврат больше ставки, уведомление один раз
    rec = json.loads(rules.rules_path("6x45").read_text(encoding="utf-8"))
    rec["next_draw"]["super_prize"] = 1_500_000_000
    rules.rules_path("6x45").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    res = nextdraw.compute_all(["6x45"], lambda s: load_game_data(get_game(s)))
    assert res["6x45"]["return"] > 1
    assert [x["slug"] for x in nextdraw.to_notify(res)] == ["6x45"] and nextdraw.to_notify(res) == []


def test_anomalous_draws_are_excluded():
    _six45()
    assert prizes.anomalies("6x45") == [50]
    assert nextdraw.expected_sales("6x45") == 300000.0
