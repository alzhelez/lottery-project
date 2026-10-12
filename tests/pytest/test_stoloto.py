"""Загрузчик: разбор ответов API и логика обновления на поддельном API."""
from datetime import datetime, timedelta

import pytest

from lottery import stoloto
from lottery.drawfile import load_game_draws
from lottery.games import get_game


@pytest.mark.parametrize("raw,slug,expected", [
    ({"combination": {"structured": [1, 5, 9, 14, 2, 7, 11, 18]}}, "4x20", [[1, 5, 9, 14], [2, 7, 11, 18]]),
    ({"combination": {"structured": [5, 44, 24, 41, 34, 33, 1]}}, "6x45plus", [[5, 44, 24, 41, 34, 33], [1]]),
    ({"combination": {"structured": {"played": [15, 20, 33], "notPlayed": [3, 7]}}}, "x", [[15, 20, 33], [3, 7]]),
    ({"combination": {"structured": {"notPlayed": [59, 74, 81]}}}, "x", [[59, 74, 81]]),
    ({"combination": {"structured": [{"first": [7, 9, 1], "second": [1]}]}}, "x", [[7, 9, 1], [1]]),
    ({"combination": {"structured": {"played": [3, 7, 15], "parity": "ODD"}}}, "x", [[3, 7, 15]]),
    ({"winningCombination": ["01", "05", "09", "14", "02", "07", "11", "16"]}, "4x20", [[1, 5, 9, 14], [2, 7, 11, 16]]),
    ({"combination": {"structured": [0, 7, 0]}}, "top3", [[0, 7, 0]]),
    ({"combination": {"structured": [0, -1, 5, 10]}}, "6x45", [[0, 5, 10]]),   # 0 — законное число, отрицательные — нет
    ({"combination": {"structured": None}}, "4x20", []),
])
def test_extract_blocks(raw, slug, expected):
    assert stoloto.extract_blocks(raw, get_game(slug)) == expected


def test_draw_without_numbers_is_dropped():
    assert stoloto.api_draw_to_draw({"number": 5, "date": "2026-01-01T10:00:00"}, get_game("4x20")) is None
    d = stoloto.api_draw_to_draw({"number": 5, "date": "2026-01-01T10:00:00.000+03:00",
                                  "combination": {"structured": [1, 2, 3, 4, 5, 6, 7, 8]}}, get_game("4x20"))
    assert d.date == "01.01.2026 10:00" and d.blocks == ((1, 2, 3, 4), (5, 6, 7, 8))


class FakeApi:
    """Архив игры: тиражи раз в день начиная с start; номера с 1."""

    def __init__(self, start: datetime, count: int):
        self.draws = []
        for i in range(count):
            dt = start + timedelta(days=i)
            nums = [(i * 3 + j * 5) % 20 + 1 for j in range(4)]
            nums = list(dict.fromkeys(nums)) + [v for v in range(1, 21) if v not in nums]
            self.draws.append({"number": i + 1, "date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                               "combination": {"structured": nums[:4] + nums[4:8]}})
        self.requests = 0

    def _in(self, date_from, date_to):
        return [d for d in self.draws
                if date_from.date() <= datetime.strptime(d["date"][:10], "%Y-%m-%d").date() <= date_to.date()]

    def archive_page(self, game, date_from, date_to, page, count=50, log=print):
        self.requests += 1
        items = self._in(date_from, date_to)
        chunk = items[(page - 1) * count: page * count]
        return chunk, page * count < len(items)

    def has_draws(self, game, date_from, date_to, log=print):
        self.requests += 1
        return bool(self._in(date_from, date_to))


@pytest.fixture
def fake(monkeypatch):
    start = datetime.today() - timedelta(days=799)
    api = FakeApi(start.replace(hour=12, minute=0, second=0, microsecond=0), 800)
    monkeypatch.setattr(stoloto, "archive_page", api.archive_page)
    monkeypatch.setattr(stoloto, "has_draws", api.has_draws)
    monkeypatch.setattr(stoloto, "REQUEST_DELAY", 0)
    return api


def test_first_date_detection(fake):
    assert stoloto.detect_first_draw_date(get_game("4x20")).date() == datetime.strptime(
        fake.draws[0]["date"][:10], "%Y-%m-%d").date()


def test_full_download_then_incremental_and_gaps(fake, data_dir):
    game = get_game("4x20")
    res = stoloto.update_game(game, log=lambda m: None)
    assert res["status"] == "done" and res["draws"] == 800 and res["missing"] == 0
    from lottery.games import read_meta
    assert read_meta("4x20").get("checked_at")          # время проверки архива — для актуальности игры
    # удаляем часть тиражей посередине и в конце — обновление должно их вернуть
    path = data_dir / "draws" / "draws_4x20.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:300] + lines[320:780]) + "\n", encoding="utf-8")
    before = fake.requests
    res = stoloto.update_game(game, log=lambda m: None)
    assert res["draws"] == 800 and res["missing"] == 0
    assert fake.requests - before < 40          # точечные запросы, а не перебор архива с 2009 года
    assert [d.no for d in load_game_draws(game)] == list(range(1, 801))


def test_fetch_all_reports_errors_per_game(monkeypatch, data_dir):
    def boom(*a, **k):
        raise stoloto.ApiUnavailable("нет сети")
    monkeypatch.setattr(stoloto, "has_draws", boom)
    events = []
    res = stoloto.fetch_all(["4x20", "6x45"], events.append)
    assert res["4x20"]["status"] == "error" and "нет сети" in res["4x20"]["message"]
    assert any(e.get("type") == "games" for e in events)


def test_no_network_fails_fast(monkeypatch, data_dir):
    """Без сети загрузка не тратит минуты на ретраи по каждой игре."""
    import requests

    calls = []

    def no_net(*a, **k):
        calls.append(1)
        raise requests.ConnectionError("connection refused")
    monkeypatch.setattr(stoloto.requests, "get", no_net)
    monkeypatch.setattr(stoloto.time, "sleep", lambda s: None)
    res = stoloto.fetch_all(["4x20", "6x45", "5x36", "7x49"], lambda e: None, workers=1)
    assert all(r["status"] == "error" for r in res.values())
    assert sum("Пропущено" in r["message"] for r in res.values()) >= 2
    assert len(calls) <= 6


class DenseCappedApi:
    """Тиражи каждые 15 минут; как настоящий API — новые первыми, а дальше page_cap
    отдаёт одну и ту же последнюю страницу с hasMore=true (из-за этого загрузка
    «Дважды два» крутилась часами)."""

    def __init__(self, start: datetime, days: int, page_cap: int):
        self.draws = []
        for i in range(days * 96):
            dt = start + timedelta(minutes=15 * i)
            a, b = i % 26 + 1, (i * 7) % 26 + 1
            self.draws.append({"number": 1000 + i, "date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                               "combination": {"structured": [a, b % 26 + 1 if b == a else b, (i * 3) % 26 + 1,
                                                              (i * 11) % 26 + 1]}})
        self.page_cap = page_cap
        self.requests = 0

    def archive_page(self, game, date_from, date_to, page, count=50, log=print):
        self.requests += 1
        assert self.requests < 5000, "загрузка зациклилась"
        items = [d for d in self.draws
                 if date_from.date() <= datetime.strptime(d["date"][:10], "%Y-%m-%d").date() <= date_to.date()]
        items.sort(key=lambda d: -d["number"])
        page = min(page, self.page_cap)
        chunk = items[(page - 1) * count: page * count]
        return chunk, page * count < len(items) or page == self.page_cap

    def has_draws(self, game, date_from, date_to, log=print):
        return any(date_from.date() <= datetime.strptime(d["date"][:10], "%Y-%m-%d").date() <= date_to.date()
                   for d in self.draws)


def test_dense_game_with_page_cap_is_fully_loaded(monkeypatch, data_dir):
    start = (datetime.today() - timedelta(days=39)).replace(hour=0, minute=0, second=0, microsecond=0)
    api = DenseCappedApi(start, 40, page_cap=6)
    monkeypatch.setattr(stoloto, "archive_page", api.archive_page)
    monkeypatch.setattr(stoloto, "has_draws", api.has_draws)
    monkeypatch.setattr(stoloto, "REQUEST_DELAY", 0)
    monkeypatch.setattr(stoloto, "MAX_PAGES", 5)
    res = stoloto.update_game(get_game("dvazhdydva"), log=lambda m: None)
    assert res["draws"] == len(api.draws) and res["missing"] == 0
    assert api.requests < 400
