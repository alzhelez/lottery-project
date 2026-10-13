"""Надёжная запись файлов на Windows.

Файл пишется во временный и подменяет оригинал (`os.replace`) — так он никогда не бывает
«наполовину записан». Но на Windows подмена падает с PermissionError (WinError 5 / 32),
пока файл держит другой процесс: антивирус (Защитник Windows проверяет каждый новый
файл), индексатор поиска, OneDrive, редактор, который открыл файл. Обычно это доли
секунды, поэтому подмену повторяем с нарастающей паузой, а если файл так и не
освободился — пишем напрямую поверх (уже не атомарно, но данные не теряются).
"""
from __future__ import annotations

import os
import stat
import threading
import time
from pathlib import Path

ATTEMPTS = 12          # ≈ 10 секунд ожидания в сумме


# через переменную модуля — тесты подменяют только запись этого модуля, не os.replace целиком
_replace = os.replace

def _pause(attempt: int) -> None:
    time.sleep(min(0.05 * 2 ** attempt, 2.0))


def _tmp_name(path: Path) -> Path:
    # своё имя для каждого процесса и потока: прошлый «зависший» .tmp не мешает записи
    return path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")


def replace_with_retry(src: Path, dst: Path, attempts: int = ATTEMPTS) -> None:
    for attempt in range(attempts):
        try:
            _replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            _pause(attempt)


def _write(path: Path, data: bytes, attempts: int = ATTEMPTS) -> None:
    for attempt in range(attempts):
        try:
            with open(path, "wb") as f:
                f.write(data)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            _pause(attempt)


def write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_name(path)
    try:
        _write(tmp, data)
        try:
            replace_with_retry(tmp, path)
        except PermissionError:
            _write(path, data)        # подмена не удалась — пишем поверх оригинала
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        except PermissionError:
            pass                      # удалится при следующей записи или вручную


def write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    write_bytes(path, text.encode(encoding))


def cleanup_stale_tmp(folder: Path, older_than_s: float = 3600) -> int:
    """Удаляет брошенные временные файлы (от прерванных записей)."""
    removed = 0
    now = time.time()
    if not folder.exists():
        return 0
    for p in folder.glob("*.tmp"):
        try:
            if now - p.stat().st_mtime > older_than_s:
                try:
                    p.unlink()
                except PermissionError:
                    # на Windows файл «только для чтения» не удаляется — снимаем атрибут
                    os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
                    p.unlink()
                removed += 1
        except OSError:
            pass
    return removed
