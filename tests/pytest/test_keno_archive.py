"""Кено 2.0 (10 чисел из 20 выпавших), шансы по архиву (бинго, Топ-3) и исключённые игры.
Выплаты — из ответов настоящего API (fixtures/api_real_draws.json), размноженных по тиражам."""
import json
from pathlib import Path

import numpy as np
from conftest import random_lotto, write_lotto_file
from scipy import stats as sps

from lottery import prizes, stoloto
from lottery.drawfile import load_game_data
from lottery.games import draws_path, get_game, local_slugs
from lottery.odds import odds_table

REAL = json.loads((Path(__file__).parent / "fixtures" / "api_real_draws.json").read_text(encoding="utf-8"))


def _prize_records(slug: str, nos) -> None:
    recs = {}
    for no in nos:
        rec = prizes.extract({**REAL[slug], "number": no})
        assert rec, slug
        rec["no"] = no
        recs[no] = rec
    prizes.save(slug, recs)


def _keno_file(t: int = 300) -> None:
    rng = np.random.default_rng(5)
    digits = [[int(v) for v in rng.integers(0, 10, 9)] for _ in range(t)]
    x = random_lotto(t, 80, 20, seed=3)
    lines = []
    for i in range(t):
        nums = ", ".join(str(j + 1) for j in np.nonzero(x[i])[0])
        lines.append(f"01.01.2026 {i // 60 % 24:02d}:{i % 60:02d}||{i + 1}||{', '.join(map(str, digits[i]))}||{nums}")
    draws_path("keno2").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_keno_format_predicts_10_of_20():
    _keno_file()
    data = load_game_data(get_game("keno2"))
    assert data.fmt.supported and len(data.fmt.blocks) == 1           # цифры не анализируются
    spec = data.fmt.blocks[0]
    assert (spec.count, spec.drawn, spec.size) == (10, 20, 80)
    assert data.matrices[0].sum(axis=1).max() == 20                    # в тираже — все 20 чисел


def test_keno_odds_exact_and_variants():
    _keno_file()
    _prize_records("keno2", range(1, 301))
    odds = odds_table(load_game_data(get_game("keno2")))
    assert odds["supported"]
    by_key = {r["key"]: r for r in odds["patterns"]}
    # точная вероятность «6 из 10»: C(20,6)·C(60,4)/C(80,10)
    assert abs(by_key["6"]["p"] - sps.hypergeom(80, 20, 10).pmf(6)) < 1e-15
    assert by_key["6"]["prize"] == 750 and by_key["6"]["prize_source"] == "archive"
    assert by_key["8"]["prize"] is None              # «Столбец 8» — другая ставка, не «8 из 10»
    v = {x["pick"]: x for x in odds["variants"]}
    assert set(v) == set(range(1, 11))
    one = {r["hits"]: r for r in v[1]["rows"]}
    assert abs(one[1]["p"] - 0.25) < 1e-12                             # 20 из 80 — каждое число с шансом 1/4
    assert v[10]["return_per_ruble"] is not None and odds["price"] == 100
    assert odds["archive"]["draws"] == 200                             # хвост файла выплат


def test_keno_money_uses_10_number_tickets():
    from lottery import money
    _keno_file()
    _prize_records("keno2", range(1, 301))
    data = load_game_data(get_game("keno2"))
    ctx = money.context(data)
    assert ctx["available"] and ctx["keys"][-1] == "10"
    # ожидание случайного билета: Σ P(k из 10) × выплата
    pmf = sps.hypergeom(80, 20, 10).pmf(np.arange(11))
    exp = sum(pmf[int(k)] * p for k, p in zip(ctx["keys"], ctx["table"][0]) if not np.isnan(p))
    assert abs(ctx["random_ev"][0] - exp) < 1e-9


def test_bingo_and_top3_get_archive_odds():
    rng = np.random.default_rng(2)
    rows = {"gzhl": lambda: sorted(rng.choice(np.arange(1, 91), int(rng.integers(2, 6)), replace=False).tolist()),
            "top-3": lambda: rng.integers(0, 10, 12).tolist()}          # 12 цифр с повторами
    for slug, make in rows.items():
        lines = [f"01.01.2026 10:{i % 60:02d}||{i}||{', '.join(map(str, make()))}" for i in range(1, 61)]
        draws_path(slug).write_text("\n".join(lines) + "\n", encoding="utf-8")
        _prize_records(slug, range(1, 61))
        odds = odds_table(load_game_data(get_game(slug)))
        assert not odds["supported"]
        a = odds["archive"]
        assert a and a["draws"] == 60 and 0 < a["return"] < 5
        raw = REAL[slug]
        bets, price = raw["betsCount"], raw["ticketPrice"]
        cats = (raw.get("winCategories") or [])
        paid = sum((c["participants"] or 0) * (c["amount"] or 0) for c in cats)
        assert abs(a["return"] - paid / (bets * price)) < 1e-9          # каждый тираж одинаковый


def test_top3_subtitles_keep_bet_types_apart():
    labels = [c["label"] for c in prizes.extract(REAL["top-3"])["categories"]]
    assert "Любой порядок 3 (2 одинаковых числа)" in labels and "Любой порядок 3 (3 разных числа)" in labels


def test_excluded_game_is_not_listed_or_loaded(monkeypatch):
    write_lotto_file(draws_path("spec"), [random_lotto(30, 10, 3)])
    write_lotto_file(draws_path("6x45"), [random_lotto(30, 45, 6)])
    assert local_slugs() == ["6x45"]
    assert get_game("spec").excluded
    monkeypatch.setattr(stoloto, "discover_games", lambda log=None: ["spec", "6x45"])
    seen = []
    monkeypatch.setattr(stoloto, "update_game", lambda game, log=None, on_status=None: seen.append(game.slug) or
                        {"status": "done", "draws": 0, "added": 0})
    stoloto.fetch_all(None, lambda e: None)
    assert seen == ["6x45"]
