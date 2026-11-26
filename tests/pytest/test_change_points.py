from datetime import datetime, timedelta

import numpy as np
from conftest import random_lotto
from lottery.change_points import apply, clear_reset, set_reset
from lottery.drawfile import Draw, load_game_data, write_draws
from lottery.games import draws_path, get_game


def test_reset_point_filters_old_draws(data_dir):
    x = random_lotto(40, 20, 4, seed=1)
    start = datetime(2010, 1, 1)
    draws = [
        Draw(i + 1, (start + timedelta(days=i)).strftime("%d.%m.%Y %H:%M"),
             (tuple(int(v) + 1 for v in np.flatnonzero(x[i])),))
        for i in range(len(x))
    ]
    write_draws(draws_path("mini"), draws)
    data = load_game_data(get_game("mini"))

    try:
        # Reset is intentionally day-granular: all draws on the selected date are included.
        set_reset("mini", data.draws[10].dt, "тестовая точка отсчёта")
        scoped, scope = apply(data)

        assert scope["active"] is True
        assert scoped.T == len(data.draws) - 10
        assert scoped.draws[0].no == data.draws[10].no
        assert scoped.draws[-1].no == data.draws[-1].no
        assert scope["skipped_draws"] == 10
    finally:
        clear_reset("mini")
