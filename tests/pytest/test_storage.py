"""Формат хранения журнала (42.12.0): описание полей — один раз в шапке, запись — одной строкой,
у записей старше месяца нет служебных полей. Остальной код формата не замечает."""
import json
from datetime import datetime, timedelta

from lottery import journal

BLOCKS = [{"name": "Поле 1", "source": 0, "position": None, "count": 5, "lo": 1, "hi": 36, "mode": "set", "avg": 0.0, "drawn": 0}]


def _entry(i: int, made: datetime, status: str = "checked", **extra) -> dict:
    e = {"id": f"e{i}", "draw_no": 100 + i, "source": "analysis_consensus", "source_title": "Консенсус методов",
         "detail": "30 методов", "made_at": made.isoformat(timespec="seconds"), "based_on": 99 + i, "blocks": BLOCKS,
         "numbers": [[1, 2, 3, 4, 5]], "status": status}
    if status == "checked":
        e.update({"checked_at": (made + timedelta(hours=1)).isoformat(timespec="seconds"), "draw_date": "01.11.2026 12:00",
                  "actual": [[1, 2, 7, 8, 9]], "hits_by_block": [2], "hits": 2, "expected": 0.694, "variance": 0.5,
                  "won": 0.0, "mechanism": "R", "spent": 100.0})
    return {**e, **extra}


def test_journal_storage_roundtrip_and_slim(data_dir):
    now = datetime.now().replace(microsecond=0)
    fresh = [_entry(i, now - timedelta(days=2)) for i in range(3)] + [_entry(9, now, "pending")]
    old = [_entry(20 + i, now - timedelta(days=40)) for i in range(3)]
    gone = _entry(30, now - timedelta(days=2), source="experiment", source_title="Эксперимент «эхо ±3»")
    journal.save("5x36", {"game": "5x36", "entries": old + fresh + [gone]})
    raw = json.loads(journal.journal_path("5x36").read_text(encoding="utf-8"))
    # описание полей — один раз; у записи — номер; название источника не пишется, если оно из SOURCES
    assert raw["format"] == 2 and raw["blocks"] == [BLOCKS] and all(e["blocks"] == 0 for e in raw["entries"])
    assert "source_title" not in raw["entries"][0] and raw["entries"][-1]["source_title"] == "Эксперимент «эхо ±3»"
    assert len(journal.journal_path("5x36").read_text(encoding="utf-8").splitlines()) == len(raw["entries"]) + 2
    got = journal.load("5x36")
    assert got["game"] == "5x36" and "format" not in got and "blocks" not in got
    # свежие записи возвращаются запись в запись
    assert got["entries"][3:] == fresh + [gone]
    # у записей старше месяца нет служебных полей; числа, выпавшее и результат — на месте
    for before, after in zip(old, got["entries"][:3]):
        assert all(k not in raw["entries"][0] for k in journal.SLIM_DROP)
        assert after == {**{k: v for k, v in before.items() if k not in journal.SLIM_DROP}, "detail": ""}
        assert after["hits_by_block"] == [2] and after["blocks"] == BLOCKS and after["source_title"] == "Консенсус методов"
    # повторное сохранение ничего не меняет
    text = journal.journal_path("5x36").read_text(encoding="utf-8")
    journal.save("5x36", journal.load("5x36"))
    assert journal.journal_path("5x36").read_text(encoding="utf-8") == text
    # ждущая сверки запись не сжимается, сколько бы ей ни было
    journal.save("5x36", {"game": "5x36", "entries": [_entry(1, now - timedelta(days=90), "pending")]})
    assert journal.load("5x36")["entries"][0]["based_on"] == 100


def test_journal_reads_old_format(data_dir):
    made = datetime(2026, 10, 1, 12, 0)
    entries = [_entry(i, made) for i in range(2)]
    journal.journal_path("5x36").parent.mkdir(parents=True, exist_ok=True)
    journal.journal_path("5x36").write_text(json.dumps({"game": "5x36", "entries": entries}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    assert journal.load("5x36")["entries"] == entries
