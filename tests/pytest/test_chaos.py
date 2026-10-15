"""«Порядок из хаоса»: настоящий хаос (логистическое отображение) находится и предсказывается,
честные тиражи — нет; модели не заглядывают в будущее; лототрон и ГСЧ — отдельные наборы,
прогноз берётся из набора способа ближайшего тиража."""
import json

import numpy as np
import pytest
from conftest import random_lotto

from lottery import chaos, journal, rules
from lottery.drawfile import load_game_data
from lottery.games import draws_path, get_game
from lottery.models import Features, hits, top_k


def logistic_draws(t: int, n: int = 20, k: int = 4, share: float = 0.6, seed: int = 1) -> np.ndarray:
    """Тиражи, за которыми стоит детерминированный хаос: в доле share тиражей выпадают k чисел
    подряд, начиная с позиции, заданной логистическим отображением x → 3,99·x·(1−x)."""
    rng = np.random.default_rng(seed)
    s = np.empty(t)
    s[0] = 0.3
    for i in range(1, t):
        s[i] = 3.99 * s[i - 1] * (1 - s[i - 1])
    x = np.zeros((t, n), np.float32)
    for i in range(t):
        if rng.random() < share:
            c = int(s[i] * (n - k + 1))
            x[i, c:c + k] = 1
        else:
            x[i, rng.choice(n, k, replace=False)] = 1
    return x


def test_chaos_models_find_deterministic_chaos():
    x = logistic_draws(2500)
    f = Features(x, 4)
    base = 4 * 4 / 20
    got = {m.key: hits(x, top_k(m.scores(f), 4))[500:].mean() for m in chaos.chaos_models()}
    assert got["random"] == pytest.approx(base, abs=0.08)
    for key in ("analog_1", "analog_2", "phase_1"):
        assert got[key] > 2 * base


def test_fair_draws_give_no_edge():
    x = random_lotto(2500, 20, 4, seed=3)
    f = Features(x, 4)
    for m in chaos.chaos_models():
        h = hits(x, top_k(m.scores(f), 4))[500:]
        assert abs(h.mean() - 0.8) < 0.08, m.key


@pytest.mark.parametrize("key", ["analog_2", "phase_3", "simplex_3", "ordinal_4"])
def test_no_lookahead(key):
    """Строки оценок до t не меняются, если переписать тиражи начиная с t."""
    x = logistic_draws(900)
    model = next(m for m in chaos.chaos_models() if m.key == key)
    s1 = model.scores(Features(x, 4))
    y = x.copy()
    y[600:] = random_lotto(300, 20, 4, seed=9)
    s2 = model.scores(Features(y, 4))
    np.testing.assert_allclose(s1[:601], s2[:601])
    assert not np.allclose(s1[650:], s2[650:])


def test_order_checks_chaos_vs_fair():
    z = chaos.draw_features(logistic_draws(2500))
    assert chaos.predictability(z[:, 0])["p_value"] < 1e-6
    assert chaos.entropy_test(z[:, 0], n_sur=99)["p_value"] <= 0.02
    zr = chaos.draw_features(random_lotto(2500, 20, 4, seed=5))
    assert chaos.predictability(zr[:, 0])["p_value"] > 0.05
    assert chaos.entropy_test(zr[:, 0], n_sur=99)["p_value"] > 0.05
    assert chaos.recurrence_test(zr, n=600, n_sur=49)["p_value"] > 0.05


# ── лототрон и ГСЧ — разные наборы ────────────────────────────────────────────

def _save_rules_4x20(next_no=None, next_date=None):
    real = json.loads((__import__("pathlib").Path(__file__).parent / "fixtures" / "rules_real.json")
                      .read_text(encoding="utf-8"))["4x20"]
    cms = {"data": [{"contents": [{"collection": "how_draws_work", "item": {"text": real["how"], "content": []}}]}]}
    draw = dict(real["draw"])
    if next_no:
        draw["number"] = next_no
    rec = rules.parse("4x20", {"draw": draw}, real["table"], cms, real["superprize"])
    if next_date:
        rec["next_draw"]["date"] = next_date
    rules.rules_dir().mkdir(parents=True, exist_ok=True)
    rules.rules_path("4x20").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def _mixed_game(t=1600):
    """«4 из 20»: тиражи лототрона (22:00) честные, тиражи ГСЧ (11:07) — хаос логистического
    отображения, которое шагает только от тиража ГСЧ к тиражу ГСЧ."""
    chaos_x = logistic_draws(t // 2, share=0.8, seed=2)
    chaos_f2 = logistic_draws(t // 2, share=0.8, seed=4)
    fair = random_lotto(t, 20, 4, seed=7)
    lines, ci = [], 0
    for i in range(t):
        kind = "R" if i % 2 else "L"
        if kind == "R":
            f1, f2 = chaos_x[ci], chaos_f2[ci]
            ci += 1
        else:
            f1, f2 = fair[i], fair[(i + 1) % t]
        hhmm = "11:07" if kind == "R" else "22:00"
        day = i // 2
        lines.append(f"{1 + day % 28:02d}.{1 + (day // 28) % 12:02d}.{2010 + day // 336} {hhmm}||{i + 1}||"
                     f"{', '.join(str(j + 1) for j in np.nonzero(f1)[0])}||"
                     f"{', '.join(str(j + 1) for j in np.nonzero(f2)[0])}")
    draws_path("4x20").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return load_game_data(get_game("4x20"))


def test_mechanisms_are_separate_chaos_sets():
    _save_rules_4x20()
    data = _mixed_game()
    res = chaos.analyze(data)
    assert set(res["groups"]) == {"L", "R"}
    gl, gr = res["groups"]["L"], res["groups"]["R"]
    assert gl["draws"] == gr["draws"] == 800
    # в наборе ГСЧ порядок есть и повторяется, у лототрона — нет
    assert any(c["significant"] and c["replicated"] for c in gr["checks"])
    assert not any(c["significant"] for c in gl["checks"])
    assert gr["best"]["holdout"]["p_adjusted"] < 0.05 and gr["best"]["holdout"]["excess_pct"] > 30
    assert gl["best"]["holdout"]["p_adjusted"] > 0.05
    assert "порядок найден" in res["conclusion"] and "ГСЧ" in res["conclusion"]


def test_forecast_comes_from_next_draw_mechanism():
    # последний тираж — ГСЧ в 11:07; следующий по расписанию — 11:37, тоже ГСЧ
    _save_rules_4x20()
    data = _mixed_game()
    res = chaos.analyze(data)
    assert res["next"]["mechanism"] == "R" and "11:37" in res["next"]["reason"]
    assert res["next"]["numbers"] == res["groups"]["R"]["evaluation"]["next_prediction"]["numbers"]
    # API говорит, что ближайший тираж (№ последний+1) — в 12:00:00: это лототрон
    _save_rules_4x20(next_no=data.draws[-1].no + 1, next_date="2026-10-15T12:00:00")
    res = chaos.analyze(data)
    assert res["next"]["mechanism"] == "L" and "12:00" in res["next"]["reason"]
    assert res["next"]["numbers"] == res["groups"]["L"]["evaluation"]["next_prediction"]["numbers"]
    # секунды во времени — ГСЧ, даже если по расписанию такого времени нет
    _save_rules_4x20(next_no=data.draws[-1].no + 1, next_date="2026-10-15T09:41:30")
    assert chaos.next_mechanism(data, ["L", "R"])[0] == "R"


def test_single_mechanism_and_journal(monkeypatch):
    import lp
    from conftest import write_lotto_file
    write_lotto_file(draws_path("5x36"), [random_lotto(700, 36, 5, seed=1)])
    data = load_game_data(get_game("5x36"))
    monkeypatch.setattr(lp, "game_activity", lambda d: {"active": True})
    res = lp.run_chaos(data)
    assert list(res["groups"]) == ["all"] and res["next"]["numbers"]
    entry = next(e for e in journal.load("5x36")["entries"] if e["source"] == "chaos")
    assert entry["draw_no"] == data.draws[-1].no + 1 and entry["source_title"] == "Порядок из хаоса"


def test_too_few_draws():
    from conftest import write_lotto_file
    write_lotto_file(draws_path("5x36"), [random_lotto(120, 36, 5, seed=1)])
    res = chaos.analyze(load_game_data(get_game("5x36")))
    assert res["groups"] == {} and res["next"]["numbers"] is None and "300" in res["conclusion"]
