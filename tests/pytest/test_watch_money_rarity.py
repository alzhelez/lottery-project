"""42.11.0: сторож аномалий, история возврата («максимум за полгода»), редкость комбинаций,
честная рамка, архив методов."""
import json
from datetime import datetime, timedelta

from test_golden_retro import _fast_game

from lottery import journal, nextdraw, notify, rarity, scan, trust


def _scan(levels: dict[str, str]) -> dict:
    return {"games": [{"slug": s, "title": s.upper(), "level": lv, "verdict": "…", "q_value": 0.01,
                       "tests": [{"title": "Частоты чисел", "significant": lv != "random"}]} for s, lv in levels.items()]}


def test_anomaly_watch_reports_only_changes():
    # первый запуск — только запоминает: о давно известном не сообщает
    assert scan.watch(_scan({"a": "random", "b": "weak"})) == []
    assert scan.watch(_scan({"a": "random", "b": "weak"})) == []
    got = scan.watch(_scan({"a": "signal", "b": "weak", "c": "random"}))          # новая игра без отклонений — молча
    assert [(c["slug"], c["before"], c["level"]) for c in got] == [("a", "random", "signal")]
    msg = notify.anomaly_message(got)
    assert "Сторож аномалий" in msg and "<b>A</b>: найдены отклонения" in msg and "частоты чисел" in msg
    gone = scan.watch(_scan({"a": "random", "b": "weak", "c": "random"}))         # отклонение исчезло — тоже событие
    assert [(c["slug"], c["level"]) for c in gone] == [("a", "random")]
    assert scan.watch(_scan({"a": "random", "b": "weak", "c": "random", "d": "na"})) == []


def test_return_history_marks_half_year_maximum():
    now = datetime(2026, 11, 15, 12, 0)
    res = lambda no, ret: {"g": {"slug": "g", "title": "Игра", "number": no, "return": ret, "super_prize": 1e6}}  # noqa: E731
    r = nextdraw.track(res(1, 0.40), now - timedelta(days=20))["g"]
    assert r["peak"] == {"days": 0, "max": None, "is_max": False}                   # сравнивать не с чем
    nextdraw.track(res(2, 0.45), now - timedelta(days=10))
    r = nextdraw.track(res(3, 0.44), now)["g"]
    assert r["peak"]["max"] == 0.45 and not r["peak"]["is_max"] and r["peak"]["days"] == 20
    high = nextdraw.track(res(3, 0.50), now)                                        # тот же тираж пересчитан — сам с собой не сравнивается
    assert high["g"]["peak"]["is_max"] and high["g"]["peak"]["max"] == 0.45
    # сообщение — один раз на тираж и не чаще раза в неделю на игру, хотя возврат ниже порога 1
    assert [x["number"] for x in nextdraw.to_notify(high, now)] == [3]
    assert nextdraw.to_notify(high, now) == []
    again = nextdraw.track(res(4, 0.55), now + timedelta(days=1))
    assert again["g"]["peak"]["is_max"] and nextdraw.to_notify(again, now + timedelta(days=1)) == []
    later = nextdraw.track(res(5, 0.60), now + timedelta(days=8))
    assert [x["number"] for x in nextdraw.to_notify(later, now + timedelta(days=8))] == [5]
    msg = notify.ev_message([{**later["g"], "date": "2026-11-23T12:00:00"}])
    assert "максимум за 28 дн. наблюдений" in msg
    # старше 200 дней — из истории уходит
    nextdraw.track(res(6, 0.1), now + timedelta(days=300))
    assert [x["no"] for x in nextdraw.load_history()["g"]] == [6]


def test_rarity_flags_popular_prediction_and_offers_rare_combination(monkeypatch):
    import lp
    data, now = _fast_game()
    monkeypatch.setattr(lp, "game_activity", lambda d: {"active": True})
    monkeypatch.setattr(lp, "FORECAST_HORIZON_MIN", 0.0)
    monkeypatch.setattr(journal, "datetime", type("D", (datetime,), {"now": classmethod(lambda cls: now)}))
    lp.journal_record(data, "analysis_consensus", [[1, 2, 3, 4, 5]], "", ordered=False)      # ряд подряд, «даты»
    lp.journal_record(data, "least", [[6, 7, 8, 9, 10]], "", ordered=False)
    r = rarity.read("5x36")
    assert r["applicable"] and r["based_on"] == data.draws[-1].no
    by = r["draws"]["402"]
    assert by["analysis_consensus"]["score"] > 0 and by["analysis_consensus"]["flags"]
    assert by["final"]["score"] > 0 and "least" not in by                         # Н — не ставка, не оцениваем
    rare = r["rare"]["numbers"]
    assert len(rare[0]) == 5 and rarity.rate(data, rare)["score"] == 0             # у редкой комбинации признаков нет
    lp.journal_record(data, "godmode", [[3, 9, 17, 26, 35]], "", ordered=False)
    again = rarity.read("5x36")
    assert again["rare"] == r["rare"]                                              # между пересчётами не меняется
    assert again["draws"]["402"]["godmode"]["score"] == 0


def test_honest_frame_in_trust_score():
    e = lambda hits: {"hits": hits, "expected": 0.7, "variance": 0.5}  # noqa: E731
    even = trust.score([e(1), e(0)] * 50, False)                         # 50 угадано при 70 ожидаемых — хуже случайного
    assert even["need"] is None and not even["proven"] and 19 < even["mde_pct"] < 21
    some = trust.score([e(1)] * 78 + [e(0)] * 22, False)                 # +11 %: z ≈ 1,13 → нужно ≈ 100·(1,96/1,13)² ≈ 300
    assert not some["proven"] and 280 < some["need"] < 320
    assert trust.score([e(1)] * 95 + [e(0)] * 5, False)["proven"]
    low = trust.score([e(0)] * 90 + [e(1)] * 10, True)                   # «наименее вероятные»: меньше — лучше
    assert low["proven"] and trust.score([e(1)] * 95 + [e(0)] * 5, True)["need"] is None


def test_archived_methods_do_not_vote_or_show_in_telegram():
    assert journal.ARCHIVED == {"analysis_best", "golden", "chaos"} and journal.ARCHIVED <= notify.TELEGRAM_HIDDEN
    assert set(journal.ACTIVE) == {"analysis_consensus", "godmode", "least", "final"}
    from lottery import botstats
    assert not set(botstats.ORDER) & journal.ARCHIVED
