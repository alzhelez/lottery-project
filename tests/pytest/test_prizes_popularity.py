"""Выплаты из архива: разбор ответа API, оценка в рублях, журнал, модель популярности."""
from datetime import datetime, timedelta

import numpy as np
import pytest
from conftest import random_lotto, write_lotto_file

from lottery import prizes
from lottery.drawfile import load_game_data
from lottery.games import draws_path, get_game


@pytest.mark.parametrize("raw,source,labels", [
    ({"number": 5, "winCategories": [{"combination": "4+4", "participants": 0, "amount": 10_000_000},
                                     {"combination": "2+2", "participants": 9123, "amount": 150}]},
     "winCategories", ["4+4", "2+2"]),
    ({"number": 5, "prizes": {"categories": [{"name": "Угадано 5", "winners": 1, "prize": "3 000 000"},
                                             {"name": "Угадано 2", "winners": 51000, "prize": 80}]}},
     "categories", ["Угадано 5", "Угадано 2"]),
    ({"number": 5, "results": [{"matches": [3, 1], "winnersCount": 12, "winAmount": {"amount": 500}},
                               {"matches": [2, 0], "winnersCount": 900, "winAmount": {"amount": 100}}]},
     "results", ["3+1", "2+0"]),
])
def test_extract_prize_shapes(raw, source, labels):
    rec = prizes.extract(raw)
    assert rec["source"] == source and [c["label"] for c in rec["categories"]] == labels
    assert all(c["winners"] is not None for c in rec["categories"])


def test_extract_ignores_draws_without_prizes():
    assert prizes.extract({"number": 1, "combination": {"structured": [1, 2, 3]}, "date": "x"}) is None
    assert prizes.extract({"number": 1, "tags": ["a", "b"]}) is None


@pytest.mark.parametrize("label,blocks,counts,key", [
    ("4+3", 2, [4, 4], "4+3"), ("4 и 0", 2, [4, 4], "4+0"), ("Угадано 5 чисел", 1, [5], "5"),
    ("5 из 36", 1, [5], "5"), ("#3", 1, [5], None), ("9+9", 2, [4, 4], None), ("Суперприз", 1, [6], None),
])
def test_category_key(label, blocks, counts, key):
    assert prizes.category_key(label, blocks, counts) == key


def write_prize_history(slug, data, prize_of, winners_of=None, price=None):
    """Таблица выплат для каждого тиража: prize_of(key) — выплата, winners_of(t, draw) — победители."""
    import itertools
    counts = [s.count for s in data.fmt.blocks]
    keys = ["+".join(map(str, h)) for h in itertools.product(*[range(c + 1) for c in counts])]
    recs = {}
    for t, d in enumerate(data.draws):
        cats = [{"label": k, "winners": winners_of(t, d) if winners_of else 10, "prize": prize_of(k)}
                for k in keys if prize_of(k)]
        recs[d.no] = {"no": d.no, "source": "test", "categories": cats, **({"price": price} if price else {})}
    prizes.save(slug, recs)


def test_money_evaluation_and_archive_prizes(data_dir):
    write_lotto_file(draws_path("5x36"), [random_lotto(600, 36, 5, 3)])
    data = load_game_data(get_game("5x36"))
    table = {"5": 1_000_000, "4": 5000, "3": 500, "2": 80}
    write_prize_history("5x36", data, lambda k: table.get(k), price=80)
    from lottery.evaluate import evaluate_game
    from lottery.odds import odds_table
    res = evaluate_game(data)
    assert res["money"]["available"] and res["money"]["price"] == 80
    rnd = next(m for m in res["models"] if m["control"])
    hold = rnd["money"]["holdout"]
    assert hold["n"] > 100 and hold["spent"] == 80 * hold["n"]
    assert 0 < hold["random_return"] < 1
    # калькулятор берёт призы из архива, если вы их не вводили
    t = odds_table(data)
    row = next(p for p in t["patterns"] if p["key"] == "3")
    assert row["prize"] == 500 and row["prize_source"] == "archive" and t["price"] == 80
    assert abs(t["return_per_ruble"] - hold["random_return"]) < 1e-9


def test_journal_records_real_payout(data_dir):
    from lottery import journal
    from lottery.drawfile import Draw, write_draws
    start = datetime(2026, 1, 1, 10)
    draws = [Draw(i + 1, (start + timedelta(hours=i)).strftime("%d.%m.%Y %H:%M"),
                  (tuple(sorted({(i * 7 + j * 11) % 36 + 1 for j in range(5)})),)) for i in range(200)]
    draws = [d for d in draws if len(d.blocks[0]) == 5]
    write_draws(draws_path("5x36"), draws[:-1])
    data = load_game_data(get_game("5x36"))
    actual = list(draws[-1].blocks[0])
    journal.record(data, "analysis_best", [actual[:3] + [v for v in range(1, 37) if v not in actual][:2]],
                   now=start - timedelta(days=1))
    write_draws(draws_path("5x36"), draws)
    write_prize_history("5x36", load_game_data(get_game("5x36")), lambda k: {"3": 500, "2": 80}.get(k))
    journal.reconcile(get_game("5x36"))
    e = journal.load("5x36")["entries"][0]
    assert e["hits"] == 3 and e["won"] == 500
    assert journal.view("5x36")["summary"][0]["won"] == 500


def _popular_world(data, gamma, seed=0):
    rng = np.random.default_rng(seed)
    x = data.matrices[0]
    sales = np.exp(np.linspace(0, 1, data.T))          # продажи растут — модель должна это убрать
    lam = 400 * sales * np.exp(x @ gamma)
    return rng.poisson(lam)


def test_popularity_recovers_birthday_bias(data_dir):
    write_lotto_file(draws_path("6x45"), [random_lotto(500, 45, 6, 5)])
    data = load_game_data(get_game("6x45"))
    gamma = np.where(np.arange(1, 46) <= 31, 0.12, -0.2)        # «даты» популярнее
    winners = _popular_world(data, gamma)
    write_prize_history("6x45", data, lambda k: {"3": 300, "2": 50}.get(k),
                        winners_of=lambda t, d: int(winners[t]))
    from lottery.popularity import fit
    model = fit(data)
    assert model["available"] and model["significant"]
    beta = {n["number"]: n["beta"] for n in model["numbers"]}
    assert np.mean([beta[v] for v in range(1, 32)]) > np.mean([beta[v] for v in range(32, 46)])
    assert all(v <= 31 for v in model["popular"][:5])


def test_popularity_not_found_when_absent(data_dir):
    write_lotto_file(draws_path("6x45"), [random_lotto(500, 45, 6, 6)])
    data = load_game_data(get_game("6x45"))
    winners = _popular_world(data, np.zeros(45), seed=2)
    write_prize_history("6x45", data, lambda k: {"3": 300}.get(k), winners_of=lambda t, d: int(winners[t]))
    from lottery.popularity import fit
    assert not fit(data)["significant"]


def test_generator_uses_popularity_model(data_dir):
    import json
    from lottery.games import results_dir
    from lottery.tickets import generate
    write_lotto_file(draws_path("6x45"), [random_lotto(300, 45, 6, 7)])
    data = load_game_data(get_game("6x45"))
    numbers = [{"block": "Числа", "number": v, "beta": 1.0 if v <= 20 else -1.0} for v in range(1, 46)]
    folder = results_dir("6x45")
    folder.mkdir(parents=True)
    (folder / "popularity.json").write_text(json.dumps({"available": True, "significant": True, "numbers": numbers}))
    res = generate(data, count=10, seed=3)
    low = [sum(v <= 20 for v in t["blocks"][0]) for t in res["tickets"]]
    assert np.mean(low) < 6 * 20 / 45            # «популярные» числа встречаются реже обычного
    assert "наименее популярных" in res["tickets"][0]["notes"][-1]
