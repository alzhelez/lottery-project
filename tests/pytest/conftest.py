"""Общие фикстуры. Каждый тест работает в отдельной временной папке данных."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    (d / "draws").mkdir(parents=True)
    monkeypatch.setenv("LOTTERY_DATA_DIR", str(d))
    return d


def random_lotto(t: int, n: int, k: int, seed: int = 0) -> np.ndarray:
    """T честных тиражей «k из n» в виде матрицы индикаторов."""
    rng = np.random.default_rng(seed)
    x = np.zeros((t, n), np.float32)
    idx = np.argsort(rng.random((t, n)), axis=1)[:, :k]
    np.put_along_axis(x, idx, 1.0, axis=1)
    return x


def write_lotto_file(path: Path, x_blocks: list, start_no: int = 1) -> None:
    """Записывает файл тиражей из матриц индикаторов (по блоку на матрицу)."""
    lines = []
    t = x_blocks[0].shape[0]
    for i in range(t):
        day, minute = divmod(i, 24 * 60)
        date = f"{1 + day % 28:02d}.{1 + (day // 28) % 12:02d}.{2010 + day // 336} {minute // 60:02d}:{minute % 60:02d}"
        blocks = [", ".join(str(j + 1) for j in np.nonzero(x[i])[0]) for x in x_blocks]
        lines.append("||".join([date, str(start_no + i)] + blocks))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── Метки для Allure-отчёта (без зависимости от allure: это обычные pytest-маркеры) ──
FEATURES = {
    "test_drawfile": "Файлы тиражей и формат игры",
    "test_stoloto": "Загрузка с API Столото",
    "test_stats": "Тесты случайности",
    "test_models": "Модели прогноза: нет утечки будущего",
    "test_evaluate": "Честная проверка методов",
    "test_godmode": "Режим Бога",
    "test_bingo": "Бинго-игры",
    "test_journal": "Журнал прогнозов и актуальность игр",
    "test_odds_tickets": "Шансы и генератор билетов",
    "test_export_auto": "Экспорт, автозапуск, продолжение режима Бога",
    "test_cli": "Командная строка",
    "test_chaos": "Порядок из хаоса: лототрон и ГСЧ отдельно",
    "test_order": "Порядок выпадения чисел",
    "test_repeats": "Повторы по позициям выпадения",
}


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.allure_label("Движок (Python)", label_type="epic"))
        feature = FEATURES.get(item.module.__name__)
        if feature:
            item.add_marker(pytest.mark.allure_label(feature, label_type="feature"))
