"""Выплаты из архива: разбор ответа API, оценка в рублях, журнал, модель популярности."""
import json
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pytest
from conftest import random_lotto, write_lotto_file

from lottery import prizes, stoloto
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


def test_extract_real_api_shape():
    """Форма настоящего ответа API (тираж «Дважды два»): winners — одни нули с номерами
    категорий, winningCategories — строка JSON с суммами в копейках, а настоящие категории —
    winCategories с подписями {"ru": "2 + 2"} и суммами в рублях."""
    from lottery import prizes
    raw = {
        "number": 258313, "ticketPrice": 15, "betsCount": 1758,
        "winningCategories": '{"main":[{"winCat":2,"amount":75000,"countWins":1}]}',
        "winners": [{"participants": 0, "amount": 0, "totalAmount": 0, "category": i} for i in range(1, 10)],
        "winCategories": [
            {"number": 1, "participants": 0, "amount": 0, "title": {"ru": "2 + 2", "en": "2 + 2"}},
            {"number": 2, "participants": 1, "amount": 750, "title": {"ru": "1 + 2", "en": "1 + 2"}},
            {"number": 6, "participants": 36, "amount": 30, "title": {"ru": "1 + 1", "en": "1 + 1"}},
            {"number": 7, "participants": 285, "amount": 15, "title": {"ru": "1 + 0", "en": "1 + 0"}},
        ],
    }
    rec = prizes.extract(raw)
    assert rec["source"] == "winCategories" and rec["price"] == 15
    keys = {prizes.category_key(c["label"], 2, [2, 2]): (c["winners"], c["prize"]) for c in rec["categories"]}
    assert keys == {"2+2": (0, 0), "1+2": (1, 750), "1+1": (36, 30), "1+0": (285, 15)}
    # 5 из 36 лайт: подпись «4 из 5»
    one = prizes.extract({"winCategories": [
        {"participants": 0, "amount": 0, "title": {"ru": "5 из 5"}},
        {"participants": 32, "amount": 50000, "title": {"ru": "4 из 5"}}]})
    assert [prizes.category_key(c["label"], 1, [5]) for c in one["categories"]] == ["5", "4"]
    # одни нули — выплат нет
    assert prizes.extract({"winners": [{"participants": 0, "amount": 0, "category": i} for i in range(3)]}) is None


def test_equal_fields_detected_from_data():
    """Игра не в реестре, числа одним списком с повторами: 2+2 из 26 и 4+4 из 20 делятся на поля."""
    import random
    from lottery.drawfile import Draw, split_bonus
    from lottery.games import Game
    rng = random.Random(1)
    for k, n in ((4, 26), (8, 20)):
        draws = [Draw(i, "01.01.2026 10:00", (tuple(rng.sample(range(1, n + 1), k // 2) + rng.sample(range(1, n + 1), k // 2)),))
                 for i in range(1, 400)]
        out, split = split_bonus(draws, Game(slug="new-game", title="x"))
        assert split and all(len(d.blocks) == 2 and len(d.blocks[0]) == k // 2 for d in out)
    digits = [Draw(i, "01.01.2026 10:00", (tuple(rng.randrange(10) for _ in range(4)),)) for i in range(1, 400)]
    assert split_bonus(digits, Game(slug="digits", title="x"))[1] is False


REAL = json.loads((Path(__file__).parent / "fixtures" / "api_real_draws.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("slug,shape,expected", [
    ("4x20", (4, 4), {"4 X 3 и 3 X 4": ["4+3", "3+4"], "3 X 3": ["3+3"]}),
    ("oxota", (4, 4), {"4 X 1 и 1 X 4": ["4+1", "1+4"]}),
    ("dvazhdydva", (2, 2), {"1 + 2": ["1+2"]}),
    ("5x2", (5, 2), {"4+1": ["4+1"]}),
    ("5x36plus", (5, 1), {"5 + 1": ["5+1"], "3": ["3+0"]}),
    ("rapido2", (8, 1), {"7 + 1": ["7+1"], "7": ["7+0"], "Больше нечётных": []}),
    ("rapidopro", (8, 1), {"6": ["6+0"]}),
    ("6x45", (6,), {"4 из 6": ["4"]}),
    ("udachanasdachu", (6,), {"1 из 6": ["1"]}),
    ("crazycombo", (12,), {"2 или 10": ["2", "10"]}),
    ("keno2", (9, 20), {}),
    ("gzhl", None, {"Тур 1": []}),
])
def test_real_api_draws(slug, shape, expected):
    """Ответы настоящего API Столото (по последнему тиражу каждой игры, октябрь 2026)."""
    from lottery.games import get_game
    raw = REAL[slug]
    blocks = stoloto.extract_blocks(raw, get_game(slug))
    if shape:
        assert tuple(len(b) for b in blocks) == shape
    rec = prizes.extract(raw)
    assert rec and rec["price"] == raw["ticketPrice"]
    labels = {c["label"]: c for c in rec["categories"]}
    counts = list(shape or [len(blocks[0])])
    for label, keys in expected.items():
        assert prizes.category_keys(label, len(counts), counts) == keys and label in labels


def test_prize_storage_appends_and_reads_old_format(data_dir):
    """Новые тиражи дописываются в конец; старый формат 40.3.0–40.3.2 читается; изменение
    сохранённого тиража переписывает файл; одинаковые записи не пишутся повторно."""
    path = prizes.prizes_file("4x20")
    old = {"no": 1, "source": "winCategories", "categories": [{"label": "4 X 4", "winners": 0.0, "prize": 0.0},
                                                             {"label": "3 X 3", "winners": 5.0, "prize": 4000.0}],
           "price": 350.0}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
    known = prizes.line_hashes("4x20")
    new = {"no": 2, "source": "winCategories", "categories": [{"label": "3 X 3", "winners": 7.0, "prize": 3500.0}],
           "price": 350.0}
    prizes.write_records("4x20", {2: prizes.record_line(new)}, known)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == json.dumps(old, ensure_ascii=False) and json.loads(lines[1])["c"] == [["3 X 3", 7.0, 3500.0]]
    hist = prizes.keyed_history("4x20", [4, 4])
    assert hist[1]["categories"]["3+3"]["prize"] == 4000.0 and hist[2]["categories"]["3+3"]["winners"] == 7.0
    assert prizes.typical_prizes("4x20", [4, 4])["prizes"]["3+3"] == 3750.0
    # переписать тираж 1 (перечитывание архива): файл пересобирается по порядку
    old["categories"][1]["prize"] = 4100.0
    prizes.write_records("4x20", {1: prizes.record_line(old)}, prizes.line_hashes("4x20"))
    assert [prizes._line_no(l) for l in path.read_text(encoding="utf-8").splitlines()] == [1, 2]
    assert prizes.load("4x20", nos={1})[1]["categories"][1]["prize"] == 4100.0
