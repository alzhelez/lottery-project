"""Проверка всех игр на случайность: с кэшем и в несколько процессов.

Тесты игры пересчитываются, только если в её архиве что-то изменилось (последний тираж,
число тиражей, формат или версия программы). Остальные результаты берутся из прошлого
scan.json. Изменившиеся игры считаются параллельно — по процессу на ядро (не больше 4).
Поправка Бенджамини–Хохберга по играм всегда пересчитывается заново.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

from . import __version__
from .drawfile import load_game_data
from .fsutil import write_text
from .games import draws_path, get_game, results_dir
from .stats import finalize_scan, game_randomness


def local_slugs() -> list[str]:
    out = []
    for p in sorted(draws_path("x").parent.glob("draws_*.txt")):
        slug = p.stem[len("draws_"):]
        try:
            if get_game(slug).excluded:
                continue
        except ValueError:
            continue
        out.append(slug)
    return out


def signature(slug: str) -> dict:
    """Дешёвая подпись архива: размер файла, хэш его конца и версия программы.
    Время изменения не годится — загрузчик может переписать файл тем же содержимым."""
    import hashlib
    path = draws_path(slug)
    size = path.stat().st_size
    with open(path, "rb") as f:
        f.seek(max(0, size - 4096))
        tail = hashlib.sha1(f.read()).hexdigest()[:16]
    return {"size": size, "tail": tail, "version": __version__}


def scan_game(slug: str) -> dict:
    """Тесты одной игры (запускается и в отдельном процессе)."""
    res = game_randomness(load_game_data(get_game(slug)))
    res["signature"] = signature(slug)
    res["computed_at"] = datetime.now().isoformat(timespec="seconds")
    return res


MAX_AGE_H = 12
GROWTH = 0.02


def _fresh_enough(old: dict, slug: str) -> bool:
    """Архив вырос меньше чем на 2%, тесты моложе 12 часов, версия та же — несколько новых
    тиражей к десяткам тысяч результат не меняют, пересчёт каждый час не нужен."""
    sig = old.get("signature") or {}
    if sig.get("version") != __version__ or not old.get("computed_at") or not sig.get("size"):
        return False
    try:
        age_h = (datetime.now() - datetime.fromisoformat(old["computed_at"])).total_seconds() / 3600
        size = draws_path(slug).stat().st_size
    except (OSError, ValueError):
        return False
    return age_h <= MAX_AGE_H and sig["size"] <= size <= sig["size"] * (1 + GROWTH)


def workers() -> int:
    return max(1, min(4, (os.cpu_count() or 2) - 1))


def run_scan(progress=None, parallel: bool = True) -> dict:
    path = results_dir() / "scan.json"
    try:
        previous = {g["slug"]: g for g in json.loads(path.read_text(encoding="utf-8")).get("games", [])}
    except (OSError, ValueError):
        previous = {}
    slugs = local_slugs()
    results: dict[str, dict] = {}
    todo = []
    for slug in slugs:
        old = previous.get(slug)
        if old and (old.get("signature") == signature(slug) or _fresh_enough(old, slug)):
            results[slug] = old
        else:
            todo.append(slug)
    done = len(results)
    if progress:
        progress({"done": done, "total": len(slugs), "cached": done})
    if todo and parallel and workers() > 1 and len(todo) > 1:
        # spawn: после бустинга в анализе (OpenMP) процессы, созданные fork, могут зависнуть
        import multiprocessing
        with ProcessPoolExecutor(max_workers=workers(), mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = {pool.submit(scan_game, s): s for s in todo}
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result()
                done += 1
                if progress:
                    progress({"done": done, "total": len(slugs), "game": futures[fut]})
    else:
        for slug in todo:
            results[slug] = scan_game(slug)
            done += 1
            if progress:
                progress({"done": done, "total": len(slugs), "game": slug})
    games = finalize_scan([results[s] for s in slugs])
    payload = {"version": __version__, "generated_at": datetime.now().isoformat(timespec="seconds"),
               "games": games, "recomputed": len(todo)}
    write_text(path, json.dumps(payload, ensure_ascii=False, default=float))
    return payload
