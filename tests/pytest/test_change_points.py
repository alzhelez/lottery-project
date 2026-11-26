from conftest import random_lotto, write_lotto_file
from lottery.change_points import apply, clear_reset, set_reset
from lottery.drawfile import load_game_data
from lottery.games import get_game


def test_reset_point_filters_old_draws(data_dir):
    path = data_dir / "draws" / "draws_mini.txt"
    write_lotto_file(path, [random_lotto(40, 20, 4, seed=1)])
    data = load_game_data(get_game("mini"))

    try:
        set_reset("mini", data.draws[10].dt, "тестовая точка отсчёта")
        scoped, scope = apply(data)

        assert scope["active"] is True
        assert scoped.T == len(data.draws) - 10
        assert scoped.draws[0].no == data.draws[10].no
        assert scoped.draws[-1].no == data.draws[-1].no
    finally:
        clear_reset("mini")
