"""Ошибки, найденные при загрузке с живого API Столото на Windows (версия 40.2.0)."""
import json
import os
from datetime import datetime, timedelta

import pytest

from lottery import fsutil, stoloto
from lottery.drawfile import Draw, load_game_data, load_game_draws, split_bonus, write_draws
from lottery.games import draws_path, get_game, read_meta


def test_replace_retries_while_file_is_locked(tmp_path, monkeypatch):
    """WinError 5/32: файл держит антивирус — подмена повторяется и проходит."""
    target = tmp_path / "draws_x.txt"
    target.write_text("old", encoding="utf-8")
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(1)
        if len(calls) < 4:
            raise PermissionError(5, "Отказано в доступе")
        real(src, dst)
    monkeypatch.setattr(fsutil, "_replace", flaky)
    monkeypatch.setattr(fsutil.time, "sleep", lambda s: None)
    fsutil.write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new" and len(calls) == 4
    assert not list(tmp_path.glob("*.tmp"))


def test_permanent_lock_falls_back_to_direct_write(tmp_path, monkeypatch):
    target = tmp_path / "draws_x.txt"
    target.write_text("old", encoding="utf-8")

    def locked(src, dst):
        raise PermissionError(32, "Процесс не может получить доступ к файлу")
    monkeypatch.setattr(fsutil, "_replace", locked)
    monkeypatch.setattr(fsutil.time, "sleep", lambda s: None)
    fsutil.write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob("*.tmp"))


def test_stale_tmp_does_not_block_writing(tmp_path):
    """Errno 13 на .tmp: временный файл от прошлого запуска больше не мешает (уникальное имя)."""
    target = tmp_path / "draws_fzp.txt"
    stale = tmp_path / "draws_fzp.txt.tmp"
    stale.write_text("x")
    stale.chmod(0o400)
    fsutil.write_text(target, "data")
    assert target.read_text() == "data"
    os.utime(stale, (0, 0))
    assert fsutil.cleanup_stale_tmp(tmp_path) == 1


def test_big_archive_is_not_rewritten_every_few_pages(monkeypatch, data_dir):
    writes = []
    monkeypatch.setattr(stoloto, "write_draws", lambda path, draws: writes.append(len(draws)))
    store = stoloto.DrawStore(get_game("4x20"), [])
    page = lambda i: [{"number": i * 50 + j, "date": "2026-01-01T10:00:00",  # noqa: E731
                       "combination": {"structured": [1, 2, 3, 4, 5, 6, 7, 8]}} for j in range(50)]
    for i in range(300):                     # 15 000 тиражей
        store.add(page(i))
    store.flush()
    assert len(writes) <= 300 // stoloto.FLUSH_MAX_PAGES + 2      # раньше было 60 перезаписей


def test_zero_is_kept_for_game_missing_from_registry():
    """top-3 (так игра называется в API) не было в реестре — нули выбрасывались."""
    raw = {"number": 5, "date": "2026-01-01T10:00:00", "combination": {"structured": [0, 7, 0]}}
    game = stoloto.Game(slug="digits-x", title="digits-x")
    assert stoloto.api_draw_to_draw(raw, game).blocks == ((0, 7, 0),)
    assert get_game("top-3").zero and get_game("top-3").counts == (3,)


def test_damaged_draws_are_repaired_once(monkeypatch, data_dir):
    """Тиражи, сохранённые без нулей, перекачиваются при следующем обновлении."""
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    import random
    rng = random.Random(4)
    full = []
    for i in range(300):
        dt = now - timedelta(hours=300 - i)
        full.append({"number": i + 1, "date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                     "combination": {"structured": [rng.randrange(10) for _ in range(3)]}})
    game = get_game("top-3")
    corrupted = []
    for d in full:
        nums = [v for v in d["combination"]["structured"] if v != 0] or [1]   # как писала 40.2.0
        dt = datetime.strptime(d["date"], "%Y-%m-%dT%H:%M:%S")
        corrupted.append(Draw(d["number"], dt.strftime("%d.%m.%Y %H:%M"), (tuple(nums),)))
    write_draws(draws_path("top-3"), corrupted)
    from lottery.games import write_meta
    write_meta("top-3", first_date="01.01.2000")
    assert len(stoloto.damaged(game, load_game_draws(game))) > 50

    def page(game, d_from, d_to, page, count=50, log=print):
        sel = [d for d in full if d_from.date() <= datetime.strptime(d["date"][:10], "%Y-%m-%d").date() <= d_to.date()]
        return sel[(page - 1) * count: page * count], page * count < len(sel)
    monkeypatch.setattr(stoloto, "archive_page", page)
    monkeypatch.setattr(stoloto, "REQUEST_DELAY", 0)
    res = stoloto.update_game(game, log=lambda m: None)
    assert res["damaged"] == 0
    assert read_meta("top-3")["repaired_v2"]
    data = load_game_data(game)
    assert data.T == 300 and data.fmt.describe().startswith("Позиция 1: 1 из 0–9")


def test_bonus_is_split_for_unknown_game():
    import random
    rng = random.Random(1)
    draws = [Draw(i + 1, "01.01.2026 10:00", (tuple(rng.sample(range(1, 21), 8) + [rng.randint(1, 4)]),))
             for i in range(400)]
    out, split = split_bonus(draws, get_game("rapidopro"))
    assert split and out[0].blocks[1][0] <= 4 and len(out[0].blocks[0]) == 8
    out, split = split_bonus(draws, get_game("rapido"))        # формат есть в реестре — не трогаем
    assert not split


def test_api_titles_are_used(data_dir):
    (data_dir / "api_games.json").write_text(json.dumps(
        {"games": [{"name": "vin", "title": "Винлото", "keys": []}]}, ensure_ascii=False), encoding="utf-8")
    assert get_game("vin").title == "Винлото"
    assert get_game("4x20").title == "4 из 20"              # реестр важнее
    assert stoloto._api_title({"name": "x", "displayName": "Золотое кольцо", "id": 3}) == "Золотое кольцо"
    assert stoloto._api_title({"name": "x", "id": 3}) is None


def test_diagnose_report(data_dir):
    import subprocess
    import sys
    from conftest import ROOT, random_lotto, write_lotto_file
    write_lotto_file(draws_path("5x36"), [random_lotto(200, 36, 5, 1)])
    env = {**os.environ, "LOTTERY_DATA_DIR": str(data_dir)}
    out = subprocess.run([sys.executable, str(ROOT / "python" / "lp.py"), "diagnose"], env=env,
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert out.returncode == 0
    text = (data_dir / "diagnose.txt").read_text(encoding="utf-8")
    assert "OK 5x36 — 5 из 36" in text and "формат: Числа: 5 из 1–36" in text
