import numpy as np
from conftest import random_lotto, write_lotto_file

from lottery.drawfile import load_game_data
from lottery.evaluate import baseline, baseline_pmf, evaluate_game
from lottery.games import draws_path, get_game


def _game(data_dir, blocks, slug="testgame"):
    write_lotto_file(draws_path(slug), blocks)
    return load_game_data(get_game(slug))


def test_baseline_matches_theory(data_dir):
    data = _game(data_dir, [random_lotto(100, 20, 4, 1), random_lotto(100, 20, 4, 2)])
    mean, var = baseline(data)
    assert np.allclose(mean, 1.6) and len(mean) == 100
    pmf = baseline_pmf(data)
    assert abs(pmf.sum() - 1) < 1e-9 and abs((pmf * np.arange(len(pmf))).sum() - 1.6) < 1e-9


def test_fair_lottery_has_no_winner(data_dir):
    data = _game(data_dir, [random_lotto(1500, 20, 4, 7)])
    res = evaluate_game(data)
    assert res["status"] == "ok"
    assert res["significant_after_correction"] == []
    assert len(res["next_prediction"]["numbers"][0]) == 4
    assert all(1 <= v <= 20 for v in res["next_prediction"]["numbers"][0])


def test_real_pattern_is_found(data_dir):
    x = random_lotto(1500, 20, 4, 8)
    rng = np.random.default_rng(0)
    for t in range(1, len(x)):
        if rng.random() < 0.5:
            x[t] = x[t - 1]                        # половина тиражей повторяет предыдущий
    res = evaluate_game(_game(data_dir, [x]))
    best = next(m for m in res["models"] if m["key"] == res["best_key"])
    assert best["holdout"]["p_better"] < 1e-6
    assert best["holdout"]["mean_hits"] > 2.0     # случайный выбор — 0.8


def test_insufficient_data(data_dir):
    res = evaluate_game(_game(data_dir, [random_lotto(60, 20, 4, 1)]))
    assert res["status"] == "insufficient"
