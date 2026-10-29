"""
Специализированные методы предсказания для каждой игры на основе глубокого анализа.

ВАЖНО: Эти методы НЕ улучшают шансы на выигрыш в честной лотерее!
Они используют обнаруженные статистические характеристики, но в честной системе
все комбинации равновероятны независимо от прошлых результатов.

Эти методы полезны только для:
1) Обнаружения аномалий и нечестности
2) Генерации "интересных" билетов для развлечения
3) Анализа паттернов (но не предсказания!)
"""
import numpy as np
from lottery.method import Method, register
from lottery.drawfile import load_game_data
from lottery.games import get_game


# =================== 6x45 ===================
@register
class Game6x45_HotCold(Method):
    """
    6x45: Комбинация горячих и холодных чисел (60/40)

    Анализ показал:
    - Горячие: 36, 2, 43, 3, 38
    - Холодные: 24, 42, 21, 17, 4
    - Avg_repeat: 0.8 (низкая память)
    """
    game_slug = "6x45"
    name = "6x45_hot_cold"
    title = "Горячие/Холодные 60/40"
    tags = ["game-specific", "frequency"]

    def predict_one(self, X, date=None):
        T, N = X.shape
        # Частоты за всю историю
        freq = X.sum(axis=0)
        # Топ-10 горячих и топ-10 холодных
        hot_idx = np.argsort(-freq)[:10]
        cold_idx = np.argsort(freq)[:10]

        # 60% горячих, 40% холодных
        probs = np.zeros(N)
        probs[hot_idx] = 0.6 / len(hot_idx)
        probs[cold_idx] = 0.4 / len(cold_idx)
        probs = probs / probs.sum()

        return probs


@register
class Game6x45_AvoidRecent(Method):
    """
    6x45: Избегать числа из последнего тиража

    Avg_repeat = 0.8, значит в среднем только 0.8 чисел повторяется.
    Стратегия: исключить последние числа.
    """
    game_slug = "6x45"
    name = "6x45_avoid_recent"
    title = "Исключить недавние"
    tags = ["game-specific", "anti-repeat"]

    def predict_one(self, X, date=None):
        T, N = X.shape
        if T < 1:
            return np.ones(N) / N

        # Исключить числа из последних 3 тиражей
        recent = X[-3:].sum(axis=0)
        probs = np.ones(N)
        probs[recent > 0] = 0.1  # Штраф
        probs = probs / probs.sum()

        return probs


# =================== 5x36plus ===================
@register
class Game5x36Plus_MegaHot(Method):
    """
    5x36plus: Мега-горячие числа (огромный архив 161K тиражей!)

    Горячие: 29, 35, 25, 26, 13
    При 161K тиражей эти различия статистически значимы.
    """
    game_slug = "5x36plus"
    name = "5x36plus_mega_hot"
    title = "Мега-горячие (161K тиражей)"
    tags = ["game-specific", "frequency", "big-data"]

    def predict_one(self, X, date=None):
        T, N = X.shape
        freq = X.sum(axis=0)

        # Топ-20% горячих получают 70% веса
        n_hot = N // 5
        hot_idx = np.argsort(-freq)[:n_hot]

        probs = np.ones(N) * 0.3
        probs[hot_idx] = 0.7 / len(hot_idx)
        probs = probs / probs.sum()

        return probs


# =================== Rapido 2.0 ===================
@register
class GameRapido2_HighRepeat(Method):
    """
    Rapido 2.0: Эксплуатация высоких повторов (avg_repeat=3.23!)

    188K тиражей, avg_repeat=3.23 из 8 чисел.
    Стратегия: взять числа из последнего тиража + горячие.
    """
    game_slug = "rapido2"
    name = "rapido2_high_repeat"
    title = "Повторы (avg=3.23)"
    tags = ["game-specific", "repeat", "memory"]

    def predict_one(self, X, date=None):
        T, N = X.shape
        if T < 1:
            return np.ones(N) / N

        # 50% последний тираж + 50% горячие
        last = X[-1]
        freq = X.sum(axis=0)
        hot = (freq > np.median(freq)).astype(float)

        probs = 0.5 * last + 0.5 * hot
        probs = probs / probs.sum()

        return probs


@register
class GameRapido2_ClusterSmall(Method):
    """
    Rapido 2.0: Кластеры (avg_gap=2.33)

    Маленький промежуток → числа кучкуются.
    Стратегия: выбрать диапазон и взять оттуда.
    """
    game_slug = "rapido2"
    name = "rapido2_cluster"
    title = "Кластеры (gap=2.33)"
    tags = ["game-specific", "cluster"]

    def predict_one(self, X, date=None):
        T, N = X.shape
        freq = X.sum(axis=0)

        # Найти "горячую зону" — где сумма частот максимальна
        window = 10
        best_score = 0
        best_start = 0

        for start in range(N - window + 1):
            score = freq[start:start+window].sum()
            if score > best_score:
                best_score = score
                best_start = start

        # Вес в окне выше
        probs = np.ones(N) * 0.2
        probs[best_start:best_start+window] = 0.8 / window
        probs = probs / probs.sum()

        return probs


# =================== Keno 2.0 ===================
@register
class GameKeno2_SuperHot(Method):
    """
    Keno 2.0: Супер-горячие числа (10 из 80!)

    79K тиражей, огромное поле 80 чисел.
    Горячие: 39, 13, 74, 73, 52
    avg_repeat=4.84 из 10 — очень высокий!
    """
    game_slug = "keno2"
    name = "keno2_super_hot"
    title = "Супер-горячие + повторы"
    tags = ["game-specific", "frequency", "repeat"]

    def predict_one(self, X, date=None):
        T, N = X.shape

        # 40% топ-20 горячих, 30% последний тираж, 30% остальные
        freq = X.sum(axis=0)
        hot_idx = np.argsort(-freq)[:20]

        probs = np.ones(N) * 0.3 / N
        probs[hot_idx] = 0.4 / len(hot_idx)

        if T >= 1:
            last = X[-1]
            probs = 0.7 * probs + 0.3 * last

        probs = probs / probs.sum()
        return probs


# =================== vin (12 из 24) ===================
@register
class GameVin_MassiveRepeat(Method):
    """
    Всё или ничего: Массивные повторы (avg_repeat=5.95!)

    12 из 24, avg_repeat=5.95 → почти половина чисел повторяется!
    Стратегия: взять последний тираж + горячие.
    """
    game_slug = "vin"
    name = "vin_massive_repeat"
    title = "Массивные повторы (5.95/12)"
    tags = ["game-specific", "repeat", "extreme"]

    def predict_one(self, X, date=None):
        T, N = X.shape
        if T < 1:
            return np.ones(N) / N

        # 70% последний тираж, 30% топ-горячие
        last = X[-1]
        freq = X.sum(axis=0)
        hot = np.zeros(N)
        hot[np.argsort(-freq)[:12]] = 1.0

        probs = 0.7 * last + 0.3 * hot
        probs = probs / probs.sum()

        return probs


# =================== Топ-3 ===================
@register
class GameTop3_PositionBased(Method):
    """
    Топ-3: Позиционный метод

    12 независимых позиций (цифры 0-9).
    Avg_repeat очень низкий (0.06-0.16) → каждая позиция независима.
    Стратегия: для каждой позиции взять наиболее частую цифру.
    """
    game_slug = "top-3"
    name = "top3_position"
    title = "Позиционные частоты"
    tags = ["game-specific", "position"]

    def predict_blocks(self, matrices, date=None):
        # Возвращаем вероятности для каждого блока отдельно
        predictions = []

        for X in matrices:
            T, N = X.shape
            freq = X.sum(axis=0)
            probs = freq / freq.sum()
            predictions.append(probs)

        return predictions


# =================== 4x20 ===================
@register
class Game4x20_TwoFields(Method):
    """
    4 из 20: Два независимых поля

    Поле 1: горячие 2,5,8,9,1
    Поле 2: горячие 15,20,1,18,4
    Разные паттерны → независимая стратегия для каждого.
    """
    game_slug = "4x20"
    name = "4x20_two_fields"
    title = "Два поля раздельно"
    tags = ["game-specific", "multi-block"]

    def predict_blocks(self, matrices, date=None):
        predictions = []

        for block_idx, X in enumerate(matrices):
            T, N = X.shape
            freq = X.sum(axis=0)

            # Топ-10 горячих получают 70% веса
            hot_idx = np.argsort(-freq)[:10]
            probs = np.ones(N) * 0.3 / N
            probs[hot_idx] = 0.7 / len(hot_idx)
            probs = probs / probs.sum()

            predictions.append(probs)

        return predictions


# =================== Метод-детектор аномалий ===================
@register
class AnomalyDetector(Method):
    """
    Детектор аномалий: выявление чисел с подозрительным поведением

    Ищет числа, у которых:
    - Частота отличается от ожидаемой > 2 сигм
    - Есть длинные серии подряд
    - Необычный тренд
    """
    name = "anomaly_detector"
    title = "Детектор аномалий"
    tags = ["game-specific", "fraud-detection"]

    def predict_one(self, X, date=None):
        T, N = X.shape
        if T < 100:
            return np.ones(N) / N

        freq = X.sum(axis=0)
        expected = T * (6 / N)  # Пример для 6 чисел
        std = np.sqrt(expected * (1 - 6/N))

        # Z-scores
        z_scores = np.abs((freq - expected) / std)

        # Аномальные числа (|z| > 2)
        anomalies = z_scores > 2

        if anomalies.sum() > 0:
            # Поставить на аномальные числа
            probs = anomalies.astype(float)
            probs = probs / probs.sum()
            return probs
        else:
            return np.ones(N) / N


# =================== Метод для новых игр ===================
@register
class NewGame_Conservative(Method):
    """
    Для новых игр с малым архивом (<100 тиражей)

    Консервативный подход: равномерное распределение + легкий уклон к горячим.
    """
    name = "new_game_conservative"
    title = "Новая игра (консервативно)"
    tags = ["game-specific", "small-data"]

    def predict_one(self, X, date=None):
        T, N = X.shape

        if T < 50:
            # Слишком мало данных → равномерно
            return np.ones(N) / N

        # 80% равномерно, 20% по частотам
        freq = X.sum(axis=0)
        freq_probs = freq / freq.sum()
        uniform = np.ones(N) / N

        probs = 0.8 * uniform + 0.2 * freq_probs
        return probs


print("✅ Специализированные методы загружены!")
print(f"📊 Всего методов: {len([m for m in dir() if m.startswith('Game')])} игровых")
print(f"🔍 + 2 универсальных (AnomalyDetector, NewGame_Conservative)")
