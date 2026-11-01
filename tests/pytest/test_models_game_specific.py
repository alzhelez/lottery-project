"""Методы под конкретные игры (идеи ветки Fable): без утечки будущего, веса по замыслу,
подключены к сравнению методов и режиму Бога."""
import numpy as np
import pytest
from conftest import random_lotto, write_lotto_file

from lottery import models_game_specific as gs
from lottery.models import Features, top_k


def _all():
    seen, out = set(), []
    for slug in list(gs.GAME_METHODS) + [None]:
        for m in gs.game_models(slug):
            if m.key not in seen:
                seen.add(m.key)
                out.append(m)
    return out


@pytest.mark.parametrize("model", _all(), ids=lambda m: m.key)
def test_no_lookahead(model):
    x = random_lotto(400, 45, 6, seed=1)
    base = model.scores(Features(x, 6))
    y = x.copy()
    y[250:] = random_lotto(150, 45, 6, seed=9)
    np.testing.assert_allclose(base[:251], model.scores(Features(y, 6))[:251], rtol=1e-6, atol=1e-6)


def test_keys_are_unique_across_games():
    keys = [m.key for slug in gs.GAME_METHODS for m in gs.game_models(slug) if m.key not in ("gs_anomaly", "gs_freq_fixed")]
    assert len(keys) == len(set(keys))


def test_hot_group_prefers_frequent_numbers():
    """В ветке «мега-горячим» доставался меньший вес, чем остальным, — исправлено."""
    x = random_lotto(2000, 36, 5, seed=2)
    x[:, 0] = 0
    x[::2, 0] = 1                                 # число 1 выпадает в каждом втором тираже
    f = Features(x, 5)
    picks = top_k(gs.hot_group(f, 0.2), 5)[-200:]
    assert np.mean([0 in p for p in picks]) > 0.5


def test_hot_zone_picks_inside_zone():
    x = np.zeros((500, 20), np.float32)
    rng = np.random.default_rng(1)
    for t in range(500):
        x[t, rng.choice(10, 8, replace=False) + 10] = 1      # выпадают только 11–20
    s = gs.hot_zone(Features(x, 8))
    assert set(top_k(s, 8)[-1]) <= set(range(10, 20))


def test_hot_cold_mix_shares():
    x = random_lotto(3000, 45, 6, seed=3)
    f = Features(x, 6)
    s = gs.hot_cold_mix(f)[-1]
    assert (s == 2).sum() == 4 and (s == 1).sum() == 2


def test_anomaly_uses_real_draw_size():
    """В ветке ожидание считалось как «6 чисел» для любой игры: у 4 из 20 «аномальными»
    оказывались почти все числа. У честной игры теперь аномальных почти нет."""
    x = random_lotto(5000, 20, 4, seed=4)
    s = gs.anomaly(Features(x, 4))[-1]
    assert (s > 0).sum() <= 3


def test_wired_into_evaluation_and_godmode(data_dir):
    from lottery.drawfile import load_game_data
    from lottery.evaluate import evaluate_game
    from lottery.games import draws_path, get_game
    from lottery.godmode import model_by_key
    write_lotto_file(draws_path("6x45"), [random_lotto(600, 45, 6, seed=5)])
    ev = evaluate_game(load_game_data(get_game("6x45")))
    keys = {m["key"] for m in ev["models"]}
    assert {"gs_hot_cold", "gs_avoid_recent", "gs_anomaly", "gs_freq_fixed"} <= keys
    assert model_by_key("gs_hot_zone") is not None and model_by_key("gs_repeat_hot_vin") is not None


def test_bonus_field_is_random_choice():
    x = random_lotto(300, 4, 1, seed=6)
    for m in [m for m in gs.game_models("rapido2") + gs.game_models("5x36plus") if m.key not in ("gs_anomaly", "gs_freq_fixed")]:
        assert not m.scores(Features(x, 1)).any()


def test_godmode_shrinks_pool_when_memory_is_high(monkeypatch):
    """Учёт памяти режима Бога: при превышении порога пул сокращается, расчёт не обрывается."""
    from conftest import random_lotto as rl
    import lottery.godmode as gm
    from lottery.drawfile import load_game_data
    from lottery.games import draws_path, get_game
    write_lotto_file(draws_path("5x36"), [rl(500, 36, 5, seed=7)])
    monkeypatch.setattr(gm, "MEMORY_SOFT_GB", 0.0)
    monkeypatch.setattr(gm, "memory_gb", lambda: 9.9)
    monkeypatch.setattr(gm, "MIN_BUDGET_S", 3)
    seen = []
    res = gm.run_godmode(load_game_data(get_game("5x36")), 0.05, on_progress=seen.append)
    assert res["status"] == "ok" and res["experts"] <= 400
    assert seen and seen[-1]["memory_gb"] == 9.9
