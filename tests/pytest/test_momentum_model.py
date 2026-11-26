import numpy as np

from lottery.models import Features, standard_models


def test_momentum_model_present_and_reproducible():
    x = np.zeros((80, 20), dtype=np.float32)
    x[np.arange(80), np.arange(80) % 20] = 1.0

    model = next(m for m in standard_models() if m.key == "momentum_20_100")
    features = Features(x, 1)

    first = model.scores(features)
    second = model.scores(features)

    assert first.shape == (81, 20)
    assert np.isfinite(first).all()
    assert np.array_equal(first, second)