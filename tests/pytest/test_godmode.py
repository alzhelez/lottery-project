import numpy as np
from conftest import random_lotto, write_lotto_file

from lottery.drawfile import load_game_data
from lottery.games import draws_path, get_game
from lottery.godmode import ExpertPool, run_godmode, run_strategies
from lottery.models import expert_grid


def _pool(slug, x):
    write_lotto_file(draws_path(slug), [x])
    data = load_game_data(get_game(slug))
    pool = ExpertPool(data)
    for m in expert_grid(1):
        pool.add(m)
    return pool


def test_strategies_do_not_look_ahead(data_dir):
    """Прогнозы мета-стратегий на общих тиражах совпадают для истории 1100 и 1200 тиражей."""
    x = random_lotto(1200, 20, 4, seed=3)
    full = run_strategies(_pool("full", x))
    part = run_strategies(_pool("part", x[:1100]))
    rows = 1100 - 200 + 1          # warmup = 200 в обоих случаях
    for a, b in zip(full, part):
        for pa, pb in zip(a["picks"], b["picks"]):
            np.testing.assert_array_equal(np.sort(pa[:rows], axis=1), np.sort(pb[:rows], axis=1),
                                          err_msg=a["key"])


def test_godmode_runs_and_saves(data_dir):
    write_lotto_file(draws_path("gm"), [random_lotto(500, 20, 4, seed=5)])
    data = load_game_data(get_game("gm"))
    checkpoints, progress = [], []
    res = run_godmode(data, budget_minutes=1, on_progress=progress.append, on_checkpoint=checkpoints.append)
    assert res["complete"] and checkpoints and progress
    assert res["next"]["no"] == 501
    assert len(res["next"]["numbers"][0]) == 4
    assert res["timeline"][0]["no"] == 500
    assert res["experts"] >= 30
