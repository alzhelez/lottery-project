"""42.6.0: доверие к методам, «Финальное предсказание», методы «Тренд» и «Ритм», Telegram-бот."""
import json
from datetime import datetime, timedelta

import numpy as np
import pytest
from conftest import random_lotto
from test_golden_retro import _fast_game

from lottery import bot, journal, notify, trust
from lottery.models import Features
from lottery.models_extra import rhythm_scores, trend_scores


def _checked(source, no, hits, when, expected=1.0, variance=0.8):
    return {"id": f"{source}{no}", "draw_no": no, "source": source, "status": "checked", "hits": hits,
            "expected": expected, "variance": variance, "checked_at": when.isoformat(timespec="seconds"),
            "made_at": when.isoformat(timespec="seconds"), "numbers": [[1, 2, 3, 4, 5]], "blocks": []}


@pytest.mark.parametrize("fn", [trend_scores, rhythm_scores])
def test_new_models_do_not_look_ahead(fn):
    x = random_lotto(400, 36, 5, seed=1)
    y = x.copy()
    y[250:] = random_lotto(150, 36, 5, seed=9)
    a, b = fn(Features(x, 5)), fn(Features(y, 5))
    assert a.shape == (401, 36) and np.isfinite(a).all()
    np.testing.assert_allclose(a[:251], b[:251], rtol=1e-6, atol=1e-6)


def test_new_models_are_in_comparison():
    from lottery.models import standard_models
    keys = {m.key for m in standard_models()}
    assert {"trend_25_200", "rhythm"} <= keys


def test_trust_scale_and_least_direction():
    now = datetime(2026, 11, 9, 12)
    lucky = [_checked("analysis_best", i, 2, now) for i in range(100)]       # вдвое больше ожидаемого
    assert trust.score(lucky, lower=False)["trust"] > 95
    assert trust.score(lucky, lower=True)["trust"] < 5                        # у «наименее вероятных» — наоборот
    assert trust.score([_checked("chaos", i, 1, now) for i in range(100)], False)["trust"] == 50.0
    few = trust.score(lucky[:3], False)
    assert few["few"] and 50 < few["trust"] < 80                              # мало прогнозов — прижато к 50
    assert trust.level(92) == "высокое" and trust.level(50) == "как у случайного выбора" and trust.level(10) == "низкое"


def test_trust_build_merges_journal_and_retro(data_dir):
    now = datetime(2026, 11, 9, 12)
    recent, old = now - timedelta(days=2), now - timedelta(days=20)
    journal.save("5x36", {"game": "5x36", "entries": [
        _checked("analysis_best", 10, 3, recent), _checked("analysis_best", 1, 0, old),      # старый — вне периода
        _checked("least", 10, 0, recent)]})
    journal.save("5x36", {"game": "5x36", "entries": [
        _checked("analysis_best", 10, 0, recent),                                            # тот же тираж — берётся журнал
        _checked("analysis_best", 11, 2, recent), _checked("chaos", 11, 0, recent)]}, retro=True)
    t = trust.build(["5x36"], 7, now)
    rows = t["games"]["5x36"]["sources"]
    assert rows["analysis_best"]["n"] == 2 and rows["analysis_best"]["hits"] == 5
    assert rows["least"]["trust"] > 50 > rows["chaos"]["trust"]
    assert t["games"]["5x36"]["ranking"][0] == "analysis_best" and rows["analysis_best"]["rank"] == 1
    assert trust.load_trust()["days"] == 7
    w = trust.weights("5x36")
    assert w["analysis_best"] > w["chaos"] == trust.BASE_WEIGHT


def test_final_numbers_follow_trust_and_avoid_least():
    blocks = [{"lo": 1, "hi": 10}]
    by = {"analysis_best": [[1, 2, 3]], "chaos": [[4, 5, 6]], "analysis_consensus": [[1, 4, 7]], "least": [[1, 9, 10]]}
    w = {"analysis_best": 1.0, "chaos": 0.1, "analysis_consensus": 0.1, "least": 0.5}
    # 1: 1,0+0,1−0,5 = 0,6; 2 и 3: 1,0; 4: 0,2; остальные ≤ 0,1
    assert trust.final_numbers(by, blocks, w) == [[1, 2, 3]]
    assert trust.final_numbers(by, blocks, {**w, "least": 1.0}) == [[2, 3, 4]]       # сильный штраф выбивает 1
    assert trust.final_numbers({"analysis_best": [[1, 2, 3]], "least": [[4, 5, 6]]}, blocks, w) is None


def test_final_is_recorded_after_two_sources(monkeypatch):
    import lp
    data, now = _fast_game()
    monkeypatch.setattr(lp, "game_activity", lambda d: {"active": True})
    monkeypatch.setattr(lp, "FORECAST_HORIZON_MIN", 0.0)
    monkeypatch.setattr(journal, "datetime", type("D", (datetime,), {"now": classmethod(lambda cls: now)}))
    lp.journal_record(data, "analysis_best", [[1, 2, 3, 4, 5]], "", ordered=False)
    assert not [e for e in journal.load("5x36")["entries"] if e["source"] == "final"]
    lp.journal_record(data, "chaos", [[1, 2, 3, 4, 6]], "", ordered=False)
    final = [e for e in journal.load("5x36")["entries"] if e["source"] == "final"]
    assert len(final) == 1 and final[0]["numbers"] == [[1, 2, 3, 4, 5]] and "доверию" in final[0]["detail"]
    lp.journal_record(data, "least", [[1, 20, 21, 22, 23]], "", ordered=False)      # пересчитывается, не дублируется
    final = [e for e in journal.load("5x36")["entries"] if e["source"] == "final"]
    assert len(final) == 1 and 1 not in final[0]["numbers"][0]


def test_auto_message_final_replaces_best_and_consensus():
    msg = notify.auto_message({"games": {}}, {"g": {"title": "Игра", "next_no": 5, "numbers": [[1, 2, 3]],
                                                    "consensus": [[1, 2, 4]], "final": [[1, 2, 9]], "golden": [[1, 2, 5]]}})
    assert "  Ф: <code>1 2 9</code>\n  З: <code>1 2 5</code>" in msg and "Л: " not in msg and "К: " not in msg


def test_retro_final_uses_only_earlier_draws():
    """Ф в анализе за период: веса на тираж — по доверию, накопленному к нему; результат тиража
    и более поздние тиражи на его прогноз не влияют."""
    from lottery import retro
    data, _ = _fast_game()
    def e(source, no, numbers, hits):
        return {"source": source, "draw_no": no, "numbers": [numbers], "hits": hits, "expected": 0.7, "variance": 0.5}
    base = []
    for no in range(300, 340):
        base += [e("analysis_best", no, [1, 2, 3, 4, 5], 3), e("chaos", no, [6, 7, 8, 9, 10], 0),
                 e("analysis_consensus", no, [1, 2, 3, 11, 12], 1)]
    rows = dict((no, nums) for no, nums, _ in retro.final_rows(data, base))
    assert rows[300] == [[1, 2, 3, 4, 5]] or len(rows[300][0]) == 5        # первый тираж — равные веса
    assert rows[339] == [[1, 2, 3, 4, 5]]                                   # дальше ведёт метод с лучшим счётом
    changed = [dict(x, hits=0) if x["draw_no"] >= 320 and x["source"] == "analysis_best" else x for x in base]
    again = dict((no, nums) for no, nums, _ in retro.final_rows(data, changed))
    assert all(again[no] == rows[no] for no in range(300, 321))             # прошлое и сам тираж 320 не изменились


def test_bot_analysis_button(monkeypatch):
    import subprocess
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **k: started.append(cmd))
    text, kb = bot.route("analyze")
    assert [b["callback_data"] for row in kb["inline_keyboard"] for b in row][:5] == ["run:1", "run:3", "run:7", "run:14", "run:30"]
    text, _ = bot.route("run:14")
    assert "Анализ за 2 недели запущен" in text and started[0][-4:] == ["retro", "--days", "14", "--notify"]
    bot.route("run:5")                                                      # нет такого периода — просто меню
    assert len(started) == 1
    done = bot.analysis_done_message(14, {"games": {"5x36": {"ranking": ["golden"], "sources": {"golden": {"trust": 71.0, "few": False}}}}})
    assert "Анализ за 2 недели завершён" in done and "5 из 36: З Золотая середина — 71" in done


# ── бот ───────────────────────────────────────────────────────────────────

class FakeApi:
    def __init__(self):
        self.calls = []

    def call(self, method, **params):
        self.calls.append((method, params))
        return {"ok": True, "result": []}


def test_bot_mute_buttons_control_messages(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    sent = []
    monkeypatch.setattr(notify, "_deliver", lambda cfg, item: sent.append(item["event"]))
    monkeypatch.setattr(notify, "flush", lambda cfg=None: 0)
    assert notify.send("сверка", "journal") and notify.send("итог", "auto")
    text, kb = bot.route("mute:journal")
    assert bot.muted() == {"journal"} and "🔕 Сверка прогнозов: выкл" in json.dumps(kb, ensure_ascii=False)
    assert notify.send("сверка", "journal") is False and notify.send("итог", "auto")
    assert notify.send("проверка", "journal", force=True)                       # тест связи проходит всегда
    bot.route("mute:journal")
    assert bot.muted() == set() and notify.send("сверка", "journal")
    assert sent == ["journal", "auto", "auto", "journal", "journal"]


def test_bot_ignores_foreign_chats_and_answers_owner():
    api = FakeApi()
    bot.handle({"message": {"chat": {"id": 7}, "text": "/menu"}}, api, "42")
    bot.handle({"callback_query": {"id": "c", "data": "status", "message": {"chat": {"id": 7}, "message_id": 1}}}, api, "42")
    assert api.calls == []
    bot.handle({"message": {"chat": {"id": 42}, "text": "привет"}}, api, "42")
    assert api.calls[0][0] == "sendMessage" and "Проверить статус приложения" in json.dumps(api.calls[0][1], ensure_ascii=False)
    bot.handle({"callback_query": {"id": "c", "data": "games", "message": {"chat": {"id": 42}, "message_id": 5}}}, api, "42")
    assert [c[0] for c in api.calls[1:]] == ["answerCallbackQuery", "editMessageText"]


def test_bot_status_reports_unavailable_app(monkeypatch):
    import requests

    def down(*a, **k):
        raise requests.ConnectionError("нет")
    monkeypatch.setattr(bot.requests, "get", down)
    assert "❌ Приложение недоступно" in bot.app_status()
    monkeypatch.setattr(bot.requests, "get", lambda *a, **k: type("R", (), {"status_code": 200})())
    assert "✅ Приложение доступно" in bot.app_status()


def test_bot_game_stats_and_method_forecast():
    data, now = _fast_game()
    made = now - timedelta(days=1)
    journal.record_many(data, "analysis_best", [(402, [[1, 2, 3, 4, 5]])], "Горячие, окно 50", now=now)
    j = journal.load("5x36")
    j["entries"] += [_checked("analysis_best", 300 + i, 2, made) for i in range(40)]
    j["entries"] += [{**_checked("least", 300 + i, 0, made), "source": "least"} for i in range(40)]
    j["entries"].append(_checked("chaos", 100, 5, now - timedelta(days=40)))     # старше двух недель — не в счёт
    journal.save("5x36", j)
    assert ("5x36", "5 из 36") in bot.games()
    text, has = bot.game_stats("5x36", now)
    assert "журнал за 14 дней" in text and "Л Лучший метод анализа: 40 · 80 / 40,0 · +100.0%" in text
    assert "Н Наименее вероятные: 40 · 0" in text and "Порядок из хаоса" not in text
    assert has == ["analysis_best"]
    _, kb = bot.game_menu("5x36")
    # первая кнопка — «Пересчитать предсказания» (истории прогнозов ещё нет), дальше — методы
    assert [r[0]["callback_data"] for r in kb["inline_keyboard"][:2]] == ["fix:5x36", "m:5x36:analysis_best"]
    fc = bot.method_forecast("5x36", "analysis_best", now)
    assert "Ближайший тираж №402 — через " in fc and "Числа на №402: <code>1 2 3 4 5</code>" in fc
    assert "Прогноза этого метода на ближайший тираж нет" in bot.method_forecast("5x36", "godmode", now)


def test_coverage_finds_draws_without_predictions_and_bot_offers_fix(monkeypatch):
    """Автоанализ — по всему архиву: пока истории прогнозов нет, бот предлагает пересчёт; после
    пересчёта пропусков нет; новый тираж без прогноза — пропуск, пока история его не дополнит."""
    import subprocess
    from lottery import coverage, history, retro
    from lottery.drawfile import Draw, load_game_data, write_draws
    from lottery.games import draws_path, get_game
    data, now = _fast_game(minutes=60, count=400, last_ago_min=10)
    text, need = coverage.summary("5x36")
    assert need and "ещё не посчитаны" in text
    msg, kb = bot.game_menu("5x36")
    assert msg.startswith("⚠️ Автоанализ") and kb["inline_keyboard"][0][0] == {"text": "Пересчитать предсказания", "callback_data": "fix:5x36"}
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **k: started.append(cmd))
    reply, _ = bot.route("fix:5x36")
    assert "Пересчёт предсказаний «5 из 36»" in reply and started[0][-2:] == ["--game", "5x36"]
    retro.run(["5x36"], days=2, godmode_budget=0, now=now, log=lambda m: None)
    c = coverage.coverage("5x36")
    assert c["built"] and c["complete"] and c["draws"] == 400 and 300 < c["with_predictions"] < 400
    text, need = coverage.summary("5x36")
    assert not need and text.startswith("✅")
    assert bot.game_menu("5x36")[1]["inline_keyboard"][0][0]["callback_data"] != "fix:5x36"
    # сыграны ещё три тиража, в журнале прогноз только у одного метода на один из них
    rng = np.random.default_rng(5)
    more = [Draw(400 + i, (now + timedelta(hours=i)).strftime("%d.%m.%Y %H:%M"),
                 (tuple(sorted(int(v) + 1 for v in rng.choice(36, 5, replace=False))),)) for i in (1, 2, 3)]
    write_draws(draws_path("5x36"), list(data.draws) + more)
    journal.save("5x36", {"game": "5x36", "entries": [_checked("analysis_consensus", 402, 1, now)]})
    c = coverage.coverage("5x36")
    assert not c["complete"] and c["missing"]["КМ"] == 2 and c["missing"]["ЛМА"] == 3
    res = history.fill(load_game_data(get_game("5x36")))
    assert res["added"] == 3 and res["restored"] > 0
    h = history.load("5x36")
    assert h["last_no"] == 403 and coverage.coverage("5x36")["complete"]
    rows = history.rows_of(h)
    assert rows["analysis_consensus"][402] == "1,2,3,4,5"          # прогноз журнала — как записан
    assert all(403 in rows[s] for s in ("analysis_best", "analysis_consensus", "least", "golden", "chaos", "final"))
    assert history.fill(load_game_data(get_game("5x36")))["status"] == "up_to_date"


def test_history_covers_whole_archive_without_lookahead():
    """История: прогноз каждого метода на каждый тираж после разгона; тиражи после t на прогноз
    тиража t не влияют (и там, где «лучший» выбирается пошагово, — до конца отрезка отбора)."""
    from lottery import history, retro
    from lottery.drawfile import Draw, write_draws
    from lottery.evaluate import warmup_size
    from lottery.games import draws_path
    data, now = _fast_game(minutes=60, count=700, last_ago_min=10)
    retro.run(["5x36"], days=2, godmode_budget=0, now=now, log=lambda m: None)
    h = history.load("5x36")
    rows = history.rows_of(h)
    warm = warmup_size(700)
    expect = [d.no for d in data.draws[warm:]]
    for s in ("analysis_best", "analysis_consensus", "least", "golden", "final"):
        assert sorted(rows[s]) == expect, s
    assert 0 < len(rows["chaos"]) < len(expect) and max(rows["chaos"]) == 700     # только контрольный отрезок
    assert h["draws"]["nos"] == expect and h["draws"]["actual"][0] == history.enc(data.draws[warm].blocks)
    # «анализ за период» — те же числа, что в истории
    for e in journal.load("5x36", retro=True)["entries"]:
        assert history.enc(e["numbers"]) == rows[e["source"]][e["draw_no"]], e["source"]
    cut = expect[150]                                  # ещё внутри отрезка отбора
    rng = np.random.default_rng(99)
    write_draws(draws_path("5x36"), [d if d.no <= cut else Draw(d.no, d.date, (tuple(sorted(int(v) + 1 for v in rng.choice(36, 5, replace=False))),))
                                    for d in data.draws])
    retro.run(["5x36"], days=2, godmode_budget=0, now=now, log=lambda m: None)
    again = history.rows_of(history.load("5x36"))
    for s in ("analysis_best", "analysis_consensus", "least", "golden", "final"):
        for no in expect[:151]:
            assert again[s][no] == rows[s][no], (s, no)
