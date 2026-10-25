"""Резервная копия того, что нельзя скачать заново, и уборка файлов убранных игр.

Тиражи, таблицы призов и правила всегда можно заново загрузить со Столото, а журнал
прогнозов (data/journal) и «Мои билеты» (data/my_tickets) — нет: это история, накопленная
на этом компьютере. Раз в сутки автозапуск складывает их в архив
backup/lottery-backup-ГГГГ-ММ-ДД.zip — папка рядом с data (или LOTTERY_BACKUP_DIR), чтобы
копия не пропала вместе с папкой data. Хранятся последние KEEP архивов.

Восстановление: `lp.bat backup restore <архив>` — перед этим текущее состояние тоже
сохраняется в архив, а из архива берутся только файлы журнала и билетов.

Уборка: у игр, убранных из программы (поле excluded в config/games.json), удаляются
тиражи, таблицы призов, правила и результаты анализа. Журнал и билеты этих игр сначала
кладутся в архив backup/removed-games-….zip — он не удаляется.
"""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from .games import _registry, data_dir

KEEP = 30
DAILY_RE = re.compile(r"^lottery-backup-(\d{4}-\d{2}-\d{2})\.zip$")
PARTS = ("journal", "my_tickets")          # что входит в архив: папки внутри data
MEMBER_RE = re.compile(r"^(journal|my_tickets)/[a-z0-9_-]+\.json$")


def backup_dir() -> Path:
    env = os.environ.get("LOTTERY_BACKUP_DIR", "").strip()
    return Path(env) if env else data_dir().parent / "backup"


def _files(slugs: set[str] | None = None) -> list[tuple[Path, str]]:
    out = []
    for part in PARTS:
        folder = data_dir() / part
        if not folder.exists():
            continue
        for p in sorted(folder.glob("*.json")):
            if slugs is None or p.stem in slugs:
                out.append((p, f"{part}/{p.name}"))
    return out


def _write_zip(target: Path, files: list[tuple[Path, str]]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p, arc in files:
            try:
                z.write(p, arc)
            except OSError:
                continue      # файл заняли или удалили во время копирования — остальные важнее
    from .fsutil import replace_with_retry
    replace_with_retry(tmp, target)
    return target


def make(name: str | None = None, now: datetime | None = None) -> Path:
    now = now or datetime.now()
    return _write_zip(backup_dir() / (name or f"lottery-backup-{now:%Y-%m-%d}.zip"), _files())


def listing() -> list[dict]:
    d = backup_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.zip"), reverse=True):
        st = p.stat()
        out.append({"name": p.name, "bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
    return out


def rotate(keep: int = KEEP) -> list[str]:
    """Удаляет ежедневные архивы старше последних keep (другие архивы не трогает)."""
    d = backup_dir()
    if not d.exists():
        return []
    daily = sorted((p for p in d.glob("lottery-backup-*.zip") if DAILY_RE.match(p.name)), reverse=True)
    gone = []
    for p in daily[keep:]:
        try:
            p.unlink()
            gone.append(p.name)
        except OSError:
            pass
    return gone


def daily(now: datetime | None = None) -> dict | None:
    """Архив за сегодня, если его ещё нет. None — сегодняшний уже есть или копировать нечего."""
    now = now or datetime.now()
    target = backup_dir() / f"lottery-backup-{now:%Y-%m-%d}.zip"
    if target.exists() or not _files():
        return None
    path = make(now=now)
    return {"path": str(path), "bytes": path.stat().st_size, "removed": rotate()}


def info() -> dict:
    items = listing()
    daily_items = [i for i in items if DAILY_RE.match(i["name"])]
    return {"dir": str(backup_dir()), "count": len(daily_items),
            "last": daily_items[0] if daily_items else None}


def restore(name: str) -> dict:
    """Возвращает журнал и билеты из архива. Перед этим сохраняет текущее состояние."""
    if "/" in name or "\\" in name or not name.endswith(".zip"):
        raise ValueError("укажите имя архива из папки резервных копий")
    src = backup_dir() / name
    if not src.exists():
        raise ValueError(f"архива {name} нет в {backup_dir()}")
    before = make(name=f"before-restore-{datetime.now():%Y-%m-%d-%H%M%S}.zip")
    restored = []
    with zipfile.ZipFile(src) as z:
        for m in z.namelist():
            if not MEMBER_RE.match(m):
                continue        # только файлы журнала и билетов, без путей вида ../
            target = data_dir() / m
            target.parent.mkdir(parents=True, exist_ok=True)
            from .fsutil import write_text
            write_text(target, z.read(m).decode("utf-8"))
            restored.append(m)
    return {"restored": restored, "before": before.name}


# ── уборка файлов убранных игр ─────────────────────────────────────────────

def _game_paths(slug: str) -> list[Path]:
    from .games import draws_path, meta_path, results_dir
    from .prizes import prizes_file
    from .rules import rules_path
    d = data_dir()
    return [draws_path(slug), meta_path(slug), prizes_file(slug), rules_path(slug),
            d / "api_samples" / f"{slug}.json", results_dir(slug),
            d / "journal" / f"{slug}.json", d / "my_tickets" / f"{slug}.json"]


def _size(p: Path) -> int:
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return p.stat().st_size


def remove_excluded(now: datetime | None = None) -> dict:
    """Удаляет файлы игр, убранных из программы. Журнал и билеты этих игр — сначала в архив.
    Возвращает {"games": {игра: байт}, "archive": имя архива или None}."""
    now = now or datetime.now()
    excluded = sorted(s for s, g in _registry().items() if g.excluded)
    found = {s: [p for p in _game_paths(s) if p.exists()] for s in excluded}
    found = {s: ps for s, ps in found.items() if ps}
    if not found:
        return {"games": {}, "archive": None}
    keep = _files(set(found))
    archive = None
    if keep:
        archive = _write_zip(backup_dir() / f"removed-games-{now:%Y-%m-%d-%H%M%S}.zip", keep).name
    freed: dict[str, int] = {}
    for slug, paths in found.items():
        total = 0
        for p in paths:
            try:
                size = _size(p)
                shutil.rmtree(p) if p.is_dir() else p.unlink()
                total += size
            except OSError:
                continue       # файл занят — попробуем в следующем цикле
        freed[slug] = total
    return {"games": freed, "archive": archive}
