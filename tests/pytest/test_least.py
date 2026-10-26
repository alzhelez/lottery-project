"""Наименее вероятные числа: анти-методы находят числа, которые выпадают реже, и не находят их
у честных тиражей; журнал засчитывает их в обратную сторону; всеобъемлющий режим Бога."""
import json
import subprocess
import sys

import numpy as np
from conftest import random_lotto, write_lotto_file

from lottery import journal, least, notify
from lottery.drawfile import load_game_data
from lottery.evaluate import evaluate_game
from lottery.games import draws_path, get_game, results_dir


def biased(t: int, seed: int = 4) -> np.ndarray:
    """«4 из 20», где числа 1–3 выпадают втрое реже остальных."""
    rng = np.random.default_rng(seed)
    w = np.ones(20)
    w[:3] = 1 / 3
    x = np.zeros((t, 20), np.float32)
    for i in range(t):
        x[i, rng.choice(20, 4, replace=False, p=w / w.sum())] = 1
    return x


def test_least_finds_rarely_drawn_numbers():
    write_lotto_file(draws_path("4x20"), [biased(3000), biased(3000, seed=5)])
    res = evaluate_game(load_game_data(get_game("4x20")))["least"]
    assert res["status"] == "ok"
    best = next(m for m in res["methods"] if m["key"] == res["best_key"])
    assert best["holdout"]["p_lower"] < 0.01 and best["holdout"]["deficit_pct"] > 10
    assert res["significant_after_correction"]
    # редкие числа 1–3 попадают в наименее вероятные
    assert {1, 2, 3} & set(res["next_consensus"][0])
    assert "реже" in res["conclusion"]


def test_least_on_fair_draws_finds_nothing():
    write_lotto_file(draws_path("4x20"), [random_lotto(2500, 20, 4, 1), random_lotto(2500, 20, 4, 2)])
    res = evaluate_game(load_game_data(get_game("4x20")))["least"]
    assert not res["significant_after_correction"]
    rand = next(m for m in res["methods"] if m["control"])
    assert abs(rand["holdout"]["mean_hits"] - res["baseline"]["mean"]) < 0.1
    assert all(len(b) == 4 for b in res["next_prediction"]["numbers"])
    assert "нельзя" in res["conclusion"]


def test_bottom_k_takes_lowest_scores():
    s = np.array([[5.0, 1.0, 3.0, 0.5, 9.0]])
    assert sorted(least.bottom_k(s, 2)[0].tolist()) == [1, 3]


def _entry(hits, source="least", expected=1.6, variance=1.0):
    return {"source": source, "status": "checked", "hits": hits, "expected": expected, "variance": variance,
            "draw_no": 1, "numbers": [[1, 2, 3, 4], [5, 6, 7, 8]], "actual": [[9, 10, 11, 12], [1, 2, 3, 4]],
            "hits_by_block": [hits, 0], "won": None}


def test_journal_counts_least_in_reverse():
    few = [_entry(0) for _ in range(40)]
    row = next(r for r in journal.summary(few) if r["source"] == "least")
    assert row["goal"] == "fewer" and row["p_better"] < 1e-6
    assert journal.sequential_p(few, lower=True) < 0.05 and journal.sequential_p(few) == 1.0
    many = [_entry(4) for _ in range(40)]
    assert next(r for r in journal.summary(many) if r["source"] == "least")["p_better"] > 0.99


def test_proven_source_ignores_least(data_dir):
    (data_dir / "journal").mkdir()
    entries = [{**_entry(0), "draw_no": i} for i in range(60)]
    (data_dir / "journal" / "4x20.json").write_text(json.dumps({"entries": entries}), encoding="utf-8")
    assert journal.proven_source("4x20") is None


def test_telegram_least_line_not_in_totals():
    e = {**_entry(1), "source_title": "Наименее вероятные"}
    best = {**_entry(3, source="analysis_best"), "source_title": "Лучший метод анализа", "won": 50.0}
    msg = notify.journal_digest([("4 из 20", [best, e])])
    assert "Н: выпало 1 из 8 (меньше — лучше)" in msg
    assert "1 шт., угадано 3" in msg
    auto = notify.auto_message({"games": {}}, {"4x20": {"title": "4 из 20", "next_no": 5, "numbers": [[1, 2, 3, 4]],
                                                        "least": [[7, 8, 9, 10]]}})
    assert "Н (не брать): <code>7 8 9 10</code>" in auto and "Н — наименее вероятные" in auto and "Э — эксперимент" in auto


def test_analysis_records_least_sorted(data_dir, monkeypatch):
    import lp
    from test_export_auto import fresh_draws
    from lottery.drawfile import write_draws
    write_draws(draws_path("5x36"), fresh_draws(400))
    payload = lp.analyze_game("5x36")
    assert payload["evaluation"]["least"]["status"] == "ok"
    entry = next(e for e in journal.load("5x36")["entries"] if e["source"] == "least")
    assert entry["numbers"] == [sorted(b) for b in entry["numbers"]] and not entry.get("ordered")
    assert entry["source_title"] == "Наименее вероятные"


# ── всеобъемлющий режим Бога ─────────────────────────────────────────────────

def _fast_godmode(monkeypatch):
    import lottery.godmode as gm
    monkeypatch.setattr(gm, "MIN_BUDGET_S", 2)
    real = gm.run_godmode
    monkeypatch.setattr(gm, "run_godmode", lambda data, budget, **kw: real(data, 0.05, **kw))


def _run(*argv):
    import lp
    old = sys.argv
    sys.argv = ["lp.py", *argv]
    try:
        lp.main()
    finally:
        sys.argv = old


def test_godmode_all_runs_every_game_from_draw_1000(data_dir, monkeypatch):
    _fast_godmode(monkeypatch)
    write_lotto_file(draws_path("5x36"), [random_lotto(1300, 36, 5, seed=1)])
    write_lotto_file(draws_path("6x45"), [random_lotto(900, 45, 6, seed=1)])
    _run("godmode-all")
    st = json.loads((results_dir() / "godmode_all.json").read_text(encoding="utf-8"))
    assert st["status"] == "done" and st["order"] == ["5x36"] and "1060" in st["skipped"]["6x45"]
    g = st["games"]["5x36"]
    assert g["status"] == "done" and g["from_no"] == 1000 and g["to_no"] == 1300 and g["baseline"] > 0
    gm = json.loads((results_dir("5x36") / "godmode.json").read_text(encoding="utf-8"))
    assert gm["evaluation"]["from"] == 1000 and gm["comprehensive"]["from"] == 1000
    assert not (data_dir / "godmode_all.lock").exists() and not (results_dir("5x36") / "godmode.lock").exists()


def test_godmode_all_resume_skips_finished_games(data_dir, monkeypatch):
    _fast_godmode(monkeypatch)
    write_lotto_file(draws_path("5x36"), [random_lotto(1200, 36, 5, seed=1)])
    write_lotto_file(draws_path("4x20"), [random_lotto(1250, 20, 4, seed=2), random_lotto(1250, 20, 4, seed=3)])
    _run("godmode-all")
    path = results_dir() / "godmode_all.json"
    st = json.loads(path.read_text(encoding="utf-8"))
    assert st["order"] == ["5x36", "4x20"]
    # проход «остановлен» на второй игре — продолжение не трогает первую
    st["status"] = "stopped"
    st["games"]["4x20"] = {**st["games"]["4x20"], "status": "running"}
    first_done = st["games"]["5x36"]["finished_at"]
    path.write_text(json.dumps(st), encoding="utf-8")
    _run("godmode-all", "--resume")
    st2 = json.loads(path.read_text(encoding="utf-8"))
    assert st2["status"] == "done" and st2["games"]["5x36"]["finished_at"] == first_done
    assert st2["games"]["4x20"]["status"] == "done" and st2["started_at"] == st["started_at"]


def test_manual_godmode_refuses_while_game_is_busy(data_dir):
    from test_cli import run
    write_lotto_file(draws_path("5x36"), [random_lotto(400, 36, 5, seed=1)])
    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        folder = results_dir("5x36")
        folder.mkdir(parents=True)
        (folder / "godmode.lock").write_text(json.dumps({"pid": sleeper.pid, "comprehensive": True}), encoding="utf-8")
        rc, ev = run(["godmode", "--game", "5x36", "--budget", "1"], data_dir)
        assert rc == 2 and "всеобъемлющий режим Бога" in ev[-1]["message"]
        (data_dir / "godmode_all.lock").write_text(json.dumps({"pid": sleeper.pid}), encoding="utf-8")
        rc, ev = run(["godmode-all"], data_dir)
        assert rc == 2 and "уже идёт" in ev[-1]["message"]
    finally:
        sleeper.kill()


def test_expert_limit_shrinks_for_long_history():
    from lottery.godmode import MAX_EXPERTS, expert_limit
    write_lotto_file(draws_path("5x36"), [random_lotto(2000, 36, 5, seed=1)])
    data = load_game_data(get_game("5x36"))
    assert expert_limit(data, 200) == MAX_EXPERTS
    class Big:  # 300 тыс. тиражей «8 из 20 + 1 из 4»
        T = 300_000
        class fmt:
            blocks = [type("B", (), {"count": 8})(), type("B", (), {"count": 1})()]
    assert 120 <= expert_limit(Big, 999) < MAX_EXPERTS
