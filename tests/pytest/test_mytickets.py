"""«Мои билеты»: сверка купленных билетов с тиражами и денежный итог; резервная копия журнала;
удаление файлов убранных игр; непопулярная комбинация в уведомлении о высоком возврате."""
import json
import zipfile
from datetime import datetime, timedelta

import pytest
from conftest import random_lotto, write_lotto_file

from lottery import backup, mytickets, notify, prizes
from lottery.drawfile import load_game_data
from lottery.games import draws_path, get_game


def _game(t=400):
    write_lotto_file(draws_path("5x36"), [random_lotto(t, 36, 5, seed=1)])
    return load_game_data(get_game("5x36"))


def _prize(no, price=80):
    return {"no": no, "source": "w", "price": price,
            "categories": [{"label": "5 из 5", "winners": 0, "prize": 1_000_000},
                           {"label": "4 из 5", "winners": 3, "prize": 7000},
                           {"label": "3 из 5", "winners": 30, "prize": 800},
                           {"label": "2 из 5", "winners": 300, "prize": 80}]}


def _three_hits(data):
    last = list(data.draws[-1].blocks[0])
    return last[:3] + [v for v in range(1, 37) if v not in last][:2]


def test_ticket_is_settled_with_real_prize_and_summary():
    data = _game()
    prizes.save("5x36", {400: _prize(400)})
    t = mytickets.add(data, [_three_hits(data)], draw_no=400)[0]
    assert t["status"] == "checked" and t["hits"] == 3 and t["won"] == 800.0 and t["price"] == 80.0
    later = mytickets.add(data, [[1, 2, 3, 4, 5]], draws=3)
    assert [x["draw_no"] for x in later] == [401, 402, 403] and all(x["status"] == "pending" for x in later)
    assert later[0]["popularity"]["popular"] and any("подряд" in f for f in later[0]["popularity"]["flags"])
    s = mytickets.overview()["summary"]
    assert s["total"] == 4 and s["checked"] == 1 and s["pending"] == 3
    assert s["spent"] == 80 and s["won"] == 800 and s["return"] == pytest.approx(10.0) and s["pending_spent"] == 240


def test_pending_ticket_settles_when_draw_arrives_and_prize_later():
    data = _game(399)
    t = mytickets.add(data, [[1, 2, 3, 4, 5]], draw_no=400, price=100)[0]
    assert t["status"] == "pending"
    data = _game(400)
    got = mytickets.settle(data.game)
    assert len(got) == 1 and got[0]["status"] == "checked" and got[0]["won"] is None   # таблицы призов ещё нет
    assert mytickets.settle(data.game) == []
    prizes.save("5x36", {400: _prize(400)})
    mytickets.settle(data.game)
    stored = mytickets.load("5x36")["tickets"][0]
    assert stored["won"] is not None and stored["price"] == 100


def test_manual_win_and_remove():
    data = _game()
    t = mytickets.add(data, [[1, 2, 3, 4, 5]], draw_no=400, price=80)[0]
    assert mytickets.set_won("5x36", t["id"], 1500)["won_manual"] == 1500
    mytickets.settle(data.game)           # повторная сверка не стирает выигрыш, вписанный вручную
    assert mytickets.summary(mytickets.load("5x36")["tickets"])["won"] == 1500
    assert mytickets.set_won("5x36", t["id"], None).get("won_manual") is None
    assert mytickets.remove("5x36", t["id"]) and not mytickets.remove("5x36", t["id"])
    assert mytickets.load("5x36")["tickets"] == []


@pytest.mark.parametrize("numbers, error", [
    ([[1, 2, 3, 4]], "нужно 5"),
    ([[1, 2, 3, 4, 40]], "от 1 до 36"),
    ([[1, 1, 2, 3, 4]], "разные"),
    ([[1, 2, 3, 4, 5], [1]], "нужно 1 поле"),
])
def test_invalid_tickets_are_rejected(numbers, error):
    data = _game()
    with pytest.raises(ValueError, match=error):
        mytickets.add(data, numbers)
    assert mytickets.load("5x36")["tickets"] == []


def test_parse():
    assert mytickets.parse("1, 2 3;4 | 7") == [[1, 2, 3, 4], [7]]
    with pytest.raises(ValueError):
        mytickets.parse("1, a")


def test_cli_add_list_won_remove(data_dir):
    from test_cli import run
    _game()
    rc, ev = run(["mytickets", "add", "--game", "5x36", "--numbers", "3,11,19,27,34", "--draws", "2",
                  "--price", "100"], data_dir)
    assert rc == 0 and [t["draw_no"] for t in ev[-1]["added"]] == [401, 402]
    tid = ev[-1]["added"][0]["id"]
    rc, ev = run(["mytickets", "list", "--game", "5x36"], data_dir)
    res = ev[-1]
    assert rc == 0 and res["summary"]["pending"] == 2 and res["summary"]["pending_spent"] == 200
    assert res["form"]["next_no"] == 401 and res["form"]["blocks"][0]["count"] == 5
    rc, ev = run(["mytickets", "won", "--game", "5x36", "--id", tid, "--won", "500"], data_dir)
    assert rc == 0 and ev[-1]["ticket"]["won_manual"] == 500
    rc, ev = run(["mytickets", "remove", "--game", "5x36", "--id", tid], data_dir)
    assert rc == 0 and ev[-1]["removed"] == tid
    rc, ev = run(["mytickets", "add", "--game", "5x36", "--numbers", "1,2"], data_dir)
    assert rc == 2 and "нужно 5" in ev[-1]["message"]
    rc, ev = run(["mytickets", "list"], data_dir)
    assert rc == 0 and ev[-1]["summary"]["total"] == 1 and ev[-1]["games"][0]["title"]


def test_telegram_tickets_message():
    t = {"draw_no": 400, "numbers": [[1, 2, 3, 4, 5]], "hits_by_block": [3], "won": 800.0}
    msg = notify.tickets_message([("5 из 36", [t, {**t, "won": 0.0}, {**t, "won": None}])],
                                 {"checked": 3, "spent": 240.0, "won": 800.0, "return": 800 / 240})
    assert "выигрыш <b>800 ₽</b>" in msg and "без выигрыша" in msg and "выплата пока неизвестна" in msg
    assert "потрачено 240 ₽, выиграно 800 ₽, возврат 3,33" in msg
    assert notify.tickets_message([]) is None
    assert "tickets" in notify.EVENTS


def test_ev_message_has_unpopular_combination():
    msg = notify.ev_message([{"title": "6 из 45", "number": 10, "date": "2026-10-26T12:00:00", "return": 1.2,
                              "super_prize": 5e8, "unpopular": [[3, 17, 28, 33, 39, 44]]}])
    assert "непопулярная комбинация: <code>3 17 28 33 39 44</code>" in msg
    assert "не повышает шанс" in msg


def test_unpopular_ticket_for_ev_alert():
    import lp
    _game()
    blocks = lp.unpopular_ticket("5x36")
    assert blocks and len(blocks[0]) == 5
    assert not mytickets.validate(load_game_data(get_game("5x36")), blocks)


# ── резервная копия ──────────────────────────────────────────────────────────

def test_daily_backup_rotation_and_restore(data_dir):
    (data_dir / "journal").mkdir()
    (data_dir / "journal" / "5x36.json").write_text('{"entries": [1]}', encoding="utf-8")
    data = _game()
    mytickets.add(data, [[1, 2, 3, 4, 5]], price=80)
    day = datetime(2026, 10, 1, 3, 0)
    first = backup.daily(now=day)
    assert first and backup.backup_dir() == data_dir.parent / "backup"
    with zipfile.ZipFile(first["path"]) as z:
        assert sorted(z.namelist()) == ["journal/5x36.json", "my_tickets/5x36.json"]
    assert backup.daily(now=day + timedelta(hours=5)) is None          # раз в сутки
    for i in range(1, backup.KEEP + 3):
        backup.daily(now=day + timedelta(days=i))
    daily = [i for i in backup.listing() if i["name"].startswith("lottery-backup-")]
    assert len(daily) == backup.KEEP and daily[-1]["name"] == "lottery-backup-2026-10-04.zip"
    info = backup.info()
    assert info["count"] == backup.KEEP and info["last"]["name"] == "lottery-backup-2026-11-02.zip"
    # восстановление: журнал испорчен — возвращаем из архива, текущее состояние тоже сохраняется
    (data_dir / "journal" / "5x36.json").write_text('{"entries": []}', encoding="utf-8")
    res = backup.restore("lottery-backup-2026-11-02.zip")
    assert sorted(res["restored"]) == ["journal/5x36.json", "my_tickets/5x36.json"]
    assert json.loads((data_dir / "journal" / "5x36.json").read_text(encoding="utf-8")) == {"entries": [1]}
    assert (backup.backup_dir() / res["before"]).exists()
    with pytest.raises(ValueError):
        backup.restore("../secret.zip")


def test_restore_ignores_foreign_paths(data_dir):
    backup.backup_dir().mkdir(parents=True)
    with zipfile.ZipFile(backup.backup_dir() / "evil.zip", "w") as z:
        z.writestr("../../outside.json", "{}")
        z.writestr("journal/../../x.json", "{}")
        z.writestr("journal/4x20.json", '{"entries": []}')
    res = backup.restore("evil.zip")
    assert res["restored"] == ["journal/4x20.json"]
    assert not (data_dir.parent.parent / "outside.json").exists()


def test_backup_dir_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTTERY_BACKUP_DIR", str(tmp_path / "copies"))
    assert backup.backup_dir() == tmp_path / "copies"


# ── файлы убранных игр ───────────────────────────────────────────────────────

def test_remove_excluded_game_files_keeps_journal_in_archive(data_dir):
    write_lotto_file(draws_path("ruslotto"), [random_lotto(50, 90, 5)])
    write_lotto_file(draws_path("4x20"), [random_lotto(50, 20, 4), random_lotto(50, 20, 4, seed=2)])
    prizes.save("ruslotto", {1: _prize(1)})
    for p, text in ((data_dir / "results" / "ruslotto" / "analysis.json", "{}"),
                    (data_dir / "rules" / "ruslotto.json", "{}"),
                    (data_dir / "journal" / "ruslotto.json", '{"entries": [7]}'),
                    (data_dir / "journal" / "4x20.json", '{"entries": [8]}')):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    res = backup.remove_excluded(now=datetime(2026, 10, 26, 4, 0))
    assert "ruslotto" in res["games"] and res["games"]["ruslotto"] > 0 and "4x20" not in res["games"]
    assert not draws_path("ruslotto").exists() and not (data_dir / "results" / "ruslotto").exists()
    assert not (data_dir / "rules" / "ruslotto.json").exists() and not prizes.prizes_file("ruslotto").exists()
    assert not (data_dir / "journal" / "ruslotto.json").exists()
    assert draws_path("4x20").exists() and (data_dir / "journal" / "4x20.json").exists()
    with zipfile.ZipFile(backup.backup_dir() / res["archive"]) as z:
        assert z.namelist() == ["journal/ruslotto.json"]
        assert json.loads(z.read("journal/ruslotto.json")) == {"entries": [7]}
    assert backup.remove_excluded() == {"games": {}, "archive": None}


def test_auto_cycle_makes_backup_cleans_up_and_settles_tickets(data_dir, monkeypatch):
    import lp
    data = _game(399)
    mytickets.add(data, [[1, 2, 3, 4, 5]], draw_no=400, price=80)
    _game(400)
    write_lotto_file(draws_path("gzhl"), [random_lotto(50, 90, 5)])
    sent = []
    monkeypatch.setattr(notify, "send", lambda text, event="auto", **k: sent.append((event, text)) or True)
    args = lp.main.__globals__["argparse"].Namespace(game=["5x36"], godmode_budget=0, godmode_every=3, every=0,
                                                     skip_fetch=True, skip_scan=True)
    status = lp.auto_once(args)
    assert status["backup"]["count"] == 1 and status["my_tickets"]["checked_now"] == 1
    assert not draws_path("gzhl").exists()
    events = [e for e, _ in sent]
    assert "tickets" in events
    assert "Мои билеты" in next(t for e, t in sent if e == "tickets")
