"""Версия 2 методов (42.13.0): веса моделей по результату на последних тиражах; сравнение с первой."""
import json
from datetime import datetime, timedelta

import numpy as np

from lottery import journal, trust, v2, v2compare
from lottery.drawfile import Draw, load_game_data, write_draws
from lottery.evaluate import Evaluator, evaluate_game
from lottery.games import draws_path, get_game

NOW = datetime(2026, 11, 16, 12, 0)


def _game(mode: str, n: int = 1600, seed: int = 5, tail_seed: int | None = None, cut: int = 0):
    """5 из 36: random — честная; shift — числа 1–9 втрое чаще до 75 % архива, потом 28–36."""
    rng = np.random.default_rng(seed)
    draws = []
    for i in range(n):
        if tail_seed is not None and i == cut:
            rng = np.random.default_rng(tail_seed)
        p = np.ones(36)
        if mode == "shift":
            p[:9], p[27:] = (3, 1) if i < n * 0.75 else (1, 3)
        p /= p.sum()
        draws.append(Draw(i + 1, (NOW - timedelta(minutes=15 * (n - i))).strftime("%d.%m.%Y %H:%M"),
                          (tuple(sorted(int(v) + 1 for v in rng.choice(36, 5, replace=False, p=p))),)))
    write_draws(draws_path("5x36"), draws)
    return load_game_data(get_game("5x36"))


def test_form_uses_only_past_draws():
    h = np.array([[1.0, 1.0, 5.0, 0.0], [0.0, 0.0, 0.0, 0.0]])
    z = v2.form(h, np.full(4, 0.5), np.full(4, 0.25))
    assert z.shape == (2, 5) and (z[:, 0] == 0).all()                    # до первого тиража формы нет
    assert z[0, 1] > 0 > z[1, 1]                                         # после первого — по нему одному
    z2 = v2.form(np.array([[1.0, 1.0, 5.0, 9.0], [0.0, 0.0, 0.0, 9.0]]), np.full(4, 0.5), np.full(4, 0.25))
    assert np.allclose(z[:, :4], z2[:, :4])                              # тираж t на форму «перед t» не влияет
    low = v2.form(h, np.full(4, 0.5), np.full(4, 0.25), lower=True)
    assert np.allclose(low, -z)                                          # у анти-методов лучше тот, у кого выпало меньше


def test_v2_adapts_to_regime_change_without_lookahead(data_dir):
    data = _game("shift")
    res = evaluate_game(data, keep_picks=True)
    picks = res.pop("_picks")
    full, warm = picks["full"], picks["warm"]
    assert set(res["v2"]["sources"]) == {"consensus_v2", "godmode_v2", "least_v2"}
    assert json.dumps(res["v2"])                                         # в отчёт анализа идёт как есть
    ev = Evaluator(data)
    cut = int(1600 * 0.75)

    def excess(source, a, b):
        h = ev.hits(full[source])
        return float(h[a:b].sum() - ev.mean0[a:b].sum())
    # уже через 30 тиражей после перелома лидер последних тиражей ловит новую закономерность
    # (у случайного выбора на 200 тиражах было бы 0 ± 12)
    assert excess("godmode_v2", cut + 30, cut + 230) > 60
    assert excess("consensus_v2", cut, 1600) > 0 and excess("least_v2", cut + 150, 1600) < 0
    # заглядывания нет: другие тиражи после 1000-го не меняют прогнозы v2 на тиражи до 1001-го
    other = evaluate_game(_game("shift", tail_seed=77, cut=1000), keep_picks=True)["_picks"]["full"]
    for source in v2.SOURCES:
        assert all((a[warm:1001] == b[warm:1001]).all() for a, b in zip(full[source], other[source])), source
        assert any((a[1001:] != b[1001:]).any() for a, b in zip(full[source], other[source])), source


def test_final_v2_votes_only_its_own_family():
    blocks = [{"lo": 1, "hi": 10}]
    by = {"analysis_consensus": [[1, 2, 3]], "godmode": [[1, 2, 4]], "least": [[9, 10, 1]],
          "consensus_v2": [[5, 6, 7]], "godmode_v2": [[5, 6, 8]], "least_v2": [[5, 9, 10]], "final": [[1, 2, 3]]}
    w = {s: 1.0 for s in by}
    assert trust.final_numbers(by, blocks, w) == [[2, 3, 4]]                      # Ф — К и Б, штраф Н (число 1)
    assert trust.final_numbers(by, blocks, w, "final_v2") == [[6, 7, 8]]          # Ф2 — К2 и Б2, штраф Н2 (число 5)
    assert trust.final_numbers({"consensus_v2": [[7, 5, 6]]}, blocks, w) is None  # чужие источники в «Ф» не голосуют
    assert trust.final_numbers({"consensus_v2": [[7, 5, 6]]}, blocks, w, "final_v2") == [[5, 6, 7]]
    assert set(trust.weights("x", {})) == set(journal.SOURCES) - {"final", "final_v2"}
    assert journal.LOWER == {"least", "least_v2"} and dict(journal.V2_PAIRS)["godmode"] == "godmode_v2"


def test_journal_gets_v2_and_final_v2(data_dir, monkeypatch):
    import lp
    data = _game("random", n=400)
    monkeypatch.setattr(lp, "game_activity", lambda d: {"active": True})
    monkeypatch.setattr(lp, "FORECAST_HORIZON_MIN", 0.0)
    for source, numbers in (("analysis_consensus", [[1, 2, 3, 4, 5]]), ("consensus_v2", [[11, 12, 13, 14, 15]]),
                            ("godmode_v2", [[11, 12, 13, 14, 16]]), ("least_v2", [[11, 30, 31, 32, 33]])):
        lp.journal_record(data, source, numbers, "", ordered=False)
    by = {e["source"]: e for e in journal.load("5x36")["entries"]}
    assert by["final"]["numbers"] == [[1, 2, 3, 4, 5]]                            # Ф — только К (Б ещё нет)
    assert by["final_v2"]["numbers"] == [[12, 13, 14, 15, 16]]                    # Ф2 — К2 и Б2 без числа Н2
    assert "К2" in by["final_v2"]["detail"] and "К " not in by["final_v2"]["detail"]


def test_v2_compare_is_paired_and_corrected(data_dir):
    _game("random", n=400)
    made = NOW.isoformat()

    def entries(source, hits):
        return [{"id": f"{source}{i}", "source": source, "draw_no": i + 1, "status": "checked", "made_at": made,
                 "draw_date": "01.11.2026 12:00", "numbers": [[1, 2, 3, 4, 5]], "hits": int(h), "expected": 0.7, "variance": 0.5}
                for i, h in enumerate(hits)]
    rng = np.random.default_rng(1)
    base = rng.integers(0, 3, 300)
    journal.save("5x36", {"game": "5x36", "entries":
                          entries("analysis_consensus", base) + entries("consensus_v2", base + (np.arange(300) % 2))   # +0,5 за тираж
                          + entries("godmode", base) + entries("godmode_v2", rng.permutation(base))                    # то же в среднем
                          + entries("least", base + 1 + (np.arange(300) % 2)) + entries("least_v2", base)                                   # выпало меньше — лучше
                          + entries("final", base[:50]) + entries("final_v2", base[:50] + 1)})                         # мало тиражей
    c = v2compare.build(["5x36"], now=NOW)
    by = {p["v1"]: p for p in c["games"][0]["pairs"]}
    assert c["rule"]["tests"] == 3 and c["rule"]["z_crit"] == 2.39 and c["rule"]["min_draws"] == 100
    assert by["analysis_consensus"]["verdict"] == "better" and by["analysis_consensus"]["history"]["diff_per_draw"] == 0.5
    assert by["godmode"]["verdict"] == "same" and by["least"]["verdict"] == "better" and by["final"]["verdict"] == "early"
    assert by["analysis_consensus"]["journal"]["n"] == 300 and c["tally"] == {"better": 2, "worse": 0, "same": 1, "early": 1}
    assert "v2 лучше — 2, хуже — 0, не отличаются — 1, рано судить — 1" in v2compare.summary()
    text = v2compare.summary(slug="5x36")
    assert "К → К2: v2 лучше (300 тиражей" in text and "Б → Б2: не отличаются" in text and "Ф → Ф2: рано судить" in text
