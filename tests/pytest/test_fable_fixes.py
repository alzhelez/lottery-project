"""Исправления ветки improvements/ai-analysis-fixes (01.11.2026): режим Бога снова работает,
специализированные методы подключены и не заглядывают в будущее, детектор нечестности не
поднимает ложных тревог на честной лотерее, без сети загрузка отказывает быстро."""
import time

import numpy as np
import pytest
import requests
from conftest import random_lotto, write_lotto_file

from lottery import models_game_specific as gs
from lottery.drawfile import load_game_data
from lottery.games import draws_path, get_game
from lottery.models import Features, top_k


@pytest.mark.parametrize("model", gs.all_game_models(), ids=lambda m: m.key)
def test_game_models_no_lookahead(model):
    x = random_lotto(400, 45, 6, seed=1)
    base = model.scores(Features(x, 6))
    y = x.copy()
    y[250:] = random_lotto(150, 45, 6, seed=9)
    np.testing.assert_allclose(base[:251], model.scores(Features(y, 6))[:251], rtol=1e-6, atol=1e-6)


def test_mega_hot_prefers_frequent_numbers():
    x = random_lotto(2000, 36, 5, seed=2)
    x[:, 0] = 0
    x[::2, 0] = 1
    picks = top_k(gs.mega_hot(Features(x, 5)), 5)[-200:]
    assert np.mean([0 in p for p in picks]) > 0.5


def test_cluster_picks_inside_zone():
    x = np.zeros((500, 20), np.float32)
    rng = np.random.default_rng(1)
    for t in range(500):
        x[t, rng.choice(10, 8, replace=False) + 10] = 1
    assert set(top_k(gs.cluster(Features(x, 8)), 8)[-1]) <= set(range(10, 20))


def test_hot_cold_takes_both():
    s = gs.hot_cold(Features(random_lotto(3000, 45, 6, seed=3), 6))[-1]
    assert (s == 2).sum() == 4 and (s == 1).sum() == 2


def test_anomaly_uses_real_draw_size():
    s = gs.anomaly(Features(random_lotto(5000, 20, 4, seed=4), 4))[-1]
    assert (s > 0).sum() <= 3


def test_bonus_field_does_not_crash():
    x = random_lotto(300, 4, 1, seed=6)
    for m in gs.game_models("rapido2") + gs.game_models("5x36plus"):
        assert m.scores(Features(x, 1)).shape == (301, 4)


def test_wired_into_evaluation(data_dir):
    from lottery.evaluate import evaluate_game
    write_lotto_file(draws_path("6x45"), [random_lotto(600, 45, 6, seed=5)])
    keys = {m["key"] for m in evaluate_game(load_game_data(get_game("6x45")))["models"]}
    assert {"fb_hot_cold", "fb_avoid_recent", "fb_anomaly", "fb_conservative"} <= keys


def test_godmode_runs_and_survives_memory_pressure(monkeypatch, data_dir):
    """В ветке режим Бога падал на data.slug; при нехватке памяти — бросал MemoryError и
    ставил жёсткий лимит адресного пространства на весь процесс."""
    import resource
    import lottery.godmode as gm
    write_lotto_file(draws_path("5x36"), [random_lotto(500, 36, 5, seed=7)])
    before = resource.getrlimit(resource.RLIMIT_AS) if hasattr(resource, "RLIMIT_AS") else None
    monkeypatch.setattr(gm, "MIN_BUDGET_S", 3)
    monkeypatch.setenv("LOTTERY_GODMODE_MAX_GB", "0.0001")
    monkeypatch.setattr(gm.MemoryMonitor, "current_usage_gb", lambda self: 9.9)
    monkeypatch.setattr(gm.time, "time", _fast_clock())
    res = gm.run_godmode(load_game_data(get_game("5x36")), 5)
    assert res["status"] == "ok"
    if before is not None:
        assert resource.getrlimit(resource.RLIMIT_AS) == before


def _fast_clock():
    """Часы, которые идут в 60 раз быстрее: проверка памяти (раз в минуту) успевает сработать."""
    real = time.time
    start = real()
    return lambda: start + (real() - start) * 60


def test_fraud_detector_quiet_on_fair_lotteries():
    from lottery.fraud_detection import FraudDetector
    alarms = sum(FraudDetector(0.01).run_all_tests(random_lotto(2000, 20, 4, seed=s))["verdict"]["status"]
                 == "suspicious" for s in range(30))
    assert alarms <= 3                       # было 30 из 30
    x = random_lotto(3000, 45, 6, seed=1)
    x[:, 0] = 0
    x[::3, 0] = 1                            # число выпадает строго каждый третий тираж
    assert FraudDetector(0.01).run_all_tests(x)["verdict"]["status"] == "suspicious"


def test_no_network_fails_within_seconds(monkeypatch):
    from lottery import stoloto
    calls = []

    def down(*a, **k):
        calls.append(1)
        raise requests.ConnectionError("нет сети")
    monkeypatch.setattr(stoloto.requests, "get", down)
    monkeypatch.setattr(stoloto.time, "sleep", lambda s: None)
    import tenacity
    monkeypatch.setattr(tenacity.nap, "sleep", lambda s: None)
    t = time.time()
    with pytest.raises(stoloto.ApiUnavailable):
        stoloto._get("https://example.invalid/x", {})
    assert time.time() - t < 5 and len(calls) <= 3
