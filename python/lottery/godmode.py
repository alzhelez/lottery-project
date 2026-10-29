"""«Режим Бога»: потиражное предсказание с адаптацией модели.

Для каждого тиража t по порядку:
  1. все эксперты (модели) делают прогноз по тиражам < t;
  2. мета-стратегия выбирает модель или взвешивает их по прошлой точности;
  3. после тиража t точность каждого эксперта обновляется — и на тираж t+1 модель
     может смениться.

Мета-стратегии:
  • «лидер за W тиражей» — берём прогноз модели, лучшей за последние W тиражей;
  • «Hedge» — экспоненциальные веса по накопленному выигрышу над случайным
    (с забыванием γ), прогноз — взвешенное голосование экспертов.

Прогноз даёт стратегия «лидер за всю историю» (выбрана заранее); остальные мета-стратегии
считаются для сравнения. Честность: эксперты отбираются по первой половине отрезка, а
результат показывается по второй половине, которая на отбор не влияла.

Пул экспертов расширяется по стадиям, пока перебор не исчерпан (40 пачек смесей подряд без
улучшения) или не прошло 8 часов; после каждой стадии результат сохраняется (можно смотреть
промежуточный итог).

Версия с контролем памяти через psutil и resource.
"""
from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
import warnings

import numpy as np
import psutil
from scipy.signal import lfilter

from .drawfile import GameData
from .fsutil import replace_with_retry, write_text
from .evaluate import Evaluator, metrics, rolling_curve, warmup_size
from .models import Model, expert_grid, gbm_scores, standard_models, tie_noise, top_k
from .stats import hypergeom_moments, ru

# Настройка logging
logger = logging.getLogger(__name__)


# ── Контроль памяти ────────────────────────────────────────────────────────

class MemoryMonitor:
    """Мониторинг и ограничение использования памяти."""

    def __init__(self, max_gb: float = 3.0, warn_gb: float = 2.5):
        """
        Args:
            max_gb: Максимально допустимая память (ГБ). При превышении - попытка очистки.
            warn_gb: Порог предупреждения (ГБ).
        """
        self.max_bytes = int(max_gb * 1024 ** 3)
        self.warn_bytes = int(warn_gb * 1024 ** 3)
        self.process = psutil.Process()

        # Попытка установить hard limit (только Linux/macOS)
        if sys.platform != 'win32':
            try:
                import resource
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (self.max_bytes, self.max_bytes)
                )
                logger.info(f"✓ Установлен лимит памяти: {max_gb:.1f} ГБ")
            except (ImportError, ValueError, OSError) as e:
                logger.warning(f"Не удалось установить hard limit памяти: {e}")

    def current_usage_gb(self) -> float:
        """Текущее использование памяти процессом в ГБ."""
        try:
            return self.process.memory_info().rss / 1024 ** 3
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def check(self) -> tuple[bool, str]:
        """
        Проверка использования памяти.

        Returns:
            (is_critical, message): is_critical=True если нужна немедленная очистка
        """
        usage_gb = self.current_usage_gb()

        if usage_gb >= self.max_bytes / 1024 ** 3:
            return True, f"❌ КРИТИЧНО: память {usage_gb:.2f} ГБ (лимит {self.max_bytes / 1024 ** 3:.1f} ГБ)"

        if usage_gb >= self.warn_bytes / 1024 ** 3:
            return False, f"⚠️ Высокое использование памяти: {usage_gb:.2f} ГБ"

        return False, f"✓ Память в норме: {usage_gb:.2f} ГБ"

    def emergency_cleanup(self, pool=None):
        """
        Экстренная очистка памяти.

        Args:
            pool: ExpertPool для очистки кэша и сокращения экспертов
        """
        usage_before = self.current_usage_gb()
        logger.warning(f"🧹 Начата экстренная очистка памяти (текущее: {usage_before:.2f} ГБ)")

        if pool is not None:
            # Сократить пул экспертов наполовину
            original_limit = getattr(pool, 'limit', MAX_EXPERTS)
            pool.prune(limit=original_limit // 2)
            logger.info(f"  • Сокращен пул экспертов до {original_limit // 2}")

            # Очистить кэш признаков
            for f in pool.ev.features:
                freed = f.trim(CACHE_BYTES // 4)  # Агрессивная очистка
                if freed > 0:
                    logger.info(f"  • Освобождено {freed / 1024 ** 2:.1f} МБ кэша")

        # Принудительная сборка мусора
        import gc
        collected = gc.collect()
        logger.info(f"  • Собран мусор: {collected} объектов")

        usage_after = self.current_usage_gb()
        freed_mb = (usage_before - usage_after) * 1024
        logger.info(f"✓ Освобождено ~{freed_mb:.0f} МБ, текущее: {usage_after:.2f} ГБ")

LEADER_WINDOWS = (50, 100, 250, 500, 1000, None)
HEDGE_PARAMS = [(eta, g) for eta in (0.02, 0.1, 0.5) for g in (1.0, 0.995, 0.98)]
SEARCH_BATCH = 20
MAX_EXPERTS = 800          # больше — слабейшие по первой половине вытесняются
STAGNATION_BATCHES = 40    # столько пачек подряд без улучшения — поиск исчерпан
SAVE_EVERY_S = 300         # состояние на диск не чаще раза в 5 минут (и в конце стадий)


STATE_MAX_AGE_DAYS = 14   # сохранения режима Бога старше — удаляются
MIN_BUDGET_S = 60.0
CHECKPOINT_EVERY_S = 600   # промежуточный итог поиска — раз в 10 минут (пересчёт стратегий дорогой)


def _compact(h: np.ndarray) -> np.ndarray:
    """Угаданных за тираж — целое от 0 до суммы полей: храним байтом, а не float32
    (в 4 раза меньше памяти и места на диске)."""
    return h.astype(np.uint8 if h.max(initial=0) < 256 else np.uint16)


def state_files(path) -> list:
    return [path, path.with_suffix(".json")]


def drop_state(path, keep_summary: bool = False) -> None:
    for p in state_files(path)[: 1 if keep_summary else 2]:
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def cleanup_states(results_root, max_age_days: float = STATE_MAX_AGE_DAYS) -> int:
    """Удаляет старые сохранения (и брошенные временные файлы) во всех играх."""
    removed = 0
    if not results_root.exists():
        return 0
    limit = time.time() - max_age_days * 86400
    for p in (list(results_root.glob("*/godmode_state.npz")) + list(results_root.glob("*/godmode_all_state.npz"))
              + list(results_root.glob("*/.godmode_state.*.tmp.npz")) + list(results_root.glob("*/.godmode_all_state.*.tmp.npz"))):
        try:
            if p.stat().st_mtime < limit or p.name.startswith("."):
                drop_state(p) if not p.name.startswith(".") else p.unlink()
                removed += 1
        except OSError:
            pass
    return removed


POOL_MEMORY = 0.8e9   # байт: прогнозы экспертов и мета-стратегии на длинной истории
CACHE_BYTES = 400e6   # байт: промежуточные матрицы признаков (частоты в окнах и т. п.)


def expert_limit(data: GameData, warm: int) -> int:
    """Сколько экспертов держать: у игр с сотнями тысяч проверяемых тиражей 800 экспертов
    не помещаются в память (прогнозы, накопленные суммы стратегий), поэтому меньше."""
    rows = max(1, data.T - warm)
    per_expert = rows * (16 + sum(s.count for s in data.fmt.blocks))
    return int(max(120, min(MAX_EXPERTS, POOL_MEMORY // per_expert)))


class ExpertPool:
    def __init__(self, data: GameData, warm: int | None = None):
        self.data = data
        self.ev = Evaluator(data)
        # warm — сколько первых тиражей только для обучения; проверка — с тиража warm
        self.warm = warmup_size(data.T) if warm is None else int(min(max(warm, 30), data.T - 60))
        self.limit = expert_limit(data, self.warm)
        self.fixed_warm = warm
        self.models: list[Model] = []
        self.hits: list[np.ndarray] = []           # по эксперту: hits на [warm, T)
        self.picks: list[list[np.ndarray]] = []    # по эксперту, по блоку: (T+1−warm)×k

    def add(self, model: Model) -> None:
        if any(m.key == model.key for m in self.models):
            return
        p = self.ev.picks(model)
        h = self.ev.hits(p)
        self.models.append(model)
        self.hits.append(_compact(h[self.warm:]))
        # храним прогнозы компактно (номера < 256), полные матрицы оценок освобождаем
        self.picks.append([pb[self.warm:].astype(np.uint8) for pb in p])
        for f in self.ev.features:
            f._cache.pop(("model", model.key), None)
            f._cache.pop(("picks", model.key), None)
            f.trim(CACHE_BYTES / max(1, len(self.ev.features)))

    def half(self) -> int:
        return (self.data.T - self.warm) // 2

    def first_half_score(self, i: int) -> float:
        return float(self.hits[i][: self.half()].mean())

    def prune(self, limit: int | None = None) -> int:
        """Оставляет limit экспертов: контрольные всегда, остальные — лучшие по ПЕРВОЙ половине.
        Вторая половина в отборе не участвует, поэтому её оценка остаётся честной."""
        limit = limit or self.limit
        if len(self.models) <= limit:
            return 0
        keep = [i for i, m in enumerate(self.models) if m.control]
        rest = sorted((i for i, m in enumerate(self.models) if not m.control),
                      key=lambda i: -self.first_half_score(i))
        keep = sorted(keep + rest[: limit - len(keep)])
        removed = len(self.models) - len(keep)
        self.models = [self.models[i] for i in keep]
        self.hits = [self.hits[i] for i in keep]
        self.picks = [self.picks[i] for i in keep]
        return removed

    def add_scores(self, model: Model, block_scores: list[np.ndarray]) -> None:
        """Эксперт с уже посчитанными оценками (дорогие модели вроде бустинга)."""
        picks = [top_k(s, spec.count, seed=11 + b) for b, (s, spec) in enumerate(zip(block_scores, self.data.fmt.blocks))]
        h = self.ev.hits(picks)
        self.models.append(model)
        self.hits.append(_compact(h[self.warm:]))
        self.picks.append([pb[self.warm:].astype(np.uint8) for pb in picks])


VOTE_CHUNK = 64   # экспертов за раз: ограничивает память при подсчёте голосов
VOTE_CELLS = 1e7   # и не больше стольких (эксперт × тираж × число) за раз


def _stacked(pool: ExpertPool) -> list[np.ndarray]:
    """Прогнозы всех экспертов одним массивом на блок: E×R×k (uint8)."""
    return [np.stack([p[b] for p in pool.picks]) for b in range(len(pool.data.fmt.blocks))]


def _vote(pool: ExpertPool, weights: np.ndarray, stacked: list[np.ndarray] | None = None) -> list[np.ndarray]:
    """Взвешенное голосование: weights E×R (R = строки таймлайна) → прогноз по блокам.

    Голоса считаются одним np.bincount по индексам «строка × число» — в десятки раз быстрее
    поэкспертного цикла (на 27 тыс. тиражей пересчёт стратегий занимал ~25 с)."""
    stacked = stacked or _stacked(pool)
    out = []
    rows = weights.shape[1]
    active = np.flatnonzero(weights.any(axis=1))
    row_base = np.arange(rows, dtype=np.int64)[None, :, None]
    for b, spec in enumerate(pool.data.fmt.blocks):
        votes = np.zeros(rows * spec.size, np.float64)
        # пачка экспертов ограничена и по числу ячеек: на 190 тыс. тиражей 64 эксперта давали
        # временные массивы по 0,8 ГБ (и пик памяти режима Бога больше 5 ГБ)
        chunk = max(1, min(VOTE_CHUNK, int(VOTE_CELLS // max(1, rows * spec.count))))
        for start in range(0, len(active), chunk):
            sel = active[start:start + chunk]
            picks = stacked[b][sel].astype(np.int64)                      # c×R×k
            idx = (row_base * spec.size + picks).ravel()
            w = np.broadcast_to(weights[sel][:, :, None], picks.shape).ravel()
            votes += np.bincount(idx, weights=w, minlength=rows * spec.size)
        out.append(top_k(votes.reshape(rows, spec.size).astype(np.float32), spec.count, seed=41 + b))
    return out


def _timeline_hits(pool: ExpertPool, picks: list[np.ndarray]) -> np.ndarray:
    warm = pool.warm
    total = np.zeros(pool.data.T - warm, np.float32)
    for x, p in zip(pool.data.matrices, picks):
        total += np.take_along_axis(x[warm:], p[:-1].astype(np.int64), axis=1).sum(axis=1)
    return total


def run_strategies(pool: ExpertPool) -> list[dict]:
    """Все мета-стратегии; для каждой — прогнозы на таймлайне и выбранный эксперт."""
    hmat = np.stack(pool.hits).astype(np.float32)   # E×R0 (R0 = T−warm)
    e_count, r0 = hmat.shape
    rows = r0 + 1                               # + будущий тираж
    mean0 = pool.ev.mean0[pool.warm:]
    strategies = []
    stacked = _stacked(pool)

    cum = np.hstack([np.zeros((e_count, 1), np.float32), np.cumsum(hmat, axis=1)])  # E×rows
    for w in LEADER_WINDOWS:
        if w is None:
            score = cum
        else:
            lag = np.hstack([np.zeros((e_count, min(w, rows)), np.float32), cum[:, : max(rows - w, 0)]])
            score = cum - lag
        noisy = score + tie_noise(score.T.shape, 5).T.astype(np.float32) * np.float32(1e-4)
        leader = noisy.argmax(axis=0)                # по строке — индекс эксперта
        picks = [st[leader, np.arange(rows)] for st in stacked]
        name = "Лидер за всю историю" if w is None else f"Лидер за {w} тиражей"
        strategies.append({"key": f"leader_{w or 'all'}", "title": name, "picks": picks, "active": leader})

    # float32: на сотнях тысяч тиражей каждая такая матрица E×T весит сотни МБ
    gains = (hmat - mean0).astype(np.float32)
    for eta, gamma in HEDGE_PARAMS:
        g = lfilter(np.float32([1.0]), np.float32([1.0, -gamma]), gains, axis=1).astype(np.float32, copy=False)
        g = np.hstack([np.zeros((e_count, 1), np.float32), g])   # G перед тиражом
        z = np.float32(eta) * g
        del g
        z -= z.max(axis=0, keepdims=True)
        w = np.exp(z)
        w /= w.sum(axis=0, keepdims=True)
        picks = _vote(pool, w.astype(np.float32), stacked)
        strategies.append({
            "key": f"hedge_{eta}_{gamma}", "title": ru(f"Hedge (η={eta}, γ={gamma})"),
            "picks": picks, "active": w.argmax(axis=0),
        })

    equal = np.ones((e_count, rows), np.float32)
    controls = np.array([m.control for m in pool.models])
    equal[controls] = 0.0
    strategies.append({"key": "vote_all", "title": "Равное голосование всех экспертов",
                       "picks": _vote(pool, equal, stacked), "active": None})
    for s in strategies:
        s["hits"] = _timeline_hits(pool, s["picks"])
    return strategies


def summarize(pool: ExpertPool, strategies: list[dict], stage: str, complete: bool, elapsed: float,
              budget_s: float) -> dict:
    data = pool.data
    warm = pool.warm
    r0 = data.T - warm
    half = r0 // 2
    mean0, var0 = pool.ev.mean0[warm:], pool.ev.var0[warm:]
    m1, v1, m2, v2 = mean0[:half], var0[:half], mean0[half:], var0[half:]

    for s in strategies:
        s["m_first"] = metrics(s["hits"][:half], m1, v1)
        s["m_second"] = metrics(s["hits"][half:], m2, v2)
        s["m_all"] = metrics(s["hits"], mean0, var0)
    # прогноз даёт всегда «лидер за всю историю»: на каждый тираж — эксперт, лучший по всем
    # предыдущим тиражам. Стратегия задана заранее, поэтому её результат на второй половине
    # честный; остальные стратегии показываются для сравнения.
    chosen = next((s for s in strategies if s["key"] == "leader_all"),
                  max(strategies, key=lambda s: s["m_first"]["mean_hits"]))

    hmat = np.stack(pool.hits).astype(np.float32)
    first = hmat[:, :half].mean(axis=1)
    noncontrol = [i for i, m in enumerate(pool.models) if not m.control]
    best_e = max(noncontrol, key=lambda i: first[i])
    controls = [i for i, m in enumerate(pool.models) if m.control]

    def expert_row(i: int) -> dict:
        m = pool.models[i]
        return {"key": m.key, "title": ru(m.title), "family": m.family, "control": m.control,
                "first": metrics(hmat[i, :half], m1, v1), "second": metrics(hmat[i, half:], m2, v2)}

    # потиражная лента (последние 150 тиражей) для выбранной стратегии
    timeline = []
    active = chosen["active"]
    for r in range(max(0, r0 - 150), r0):
        t = warm + r
        d = data.draws[t]
        act_i = None if active is None else int(active[r])
        timeline.append({
            "no": d.no, "date": d.date,
            "predicted": [sorted(int(v) + s.lo for v in p[r]) for p, s in zip(chosen["picks"], data.fmt.blocks)],
            "actual": [sorted(int(v) + s.lo for v in np.nonzero(x[t])[0]) for x, s in zip(data.matrices, data.fmt.blocks)],
            "hits": int(chosen["hits"][r]),
            "model": None if act_i is None else ru(pool.models[act_i].title),
        })
    timeline.reverse()

    # смены активной модели
    switches = 0
    if active is not None:
        switches = int(np.sum(active[1:r0] != active[: r0 - 1]))

    next_row = r0
    next_numbers = [sorted(int(v) + s.lo for v in p[next_row]) for p, s in zip(chosen["picks"], data.fmt.blocks)]
    next_model = None if active is None else ru(pool.models[int(active[next_row])].title)
    leader = None
    if active is not None:
        lm = pool.models[int(active[next_row])]
        leader = {"key": lm.key, "title": ru(lm.title),
                  "params": {k: v for k, v in lm.params.items() if k in ("w", "window", "half_life", "alpha")}}

    second = chosen["m_second"]
    if second["p_better"] < 0.05:
        verdict = (f"Стратегия «{chosen['title']}» на проверочной половине угадывает в среднем "
                   f"{second['mean_hits']:.3f} при {second['baseline']:.3f} у случайного выбора (p={second['p_better']:.3f}). "
                   "Это статистически заметно, но проверьте на новых тиражах: эффект может исчезнуть.")
    else:
        verdict = (f"Стратегия «{chosen['title']}» на проверочной половине угадывает в среднем "
                   f"{second['mean_hits']:.3f} при {second['baseline']:.3f} у случайного выбора (p={second['p_better']:.2f}) — "
                   "преимущество в пределах случайности. Адаптация моделей не находит устойчивой закономерности.")

    ctrl_second = [metrics(hmat[i, half:], m2, v2)["excess"] for i in controls]
    return {
        "status": "ok",
        "complete": complete,
        "stage": stage,
        "elapsed_seconds": round(elapsed, 1),
        "budget_seconds": round(budget_s),
        "draws": data.T,
        "warmup": warm,
        "evaluation": {"from": data.draws[warm].no, "split": data.draws[warm + half].no, "to": data.draws[-1].no},
        "baseline": {"mean": float(mean0.mean()), "sd": math.sqrt(float(var0.mean()))},
        "experts": len(pool.models),
        "strategies": [{"key": s["key"], "title": s["title"], "first": s["m_first"], "second": s["m_second"],
                        "curve": rolling_curve(s["hits"], mean0)} for s in strategies],
        "chosen": chosen["key"],
        "chosen_title": chosen["title"],
        "best_expert": expert_row(best_e),
        "random_control_excess": ctrl_second,
        "top_experts": [expert_row(i) for i in sorted(noncontrol, key=lambda i: -first[i])[:10]],
        "curves": {
            "chosen": rolling_curve(chosen["hits"], mean0),
            "best_expert": rolling_curve(hmat[best_e], mean0),
            "random": rolling_curve(hmat[controls[0]], mean0) if controls else [],
        },
        "switches": switches,
        "timeline": timeline,
        "next": {"no": data.draws[-1].no + 1, "numbers": next_numbers, "model": next_model,
                 "strategy": chosen["title"], "leader": leader},
        "verdict": ru(verdict),
    }


# ── Состояние для продолжения ─────────────────────────────────────────────

def _signature(data: GameData, warm: int | None = None) -> dict:
    sig = {"last_draw_no": data.draws[-1].no, "draws": data.T, "format": data.fmt.describe()}
    if warm is not None:
        sig["warm"] = int(warm)     # всеобъемлющий режим: проверка с заданного тиража
    return sig


def save_state(path, pool: ExpertPool, meta: dict) -> None:
    """Пул экспертов (прогнозы и угаданные) + ход поиска — чтобы продолжить после остановки."""
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {"hits": np.stack(pool.hits)}
    for b in range(len(pool.data.fmt.blocks)):
        arrays[f"picks_{b}"] = np.stack([p[b] for p in pool.picks])
    models = [{"key": m.key, "title": m.title, "family": m.family, "control": m.control,
               "weights": m.params.get("w")} for m in pool.models]
    payload = {**meta, "signature": _signature(pool.data, getattr(pool, "fixed_warm", None)), "models": models}
    tmp = path.with_name(f".{path.stem}.{os.getpid()}.tmp.npz")
    np.savez_compressed(tmp, meta=np.array(json.dumps(payload, ensure_ascii=False)), **arrays)
    replace_with_retry(tmp, path)
    # краткая сводка для интерфейса (он не читает .npz)
    summary = {"signature": payload["signature"], "elapsed": meta.get("elapsed", 0), "experts": len(models),
               "stages_done": meta.get("stages_done", []), "exhausted": meta.get("exhausted", False),
               "search_idx": (meta.get("search") or {}).get("idx", 0)}
    write_text(path.with_suffix(".json"), json.dumps(summary, ensure_ascii=False))


def load_state(path, data: GameData, warm: int | None = None) -> tuple[ExpertPool, dict] | tuple[None, str]:
    if not path.exists():
        return None, "сохранённого состояния нет"
    try:
        with np.load(path, allow_pickle=False) as z:
            meta = json.loads(str(z["meta"]))
            if meta.get("signature") != _signature(data, warm):
                return None, "после сохранения загружены новые тиражи — продолжить нельзя, запустите заново"
            pool = ExpertPool(data, warm=warm)
            pool.fixed_warm = warm
            pool.hits = list(z["hits"])
            blocks = [z[f"picks_{b}"] for b in range(len(data.fmt.blocks))]
    except (OSError, ValueError, KeyError) as exc:
        return None, f"состояние повреждено: {exc}"
    for i, d in enumerate(meta["models"]):
        params = {"w": d["weights"]} if d.get("weights") is not None else {}
        pool.models.append(Model(d["key"], d["title"], d["family"], lambda f: None, control=d["control"], params=params))
        pool.picks.append([blk[i] for blk in blocks])
    return pool, meta


def state_info(path, data: GameData) -> dict | None:
    """Можно ли продолжить: сводка сохранённого состояния без загрузки массивов."""
    if not path.exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as z:
            meta = json.loads(str(z["meta"]))
    except (OSError, ValueError, KeyError):
        return None
    return {"resumable": meta.get("signature") == _signature(data), "elapsed": meta.get("elapsed", 0),
            "experts": len(meta.get("models", [])), "stages": meta.get("stages_done", []),
            "exhausted": meta.get("exhausted", False)}


def _mutate(base: Model, names: list[str], rng: np.random.Generator, idx: int) -> Model:
    """Локальный поиск: небольшое изменение весов одной из лучших смесей."""
    w = np.asarray(base.params["w"], float) + rng.normal(scale=0.15, size=len(names))
    return mixture_from_weights(w, names, idx, f"вариация «{base.title}»")


def mixture_from_weights(w: np.ndarray, names: list[str], idx: int, note: str = "") -> Model:
    w = w / max(np.abs(w).sum(), 1e-9)

    def fn(f):
        _, feats = f.feature_stack(sampled=True)
        return np.tensordot(feats, w, axes=([2], [0])).astype(np.float32)

    return Model(f"rmix_{idx}", f"Смесь признаков #{idx}", "search", fn,
                 params={"w": [round(float(v), 6) for v in w], "note": note})


def run_godmode(data: GameData, budget_minutes: float, on_progress=None, on_checkpoint=None,
                state_path=None, resume: bool = False, eval_from: int | None = None) -> dict:
    """Режим Бога. budget_minutes — время этого запуска; при resume=True работа продолжается
    с сохранённого состояния (пройденные стадии и найденные эксперты не пересчитываются).
    eval_from — индекс тиража, с которого эксперты проверяются (всеобъемлющий режим: с
    1000-го тиража); по умолчанию — после короткого разогрева (warmup_size)."""
    t_start = time.time()
    budget_s = max(MIN_BUDGET_S, budget_minutes * 60.0)
    deadline = t_start + budget_s

    # Инициализация монитора памяти
    memory_monitor = MemoryMonitor(max_gb=3.0, warn_gb=2.5)
    logger.info(f"🚀 Запуск режима Бога: бюджет {budget_minutes:.1f} мин, игра {data.slug}, тиражей {data.T}")

    pool, meta = None, {}
    if resume and state_path is not None:
        pool, meta = load_state(state_path, data, eval_from)
        if pool is None:
            raise ValueError(f"Продолжить нельзя: {meta}")
    if pool is None:
        pool = ExpertPool(data, warm=eval_from)
        pool.fixed_warm = eval_from
    meta = meta if isinstance(meta, dict) else {}
    stages_done: list[str] = list(meta.get("stages_done", []))
    elapsed_before = float(meta.get("elapsed", 0.0))
    search = meta.get("search", {"idx": 0, "best": None, "stale": 0})
    rng = np.random.default_rng(2024)
    if meta.get("rng"):
        rng.bit_generator.state = meta["rng"]
    last_save = [time.time()]
    last_memory_check = [time.time()]

    def total_elapsed() -> float:
        return elapsed_before + time.time() - t_start

    def check_memory_and_cleanup() -> None:
        """Проверка памяти и очистка при необходимости."""
        # Проверяем не чаще раза в минуту
        if time.time() - last_memory_check[0] < 60:
            return

        last_memory_check[0] = time.time()
        is_critical, message = memory_monitor.check()

        if is_critical:
            logger.error(message)
            memory_monitor.emergency_cleanup(pool)
            # Проверяем снова
            is_critical2, message2 = memory_monitor.check()
            if is_critical2:
                raise MemoryError(
                    f"Недостаточно памяти для продолжения работы: {message2}. "
                    "Попробуйте уменьшить бюджет времени или использовать игру с меньшим архивом."
                )
        elif "⚠️" in message:
            logger.warning(message)

    def progress(stage: str, done: int, total: int, note: str = "") -> None:
        if on_progress:
            mem_gb = memory_monitor.current_usage_gb()
            on_progress({"stage": stage, "done": done, "total": total, "experts": len(pool.models),
                         "elapsed": round(time.time() - t_start, 1), "budget": budget_s, "note": note,
                         "total_elapsed": round(total_elapsed(), 1), "memory_gb": round(mem_gb, 2)})

    def persist(force: bool = False, exhausted: bool = False) -> None:
        if state_path is None or (not force and time.time() - last_save[0] < SAVE_EVERY_S):
            return
        save_state(state_path, pool, {"stages_done": stages_done, "elapsed": total_elapsed(),
                                      "search": search, "rng": rng.bit_generator.state, "exhausted": exhausted})
        last_save[0] = time.time()

    last_checkpoint = [time.time()]

    def checkpoint(stage: str, complete: bool, exhausted: bool = False) -> dict:
        last_checkpoint[0] = time.time()
        progress(stage, 0, 0, "пересчёт мета-стратегий")
        res = summarize(pool, run_strategies(pool), stage, complete, total_elapsed(), budget_s)
        res["exhausted"] = exhausted
        res["resumed"] = bool(elapsed_before)
        res["memory_peak_gb"] = round(memory_monitor.current_usage_gb(), 2)
        if on_checkpoint:
            on_checkpoint(res)
        return res

    def out_of_time() -> bool:
        return time.time() > deadline

    # Стадия 1 — базовый пул (быстро)
    if "base" not in stages_done:
        base = expert_grid(1) + [m for m in standard_models() if not m.control]
        for i, m in enumerate(base):
            progress("Базовые модели", i, len(base), m.title)
            pool.add(m)
            if i % 10 == 0:  # Проверка памяти каждые 10 моделей
                check_memory_and_cleanup()
        stages_done.append("base")
        persist(force=True)
        checkpoint("Базовые модели", complete=False)

    # Стадия 2 — расширенная сетка параметров
    if "grid" not in stages_done:
        ext = expert_grid(2)
        for i, m in enumerate(ext):
            if out_of_time():
                persist(force=True)
                return checkpoint("Время вышло", complete=True)
            progress("Расширенная сетка", i, len(ext), m.title)
            pool.add(m)
            if i % 10 == 0:
                check_memory_and_cleanup()
        stages_done.append("grid")
        persist(force=True)
        checkpoint("Расширенная сетка", complete=False)

    # Стадия 3 — градиентный бустинг (дорого; только если хватает времени)
    for retrain in (1000, 400):
        tag = f"gbm{retrain}"
        if tag in stages_done:
            continue
        if deadline - time.time() < 120:
            break
        progress("Градиентный бустинг", 0, 1, f"переобучение каждые {retrain} тиражей")
        try:
            scores = [gbm_scores(f, retrain_every=retrain, deadline=deadline) for f in pool.ev.features]
        except TimeoutError:
            break
        pool.add_scores(Model(f"gbm_{retrain}", f"Градиентный бустинг (переобучение раз в {retrain})", "ml",
                              lambda f: None), scores)
        stages_done.append(tag)
        persist(force=True)
        checkpoint("Градиентный бустинг", complete=False)

    # Стадия 4 — поиск комбинаций признаков до конца бюджета или пока есть улучшения.
    # Улучшение меряется по первой половине тиражей; вторая половина остаётся проверочной.
    names, _ = pool.ev.features[0].feature_stack()
    exhausted = bool(meta.get("exhausted"))
    while not out_of_time() and not exhausted:
        # Проверка памяти перед каждой пачкой поиска
        check_memory_and_cleanup()

        best_before = max((pool.first_half_score(i) for i, m in enumerate(pool.models) if not m.control),
                          default=0.0)
        top = sorted((m for m in pool.models if m.params.get("w") is not None),
                     key=lambda m: -pool.first_half_score(pool.models.index(m)))[:5]
        for j in range(SEARCH_BATCH):
            if out_of_time():
                break
            search["idx"] += 1
            idx = search["idx"]
            progress("Поиск комбинаций признаков", idx, 0,
                     f"без улучшений {search['stale']} из {STAGNATION_BATCHES} пачек")
            if top and j % 2 == 1:
                pool.add(_mutate(top[(j // 2) % len(top)], names, rng, idx))
            else:
                pool.add(mixture_from_weights(rng.normal(size=len(names)), names, idx))
        pool.prune()
        best_after = max(pool.first_half_score(i) for i, m in enumerate(pool.models) if not m.control)
        search["stale"] = 0 if best_after > best_before + 1e-9 else search["stale"] + 1
        exhausted = search["stale"] >= STAGNATION_BATCHES
        persist(force=exhausted)
        if exhausted or time.time() - last_checkpoint[0] >= CHECKPOINT_EVERY_S:
            checkpoint("Поиск комбинаций признаков", complete=False)

    persist(force=True, exhausted=exhausted)
    result = checkpoint("Перебор исчерпан" if exhausted else "Время вышло", complete=True, exhausted=exhausted)
    if exhausted and state_path is not None:
        drop_state(state_path, keep_summary=True)   # продолжать нечего — 50+ МБ не храним

    # Финальный отчет по памяти
    mem_final = memory_monitor.current_usage_gb()
    logger.info(f"✓ Режим Бога завершен: {len(pool.models)} экспертов, память {mem_final:.2f} ГБ")

    return result


# ── Автозапуск ─────────────────────────────────────────────────────────────

def model_by_key(key: str, params: dict | None = None) -> Model | None:
    """Эксперт по ключу — чтобы лидер прошлого запуска давал прогноз на новые тиражи без
    повторного перебора. Бустинг не восстанавливается (дорого) — None."""
    params = params or {}
    if key.startswith("rmix_") and params.get("w"):
        idx = int(key.split("_", 1)[1]) if key.split("_", 1)[1].isdigit() else 0
        return mixture_from_weights(np.asarray(params["w"], float), [], idx)
    for m in expert_grid(1) + [m for m in standard_models() if not m.control] + expert_grid(2):
        if m.key == key:
            return m
    return None


def predict_leader(data: GameData, leader: dict | None) -> list[list[int]] | None:
    """Прогноз модели-лидера (из прошлого запуска режима Бога) на следующий тираж."""
    if not leader:
        return None
    m = model_by_key(leader.get("key", ""), leader.get("params"))
    if m is None:
        return None
    ev = Evaluator(data)
    return ev.numbers(ev.picks(m), data.T)


def auto_run(slug: str, budget_minutes: float, max_draws: int) -> dict:
    """Режим Бога для автозапуска (запускается в отдельном процессе): последние max_draws
    тиражей, без сохранения состояния для продолжения."""
    from .drawfile import load_game_data
    from .games import get_game
    from .mechanics import subset
    data = load_game_data(get_game(slug))
    if data.T > max_draws:
        data = subset(data, np.arange(data.T - max_draws, data.T))
    res = run_godmode(data, budget_minutes, state_path=None)
    return json.loads(json.dumps(res, default=float))
