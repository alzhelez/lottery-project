#!/usr/bin/env python3
"""Мок API Столото для сквозных тестов: отдаёт тиражи из fixtures/ в формате реального API.

  python tests/mock_stoloto/server.py --port 3199
  STOLOTO_API_BASE=http://127.0.0.1:3199 — направить приложение на мок.

Даты активных игр сдвигаются так, чтобы последний тираж был вчера; «закрытые» игры
(STALE) отдаются с исходными старыми датами — так проверяется деление на активные
и устаревшие игры.
"""
import argparse
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FIXTURES = Path(__file__).parent / "fixtures"
ACTIVE_WITHOUT_ARCHIVE = ["5x36"]
STALE = {"duel"}
# как игра отдаёт числа: list — плоский список; not_played — {"notPlayed": [...]};
# played — {"played": [...], "notPlayed": [остаток диапазона]}
FORMATS = {"ruslotto": "not_played", "bingo75": "played"}
RANGES = {"bingo75": 75}
LOTOTRON = {"4x20"}           # смешанная игра: лототрон в :00, остальное — ГСЧ
HOW = {"4x20": "<p>Тиражи лотереи проходят каждый день в 10:00 (лототрон), 12:07:30 (ГСЧ), 13:00 (лототрон), "
               "13:52:30 (ГСЧ), 16:07:30 (ГСЧ), 16:22:30 (ГСЧ), 18:00 (лототрон), 20:07:30 (ГСЧ), "
               "22:00 (лототрон), 23:22:30 (ГСЧ) мск. Продажи билетов заканчиваются за 5 минут до начала.</p>"
               "<p>Розыгрыши проводят на&nbsp;лототроне, а также с помощью ГСЧ (генератор случайных чисел).</p>",
       "6x45plus": "<p>Розыгрыши проходят каждые 15 минут с помощью генератора случайных чисел.</p>"}
SUPER = {"4x20": 300_000_000, "6x45plus": 45_000_000}


def structured(game: str, nums: list[int]):
    fmt = FORMATS.get(game, "list")
    if fmt == "not_played":
        return {"notPlayed": nums}
    if fmt == "played":
        return {"played": nums, "notPlayed": [v for v in range(1, RANGES[game] + 1) if v not in nums]}
    return nums


PRIZES = {  # тестовая таблица выплат (не реальные суммы Столото)
    "4x20": ({"4+4": 10_000_000, "4+3": 50_000, "3+3": 3000, "3+2": 800, "2+2": 300, "2+1": 150}, 150),
    "6x45plus": ({"6+1": 50_000_000, "6+0": 1_000_000, "5+1": 20_000, "5+0": 5000, "4+1": 1000, "4+0": 500,
                  "3+1": 200, "3+0": 100}, 100),
}


def prize_block(game: str, no: int, nums: list[int]):
    """Категории выплат тиража в форме, похожей на ответ API (число победителей — от номера тиража)."""
    if game not in PRIZES:
        return {}
    table, price = PRIZES[game]
    cats = []
    for i, (key, amount) in enumerate(table.items()):
        winners = 0 if i == 0 else (no * 37 + i * 101) % (40 * (i + 1) ** 2) + 3 * i
        cats.append({"combination": key, "participants": winners, "amount": amount})
    return {"winCategories": cats, "betCost": price}


def load():
    games = {}
    yesterday = datetime.now().replace(second=0, microsecond=0) - timedelta(days=1)
    for f in FIXTURES.glob("*.txt"):
        rows = []
        for line in f.read_text(encoding="utf-8").splitlines():
            parts = line.split("||")
            if len(parts) < 3:
                continue
            rows.append((datetime.strptime(parts[0], "%d.%m.%Y %H:%M"), int(parts[1]),
                         [int(v) for p in parts[2:] for v in p.split(",") if v.strip()]))
        shift = timedelta(0)
        if f.stem not in STALE and rows:
            shift = timedelta(days=(yesterday.date() - max(r[0] for r in rows).date()).days)
        draws = []
        for dt, no, nums in rows:
            dt = dt + shift
            # как в реальном API: у тиражей на лототроне есть видео, тиражи ГСЧ идут «с секундами»
            lototron = f.stem in LOTOTRON and dt.minute == 0
            sec = "00" if f.stem not in LOTOTRON or lototron else "30"
            draws.append({"number": no, "date": dt.strftime(f"%Y-%m-%dT%H:%M:{sec}.000+03:00"),
                          "combination": {"structured": structured(f.stem, nums)}, "_dt": dt,
                          "videoLink": "https://vkvideo.ru/video_ext.php?id=1" if lototron else None,
                          "betsCount": 20000 + (no * 7919) % 5000, "status": "COMPLETED",
                          **prize_block(f.stem, no, nums)})
        games[f.stem] = draws
    return games


GAMES = load()
HELD: dict[str, dict] = {}   # придержанные последние тиражи (для проверки журнала прогнозов)


def hold(games: list[str]) -> None:
    for g in games:
        if GAMES.get(g):
            last = max(GAMES[g], key=lambda d: d["number"])
            GAMES[g].remove(last)
            HELD[g] = last


def release() -> list[int]:
    """Публикует придержанные тиражи как только что сыгранные (время — через 2 минуты,
    чтобы прогноз, сделанный до вызова, считался сделанным до тиража)."""
    out = []
    for g, d in list(HELD.items()):
        dt = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=2)
        d = {**d, "_dt": dt, "date": dt.strftime("%Y-%m-%dT%H:%M:00.000+03:00")}
        GAMES[g].append(d)
        out.append(d["number"])
        del HELD[g]
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path == "/__release":
            return self.send(200, {"released": release()})
        if url.path.endswith("/games/info-new"):
            # закрытая игра по-прежнему числится «активной» в API, но тиражей давно нет
            names = sorted(GAMES) + ACTIVE_WITHOUT_ARCHIVE
            titles = {"top-3": "Топ-3"}   # как в реальном API: название есть не у всех полей
            def next_draw(n):
                if n not in GAMES or n in STALE or not GAMES[n]:
                    return None
                last = max(GAMES[n], key=lambda d: d["number"])
                dt = last["_dt"] + timedelta(hours=2)
                return {"number": last["number"] + 1, "date": int(dt.timestamp()), "superPrize": SUPER.get(n, 10_000_000),
                        "betCost": PRIZES.get(n, ({}, 100))[1], "tvShow": n in LOTOTRON and dt.minute == 0,
                        "winnersDistribitionPers": 50, "jackpotGuaranteed": 10_000_000, "status": "WAITING"}
            return self.send(200, {"games": [{"name": n, "active": True, "draw": next_draw(n),
                                              **({"title": titles[n]} if n in titles else {})}
                                             for n in names]})
        if url.path.endswith("/winning-table"):
            game = url.path.split("/")[-2]
            if game not in PRIZES or not q.get("drawNumber"):
                return self.send(200, {"requestStatus": "error", "errors": ["not valid request"], "winningTable": []})
            rows = []
            for i, (key, amount) in enumerate(PRIZES[game][0].items()):
                g1, g2 = (int(v) for v in key.split("+"))
                rows.append({"guessNumber1": g1, "guessNumber2": g2, "prize": 0 if i == 0 else amount,
                             "superprize": i == 0, "percentprize": None, "wcnumber": i + 1})
            return self.send(200, {"requestStatus": "success", "errors": [], "minPrize": PRIZES[game][1],
                                   "winningTable": rows})
        if "/cms/api/about-lottery-categories/" in url.path:
            game = url.path.rsplit("/", 1)[-1]
            contents = [{"collection": "how_draws_work", "item": {"title": "Как проходят розыгрыши",
                                                                  "text": HOW.get(game), "content": []}},
                        {"collection": "faq", "item": {"rulesFaqs": [
                            {"question": "Как копится суперприз?",
                             "answer": "<p>В призовой фонд уходит {{lottery_winners_distribution_pers}}. "
                                       "Минимальный суперприз — {{lottery_jackpot_guaranteed}}.</p>"}]}},
                        {"collection": "about_prize", "item": {"cards": [{"title": "Призовой фонд",
                                                                          "text": "{{lottery_winners_distribution_pers}}"}]}}]
            return self.send(200, {"data": [{"contents": contents}]})
        if "/cms/api/winning-table-superprize/" in url.path:
            return self.send(200, {"data": []})
        if url.path.endswith("/draws/archive"):
            draws = GAMES.get(q.get("game"), [])
            d_from = datetime.strptime(q["date_from"], "%d.%m.%Y")
            d_to = datetime.strptime(q["date_to"], "%d.%m.%Y")
            sel = [d for d in draws if d_from.date() <= d["_dt"].date() <= d_to.date()]
            sel.sort(key=lambda d: d["number"], reverse=True)   # как на сайте: новые сверху
            count, page = int(q.get("count", 50)), int(q.get("page", 1))
            chunk = sel[(page - 1) * count: page * count]
            return self.send(200, {"draws": [{k: v for k, v in d.items() if k != "_dt"} for d in chunk],
                                   "hasMore": page * count < len(sel)})
        self.send(404, {"error": "not found"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3199)
    ap.add_argument("--hold", action="append", default=[], help="придержать последний тираж игры до /__release")
    args = ap.parse_args()
    port = args.port
    hold(args.hold)
    print(f"mock stoloto on {port}: {', '.join(f'{k}={len(v)}' for k, v in GAMES.items())}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
