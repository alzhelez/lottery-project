from lottery.drawfile import infer_format, load_game_draws, merge_legacy, parse_line, read_draws, write_draws
from lottery.games import get_game


def test_parse_four_part_line():
    d = parse_line("12.06.2026 16:22||13896||10, 8, 9, 6||16, 7, 12, 2")
    assert d.no == 13896 and d.blocks == ((10, 8, 9, 6), (16, 7, 12, 2))
    assert d.dt.year == 2026


def test_legacy_line_is_split_by_counts():
    d = parse_line("31.12.2016 15:10||1||20,2,10,4,2,16,9,17", counts=(4, 4))
    assert d.blocks == ((20, 2, 10, 4), (2, 16, 9, 17))


def test_legacy_line_with_wrong_length_stays_single_block():
    d = parse_line("31.12.2016 15:10||1||20,2,10", counts=(4, 4))
    assert d.blocks == ((20, 2, 10),)


def test_bad_lines_are_skipped():
    for bad in ["", "мусор", "01.01.2020||abc||1,2", "01.01.2020||5||", "01.01.2020||5||1,x,3"]:
        assert parse_line(bad) is None


def test_zero_is_kept():
    assert parse_line("01.01.2020 10:00||5||0, 9, 0").blocks == ((0, 9, 0),)


def test_read_dedupes_and_sorts(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("01.01.2020 10:00||2||1,2\n01.01.2020 09:00||1||3,4\n01.01.2020 11:00||2||5,6", encoding="utf-8")
    draws = read_draws(p)
    assert [d.no for d in draws] == [1, 2] and draws[1].blocks == ((1, 2),)


def test_write_roundtrip(tmp_path):
    p = tmp_path / "f.txt"
    src = [parse_line("01.01.2020 10:00||2||1, 2||3"), parse_line("01.01.2020 09:00||1||4, 5||6")]
    write_draws(p, src)
    assert [d.to_line() for d in read_draws(p)] == [src[1].to_line(), src[0].to_line()]


def _draws(lines):
    return [parse_line(l) for l in lines]


def test_infer_lotto_two_blocks():
    lines = [f"01.01.2020 10:00||{i}||{i % 20 + 1}, {(i + 3) % 20 + 1}, {(i + 7) % 20 + 1}, {(i + 11) % 20 + 1}||{i % 4 + 1}"
             for i in range(100)]
    fmt = infer_format(_draws(lines))
    assert fmt.supported
    assert [(b.count, b.lo, b.hi) for b in fmt.blocks] == [(4, 1, 20), (1, 1, 4)]


def test_infer_digits_become_positions():
    lines = [f"01.01.2020 10:00||{i}||{i % 10}, {(i * 3) % 10}, {(i * 7) % 10}" for i in range(100)]
    fmt = infer_format(_draws(lines))
    assert fmt.supported and len(fmt.blocks) == 3
    assert all(b.count == 1 and b.lo == 0 and b.hi == 9 for b in fmt.blocks)


def test_infer_variable_count_with_repeats_is_unsupported():
    lines = [f"01.01.2020 10:00||{i}||" + ", ".join(["3"] * (5 + i % 5)) for i in range(100)]
    fmt = infer_format(_draws(lines))
    assert not fmt.supported and "повторы" in fmt.reason


def test_merge_legacy_api_wins(data_dir):
    (data_dir / "tirazh4x20.txt").write_text(
        "01.01.2020 10:00||1||1,2,3,4,5,6,7,8\n01.01.2020 11:00||2||1,2,3,4,5,6,7,9\n", encoding="utf-8")
    (data_dir / "draws" / "draws_4x20.txt").write_text(
        "01.01.2020 11:00||2||1, 2, 3, 4||5, 6, 7, 10\n01.01.2020 12:00||3||1, 2, 3, 4||5, 6, 7, 8\n", encoding="utf-8")
    added, conflicts = merge_legacy(get_game("4x20"))
    assert (added, conflicts) == (1, 1)
    draws = load_game_draws(get_game("4x20"))
    assert [d.no for d in draws] == [1, 2, 3]
    assert draws[0].blocks == ((1, 2, 3, 4), (5, 6, 7, 8))   # legacy-строка разрезана на два поля
    assert draws[1].blocks[1] == (5, 6, 7, 10)              # при конфликте побеждает версия API
