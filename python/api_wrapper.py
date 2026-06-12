#!/usr/bin/env python3
"""
Unified API wrapper for lottery analysis web app.

CRITICAL: All output goes to stdout as JSON. Debug/errors go to stderr.
         No print() calls — only json.dumps() to stdout.
         This prevents "Unexpected token '<'" errors on the frontend.

Usage:
    python3 api_wrapper.py games
    python3 api_wrapper.py draws --game 4x20
    python3 api_wrapper.py analyze --game 4x20
"""
import sys
import os
import json
import argparse
import time
import requests as _req

# Add upload dir to path
_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'upload')
if os.path.isdir(_UPLOAD_DIR):
    sys.path.insert(0, _UPLOAD_DIR)

# ── Save real stdout BEFORE any monkey-patching ───────────────────
_real_stdout = sys.stdout

# ── Suppress all print() output (redirect to stderr) BEFORE import ────
# This prevents any stdout pollution from module-level code during import.
_orig_print = print
def _quiet_print(*a, **kw):
    _orig_print(*a, file=sys.stderr, **{k: v for k, v in kw.items() if k != 'file'})
import builtins
builtins.print = _quiet_print

# ── Import Stoloto constants (not functions — we implement our own to control output) ──
import importlib.util

# Look for stoloto_analyzer_v3.py in python/ first, then upload/
_cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stoloto_analyzer_v3.py')
if not os.path.exists(_cfg_path):
    _cfg_path = os.path.join(_UPLOAD_DIR, 'stoloto_analyzer_v3.py')

_spec = importlib.util.spec_from_file_location(
    "stoloto_cfg",
    _cfg_path,
)
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)

BASE = _cfg.BASE
HEADERS = dict(_cfg.HEADERS)
COOKIES = dict(_cfg.COOKIES)
MAX_DRAWS_PER_GAME = 15000
DRAWS_PER_PAGE = 50
REQUEST_DELAY = 0.5
GameStats = _cfg.GameStats
extract_numbers = _cfg.extract_numbers

# ── Output helpers — ALWAYS write to _real_stdout ─────────────────────
def _ok(data: dict):
    data["status"] = "ok"
    _orig_print(json.dumps(data, ensure_ascii=False, default=str), file=_real_stdout)

def _err(msg: str, extra: dict | None = None):
    result = {"status": "error", "error": msg}
    if extra:
        result.update(extra)
    _orig_print(json.dumps(result, ensure_ascii=False), file=_real_stdout)

def _get_games_raw() -> list[dict]:
    """Fetch active games — our own implementation (no print, no sys.exit)."""
    hdrs = dict(HEADERS)
    hdrs["gosloto-token"] = "161aa1be13-07d882-41dd32-8fa380-de2eea7bf30a66"
    r = _req.get(f"{BASE}/games/info-new", headers=hdrs, cookies=COOKIES, timeout=15)
    r.raise_for_status()
    data = r.json()
    return [g for g in data.get("games", []) if g.get("active") and g.get("name")]


def _fetch_draws_raw(game_name: str, max_draws: int = 200) -> list[dict]:
    """Fetch draws — our own implementation (no print, no sys.exit)."""
    url = f"{BASE}/draws/archive"
    result = []
    page = 1
    while len(result) < max_draws:
        params = {"game": game_name, "count": DRAWS_PER_PAGE, "page": page}
        try:
            r = _req.get(url, headers=HEADERS, cookies=COOKIES, params=params, timeout=15)
            if r.status_code in (400, 404, 405):
                break
            r.raise_for_status()
            data = r.json()
        except _req.exceptions.HTTPError:
            break
        except Exception:
            break
        draws_page = data.get("draws", [])
        if not draws_page:
            break
        result.extend(draws_page)
        if not data.get("hasMore", False):
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return result[:max_draws]


def cmd_games():
    try:
        games = _get_games_raw()
        result = []
        for g in games:
            cd = g.get("completedDraw", {})
            # Extract last draw numbers for preview
            nums = extract_numbers(cd) if cd else []
            result.append({
                "name": g.get("name", ""),
                "description": g.get("description", ""),
                "active": g.get("active", False),
                "completedDraw": {
                    "number": cd.get("number"),
                    "superPrize": cd.get("superPrize"),
                },
                "lastNumbers": nums[:12],  # preview (max 12)
                "lastNumbersTotal": len(nums),
            })
        _ok({"count": len(result), "games": result})
    except Exception as e:
        _err(str(e))


def cmd_draws(game, max_draws=200):
    try:
        draws = _fetch_draws_raw(game, max_draws)
        result = []
        for d in draws:
            nums = extract_numbers(d)
            result.append({
                "number": d.get("number", d.get("drawNumber", "")),
                "date": d.get("date", d.get("drawDate", "")),
                "numbers": nums,
                "superPrize": d.get("superPrize"),
                "jackpot": d.get("jackpot", d.get("superPrize")),
            })
        _ok({"game": game, "total": len(result), "draws": result})
    except Exception as e:
        _err(str(e), {"game": game})


def cmd_analyze(game, max_draws=200):
    try:
        draws = _fetch_draws_raw(game, max_draws)
        if not draws:
            _err("No draws found", {"game": game})
            return
        stats = GameStats(game)
        for d in draws:
            nums = extract_numbers(d)
            if nums:
                stats.add(nums)
        report = stats.report()
        _ok({"game": game, "report": report})
    except Exception as e:
        _err(str(e), {"game": game})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Lottery API wrapper')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('games')

    dp = sub.add_parser('draws')
    dp.add_argument('--game', type=str, default='4x20')
    dp.add_argument('--max-draws', type=int, default=200)

    ap = sub.add_parser('analyze')
    ap.add_argument('--game', type=str, default='4x20')
    ap.add_argument('--max-draws', type=int, default=200)

    args = parser.parse_args()

    if args.command == 'games':
        cmd_games()
    elif args.command == 'draws':
        cmd_draws(args.game, args.max_draws)
    elif args.command == 'analyze':
        cmd_analyze(args.game, args.max_draws)
    else:
        _err("Unknown command")
