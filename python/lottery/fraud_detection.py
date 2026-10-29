"""Обнаружение нечестных лотерей и физических дефектов лототрона.

Статистические тесты для выявления:
- Неравномерности частот (Chi-square test)
- Подозрительных последовательностей (Runs test)
- Зависимости между тиражами (Autocorrelation)
- Смещения позиций выпадения (Position bias)
- Корреляции порядка выпадения (Position correlation)
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from dataclasses import dataclass
from typing import Optional


@dataclass
class FraudTestResult:
    """Результат одного теста."""
    test_name: str
    statistic: float
    p_value: float
    is_suspicious: bool
    description: str
    details: dict = None


class FraudDetector:
    """Статистические тесты для обнаружения манипуляций."""

    def __init__(self, significance_level: float = 0.01):
        """
        Args:
            significance_level: Уровень значимости (alpha). По умолчанию 0.01 (99% уверенность).
        """
        self.alpha = significance_level

    def run_all_tests(self, x: np.ndarray, positions: Optional[np.ndarray] = None) -> dict:
        """
        Запустить все тесты.

        Args:
            x: матрица тиражей (T×N, 1 = число выпало)
            positions: порядок выпадения (T×k), если известен

        Returns:
            dict с результатами всех тестов и общим вердиктом
        """
        results = {
            "chi_square": self.chi_square_test(x),
            "runs": self.runs_test(x),
            "autocorrelation": self.autocorrelation_test(x),
        }

        if positions is not None:
            results["position_bias"] = self.position_bias_test(positions, x.shape[1])
            results["position_correlation"] = self.position_correlation_test(positions)

        # Общий вердикт
        suspicious_tests = [r for r in results.values() if r.is_suspicious]
        results["verdict"] = {
            "status": "suspicious" if suspicious_tests else "fair",
            "suspicious_tests": len(suspicious_tests),
            "total_tests": len(results),
            "message": self._verdict_message(suspicious_tests),
            "confidence": 1.0 - self.alpha,
        }

        return results

    def chi_square_test(self, x: np.ndarray) -> FraudTestResult:
        """
        Тест Хи-квадрат на равномерность частот.
        Проверяет, все ли числа выпадают примерно с одинаковой частотой.

        H0: все числа имеют одинаковую вероятность выпадения
        H1: некоторые числа выпадают значимо чаще/реже других
        """
        T, N = x.shape
        observed = x.sum(axis=0)  # Сколько раз каждое число выпало
        expected = observed.mean()  # Ожидаемая частота

        if expected == 0:
            return FraudTestResult(
                "Chi-Square", 0.0, 1.0, False,
                "Недостаточно данных для теста"
            )

        chi2_stat = ((observed - expected) ** 2 / expected).sum()
        p_value = 1 - stats.chi2.cdf(chi2_stat, df=N - 1)

        # Найти числа с наибольшим отклонением
        deviations = (observed - expected) / np.sqrt(expected)
        top_hot = np.argsort(-deviations)[:3]  # 3 самых "горячих"
        top_cold = np.argsort(deviations)[:3]  # 3 самых "холодных"

        details = {
            "expected_freq": float(expected),
            "hot_numbers": [{"number": int(i), "freq": int(observed[i]),
                           "deviation": float(deviations[i])} for i in top_hot],
            "cold_numbers": [{"number": int(i), "freq": int(observed[i]),
                            "deviation": float(deviations[i])} for i in top_cold],
        }

        return FraudTestResult(
            test_name="Chi-Square (равномерность частот)",
            statistic=chi2_stat,
            p_value=p_value,
            is_suspicious=p_value < self.alpha,
            description=(
                f"Некоторые числа выпадают значимо чаще/реже других (χ²={chi2_stat:.2f}, p={p_value:.4f})"
                if p_value < self.alpha else
                f"Частоты чисел равномерны (χ²={chi2_stat:.2f}, p={p_value:.4f})"
            ),
            details=details,
        )

    def runs_test(self, x: np.ndarray) -> FraudTestResult:
        """
        Тест серий (Runs Test).
        Проверяет, нет ли подозрительных последовательностей выпадений/невыпадений.

        Слишком мало серий → числа "залипают" (выпадают блоками)
        Слишком много серий → числа чередуются слишком регулярно
        """
        T, N = x.shape

        z_scores = []
        suspicious_numbers = []

        for num_idx in range(N):
            seq = x[:, num_idx]

            # Подсчет серий (runs): переключений 0→1 или 1→0
            changes = np.diff(np.concatenate([[0], seq, [0]])).nonzero()[0]
            n_runs = len(changes) // 2

            n1 = int(seq.sum())  # Единиц (выпадений)
            n0 = len(seq) - n1   # Нулей (невыпадений)

            if n1 > 0 and n0 > 0:
                # Ожидаемое число серий при случайности
                expected_runs = 2 * n1 * n0 / (n1 + n0) + 1
                var_runs = 2 * n1 * n0 * (2 * n1 * n0 - n1 - n0) / ((n1 + n0) ** 2 * (n1 + n0 - 1))

                if var_runs > 0:
                    z = (n_runs - expected_runs) / np.sqrt(var_runs)
                    z_scores.append(abs(z))

                    if abs(z) > stats.norm.ppf(1 - self.alpha / (2 * N)):  # Поправка Бонферрони
                        suspicious_numbers.append({
                            "number": num_idx,
                            "n_runs": n_runs,
                            "expected": float(expected_runs),
                            "z_score": float(z),
                            "pattern": "залипание" if z < 0 else "чередование"
                        })

        if not z_scores:
            return FraudTestResult(
                "Runs Test", 0.0, 1.0, False,
                "Недостаточно данных для теста"
            )

        # Максимальное отклонение
        max_z = max(z_scores)
        p_value = 2 * (1 - stats.norm.cdf(max_z))

        return FraudTestResult(
            test_name="Runs Test (последовательности)",
            statistic=max_z,
            p_value=p_value,
            is_suspicious=p_value < self.alpha,
            description=(
                f"Обнаружены подозрительные серии выпадений (Z={max_z:.2f}, p={p_value:.4f})"
                if p_value < self.alpha else
                f"Серии выпадений выглядят случайными (Z={max_z:.2f}, p={p_value:.4f})"
            ),
            details={"suspicious_numbers": suspicious_numbers[:5]},  # Топ-5
        )

    def autocorrelation_test(self, x: np.ndarray, max_lag: int = 50) -> FraudTestResult:
        """
        Тест автокорреляции.
        Проверяет, нет ли зависимости между тиражами (память системы).

        H0: тиражи независимы
        H1: есть корреляция между тиражами на некоторой задержке
        """
        T, N = x.shape
        max_lag = min(max_lag, T // 2)

        correlations = []
        significant_correlations = []

        for lag in range(1, max_lag):
            for num_idx in range(N):
                seq = x[:, num_idx]

                # Автокорреляция на задержке lag
                corr = np.corrcoef(seq[:-lag], seq[lag:])[0, 1]

                if not np.isnan(corr):
                    correlations.append(abs(corr))

                    # Критическое значение с поправкой Бонферрони
                    critical = stats.norm.ppf(1 - self.alpha / (2 * N * max_lag)) / np.sqrt(T)

                    if abs(corr) > critical:
                        significant_correlations.append({
                            "number": num_idx,
                            "lag": lag,
                            "correlation": float(corr),
                        })

        if not correlations:
            return FraudTestResult(
                "Autocorrelation", 0.0, 1.0, False,
                "Недостаточно данных для теста"
            )

        max_corr = max(correlations)
        # Под нулевой гипотезой: corr ~ N(0, 1/√T)
        z = max_corr * np.sqrt(T)
        p_value = 2 * (1 - stats.norm.cdf(z))

        return FraudTestResult(
            test_name="Autocorrelation (зависимость тиражов)",
            statistic=max_corr,
            p_value=p_value,
            is_suspicious=p_value < self.alpha,
            description=(
                f"Обнаружена зависимость между тиражами (max ρ={max_corr:.3f}, p={p_value:.4f})"
                if p_value < self.alpha else
                f"Тиражи независимы (max ρ={max_corr:.3f}, p={p_value:.4f})"
            ),
            details={"significant": significant_correlations[:10]},  # Топ-10
        )

    def position_bias_test(self, positions: np.ndarray, N: int) -> FraudTestResult:
        """
        Тест смещения позиций.
        Проверяет, все ли числа выпадают на всех позициях равномерно.

        Если лототрон имеет физические дефекты (неравномерность барабана),
        некоторые числа могут "предпочитать" определенные позиции.
        """
        T, k = positions.shape

        # Подсчитаем, сколько раз каждое число выпало на каждой позиции
        position_counts = np.zeros((N, k), dtype=int)
        for t in range(T):
            for pos in range(k):
                num = positions[t, pos]
                if 0 <= num < N:
                    position_counts[num, pos] += 1

        # Хи-квадрат для каждого числа
        chi2_stats = []
        biased_numbers = []

        for num in range(N):
            observed = position_counts[num]
            total = observed.sum()

            if total > 0:
                expected = total / k
                chi2 = ((observed - expected) ** 2 / expected).sum()
                chi2_stats.append(chi2)

                # Критическое значение с поправкой Бонферрони
                critical = stats.chi2.ppf(1 - self.alpha / N, df=k - 1)

                if chi2 > critical:
                    favorite_pos = np.argmax(observed)
                    biased_numbers.append({
                        "number": num,
                        "chi2": float(chi2),
                        "favorite_position": int(favorite_pos),
                        "freq_at_favorite": int(observed[favorite_pos]),
                        "expected_freq": float(expected),
                    })

        if not chi2_stats:
            return FraudTestResult(
                "Position Bias", 0.0, 1.0, False,
                "Недостаточно данных для теста"
            )

        max_chi2 = max(chi2_stats)
        p_value = 1 - stats.chi2.cdf(max_chi2, df=k - 1)

        return FraudTestResult(
            test_name="Position Bias (смещение позиций)",
            statistic=max_chi2,
            p_value=p_value,
            is_suspicious=p_value < self.alpha,
            description=(
                f"Некоторые числа 'предпочитают' определенные позиции (χ²={max_chi2:.2f}, p={p_value:.4f})"
                if p_value < self.alpha else
                f"Позиции выпадения равномерны (χ²={max_chi2:.2f}, p={p_value:.4f})"
            ),
            details={"biased_numbers": biased_numbers[:5]},
        )

    def position_correlation_test(self, positions: np.ndarray) -> FraudTestResult:
        """
        Корреляция между позициями в соседних тиражах.
        Проверяет, нет ли связи между порядком выпадения.

        Если есть механическая закономерность (вращение барабана),
        порядок может коррелировать между тиражами.
        """
        T, k = positions.shape

        correlations = []
        significant = []

        for lag in range(1, min(10, T // 2)):
            for pos in range(k):
                seq1 = positions[:-lag, pos]
                seq2 = positions[lag:, pos]

                # Корреляция Спирмена (ранговая) - более робастная
                corr, _ = stats.spearmanr(seq1, seq2)

                if not np.isnan(corr):
                    correlations.append(abs(corr))

                    # Критическое значение
                    critical = stats.norm.ppf(1 - self.alpha / (2 * k * 10)) / np.sqrt(T - lag)

                    if abs(corr) > critical:
                        significant.append({
                            "position": pos,
                            "lag": lag,
                            "correlation": float(corr),
                        })

        if not correlations:
            return FraudTestResult(
                "Position Correlation", 0.0, 1.0, False,
                "Недостаточно данных для теста"
            )

        max_corr = max(correlations)
        z = max_corr * np.sqrt(T)
        p_value = 2 * (1 - stats.norm.cdf(z))

        return FraudTestResult(
            test_name="Position Correlation (корреляция порядка)",
            statistic=max_corr,
            p_value=p_value,
            is_suspicious=p_value < self.alpha,
            description=(
                f"Порядок выпадения коррелирует между тиражами (max ρ={max_corr:.3f}, p={p_value:.4f})"
                if p_value < self.alpha else
                f"Порядок выпадения случаен (max ρ={max_corr:.3f}, p={p_value:.4f})"
            ),
            details={"significant": significant[:10]},
        )

    def _verdict_message(self, suspicious_tests: list[FraudTestResult]) -> str:
        """Итоговое сообщение о результатах всех тестов."""
        if not suspicious_tests:
            return (
                "✓ Все тесты пройдены. Статистических свидетельств нечестности не обнаружено. "
                "Результаты лотереи соответствуют случайному распределению с уровнем уверенности "
                f"{int((1 - self.alpha) * 100)}%."
            )

        test_names = ", ".join(t.test_name for t in suspicious_tests)
        return (
            f"⚠️ ВНИМАНИЕ: Обнаружены статистически значимые аномалии! "
            f"Не прошли тесты: {test_names}. "
            f"Это может указывать на:\n"
            f"• Физические дефекты лототрона (неравномерность, износ)\n"
            f"• Неслучайность ГСЧ (генератора случайных чисел)\n"
            f"• Возможные манипуляции\n"
            f"Рекомендуется дополнительная проверка независимыми экспертами."
        )


def analyze_game_for_fraud(data, output_json: bool = False) -> dict:
    """
    Анализ одной игры на предмет нечестности.

    Args:
        data: GameData объект
        output_json: если True, вернуть JSON-сериализуемый dict

    Returns:
        dict с результатами анализа
    """
    detector = FraudDetector(significance_level=0.01)

    # Проверка по блокам
    results_by_block = []

    for i, (x, spec) in enumerate(zip(data.matrices, data.fmt.blocks)):
        # Получить позиции если есть
        positions = None
        try:
            from .mechanics import _ordered_rows
            positions = _ordered_rows(data, spec)
            if positions is not None:
                positions = positions - spec.lo  # Нормализовать к 0..N-1
        except Exception:
            pass

        block_results = detector.run_all_tests(x, positions)

        if output_json:
            # Сериализация для JSON
            serialized = {
                "block_name": spec.name,
                "tests": {},
                "verdict": block_results["verdict"],
            }
            for test_name, result in block_results.items():
                if test_name != "verdict":
                    serialized["tests"][test_name] = {
                        "test_name": result.test_name,
                        "statistic": float(result.statistic),
                        "p_value": float(result.p_value),
                        "is_suspicious": result.is_suspicious,
                        "description": result.description,
                        "details": result.details,
                    }
            results_by_block.append(serialized)
        else:
            results_by_block.append({
                "block": spec.name,
                "results": block_results,
            })

    # Общий вердикт
    any_suspicious = any(
        block.get("verdict", {}).get("status") == "suspicious"
        for block in results_by_block
    )

    return {
        "game": data.slug,
        "draws_analyzed": data.T,
        "blocks": results_by_block,
        "overall_status": "suspicious" if any_suspicious else "fair",
    }
