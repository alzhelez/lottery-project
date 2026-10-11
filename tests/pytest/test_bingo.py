"""Бинго-игры: переменное количество чисел в тираже (Русское лото, Жилищная лотерея и т. п.)."""
import numpy as np
from conftest import ROOT  # noqa: F401  (путь к движку)

from lottery import stoloto
from lottery.drawfile import Draw, block_values, infer_format, load_game_data, write_draws
from lottery.evaluate import baseline, baseline_pmf, evaluate_game
from lottery.games import draws_path, get_game
from lottery.stats import freq_uniformity, serial_overlap


def bingo_draws(t: int, n: int = 90, seed: int = 0, ordered: bool = True, sticky: np.ndarray | None = None):
    """Тиражи «выпавшие шары по порядку»: случайная перестановка, обрезанная на 70–86 шарах.
    sticky — числа, которые выпадают реже (для проверки, что закономерность находится)."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(t):
        w = np.ones(n)
        if sticky is not None:
            w[sticky] = 0.25
        perm = rng.choice(n, size=n, replace=False, p=w / w.sum()) + 1
        seq = perm[: rng.integers(70, 87)]
        if not ordered:
            seq = np.sort(seq)
        day, h = divmod(i, 3)
        out.append(Draw(no=i + 1, date=f"{1 + day % 28:02d}.{1 + (day // 28) % 12:02d}.{2010 + day // 336} {10 + h}:00",
                        blocks=(tuple(int(v) for v in seq),)))
    return out


def not_played_draws(t: int, seed: int = 0):
    """Русское лото в формате API: только невыпавшие числа (несортированные)."""
    rng = np.random.default_rng(seed)
    out = []
    for d in bingo_draws(t, seed=seed):
        drawn = set(d.blocks[0])
        miss = [v for v in range(1, 91) if v not in drawn]
        rng.shuffle(miss)
        out.append(Draw(d.no, d.date, (tuple(miss),)))
    return out


def test_ordered_bingo_format():
    fmt = infer_format(bingo_draws(300))
    assert fmt.supported and fmt.bingo
    modes = [(b.mode, b.lo, b.hi) for b in fmt.blocks]
    assert modes == [("first", 1, 90), ("missing", 1, 90)]
    assert fmt.blocks[0].count == 10
    assert 4 <= fmt.blocks[1].count <= 20 and 4 < fmt.blocks[1].avg < 20


def test_sorted_bingo_has_no_first_balls():
    fmt = infer_format(bingo_draws(300, ordered=False))
    assert [b.mode for b in fmt.blocks] == ["missing"]


def test_not_played_registry_game():
    fmt = infer_format(not_played_draws(300), get_game("ruslotto"))
    assert fmt.supported
    assert [(b.name, b.mode, b.lo, b.hi) for b in fmt.blocks] == [("Невыпавшие числа", "drawn", 1, 90)]


def test_block_values():
    fmt = infer_format(bingo_draws(300))
    d = Draw(1, "01.01.2020 10:00", (tuple(range(90, 10, -1)),))
    assert block_values(d, fmt.blocks[0]) == tuple(range(90, 80, -1))
    assert block_values(d, fmt.blocks[1]) == tuple(range(1, 11))
    assert fmt.matches(d)
    assert not fmt.matches(Draw(2, "01.01.2020 10:00", ((5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14),)))


def test_api_played_and_not_played_keeps_played():
    played = list(range(90, 10, -1))
    raw = {"combination": {"structured": {"played": played, "notPlayed": list(range(1, 11))}}}
    assert stoloto.extract_blocks(raw, get_game("bingo75")) == [played]
    raw = {"combination": {"structured": {"notPlayed": [59, 74, 81]}}}
    assert stoloto.extract_blocks(raw, get_game("ruslotto")) == [[59, 74, 81]]


def test_variable_tests_are_calibrated():
    rejections = {"freq": 0, "overlap": 0}
    runs = 150
    for s in range(runs):
        draws = bingo_draws(150, seed=500 + s, ordered=False)
        spec = infer_format(draws).blocks[0]
        x = np.zeros((len(draws), spec.size), np.float32)
        for t, d in enumerate(draws):
            for v in block_values(d, spec):
                x[t, v - 1] = 1
        rejections["freq"] += freq_uniformity(x)["p_value"] < 0.05
        rejections["overlap"] += serial_overlap(x)["p_value"] < 0.05
    for name, r in rejections.items():
        assert r / runs < 0.11, f"{name}: ложных срабатываний {r}/{runs}"


def _bingo_game(draws, slug="bingotest"):
    write_draws(draws_path(slug), draws)
    return load_game_data(get_game(slug))


def test_baseline_matches_simulation(data_dir):
    data = _bingo_game(bingo_draws(400, seed=3))
    mean, var = baseline(data)
    rng = np.random.default_rng(1)
    sim = []
    for x, spec in zip(data.matrices, data.fmt.blocks):
        picks = np.argsort(rng.random((len(x), spec.size)), axis=1)[:, : spec.count]
        sim.append(np.take_along_axis(x, picks, axis=1).sum(axis=1))
    total = np.sum(sim, axis=0)
    assert abs(total.mean() - mean.mean()) < 3 * np.sqrt(var.mean() / len(total))
    pmf = baseline_pmf(data)
    assert abs(pmf.sum() - 1) < 1e-9 and abs((pmf * np.arange(len(pmf))).sum() - mean.mean()) < 1e-6


def test_fair_bingo_evaluation(data_dir):
    res = evaluate_game(_bingo_game(bingo_draws(900, seed=4)))
    assert res["status"] == "ok"
    assert res["significant_after_correction"] == []
    first, missing = res["next_prediction"]["numbers"]
    assert len(first) == 10 and len(set(first)) == 10


def test_biased_bingo_is_detected(data_dir):
    sticky = np.arange(0, 90, 9)  # каждое девятое число выпадает реже — чаще остаётся невыпавшим
    res = evaluate_game(_bingo_game(bingo_draws(900, seed=5, sticky=sticky)))
    best = next(m for m in res["models"] if m["key"] == res["best_key"])
    assert best["holdout"]["p_better"] < 1e-4
