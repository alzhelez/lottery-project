"""Скорость на больших архивах: кэш проверки на случайность, параллельность, лишние записи."""
import json
import time

from conftest import random_lotto, write_lotto_file

from lottery import stoloto
from lottery.games import draws_path, get_game, results_dir
from lottery.scan import run_scan


def _games(n):
    for i in range(n):
        write_lotto_file(draws_path(f"g{i}"), [random_lotto(800, 36, 5, seed=i)])


def test_scan_uses_cache_and_recomputes_changed_only(data_dir):
    _games(3)
    first = run_scan(parallel=False)
    assert first["recomputed"] == 3 and len(first["games"]) == 3
    t0 = time.time()
    second = run_scan(parallel=False)
    assert second["recomputed"] == 0 and time.time() - t0 < 2
    assert [g["verdict"] for g in second["games"]] == [g["verdict"] for g in first["games"]]
    write_lotto_file(draws_path("g1"), [random_lotto(801, 36, 5, seed=99)])
    assert run_scan(parallel=False)["recomputed"] == 1


def test_parallel_scan_matches_sequential(data_dir):
    _games(3)
    seq = run_scan(parallel=False)
    (results_dir() / "scan.json").unlink()
    par = run_scan(parallel=True)
    strip = lambda g: {k: v for k, v in g.items() if k != "signature"}  # noqa: E731
    assert [strip(g) for g in seq["games"]] == [strip(g) for g in par["games"]]


def test_unchanged_archive_is_not_rewritten(monkeypatch, data_dir):
    writes = []
    monkeypatch.setattr(stoloto, "write_draws", lambda path, draws: writes.append(1))
    raw = [{"number": i, "date": "2026-01-01T10:00:00", "combination": {"structured": [1, 2, 3, 4, 5, 6, 7, 8]}}
           for i in range(1, 51)]
    existing = [stoloto.api_draw_to_draw(r, get_game("4x20")) for r in raw]
    store = stoloto.DrawStore(get_game("4x20"), existing)
    store.add(raw)               # тот же ответ API ещё раз
    store.flush()
    assert writes == [] and store.added == 0
