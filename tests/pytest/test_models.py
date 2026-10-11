"""Главное свойство моделей: прогноз на тираж t не зависит от тиражей ≥ t (нет утечки будущего)."""
import numpy as np
import pytest
from conftest import random_lotto

from lottery.models import Features, expert_grid, gbm_scores, hits, online_logreg, random_mixture, standard_models, top_k


def _all_models():
    seen, out = set(), []
    for m in standard_models() + expert_grid(1) + expert_grid(2):
        if m.key not in seen:
            seen.add(m.key)
            out.append(m)
    return out


@pytest.mark.parametrize("model", _all_models(), ids=lambda m: m.key)
def test_no_lookahead(model):
    x = random_lotto(120, 20, 4, seed=1)
    base = model.scores(Features(x, 4))
    assert base.shape == (121, 20)
    t = 70
    x2 = x.copy()
    x2[t:] = random_lotto(50, 20, 4, seed=99)       # меняем «будущее» начиная с тиража t
    changed = model.scores(Features(x2, 4))
    np.testing.assert_allclose(base[: t + 1], changed[: t + 1], rtol=1e-5, atol=1e-5,
                               err_msg=f"{model.key} использует будущие тиражи")


def test_random_mixture_no_lookahead():
    x = random_lotto(100, 20, 4, seed=2)
    names, _ = Features(x, 4).feature_stack()
    m = random_mixture(names, np.random.default_rng(1), 1)
    a = m.scores(Features(x, 4))
    x2 = x.copy()
    x2[60:] = random_lotto(40, 20, 4, seed=5)
    np.testing.assert_allclose(a[:61], m.scores(Features(x2, 4))[:61], atol=1e-5)


@pytest.mark.slow
def test_gbm_no_lookahead():
    x = random_lotto(700, 10, 3, seed=3)
    a = gbm_scores(Features(x, 3), retrain_every=200)
    x2 = x.copy()
    x2[450:] = random_lotto(250, 10, 3, seed=4)
    np.testing.assert_allclose(a[:451], gbm_scores(Features(x2, 3), retrain_every=200)[:451], atol=1e-6)


def test_window_and_gap_values():
    x = np.zeros((5, 3), np.float32)
    x[0, 0] = x[2, 0] = x[3, 1] = 1
    f = Features(x, 1)
    assert f.window(2)[4].tolist() == [1, 1, 0]          # тиражи 2 и 3
    assert f.window(None)[5].tolist() == [2, 1, 0]
    assert f.gap()[5].tolist() == [2, 1, 5]             # последний тираж — индекс 4


def test_top_k_and_hits():
    s = np.array([[0.1, 0.9, 0.5, 0.2]], np.float32)
    p = top_k(s, 2)
    assert sorted(p[0].tolist()) == [1, 2]
    x = np.array([[0, 1, 0, 1]], np.float32)
    assert hits(x, np.vstack([p, p])).tolist() == [1]


def test_top_k_ties_are_unbiased():
    s = np.zeros((4000, 10), np.float32)
    counts = np.bincount(top_k(s, 1, seed=3).ravel(), minlength=10)
    assert counts.min() > 300   # без систематического выбора маленьких номеров


def test_logreg_learns_strong_signal():
    rng = np.random.default_rng(0)
    x = np.zeros((600, 10), np.float32)
    x[0, :2] = 1
    for t in range(1, 600):            # повторяем прошлый тираж с вероятностью 0.8
        x[t] = x[t - 1] if rng.random() < 0.8 else 0
        if x[t].sum() == 0:
            x[t, rng.choice(10, 2, replace=False)] = 1
    s = online_logreg(Features(x, 2), lr=0.2)
    h = hits(x, top_k(s, 2))[300:].mean()
    assert h > 1.3                      # случайный выбор дал бы 0.4
