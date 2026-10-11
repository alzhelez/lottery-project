import numpy as np
from conftest import random_lotto

from lottery.drawfile import BlockSpec
from lottery.stats import (benjamini_hochberg, freq_uniformity, holm, hypergeom_moments, persistence, serial_overlap,
                           block_tests)


def test_hypergeom_moments_match_simulation():
    n, k = 20, 4
    a = random_lotto(20000, n, k, 1)
    b = random_lotto(20000, n, k, 2)
    ov = (a * b).sum(axis=1)
    mean, var = hypergeom_moments(n, k)
    assert abs(ov.mean() - mean) < 0.02 and abs(ov.var() - var) < 0.03


def test_type_one_error_is_controlled():
    """При честной лотерее тесты срабатывают примерно в 5% случаев, а не чаще."""
    rng = np.random.default_rng(0)
    rejections = {"freq": 0, "overlap1": 0, "persist": 0}
    runs = 200
    for s in range(runs):
        x = random_lotto(300, 20, 4, seed=1000 + s)
        rejections["freq"] += freq_uniformity(x)["p_value"] < 0.05
        rejections["overlap1"] += serial_overlap(x)["p_value"] < 0.05
        rejections["persist"] += persistence(x, rng, n_perm=300)["p_value"] < 0.05
    for name, r in rejections.items():
        assert r / runs < 0.10, f"{name}: ложных срабатываний {r}/{runs}"


def test_old_uncorrected_chi2_was_wrong_scale():
    """Без поправки (N−1)/(N−k) статистика смещена: её среднее N−k вместо N−1."""
    n, k = 20, 4
    vals = []
    for s in range(300):
        x = random_lotto(400, n, k, seed=s)
        c = x.sum(0)
        e = 400 * k / n
        vals.append(((c - e) ** 2 / e).sum())
    assert abs(np.mean(vals) - (n - k)) < 1.0


def test_detects_biased_frequencies():
    rng = np.random.default_rng(1)
    x = np.zeros((3000, 20), np.float32)
    p = np.ones(20)
    p[:3] = 2.0
    p /= p.sum()
    for t in range(3000):
        x[t, rng.choice(20, 4, replace=False, p=p)] = 1
    assert freq_uniformity(x)["p_value"] < 1e-6
    assert persistence(x, rng)["p_value"] < 0.01


def test_detects_repeats():
    x = random_lotto(1000, 20, 4, seed=4)
    x[1::2] = x[0::2][: len(x[1::2])]      # каждый второй тираж повторяет предыдущий
    assert serial_overlap(x)["p_value"] < 1e-6


def test_block_tests_fields():
    x = random_lotto(200, 10, 3, seed=1)
    res = block_tests(x, BlockSpec("Числа", 0, None, 3, 1, 10), np.random.default_rng(0))
    assert {r["test"] for r in res} == {"freq", "overlap1", "overlap2", "persist", "sumac", "pairs"}
    assert all(0 <= r["p_value"] <= 1 for r in res)


def test_holm_and_bh():
    p = [0.01, 0.04, 0.03, 0.5]
    assert np.allclose(holm(p), [0.04, 0.09, 0.09, 0.5])
    assert np.allclose(benjamini_hochberg(p), [0.04, 0.0533333, 0.0533333, 0.5])
