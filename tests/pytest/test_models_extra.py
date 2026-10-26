"""Новые методы (42.2.0): нет утечки будущего, ловят свои закономерности, ансамбль смотрит
только в прошлое; кэш признаков ограничен."""
import numpy as np
import pytest
from conftest import random_lotto

from lottery import models_extra as mx
from lottery.models import Features, hits, standard_models, top_k


@pytest.mark.parametrize("fn", [mx.gbm_batch, mx.forest_batch, mx.online_mlp], ids=["gbm", "forest", "mlp"])
def test_trained_models_no_lookahead(fn):
    x = random_lotto(2500, 20, 4, seed=1)
    base = fn(Features(x, 4))
    t = 1700
    y = x.copy()
    y[t:] = random_lotto(800, 20, 4, seed=9)
    changed = fn(Features(y, 4))
    np.testing.assert_allclose(base[: t + 1], changed[: t + 1], rtol=1e-5, atol=1e-5)
    assert not np.allclose(base[t + 50:], changed[t + 50:])


def test_positions_use_order_without_lookahead():
    rng = np.random.default_rng(2)
    t_len, n, k = 900, 20, 4
    ordered = np.stack([rng.permutation(n)[:k] for _ in range(t_len)])
    ordered[::2, 0] = 6                      # число 7 часто выходит первым
    for row in ordered[::2]:
        if (row[1:] == 6).any():
            row[1:][row[1:] == 6] = 19 if 19 not in row else 18
    x = np.zeros((t_len, n), np.float32)
    x[np.arange(t_len)[:, None], ordered] = 1
    f = Features(x, k)
    f.ordered = ordered
    s = mx.position_scores(f, 300)
    assert np.argmax(s[-1]) == 6
    g = Features(x.copy(), k)
    o2 = ordered.copy()
    o2[600:] = np.stack([rng.permutation(n)[:k] for _ in range(300)])
    x2 = np.zeros_like(x)
    x2[np.arange(t_len)[:, None], o2] = 1
    g = Features(x2, k)
    g.ordered = o2
    np.testing.assert_allclose(s[:601], mx.position_scores(g, 300)[:601])


def test_structure_finds_decade_bias():
    rng = np.random.default_rng(5)
    t_len, n, k = 3000, 36, 5
    x = np.zeros((t_len, n), np.float32)
    w = np.ones(n)
    w[:10] = 2.0                              # первая десятка выпадает вдвое чаще
    for t in range(t_len):
        x[t, rng.choice(n, k, replace=False, p=w / w.sum())] = 1
    f = Features(x, k)
    h = hits(x, top_k(mx.structure_scores(f, 100), k))[500:]
    fair = hits(x, top_k(mx.structure_scores(Features(random_lotto(t_len, n, k, 1), k), 100), k))[500:]
    assert h.mean() > fair.mean() * 1.15


def test_echo_marks_numbers_three_away():
    x = np.zeros((3, 20), np.float32)
    x[1, [4, 10]] = 1                          # числа 5 и 11
    s = mx.echo_scores(Features(x, 2))
    assert set(np.nonzero(s[2])[0] + 1) == {2, 8, 14}   # 5±3 и 11±3; 8 — дважды
    assert s[2, 7] == 2


def test_leaders_ensemble_uses_only_past_hits():
    t_len, n = 50, 10
    good = [np.tile(np.array([0, 1]), (t_len + 1, 1))]   # метод 0 всё время предлагает 1 и 2
    bad = [np.tile(np.array([8, 9]), (t_len + 1, 1))]
    hits_rows = np.zeros((4, t_len))
    hits_rows[0, 25:] = 2                     # метод 0 начинает угадывать с 25-го тиража
    hits_rows[1:, :25] = 1
    picks = [good, bad, bad, bad]
    ens = mx.leaders_ensemble(picks, hits_rows, [n], [2], top=1)[0]
    assert set(ens[10]) == {8, 9}             # до 25-го лидер — «плохие»
    assert set(ens[49]) == {0, 1}             # потом лидер — метод 0
    early = mx.leaders_ensemble(picks, hits_rows[:, :30], [n], [2], top=1)[0]
    np.testing.assert_array_equal(early[:26], ens[:26])


def test_standard_models_include_new_families():
    keys = {m.key for m in standard_models()}
    assert {"structure_100", "center_50", "positions_300", "mlp", "gbm", "forest", "experiment_echo3"} <= keys


def test_features_trim_keeps_stack():
    f = Features(random_lotto(3000, 20, 4, 1), 4)
    f.feature_stack()
    for w in (10, 20, 30, 40, 50):
        f.window(w)
    f.trim(0)
    assert ("stack", False) in f._cache and not any(k[0] == "win" for k in f._cache if isinstance(k, tuple))
