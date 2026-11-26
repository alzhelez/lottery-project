"""Точки отсчёта после изменения правил лотереи.

Архив тиражей не удаляется. Точка отсчёта ограничивает данные, которые видят анализ,
история прогнозов, доверие к методам и режим Бога. Старые записи журнала остаются
для аудита, но не участвуют в новом расчёте доверия.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .fsutil import write_text
from .games import data_dir

if TYPE_CHECKING:
    from .drawfile import GameData

RESETS_VERSION = 1

CHANGES_PATH = Path(__file__).resolve().parents[2] / "config" / "game_changes.json"
RESETS_PATH = data_dir() / "game_resets.json"


def parse_date(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Непонятная дата: {value!r}") from exc


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_changes() -> dict:
    payload = _load_json(CHANGES_PATH)
    return payload.get("games") or {}


def changes(slug: str) -> list[dict]:
    rows = load_changes().get(slug) or []
    return sorted(rows, key=lambda r: parse_date(r["date"]))


def latest_change(slug: str) -> datetime | None:
    rows = changes(slug)
    return parse_date(rows[-1]["date"]) if rows else None


def load_resets() -> dict:
    payload = _load_json(RESETS_PATH)
    payload.setdefault("version", RESETS_VERSION)
    payload.setdefault("games", {})
    return payload


def save_resets(payload: dict) -> None:
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    RESETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_text(RESETS_PATH, json.dumps(payload, ensure_ascii=False, indent=1))


def set_reset(slug: str, date: str | datetime, reason: str = "") -> dict:
    dt = parse_date(date)
    payload = load_resets()
    payload["games"][slug] = {
        "date": dt.date().isoformat(),
        "reason": reason,
        "set_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_resets(payload)
    return reset_info(slug)


def clear_reset(slug: str) -> None:
    payload = load_resets()
    payload.get("games", {}).pop(slug, None)
    save_resets(payload)


def get_reset(slug: str) -> datetime | None:
    row = load_resets().get("games", {}).get(slug)
    return parse_date(row["date"]) if row and row.get("date") else None


def reset_info(slug: str) -> dict:
    row = load_resets().get("games", {}).get(slug)
    if not row:
        return {"active": False, "slug": slug}
    return {
        "active": True,
        "slug": slug,
        "from": row["date"],
        "reason": row.get("reason", ""),
        "set_at": row.get("set_at"),
    }


def effective_since(slug: str, since: datetime) -> datetime:
    """Начало периода доверия: выбранный период не может начаться раньше точки отсчёта."""
    reset = get_reset(slug)
    return max(since, reset) if reset else since


def apply(data: "GameData") -> tuple["GameData", dict]:
    """Ограничивает GameData тиражами от точки отсчёта. Без точки возвращает исходные данные."""
    reset = get_reset(data.game.slug)
    if reset is None:
        return data, {"active": False, "slug": data.game.slug, "draws": data.T}

    idx = np.array(
        [i for i, d in enumerate(data.draws) if getattr(d, "dt", None) is not None and d.dt >= reset],
        dtype=np.int64,
    )
    if len(idx) == 0:
        raise ValueError(
            f"После {reset.date().isoformat()} в архиве «{data.game.slug}» нет тиражей"
        )

    from .mechanics import subset

    scoped = subset(data, idx)
    return scoped, {
        "active": True,
        "slug": data.game.slug,
        "from": reset.isoformat(timespec="seconds"),
        "first_no": scoped.draws[0].no,
        "last_no": scoped.draws[-1].no,
        "draws": scoped.T,
        "skipped_draws": data.T - scoped.T,
    }