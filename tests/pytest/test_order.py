"""Порядок выпадения: прогноз ставит числа по позициям, журнал считает «на своём месте»."""
from datetime import datetime, timedelta

import numpy as np

from lottery import journal, order
from lottery.drawfile import Draw, load_game_data, write_draws
from lottery.games import draws_path, get_game


def _draws(t=1500, first7=False, seed=0):
    rng = np.random.default_rng(seed)
    now = datetime.now().replace(second=0, microsecond=0)
    out = []
    for i in range(t):
        nums = [int(v) for v in rng.choice(np.arange(1, 37), 5, replace=False)]
        if first7 and 7 in nums:
            nums.remove(7)
            nums.insert(0, 7)                 # «7» всегда выходит первой
        out.append(Draw(i + 1, (now - timedelta(hours=t - i)).strftime("%d.%m.%Y %H:%M"), (tuple(nums),)))
    write_draws(draws_path("5x36"), out)
    return load_game_data(get_game("5x36"))


def test_order_follows_position_history():
    data = _draws(first7=True)
    assert 0 in order.ordered_blocks(data)
    for no in range(100):
        got = order.order_numbers(data, 0, [3, 7, 12, 20, 33], 2000 + no)
        assert got[0] == 7 and sorted(got) == [3, 7, 12, 20, 33]
    bt = order.backtest(data)[0]
    assert bt["p_value"] < 1e-4 and bt["rate"] > bt["expected"]


def test_fair_order_is_not_predictable_and_varies():
    data = _draws(seed=3)
    bt = order.backtest(data)[0]
    assert bt["p_value"] > 0.01 and abs(bt["rate"] - 0.2) < 0.03
    orders = {tuple(order.order_numbers(data, 0, [3, 7, 12, 20, 33], 2000 + no)) for no in range(30)}
    assert len(orders) > 10                    # где история не различает позиции, порядок меняется


def test_sorted_archive_has_no_order():
    now = datetime.now().replace(second=0, microsecond=0)
    rng = np.random.default_rng(1)
    write_draws(draws_path("5x36"), [Draw(i + 1, (now - timedelta(hours=900 - i)).strftime("%d.%m.%Y %H:%M"),
                                          (tuple(sorted(int(v) for v in rng.choice(np.arange(1, 37), 5, replace=False))),))
                                     for i in range(900)])
    data = load_game_data(get_game("5x36"))
    assert order.ordered_blocks(data) == {}
    assert order.order_numbers(data, 0, [20, 3, 7], 5) == [20, 3, 7]


def test_journal_counts_in_place():
    data = _draws(t=400)
    entry = journal.record(data, "analysis_best", [[7, 3, 12, 20, 33]], ordered=True,
                           now=datetime.now() - timedelta(hours=3), draw_no=data.draws[-1].no)
    draw = Draw(entry["draw_no"], datetime.now().strftime("%d.%m.%Y %H:%M"), ((7, 12, 3, 20, 1),))
    res = journal._check(entry, draw, datetime.now())
    assert res["hits"] == 4 and res["in_place"] == 2 and abs(res["in_place_expected"] - 5 / 36) < 1e-9
    row = journal.summary([res])[0]
    assert row["in_place"] == 2 and row["ordered_checked"] == 1
