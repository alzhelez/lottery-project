"""Журнал прогнозов и проверка актуальности игр."""
from datetime import datetime, timedelta

from lottery import journal
from lottery.drawfile import Draw, load_game_data, write_draws
from lottery.games import activity, draws_path, get_game, write_meta


def _draws(n: int, start: datetime) -> list[Draw]:
    out = []
    for i in range(n):
        dt = start + timedelta(hours=i)
        nums = tuple(((i * 3 + j * 5) % 20) + 1 for j in range(4))
        out.append(Draw(i + 1, dt.strftime("%d.%m.%Y %H:%M"), (nums, tuple(((v + 7) % 20) + 1 for v in nums))))
    return out


def _setup(slug: str, n: int, start: datetime):
    write_draws(draws_path(slug), _draws(n, start))
    return load_game_data(get_game(slug))


def test_record_check_and_summary(data_dir):
    start = datetime(2026, 1, 1, 10)
    data = _setup("jgame", 50, start)
    made = start + timedelta(hours=49, minutes=10)                 # после тиража №50, до №51
    e = journal.record(data, "analysis_best", [[1, 2, 3, 4], [5, 6, 7, 8]], "метод", now=made)
    assert e["draw_no"] == 51 and e["status"] == "pending"
    # повторный прогноз на тот же тираж заменяет прежний
    journal.record(data, "analysis_best", [[9, 10, 11, 12], [5, 6, 7, 8]], "метод", now=made)
    assert len(journal.load("jgame")["entries"]) == 1
    assert journal.reconcile(get_game("jgame")) == 0                # тиража ещё нет

    full = _draws(51, start)
    write_draws(draws_path("jgame"), full)
    assert journal.reconcile(get_game("jgame")) == 1
    entry = journal.load("jgame")["entries"][0]
    actual = [list(b) for b in full[50].blocks]
    assert entry["status"] == "checked" and entry["actual"] == actual
    expected_hits = len({9, 10, 11, 12} & set(actual[0])) + len({5, 6, 7, 8} & set(actual[1]))
    assert entry["hits"] == expected_hits
    assert abs(entry["expected"] - 1.6) < 1e-9
    row = journal.view("jgame")["summary"][0]
    assert row["checked"] == 1 and row["mean_hits"] == expected_hits and abs(row["expected"] - 1.6) < 1e-9


def test_prediction_after_draw_is_not_counted(data_dir):
    start = datetime(2026, 1, 1, 10)
    data = _setup("late", 50, start)
    journal.record(data, "godmode", [[1, 2, 3, 4], [5, 6, 7, 8]], now=start + timedelta(days=30))
    write_draws(draws_path("late"), _draws(51, start))
    journal.reconcile(get_game("late"))
    assert journal.load("late")["entries"][0]["status"] == "late"
    row = journal.view("late")["summary"][0]
    assert row["late"] == 1 and row["checked"] == 0 and "mean_hits" not in row


def test_activity():
    now = datetime(2026, 10, 8, 12)
    assert activity(now - timedelta(days=3), None, now)["active"]
    assert not activity(now - timedelta(days=20), None, now)["active"]
    # при старой проверке архива отсчёт идёт от неё, а не от сегодняшнего дня
    checked = (now - timedelta(days=60)).isoformat()
    res = activity(now - timedelta(days=62), checked, now)
    assert res["active"] and res["data_age_days"] == 60
    assert not activity(None, None, now)["active"]


def test_cli_records_only_for_active_games(data_dir):
    import json
    import os
    import subprocess
    import sys
    from conftest import ROOT, random_lotto, write_lotto_file

    write_lotto_file(draws_path("5x36"), [random_lotto(400, 36, 5, 1)])   # даты в 2010 году — игра неактивна
    env = {**os.environ, "LOTTERY_DATA_DIR": str(data_dir)}
    subprocess.run([sys.executable, str(ROOT / "python" / "lp.py"), "analyze", "--game", "5x36"],
                   env=env, check=True, capture_output=True, timeout=300)
    assert journal.load("5x36")["entries"] == []

    now = datetime.now().replace(second=0, microsecond=0)
    write_draws(draws_path("5x36"), [Draw(i + 1, (now - timedelta(hours=400 - i)).strftime("%d.%m.%Y %H:%M"),
                                          (tuple(range(1 + i % 30, 6 + i % 30)),)) for i in range(400)])
    write_meta("5x36", checked_at=now.isoformat())
    subprocess.run([sys.executable, str(ROOT / "python" / "lp.py"), "analyze", "--game", "5x36"],
                   env=env, check=True, capture_output=True, timeout=300)
    entries = journal.load("5x36")["entries"]
    assert {e["source"] for e in entries} == {"analysis_best", "analysis_consensus"}
    assert all(e["draw_no"] == 401 for e in entries)
    out = subprocess.run([sys.executable, str(ROOT / "python" / "lp.py"), "journal", "--game", "5x36"],
                         env=env, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    res = json.loads([l for l in out.splitlines() if l.startswith("@@")][-1][2:])
    assert len(res["journals"]["5x36"]["entries"]) == 2
