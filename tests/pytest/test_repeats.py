"""Гипотезы о повторах по позициям: подсчёт через БПФ совпадает с прямым, заложенный повтор
находится (свои задержка и сдвиг), у честных тиражей находок нет."""
from datetime import datetime, timedelta

import numpy as np
import pytest

from lottery import repeats
from lottery.drawfile import Draw, load_game_data, write_draws
from lottery.games import draws_path, get_game


def _arr(t=600, k=5, n=36, seed=0):
    rng = np.random.default_rng(seed)
    return np.array([rng.choice(n, k, replace=False) + 1 for _ in range(t)])


@pytest.mark.parametrize("lag,s,d", [(1, 0, 0), (7, 0, 3), (13, 0, -5), (4, 2, 0), (29, -3, 0), (599, 0, 0)])
def test_fft_counts_match_direct(lag, s, d):
    arr = _arr()
    c_num, c_pos = repeats.counts(arr, 1, 36)
    e_num, e_pos = repeats.expected(arr, 1, 36)
    obs, exp = repeats.count_one(arr, lag, s, d, 1, 36)
    if s == 0:
        assert c_num[lag, d + 35] == obs and e_num[lag, d + 35] == pytest.approx(exp)
    else:
        assert c_pos[lag, s + 4] == obs and e_pos[lag, s + 4] == pytest.approx(exp)


def _write(arr):
    now = datetime.now().replace(second=0, microsecond=0)
    write_draws(draws_path("5x36"), [Draw(i + 1, (now - timedelta(hours=len(arr) - i)).strftime("%d.%m.%Y %H:%M"),
                                          (tuple(int(v) for v in row),)) for i, row in enumerate(arr)])
    return load_game_data(get_game("5x36"))


def test_planted_shifted_repeat_is_found():
    """Число со 2-й позиции через 17 тиражей часто выходит на 4-й позиции увеличенным на 2."""
    arr = _arr(t=3000, seed=4)
    rng = np.random.default_rng(1)
    for t in range(17, len(arr)):
        v = arr[t - 17, 1] + 2
        if v <= 36 and v not in arr[t] and rng.random() < 0.35:
            arr[t, 3] = v
    res = repeats.analyze(_write(arr))
    rows = res["groups"]["all"][0]
    assert res["available"] and "Найдены" in res["verdict"]
    found = rows["found"]
    assert any(h["key"] == "both_shift" and (h["lag"], h["shift_pos"], h["shift_num"]) == (17, 2, 2) for h in found)
    assert all(h["replicated"] for h in found) and all(len(h["next"]) == 5 for h in found)


def test_fair_draws_have_no_repeats():
    res = repeats.analyze(_write(_arr(t=3000, seed=9)))
    rows = res["groups"]["all"][0]
    assert not rows["found"] and rows["tests"] == 2999 * (71 + 9 - 1) + 2999 * 8 * 70
    assert all(h["p_adjusted"] > 0.05 for h in rows["hypotheses"]) and rows["detectable_ratio"] < 1.5
    assert "не найдено" in res["verdict"]


def test_planted_same_position_repeat_is_found():
    """Число с 1-й позиции через 40 тиражей часто снова выходит первым (H1)."""
    arr = _arr(t=3000, seed=6)
    rng = np.random.default_rng(2)
    for t in range(40, len(arr)):
        v = arr[t - 40, 0]
        if v not in arr[t] and rng.random() < 0.3:
            arr[t, 0] = v
    rows = repeats.analyze(_write(arr))["groups"]["all"][0]
    same = next(h for h in rows["hypotheses"] if h["key"] == "same")
    assert same["replicated"] and same["lag"] == 40 and same["observed"] > 2 * same["expected"]
