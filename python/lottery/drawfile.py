"""Чтение/запись файлов тиражей и определение формата игры.

Формат строки: ``ДД.ММ.ГГГГ ЧЧ:ММ||НОМЕР||a, b, c||d`` — блоки чисел через ``||``.
Старый 3-частный формат (все числа одним блоком) разбивается на блоки по подсказке
``counts`` из реестра игр.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from .fsutil import write_text
from .games import Game, data_dir, draws_path

DATE_FORMATS = ("%d.%m.%Y %H:%M", "%d.%m.%Y")


@dataclass(frozen=True)
class Draw:
    no: int
    date: str  # как в файле: "ДД.ММ.ГГГГ ЧЧ:ММ"
    blocks: tuple[tuple[int, ...], ...]

    @property
    def dt(self) -> datetime | None:
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(self.date.strip(), fmt)
            except ValueError:
                continue
        return None

    def to_line(self) -> str:
        return "||".join([self.date, str(self.no)] + [", ".join(map(str, b)) for b in self.blocks])


def parse_line(line: str, counts: tuple[int, ...] = ()) -> Draw | None:
    """Разбирает строку файла. Возвращает None для пустых/битых строк."""
    line = line.strip()
    if not line or "||" not in line:
        return None
    parts = line.split("||")
    if len(parts) < 3:
        return None
    try:
        no = int(parts[1].strip())
    except ValueError:
        return None
    blocks: list[tuple[int, ...]] = []
    for chunk in parts[2:]:
        nums = []
        for tok in chunk.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                nums.append(int(tok))
            except ValueError:
                return None
        if nums:
            blocks.append(tuple(nums))
    if not blocks:
        return None
    # legacy: всё в одном блоке, а игра многоблочная — режем по подсказке
    if len(blocks) == 1 and len(counts) > 1 and len(blocks[0]) == sum(counts):
        flat, cut = blocks[0], []
        pos = 0
        for c in counts:
            cut.append(flat[pos:pos + c])
            pos += c
        blocks = cut
    return Draw(no=no, date=parts[0].strip(), blocks=tuple(blocks))


def read_draws(path: Path, counts: tuple[int, ...] = ()) -> list[Draw]:
    """Читает файл, убирает дубликаты по номеру (первая запись побеждает), сортирует."""
    if not path.exists():
        return []
    seen: dict[int, Draw] = {}
    with open(path, encoding="utf-8") as f:
        for raw in f:
            d = parse_line(raw, counts)
            if d is not None and d.no not in seen:
                seen[d.no] = d
    return [seen[k] for k in sorted(seen)]


def write_draws(path: Path, draws: list[Draw]) -> None:
    # атомарная замена с повторами: на Windows файл может держать антивирус (см. fsutil)
    text = "\n".join(d.to_line() for d in sorted(draws, key=lambda d: d.no)) + "\n"
    write_text(path, text)


def load_game_draws(game: Game) -> list[Draw]:
    return read_draws(draws_path(game.slug), game.counts)


def merge_legacy(game: Game) -> tuple[int, int]:
    """Сливает legacy-файлы (data/tirazh*.txt) в data/draws. Данные API имеют приоритет.

    Возвращает (добавлено тиражей, конфликтов — тиражей с разными числами).
    """
    if not game.legacy:
        return 0, 0
    current = {d.no: d for d in load_game_draws(game)}
    added = conflicts = 0
    for name in game.legacy:
        for d in read_draws(data_dir() / name, game.counts):
            have = current.get(d.no)
            if have is None:
                current[d.no] = d
                added += 1
            elif [sorted(b) for b in have.blocks] != [sorted(b) for b in d.blocks]:
                conflicts += 1
    if added:
        write_draws(draws_path(game.slug), list(current.values()))
    return added, conflicts


# ── Формат игры ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BlockSpec:
    """Один «прогнозируемый» блок: из диапазона lo..hi прогнозируем count разных чисел.

    Режимы (mode):
      set      — в каждом тираже выпадает ровно count разных чисел («k из N»);
      position — цифровые игры: одна позиция блока, «1 из 10»;
      first    — бинго: первые count шаров последовательности (если порядок известен);
      drawn    — бинго: множество выпавших чисел переменного размера;
      missing  — бинго: числа диапазона, которые НЕ выпали (дополнение).
    Для drawn/missing размер множества в тираже меняется, count — сколько чисел
    прогнозируем, avg — средний размер множества.
    """
    name: str
    source: int            # индекс блока в строке файла
    position: int | None   # позиция внутри блока (для позиционных блоков)
    count: int
    lo: int
    hi: int
    mode: str = "set"
    avg: float = 0.0

    @property
    def size(self) -> int:
        return self.hi - self.lo + 1

    @property
    def variable(self) -> bool:
        return self.mode in ("drawn", "missing")

    def to_dict(self) -> dict:
        return {"name": self.name, "source": self.source, "position": self.position, "count": self.count,
                "lo": self.lo, "hi": self.hi, "mode": self.mode, "avg": self.avg}

    @classmethod
    def from_dict(cls, d: dict) -> "BlockSpec":
        return cls(d["name"], d["source"], d.get("position"), d["count"], d["lo"], d["hi"],
                   d.get("mode", "set"), d.get("avg", 0.0))


def block_values(d: Draw, spec: BlockSpec) -> tuple[int, ...]:
    """Числа тиража, которые относятся к блоку прогноза."""
    vals = d.blocks[spec.source]
    if spec.mode == "position":
        return (vals[spec.position],)
    if spec.mode == "first":
        return tuple(vals[: spec.count])
    if spec.mode == "missing":
        present = set(vals)
        return tuple(v for v in range(spec.lo, spec.hi + 1) if v not in present)
    return tuple(vals)


@dataclass
class GameFormat:
    supported: bool
    blocks: list[BlockSpec] = field(default_factory=list)
    reason: str = ""
    shape: tuple = ()        # по блоку строки: ожидаемое количество чисел или None (переменное)
    min_len: tuple = ()      # по блоку строки: минимальная длина для переменных блоков

    @property
    def bingo(self) -> bool:
        return any(b.variable or b.mode == "first" for b in self.blocks)

    def matches(self, d: Draw) -> bool:
        if len(d.blocks) != len(self.shape):
            return False
        for i, (k, m) in enumerate(zip(self.shape, self.min_len)):
            b = d.blocks[i]
            if k is not None and len(b) != k:
                return False
            if k is None and (len(b) < m or len(set(b)) != len(b)):
                return False
        return all(all(s.lo <= v <= s.hi for v in d.blocks[s.source]) for s in self.blocks)

    def describe(self) -> str:
        if not self.supported:
            return self.reason
        parts = []
        for s in self.blocks:
            if s.variable:
                parts.append(f"{s.name}: прогноз {s.count} из {s.lo}–{s.hi} "
                             f"(в тираже в среднем {s.avg:.1f})".replace(".", ","))
            elif s.mode == "first":
                parts.append(f"{s.name}: {s.count} из {s.lo}–{s.hi} по порядку выпадения")
            else:
                parts.append(f"{s.name}: {s.count} из {s.lo}–{s.hi}")
        return "; ".join(parts)


MIN_SHARE = 0.95
FIRST_BALLS_MAX = 10


def _range(values: list[int], hint: tuple[int, int] | None) -> tuple[int, int] | str:
    if min(values) < 0:
        return "отрицательные числа в данных"
    if hint and hint[0] <= min(values) and max(values) <= hint[1]:
        return hint
    lo = 0 if min(values) == 0 else 1
    hi = max(values)
    if hi - lo + 1 > 200:
        return f"слишком большой диапазон чисел ({lo}–{hi})"
    return lo, hi


def _variable_block(i: int, rows: list[tuple[int, ...]], label: str, hint) -> tuple[list[BlockSpec], int] | str:
    """Блок переменной длины (бинго): выпавшие или невыпавшие числа, а если известен
    порядок — ещё и первые шары."""
    if sum(len(set(r)) == len(r) for r in rows) / len(rows) < MIN_SHARE:
        return f"повторы чисел в блоке {i + 1} переменной длины"
    rows = [r for r in rows if len(set(r)) == len(r) and r]
    rng = _range([v for r in rows for v in r], hint)
    if isinstance(rng, str):
        return rng
    lo, hi = rng
    size = hi - lo + 1
    lens = np.array([len(r) for r in rows])
    long_rows = [r for r in rows if len(r) >= 3]
    ascending = sum(all(a < b for a, b in zip(r, r[1:])) for r in long_rows) / max(len(long_rows), 1)
    specs: list[BlockSpec] = []
    min_len = 1
    plain = label == "Числа"

    def name(part: str) -> str:
        return part[0].upper() + part[1:] if plain else f"{label}: {part}"
    if ascending < 0.5 and "невыпав" not in label.lower():  # числа записаны в порядке выпадения
        k1 = int(min(FIRST_BALLS_MAX, np.percentile(lens, 5)))
        if 1 <= k1 < size:
            specs.append(BlockSpec(name(f"первые {k1} шаров"), i, None, k1, lo, hi, mode="first"))
            min_len = k1
    avg = float(lens.mean())
    if avg / size <= 0.5:
        k = int(np.clip(round(float(np.median(lens))), 1, size - 1))
        specs.append(BlockSpec(label if not plain else "Выпавшие числа", i, None, k, lo, hi, mode="drawn", avg=avg))
    else:
        comp = size - lens
        if np.median(comp) >= 1:
            k = int(np.clip(round(float(np.median(comp))), 1, size - 1))
            specs.append(BlockSpec(name("невыпавшие числа"), i, None, k, lo, hi, mode="missing",
                                   avg=float(comp.mean())))
    if not specs:
        return f"в блоке {i + 1} почти всегда выпадают все числа диапазона"
    return specs, min_len


def split_bonus(draws: list[Draw], game: Game) -> tuple[list[Draw], bool]:
    """Игра не описана в реестре, а API отдаёт все числа одним списком («8 из 20» + бонус
    «1 из 4» подряд). Если первые m чисел всегда разные, последние — тоже разные между собой
    и заметно меньше по диапазону, это два поля: делим. Цифровые игры (повторы внутри
    префикса) не делятся и разбираются по позициям."""
    if game.counts or not draws:
        return draws, False
    if Counter(len(d.blocks) for d in draws).most_common(1)[0][0] != 1:
        return draws, False
    k, n = Counter(len(d.blocks[0]) for d in draws).most_common(1)[0]
    if n / len(draws) < MIN_SHARE or k < 3:
        return draws, False
    rows = [d.blocks[0] for d in draws if len(d.blocks) == 1 and len(d.blocks[0]) == k]
    share = lambda ok: sum(ok) / len(rows)  # noqa: E731
    if share(len(set(r)) == k for r in rows) >= 0.995:
        return draws, False                   # обычное «k из N»
    # равные поля без повторов внутри («Дважды два»: 2+2, «4 из 20 мини»: 4+4)
    for p in range(k // 2, 1, -1):
        if k % p:
            continue
        parts = [(j, j + p) for j in range(0, k, p)]
        if all(share(len(set(r[a:b])) == p for r in rows) >= 0.995 for a, b in parts):
            out = [Draw(d.no, d.date, tuple(d.blocks[0][a:b] for a, b in parts))
                   if len(d.blocks) == 1 and len(d.blocks[0]) == k else d for d in draws]
            return out, True
    for m in range(k - 1, 1, -1):
        if share(len(set(r[:m])) == m for r in rows) < 0.995:
            continue
        if share(len(set(r[m:])) == k - m for r in rows) < 0.995:
            continue
        hi_main = max(max(r[:m]) for r in rows)
        hi_bonus = max(max(r[m:]) for r in rows)
        if hi_bonus <= 0.75 * hi_main:
            out = [Draw(d.no, d.date, (d.blocks[0][:m], d.blocks[0][m:]))
                   if len(d.blocks) == 1 and len(d.blocks[0]) == k else d for d in draws]
            return out, True
    return draws, False


def infer_format(draws: list[Draw], game: Game | None = None, labels: list[str] | None = None) -> GameFormat:
    if not draws:
        return GameFormat(False, reason="нет тиражей")
    nb, nb_cnt = Counter(len(d.blocks) for d in draws).most_common(1)[0]
    if nb_cnt / len(draws) < MIN_SHARE:
        return GameFormat(False, reason="разное количество блоков в тиражах")
    same = [d for d in draws if len(d.blocks) == nb]
    labels = labels or (list(game.labels) if game and game.labels else [])
    hint = tuple(game.range) if game and game.range else None
    shape, min_len, blocks = [], [], []
    for i in range(nb):
        label = labels[i] if i < len(labels) else ("Числа" if nb == 1 else f"Поле {i + 1}")
        k, k_cnt = Counter(len(d.blocks[i]) for d in same).most_common(1)[0]
        if k_cnt / len(same) < MIN_SHARE:
            res = _variable_block(i, [d.blocks[i] for d in same], label, hint)
            if isinstance(res, str):
                return GameFormat(False, reason=res)
            specs, m = res
            blocks.extend(specs)
            shape.append(None)
            min_len.append(m)
            continue
        rows = [d.blocks[i] for d in same if len(d.blocks[i]) == k]
        rng = _range([v for r in rows for v in r], hint)
        if isinstance(rng, str):
            return GameFormat(False, reason=rng)
        lo, hi = rng
        size = hi - lo + 1
        distinct = all(len(set(r)) == len(r) for r in rows)
        shape.append(k)
        min_len.append(k)
        if distinct and k < size:
            blocks.append(BlockSpec(label, i, None, k, lo, hi))
        elif not distinct:
            for j in range(k):
                blocks.append(BlockSpec(f"Позиция {j + 1}", i, j, 1, lo, hi, mode="position"))
        else:
            return GameFormat(False, reason="в каждом тираже выпадают все числа диапазона")
    return GameFormat(True, blocks=blocks, shape=tuple(shape), min_len=tuple(min_len))


def block_matrix(draws: list[Draw], spec: BlockSpec) -> np.ndarray:
    """Матрица T×N индикаторов: X[t, v-lo] = 1, если число v входит в блок тиража t."""
    x = np.zeros((len(draws), spec.size), dtype=np.float32)
    for t, d in enumerate(draws):
        for v in block_values(d, spec):
            x[t, v - spec.lo] = 1.0
    return x


@dataclass
class GameData:
    game: Game
    draws: list[Draw]           # только тиражи, подходящие под формат
    all_count: int              # всего тиражей в файле
    fmt: GameFormat
    matrices: list[np.ndarray]  # по одному на BlockSpec

    @property
    def T(self) -> int:
        return len(self.draws)


def load_game_data(game: Game) -> GameData:
    draws = load_game_draws(game)
    draws, split = split_bonus(draws, game)
    fmt = infer_format(draws, game, labels=["Числа", "Бонус"] if split else None)
    valid = [d for d in draws if fmt.supported and fmt.matches(d)]
    mats = [block_matrix(valid, s) for s in fmt.blocks] if fmt.supported else []
    return GameData(game, valid, len(draws), fmt, mats)


def same_draws(a: list[Draw], b: list[Draw], last: int = 200, min_common: int = 30) -> bool:
    """Одни и те же тиражи под разными именами игр (в API так бывает: «Дважды два» и
    «Охота: вызов», «Crazy Combo» и «Остатки сладки»). Сравниваются общие номера среди
    последних тиражей — у одной игры может быть на пару тиражей больше."""
    ma = {d.no: d.blocks for d in a[-last:]}
    common = [d for d in b[-last:] if d.no in ma]
    return len(common) >= min_common and all(ma[d.no] == d.blocks for d in common)
