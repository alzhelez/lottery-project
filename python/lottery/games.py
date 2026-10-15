"""Реестр игр и пути проекта."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_")


def data_dir() -> Path:
    return Path(os.environ.get("LOTTERY_DATA_DIR", PROJECT_ROOT / "data"))


def draws_path(slug: str) -> Path:
    return data_dir() / "draws" / f"draws_{slug}.txt"


def results_dir(slug: str | None = None) -> Path:
    base = data_dir() / "results"
    return base / slug if slug else base


@dataclass(frozen=True)
class Game:
    slug: str
    title: str
    counts: tuple[int, ...] = ()
    zero: bool = False
    legacy: tuple[str, ...] = field(default_factory=tuple)
    labels: tuple[str, ...] = field(default_factory=tuple)   # названия блоков строки
    range: tuple[int, ...] = ()                               # (lo, hi), если известен заранее
    variable: bool = False      # в реестре "counts": [] — число шаров меняется (бинго)
    picks: tuple[int, ...] = ()  # сколько чисел выбирает игрок в блоке (0 — блок не анализируется)
    excluded: str = ""          # причина, по которой игра не загружается и не показывается

    @property
    def stoloto_url(self) -> str:
        return f"https://www.stoloto.ru/{self.slug}/game/"


@lru_cache(maxsize=1)
def _config() -> dict:
    return json.loads((PROJECT_ROOT / "config" / "games.json").read_text(encoding="utf-8"))


def inactive_days() -> int:
    return int(os.environ.get("LOTTERY_INACTIVE_DAYS", _config().get("inactive_days", 15)))


def meta_path(slug: str) -> Path:
    return draws_path(slug).with_suffix(".meta.json")


def read_meta(slug: str) -> dict:
    try:
        return json.loads(meta_path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_meta(slug: str, **fields) -> None:
    from .fsutil import write_text
    write_text(meta_path(slug), json.dumps({**read_meta(slug), **fields}, ensure_ascii=False))


def activity(last_dt: datetime | None, checked_at: str | None, now: datetime | None = None) -> dict:
    """Игра активна, если последний тираж не старше inactive_days дней на момент последней
    проверки архива (если архив не проверялся — на текущий момент)."""
    now = now or datetime.now()
    ref = now
    if checked_at:
        try:
            ref = datetime.fromisoformat(checked_at)
        except ValueError:
            pass
    days = inactive_days()
    if last_dt is None:
        return {"active": False, "days_since_last": None, "checked_at": checked_at, "threshold": days}
    since = (ref - last_dt).total_seconds() / 86400
    return {"active": since <= days, "days_since_last": round(since, 1), "checked_at": checked_at,
            "data_age_days": round((now - ref).total_seconds() / 86400, 1), "threshold": days}


@lru_cache(maxsize=1)
def _registry() -> dict[str, Game]:
    raw = _config()
    games = {}
    for g in raw["games"]:
        games[g["slug"]] = Game(
            slug=g["slug"],
            title=g.get("title", ""),          # пусто — название возьмётся из ответа API
            counts=tuple(g.get("counts", [])),
            zero=bool(g.get("zero", False)),
            legacy=tuple(g.get("legacy", [])),
            labels=tuple(g.get("labels", [])),
            range=tuple(g.get("range", [])),
            variable="counts" in g and not g["counts"],
            picks=tuple(g.get("picks", [])),
            excluded=g.get("excluded", ""),
        )
    return games


def validate_slug(slug: str) -> str:
    if not slug or len(slug) > 40 or not set(slug) <= SLUG_CHARS:
        raise ValueError(f"Недопустимое имя игры: {slug!r}")
    return slug


def api_titles() -> dict[str, str]:
    """Названия игр из последнего ответа API (data/api_games.json), если они там есть."""
    try:
        raw = json.loads((data_dir() / "api_games.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {g["name"]: g["title"] for g in raw.get("games", []) if g.get("title")}


def get_game(slug: str) -> Game:
    """Игра из реестра; неизвестная игра получает пустые подсказки (формат определится по данным),
    а название — из ответа API или имя игры как есть."""
    validate_slug(slug)
    game = _registry().get(slug)
    if game is None:
        return Game(slug=slug, title=api_titles().get(slug, slug))
    return game if game.title else replace(game, title=api_titles().get(slug, slug))


def all_games() -> list[Game]:
    return list(_registry().values())


def is_excluded(slug: str) -> bool:
    g = _registry().get(slug)
    return bool(g and g.excluded)


def local_slugs() -> list[str]:
    """Игры, по которым есть файл тиражей (кроме исключённых из реестра)."""
    folder = draws_path("x").parent
    if not folder.exists():
        return []
    return sorted(s for s in (p.stem[len("draws_"):] for p in folder.glob("draws_*.txt")) if not is_excluded(s))
