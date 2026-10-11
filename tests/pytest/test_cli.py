import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import ROOT, random_lotto, write_lotto_file


def run(args, data_dir):
    env = {**os.environ, "LOTTERY_DATA_DIR": str(data_dir)}
    out = subprocess.run([sys.executable, str(ROOT / "python" / "lp.py")] + args, capture_output=True,
                         text=True, encoding="utf-8", env=env, timeout=600)
    events = [json.loads(l[2:]) for l in out.stdout.splitlines() if l.startswith("@@")]
    return out.returncode, events


def test_info_scan_analyze(data_dir):
    write_lotto_file(data_dir / "draws" / "draws_5x36.txt", [random_lotto(400, 36, 5, 1)])
    rc, ev = run(["info", "--game", "5x36"], data_dir)
    info = ev[-1]["info"]
    assert rc == 0 and info["draws_valid"] == 400 and info["next_no"] == 401
    assert info["stoloto_url"] == "https://www.stoloto.ru/5x36/game/"
    rc, ev = run(["scan"], data_dir)
    assert rc == 0
    scan = json.loads((data_dir / "results" / "scan.json").read_text(encoding="utf-8"))
    assert scan["games"][0]["slug"] == "5x36" and scan["games"][0]["level"] in ("random", "weak", "signal")
    rc, ev = run(["analyze", "--game", "5x36"], data_dir)
    assert rc == 0 and ev[-1]["type"] == "result"
    res = json.loads(Path(ev[-1]["path"]).read_text(encoding="utf-8"))
    assert res["evaluation"]["status"] == "ok" and res["last_draw_no"] == 400


def test_bad_game_name_is_rejected(data_dir):
    rc, ev = run(["info", "--game", "../etc"], data_dir)
    assert rc == 1 and ev[-1]["type"] == "error"
