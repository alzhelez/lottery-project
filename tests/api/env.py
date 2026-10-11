#!/usr/bin/env python3
"""Тестовое окружение для API-автотестов (Java, Python, Go).

  python tests/api/env.py start   — мок API Столото + загрузка тиражей + приложение на :3100
  python tests/api/env.py stop    — остановить
  python tests/api/env.py run -- <команда>  — поднять, выполнить команду, остановить

Данные — в отдельной папке tests/api/.data (ваши data/ не затрагиваются). Перед запуском
приложение должно быть собрано: npm run build.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = HERE / ".data"
STATE = HERE / ".env-state.json"
APP_PORT = int(os.environ.get("API_TEST_PORT", "3100"))
MOCK_PORT = int(os.environ.get("API_TEST_MOCK_PORT", "3199"))
BASE_URL = f"http://127.0.0.1:{APP_PORT}"
WIN = os.name == "nt"


def _python() -> str:
    return os.environ.get("PYTHON_BIN") or sys.executable


def _spawn(cmd: list[str], env: dict, log: Path) -> subprocess.Popen:
    kwargs = {"cwd": ROOT, "env": env, "stdout": open(log, "w", encoding="utf-8"), "stderr": subprocess.STDOUT}
    if WIN:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True      # чтобы остановить и дочерние процессы (next-server)
    return subprocess.Popen(cmd, **kwargs)


def _wait(url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f"Не дождались {url}")


def start() -> None:
    stop(quiet=True)
    shutil.rmtree(DATA, ignore_errors=True)
    (DATA / "draws").mkdir(parents=True)
    env = {**os.environ, "LOTTERY_DATA_DIR": str(DATA), "STOLOTO_API_BASE": f"http://127.0.0.1:{MOCK_PORT}",
           "STOLOTO_DELAY": "0", "LOTTERY_ENV_FILE": str(DATA / ".env"), "LOTTERY_JSON": "1",
           "PYTHON_BIN": _python()}
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):   # тесты не должны слать уведомления
        env.pop(key, None)
    mock = _spawn([_python(), "tests/mock_stoloto/server.py", "--port", str(MOCK_PORT)], env, HERE / "mock.log")
    _wait(f"http://127.0.0.1:{MOCK_PORT}/p/api/mobile/api/v35/service/games/info-new", 30)
    print("Загружаю тиражи с мока API…", flush=True)
    subprocess.run([_python(), "python/lp.py", "fetch"], cwd=ROOT, env=env, check=True,
                   stdout=subprocess.DEVNULL, timeout=600)
    npx = "npx.cmd" if WIN else "npx"
    app = _spawn([npx, "next", "start", "-p", str(APP_PORT)], env, HERE / "app.log")
    _wait(f"{BASE_URL}/api/games", 120)
    STATE.write_text(json.dumps({"pids": [mock.pid, app.pid], "base_url": BASE_URL}), encoding="utf-8")
    print(f"Окружение готово: {BASE_URL}", flush=True)


def _kill(pid: int) -> None:
    try:
        if WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def stop(quiet: bool = False) -> None:
    if not STATE.exists():
        return
    for pid in json.loads(STATE.read_text(encoding="utf-8")).get("pids", []):
        _kill(pid)
    STATE.unlink(missing_ok=True)
    if not quiet:
        print("Окружение остановлено")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "run":
        rest = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        start()
        try:
            code = subprocess.run(rest, cwd=ROOT, env={**os.environ, "API_BASE_URL": BASE_URL}, shell=WIN).returncode if rest else 0
        finally:
            stop()
        sys.exit(code)
    else:
        raise SystemExit("Использование: env.py start | stop | run -- <команда>")


if __name__ == "__main__":
    main()
