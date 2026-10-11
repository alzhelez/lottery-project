"""Уведомления в Telegram — на поддельном Bot API (настоящий Telegram в тестах не нужен)."""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import ROOT

from lottery import notify


class FakeBotApi:
    """Минимальный Bot API: getMe, getUpdates, sendMessage. Токен «bad» → 401."""

    def __init__(self):
        self.messages = []
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                token, method = self.path.split("/")[1][3:], self.path.split("/")[2]
                if token == "bad":
                    return self.reply(401, {"ok": False, "description": "Unauthorized"})
                if method == "getMe":
                    return self.reply(200, {"ok": True, "result": {"username": "lottery_test_bot"}})
                if method == "getUpdates":
                    return self.reply(200, {"ok": True, "result": [
                        {"message": {"chat": {"id": 4242, "type": "private", "first_name": "Александр"}}}]})
                if method == "sendMessage":
                    api.messages.append(body)
                    return self.reply(200, {"ok": True, "result": {}})
                self.reply(404, {"ok": False})

            def reply(self, code, payload):
                data = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def bot(monkeypatch, tmp_path):
    api = FakeBotApi()
    monkeypatch.setenv("TELEGRAM_API_BASE", api.base)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "4242")
    monkeypatch.setenv("LOTTERY_ENV_FILE", str(tmp_path / ".env"))
    yield api
    api.server.shutdown()


def test_not_configured_sends_nothing(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert not notify.config()["configured"]
    assert notify.send("x") is False


def test_send_and_split_long_messages(bot):
    assert notify.send("<b>Привет</b>", "journal")
    assert bot.messages[0] == {"chat_id": "4242", "text": "<b>Привет</b>\n", "parse_mode": "HTML",
                               "disable_web_page_preview": True}
    long = "\n".join(f"строка {i} " + "х" * 80 for i in range(120))
    assert notify.send(long, "auto")
    assert len(bot.messages) == 1 + 3 and all(len(m["text"]) <= 4096 for m in bot.messages)


def test_disabled_event_and_bad_token(bot, monkeypatch, data_dir):
    monkeypatch.setenv("TELEGRAM_EVENTS", "journal")
    assert notify.send("x", "auto") is False and not bot.messages
    assert notify.send("x", "auto", force=True)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bad")
    assert notify.send("x", "journal") is False
    assert "Unauthorized" in (data_dir / "logs" / "telegram.log").read_text(encoding="utf-8")


def test_journal_message_text():
    entries = [{"status": "checked", "draw_no": 501, "actual": [[1, 2, 3, 4], [5, 6, 7, 8]],
                "source_title": "Лучший метод анализа", "hits": 3, "expected": 1.6, "won": 800.0},
               {"status": "late", "draw_no": 501, "actual": [[1, 2, 3, 4], [5, 6, 7, 8]],
                "source_title": "Режим Бога", "hits": 1, "expected": 1.6}]
    text = notify.journal_message("4 из 20", entries)
    assert "Тираж №501" in text and "угадано 3 при ожидаемых 1,60, выигрыш 800 ₽" in text
    assert "не засчитан" in text and "<code>1 2 3 4 | 5 6 7 8</code>" in text


def run(args, data_dir, env_extra):
    env = {**os.environ, "LOTTERY_DATA_DIR": str(data_dir), **env_extra}
    out = subprocess.run([sys.executable, str(ROOT / "python" / "lp.py")] + args, capture_output=True,
                         text=True, encoding="utf-8", env=env, timeout=60)
    events = [json.loads(l[2:]) for l in out.stdout.splitlines() if l.startswith("@@")]
    return out.returncode, events


def test_cli_setup_writes_chat_id_and_test_sends(bot, data_dir, tmp_path, monkeypatch):
    env = {"TELEGRAM_API_BASE": bot.base, "TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "",
           "LOTTERY_ENV_FILE": str(tmp_path / ".env")}
    rc, ev = run(["telegram", "setup"], data_dir, env)
    assert rc == 0 and ev[-1]["bot"] == "lottery_test_bot" and ev[-1]["chats"][0]["id"] == 4242
    assert "TELEGRAM_CHAT_ID=4242" in (tmp_path / ".env").read_text(encoding="utf-8")
    env.pop("TELEGRAM_CHAT_ID")
    rc, ev = run(["telegram", "test"], data_dir, {**env, "TELEGRAM_CHAT_ID": "4242"})
    assert rc == 0 and ev[-1]["sent"] and "уведомления работают" in bot.messages[-1]["text"]
    rc, ev = run(["telegram", "status"], data_dir, {**env, "TELEGRAM_CHAT_ID": "4242"})
    assert ev[-1]["telegram"]["configured"]


def test_fetch_notifies_about_checked_predictions(bot, monkeypatch, data_dir):
    from datetime import datetime, timedelta

    from test_stoloto import FakeApi

    from lottery import journal, stoloto
    from lottery.drawfile import load_game_data
    from lottery.games import get_game
    api = FakeApi(datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=99), 100)
    last = api.draws.pop()                                     # тираж №100 ещё «не состоялся»
    monkeypatch.setattr(stoloto, "archive_page", api.archive_page)
    monkeypatch.setattr(stoloto, "has_draws", api.has_draws)
    monkeypatch.setattr(stoloto, "REQUEST_DELAY", 0)
    stoloto.update_game(get_game("4x20"), log=lambda m: None)
    data = load_game_data(get_game("4x20"))
    journal.record(data, "analysis_best", [[1, 2, 3, 4], [5, 6, 7, 8]], now=datetime.now() - timedelta(days=2))
    api.draws.append(last)
    res = stoloto.update_game(get_game("4x20"), log=lambda m: None)
    assert res["journal_checked"] == 1
    assert any("сверка прогнозов" in m["text"] and "Тираж №100" in m["text"] for m in bot.messages)
