"""Калькулятор шансов и генератор непопулярных комбинаций."""
from math import comb

import numpy as np
from conftest import random_lotto, write_lotto_file

from lottery.drawfile import BlockSpec, load_game_data
from lottery.games import draws_path, get_game
from lottery.odds import load_prizes, odds_table, save_prizes
from lottery.tickets import check, flags, generate, score


def _game(slug, blocks):
    write_lotto_file(draws_path(slug), blocks)
    return load_game_data(get_game(slug))


def test_jackpot_and_probabilities(data_dir):
    data = _game("6x45", [random_lotto(300, 45, 6, 1)])
    t = odds_table(data)
    assert t["supported"] and t["combinations"] == comb(45, 6) == 8_145_060
    assert abs(t["jackpot"]["one_in"] - 8_145_060) < 1
    assert abs(sum(p["p"] for p in t["patterns"]) - 1) < 1e-12
    three = next(p for p in t["patterns"] if p["key"] == "3")
    assert abs(three["p"] - comb(6, 3) * comb(39, 3) / comb(45, 6)) < 1e-15


def test_two_fields_are_independent(data_dir):
    data = _game("4x20", [random_lotto(300, 20, 4, 1), random_lotto(300, 20, 4, 2)])
    t = odds_table(data)
    p44 = next(p for p in t["patterns"] if p["key"] == "4+4")
    assert abs(p44["one_in"] - comb(20, 4) ** 2) < 1e-3
    assert t["patterns"][0]["key"] == "4+4"


def test_expected_value_from_user_prizes(data_dir):
    data = _game("5x36", [random_lotto(300, 36, 5, 1)])
    save_prizes("5x36", 80, {"5": 3_000_000, "4": 8000, "3": 800, "2": 80})
    assert load_prizes("5x36")["price"] == 80
    t = odds_table(data)
    pmf = {p["key"]: p["p"] for p in t["patterns"]}
    ev = 3_000_000 * pmf["5"] + 8000 * pmf["4"] + 800 * pmf["3"] + 80 * pmf["2"]
    assert abs(t["expected_value"] - ev) < 1e-9 and abs(t["return_per_ruble"] - ev / 80) < 1e-12
    assert abs(t["p_any_prize"] - (pmf["5"] + pmf["4"] + pmf["3"] + pmf["2"])) < 1e-12


def test_bingo_is_not_supported_by_calculator(data_dir):
    from test_bingo import bingo_draws
    from lottery.drawfile import write_draws
    write_draws(draws_path("bingo75"), bingo_draws(200, n=75))
    assert not odds_table(load_game_data(get_game("bingo75")))["supported"]


SPEC = BlockSpec("Числа", 0, None, 6, 1, 45)


def test_popularity_flags():
    codes = lambda nums, last=None: {f["code"] for f in flags(nums, SPEC, last)}  # noqa: E731
    assert "dates" in codes([3, 7, 12, 19, 24, 30])
    assert "runs" in codes([10, 11, 12, 30, 38, 44])
    assert "progression" in codes([5, 10, 15, 20, 25, 30])
    assert "multiples" in codes([5, 10, 20, 35, 40, 45])
    assert "last_draw" in codes([2, 9, 33, 38, 41, 44], {2, 9, 33, 1, 5, 6})
    assert score([4, 17, 23, 36, 40, 44], SPEC) == 0


def test_generated_tickets_are_clean_uniform_and_diverse(data_dir):
    data = _game("6x45", [random_lotto(300, 45, 6, 3)])
    res = generate(data, count=20, seed=1)
    assert res["supported"] and len(res["tickets"]) == 20
    last = set(int(v) for v in data.draws[-1].blocks[0])
    for t in res["tickets"]:
        nums = t["blocks"][0]
        assert len(set(nums)) == 6 and all(1 <= v <= 45 for v in nums)
        assert score(nums, SPEC, last) == 0
    for i, a in enumerate(res["tickets"]):
        for b in res["tickets"][i + 1:]:
            assert len(set(a["blocks"][0]) & set(b["blocks"][0])) <= 3
    assert 0.3 < res["accepted_share"] < 0.95


def test_filter_does_not_bias_single_numbers(data_dir):
    """Отбор по признакам не должен систематически выкидывать отдельные числа (кроме дат)."""
    data = _game("6x45", [random_lotto(300, 45, 6, 4)])
    res = generate(data, count=50, seed=2, max_overlap=6)
    counts = np.bincount([v for t in res["tickets"] for v in t["blocks"][0]], minlength=46)[1:]
    assert (counts > 0).sum() >= 40


def test_check_user_combination(data_dir):
    data = _game("4x20", [random_lotto(300, 20, 4, 1), random_lotto(300, 20, 4, 2)])
    bad = check(data, [[1, 2, 3, 4], [5, 10, 15, 20]])
    assert bad["valid"] and bad["score"] > 0
    assert not check(data, [[1, 2, 3]])["valid"]
    assert not check(data, [[1, 2, 3, 99], [1, 2, 3, 4]])["valid"]
