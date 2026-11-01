"""Режим Бога считает в одном потоке: автозапуск считает две игры параллельно, и потоки бустинга
и numpy двух процессов, деля ядра, замедляли расчёт в 3–4 раза."""
import numpy as np  # noqa: F401 — загружает OpenBLAS, чтобы было что ограничивать
from threadpoolctl import threadpool_info

import lottery.godmode as gm


def _threads(*_a, **_k):
    return [(lib["internal_api"], lib["num_threads"]) for lib in threadpool_info()]


def test_godmode_runs_single_threaded(monkeypatch):
    monkeypatch.setattr(gm, "_run_godmode", _threads)
    monkeypatch.delenv(gm.GODMODE_THREADS_ENV, raising=False)
    inside = gm.run_godmode(None, 1)
    assert "openmp" in {api for api, _ in inside}          # бустинг scikit-learn
    assert {n for _, n in inside} == {1}


def test_thread_limit_can_be_disabled(monkeypatch):
    monkeypatch.setattr(gm, "_run_godmode", _threads)
    monkeypatch.setenv(gm.GODMODE_THREADS_ENV, "0")
    assert gm.run_godmode(None, 1) == _threads()


def test_wrapper_keeps_docstring():
    assert "Режим Бога" in (gm.run_godmode.__doc__ or "")
