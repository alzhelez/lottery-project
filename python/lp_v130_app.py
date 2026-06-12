# -*- coding: utf-8 -*-
"""
lp_v130_app.py — Полный Python/Streamlit аналог LP-v130.html (v13.0)
Запуск: streamlit run lp_v130_app.py

Требования: pip install streamlit plotly pandas numpy scipy

v13.0 — Critical and high bug fixes:
  - F1: Added PICK_B1/PICK_B2 constants (dynamic pick counts per block)
  - F2: Fixed _monte_carlo_confidence performance — consensus() moved outside simulation loop
  - F3: Fixed _fast_pred model index 9→14 for m15_cyclic
  - F4: Fixed zone-model tail — last zone now extends to B1_MAX/B2_MAX
  - F5: PRIMES set now dynamically generated via Sieve of Eratosthenes
  - F6: All hardcoded pick counts (4/8) replaced with PICK_B1/PICK_B2 constants
  - F7: Docstring updated: 132→133 models
  - F8: Version bumped to v13.0
  - Total: 133 models (v25.0: G9/G10 disabled)

v9.0 — Fundamental accuracy overhaul:
  - F1: Parser now accepts B1 (1-35) and B2 (1-12) numbers (was limited to 1-20)
  - F2: Auto-detection of number ranges from uploaded data
  - F3: All models now use correct B1_MAX/B2_MAX ranges
  - F4: b1b2_from_scores supports separate ranges, fixed noise (os.urandom)
  - F5: FreqCache supports dynamic ranges
  - F6: _fast_pred model indices corrected (were pointing to wrong models)
  - F7: DualBayesRing: separate STD/RNG tracking with weight decay
  - F8: Position-aware ensemble for per-position model weighting
  - F9: Triplet analysis models (frequent 3-number combinations) [removed in v25.0]
  - F10: k-fold cross-validation for accuracy stability measurement
  - F11: Monte Carlo confidence intervals for predictions
  - F12: Dynamic model selection (auto-exclude underperformers)
  - F13: Zone-based spread model adapts to actual number ranges [removed in v25.0]
  - F14: 5 new models (total: 155, now 133 after v25.0 cleanup)

v8.0 — Critical accuracy fixes and diversity improvements:
  - B1: b1b2_from_scores now adds tiny random noise to break deterministic ties
  - B2: _fast_pred model indices corrected (were off by 1-2 positions)
  - B3: Anti-consensus models now use stronger diversity factors [removed in v25.0]
  - B4: Overall prediction diversity increased ~15% (more unique predictions)
  - B5: Accuracy metric improved: shows per-block average instead of just >=5 count

v7.0 — Final audit and accuracy improvements:
  - A1: _fast_pred now uses 16 diverse models (was 8) for better accuracy during training
  - A2: Recency blend increased to 35% (was 25%) for more responsive predictions
  - A3: parse_text now logs rejected lines count for better data diagnostics
  - A4: model_report_data cap increased to 3000 (was 1000) for richer LPD_DATA
  - A5: Accuracy tab now shows STD vs RNG breakdown
  - A6: Added draw-type-specific models to _fast_pred

v6.1 — Final audit and quality fixes:
  - F1: Added _check_data_quality() — diagnostics for gaps, duplicates, type distribution
  - F2: Data quality warnings shown after file upload
  - F3: Added STD-specific prediction section (was missing — only RNG existed)
  - F4: Draw numbering now correctly reports gaps in data
  - F5: Improved accuracy baseline comparison

v6.0 — Model diversity and next-draw fixes:
  - V7: _compute_next_draw_info helper — correct draw numbering from draws_raw
  - V8: Diversity models (ColdNumberFocus) [anti-consensus/rand-perm removed in v25.0]
  - V9: G9 model group (6 old + diversity models) [cleaned in v25.0]
  - V10: Next draw info now shows ГСЧ/STD next times separately
  - V11: Random baseline comparison in Accuracy tab
  - V12: RNG prediction section uses draws_raw for correct numbering

v3.0 — Новые модели и исправленный формат отчёта:
  - V1: 17 новых моделей (AntiMajority, Cold, Combo) [PosFreq/DTPos/Spread removed in v25.0]
  - V2: TOTAL_MODELS увеличено до 150
  - V3: report.html v3.0 — per-draw per-model позиционные данные (LPD_DATA)
  - V4: lottery_pipeline.py v3.0 — recency-weighted ensemble, draw-type awareness
  - V5: model_report_data включает draw_type для каждого тиража
  - V6: Исправлена ошибка парсинга 'Энтропия' (новый формат отчёта)

v1.6 — Аудит и чистка:
  - A1: Удалены неиспользуемые импорты (random, base64, deque, plotly.express)
  - A2: Все bare except: заменены на except Exception
  - A3: Добавлена защита от повторного парсинга при rerun (хеш файла)
  - A4: Полный аудит моделей — все уникальны, ключи кэша не дублируются
  - A5: Проверены все весовые наборы G6 — нет скалярных кратных

v1.5 — Рефакторинг и улучшения:
  - T1: LSTM Pipeline вынесен в lottery_pipeline.py (standalone CLI + import)
  - T2: Исправлены 9 критических SyntaxError в LSTM-индексации массивов
  - T3: model_report_data ограничено 1000 записей + прогресс-бар для экспорта
  - T4: Добавлены пояснения к вкладкам Обучение/Проверка
  - T5: Вкладка Точность — последние 100 тиражей с датой, выбор кол-ва
  - T6: Вкладка Прогноз — информация о следующем тираже
  - T7: Уменьшен отступ сверху, h1 уменьшен до 1.6rem
  - T8: Версия обновлена до 1.5

v1.4 — Повторный аудит и исправления:
  - C1+C4: LSTM Pipeline — исправлен SyntaxError, добавлена фильтрация прогнозов
  - C2: _adaptive_ewma — alpha теперь реально адаптируется per-draw (0.05→0.30)
  - C3: m09_deep — сравнивает все 4 элемента блока вместо первых 2
  - D1: PosFreq заменена на PosDrift (positional drift: recent vs older)
  - D2: ColdStreak заменена на GapAccel (gap acceleration: overdue detection)
  - R3: Добавлена DrawTypeFreq — отдельная частота для std/rng тиражей

v1.2 — Исправления:
  - .style.map() → HTML-таблица (не нужен jinja2)
  - TF_CPP_MIN_LOG_LEVEL=3 (подавление TF warnings)
  - TF_ENABLE_ONEDNN_OPTS=0 (подавление oneDNN warnings)

v1.1 — Исправления:
  - use_container_width → width="stretch" (Streamlit 1.44+)
  - render_stat_badges исправлен
  - HTML-отчёт совместим с lottery_pipeline.py
  - model_report_data для всех моделей
  - all_model_predictions.csv (pipe-separated)
  - Таймер и процент к прогресс-барам
  - Новая вкладка "🧠 LSTM Pipeline"
  - _velocity уникальные ключи
  - Обработка ошибок, валидация данных
  - Цветовое кодирование согласия в моделях
  - Защита от деления на ноль
"""

import os
import sys
import math
import re
import io
import csv
import time
import hashlib
from collections import defaultdict, Counter

# Suppress TensorFlow warnings BEFORE any TF import
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

__version__ = "14.0"
# v25.0: G9/G10 model groups disabled — code removed
TOTAL_MODELS = 133  # 107 active after 26 disabled (see _DISABLED_MODELS)

# v25.1: Models disabled based on cross-game backtesting (consistently underperform
# random baseline on BOTH 4x20 and 6x45plus games).  These get empty predictions
# in all_predictions() and are excluded from consensus voting.
_DISABLED_MODELS = frozenset({
    13,   # Entropy
    15,   # EnhancedEnsemble — 1.32 (4x20), consistently bad
    39,   # Gap+Freq-2.5
    41,   # Gap+Freq-3.0
    65,   # StreakReversal
    66,   # StreakReversal2
    68,   # FreqGapHybrid
    69,   # PeriodDetect
    70,   # Ensemble-1 — 1.32 (4x20), 0.94 (6x45plus), weak on BOTH
    72,   # Ensemble-3
    74,   # Ensemble-5 — 1.34 (4x20), 1.02 (6x45plus), weak on BOTH
    78,   # Ensemble-9
    81,   # Ensemble-12 — 1.34 (4x20), 1.02 (6x45plus), weak on BOTH
    84,   # Ensemble-15
    86,   # Ensemble-17
    87,   # Ensemble-18 — 1.36 (4x20), consistently bad
    88,   # AdaptWindow
    89,   # AdaptWindow2
    90,   # Ensemble-21 — 1.34 (4x20), 1.02 (6x45plus), weak on BOTH
    95,   # Ensemble-26 — 1.34 (4x20), 1.02 (6x45plus), weak on BOTH
    97,   # Ensemble-28 — 1.36 (4x20), consistently bad
    98,   # StreakReversal3
    103,  # HotStreak-10 — 1.28 (4x20), worst non-ensemble active model
    125,  # Pos-P2
    # v38.2: Additional models disabled — consistently below random on 4x20 eval
    # 21 (Window-10): 1.38, 67 (DrawType): 1.40
    21,   # Window-10 — 1.38 (4x20), below random baseline
    67,   # DrawType — 1.40 (4x20), at/below random baseline
})

# v25.1: Cross-game top performers — beat random baseline on BOTH games.
# Removed models that only performed well on one game (game-specific).
# These get 2x voting weight in weighted consensus.
_BOOSTED_MODELS = frozenset({
    9,    # Fibonacci — 1.38 (4x20), 1.12 (6x45plus)
    19,   # EWMA — 1.62 (4x20), 1.14 (6x45plus)
    22,   # Window-15 — 1.46 (4x20), 1.26 (6x45plus) ★ best 6x45plus
    37,   # Gap+Freq-0.5 — 1.68 (4x20), 1.16 (6x45plus)
    40,   # Gap+Freq-0.3 — 1.66 (4x20), 1.14 (6x45plus)
    42,   # Gap+Freq-0.6 — 1.72 (4x20), 1.14 (6x45plus)
    62,   # Bayesian-0.3 — 1.66 (4x20), 1.00 (6x45plus, at baseline)
    85,   # HotColdBalance — 1.66 (4x20), 1.10 (6x45plus)
    93,   # HotColdBalance2 — 1.66 (4x20), 1.08 (6x45plus)
    94,   # HotColdBalance3 — 1.66 (4x20), 1.12 (6x45plus)
    106,  # SumParity — 1.42 (4x20), 1.18 (6x45plus)
    111,  # EntropyWeighted — 1.66 (4x20), 1.24 (6x45plus)
    112,  # MeanRevert-50 — 1.56 (4x20), 1.20 (6x45plus)
    115,  # LagCorrel — 1.52 (4x20), 1.22 (6x45plus)
    126,  # Pos-P3 — 1.82 (4x20), 1.24 (6x45plus) ★ best 4x20
})

# Threshold: below this many training draws, fall back to simple majority vote
_LOW_DATA_THRESHOLD = 500

# Number ranges — auto-detected from data, defaults to 1-20/1-20 for backward compatibility
B1_MAX = 20  # Will be updated by parse_text() auto-detection
B2_MAX = 20  # Will be updated by parse_text() auto-detection
PICK_B1 = 4  # Numbers to pick from Block 1 (will be updated by parse_text auto-detection)
PICK_B2 = 4  # Numbers to pick from Block 2

# Flag to prevent auto-detection from overriding game hints
# CAVEAT: _game_hint_applied is a module-level mutable boolean used as a global sentinel.
# It is reset to False at the start of parse_text() and set to True by _apply_game_hint().
# This design is fragile because concurrent or sequential calls to parse_text() for different
# games can interfere — a subsequent parse_text() call resets the flag before the previous
# caller has finished using it. In practice, this is safe because parse_text() is always
# called in a single-threaded context, but it should be refactored to an instance attribute
# if multi-threading or concurrent parsing is ever introduced.
_game_hint_applied = False

# Game format hints: pick counts and max values for known games.
# Used by parse_text() to correctly split 3-part draw data.
# Key = game name (from stoloto.ru API), Value = {pick_b1, pick_b2, b1_max, b2_max}
GAME_FORMAT_HINTS = {
    '4x20':        {'pick_b1': 4, 'pick_b2': 4, 'b1_max': 20, 'b2_max': 20},
    '6x45plus':    {'pick_b1': 6, 'pick_b2': 1, 'b1_max': 45, 'b2_max': 4},
    '6x45':        {'pick_b1': 6, 'pick_b2': 0, 'b1_max': 45, 'b2_max': 1},
    '5x36plus':    {'pick_b1': 5, 'pick_b2': 1, 'b1_max': 36, 'b2_max': 4},
    '5x36':        {'pick_b1': 5, 'pick_b2': 0, 'b1_max': 36, 'b2_max': 1},
    '5x2':         {'pick_b1': 5, 'pick_b2': 2, 'b1_max': 50, 'b2_max': 10},
    '7x49':        {'pick_b1': 7, 'pick_b2': 0, 'b1_max': 49, 'b2_max': 1},
    '6x36':        {'pick_b1': 6, 'pick_b2': 0, 'b1_max': 36, 'b2_max': 1},
    '5x50':        {'pick_b1': 5, 'pick_b2': 0, 'b1_max': 50, 'b2_max': 1},
    '6x49':        {'pick_b1': 6, 'pick_b2': 0, 'b1_max': 49, 'b2_max': 1},
    'rapido':      {'pick_b1': 8, 'pick_b2': 1, 'b1_max': 20, 'b2_max': 4},
    'top3':        {'pick_b1': 3, 'pick_b2': 0, 'b1_max': 9,  'b2_max': 1},
    'keno':        {'pick_b1': 20,'pick_b2': 0, 'b1_max': 80, 'b2_max': 1},
    'keno2':       {'pick_b1': 20,'pick_b2': 1, 'b1_max': 80, 'b2_max': 10},
    'zabeg':       {'pick_b1': 6, 'pick_b2': 0, 'b1_max': 20, 'b2_max': 1},
    'zabegalochka':{'pick_b1': 6, 'pick_b2': 0, 'b1_max': 20, 'b2_max': 1},
    'duel':        {'pick_b1': 6, 'pick_b2': 0, 'b1_max': 20, 'b2_max': 1},
    '12x24':       {'pick_b1': 12,'pick_b2': 0, 'b1_max': 24, 'b2_max': 1},
    '6x49plus':    {'pick_b1': 6, 'pick_b2': 1, 'b1_max': 49, 'b2_max': 4},
    '4x20plus':    {'pick_b1': 4, 'pick_b2': 1, 'b1_max': 20, 'b2_max': 4},
}


def _apply_game_hint(game_name):
    """Set global PICK_B1, PICK_B2, B1_MAX, B2_MAX from game format hints."""
    global PICK_B1, PICK_B2, B1_MAX, B2_MAX, _game_hint_applied
    if not game_name:
        return False
    # Normalize: strip draws_ prefix, .txt suffix
    name = game_name.replace('draws_', '').replace('tirazh', '').strip()
    # Try exact match and common variations
    for key in (name, name.lower()):
        if key in GAME_FORMAT_HINTS:
            hint = GAME_FORMAT_HINTS[key]
            PICK_B1 = hint['pick_b1']
            PICK_B2 = hint['pick_b2']
            B1_MAX = max(hint.get('b1_max', 20), 20)
            B2_MAX = max(hint.get('b2_max', 1), 1)
            _game_hint_applied = True
            return True
    return False

# ════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG  (must be first Streamlit call)
# ════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="LP-v130 · Lottery Predictor",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════════════
#  CUSTOM CSS  — dark theme matching LP-v130.html
# ════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
  /* ── Global ── */
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Rajdhani:wght@400;600;700&display=swap');

  [data-testid="stAppViewContainer"] {
      background: linear-gradient(135deg, #0a0f1e 0%, #0d1117 60%, #060b18 100%);
      color: #e2e8f0;
      font-family: 'Rajdhani', sans-serif;
  }
  [data-testid="stAppViewContainer"] > div { padding-top: 1rem !important; }
  [data-testid="stSidebar"] {
      background: linear-gradient(180deg, #0d1228 0%, #111827 100%);
      border-right: 1px solid #1e2d4a;
  }
  /* Headers */
  h1,h2,h3 { font-family:'Rajdhani',sans-serif; }
  h1 { color:#60a5fa; font-size:1.6rem; font-weight:700; }
  h2 { color:#60a5fa; font-size:1.35rem; }
  h3 { color:#94a3b8; font-size:1.05rem; }

  /* Metric cards */
  [data-testid="metric-container"] {
      background: rgba(30,58,110,.25);
      border: 1px solid rgba(59,130,246,.25);
      border-radius:10px;
      padding:12px;
  }
  [data-testid="stMetricValue"] { color:#f1f5f9; font-size:1.6rem; font-weight:700; }
  [data-testid="stMetricLabel"] { color:#94a3b8; font-size:.75rem; text-transform:uppercase; }

  /* Buttons */
  .stButton>button {
      background: linear-gradient(135deg,#2563eb,#1d4ed8);
      color:white; border:none; border-radius:8px;
      font-family:'Rajdhani',sans-serif; font-weight:700;
      font-size:.95rem; transition: all .2s;
  }
  .stButton>button:hover { background:linear-gradient(135deg,#3b82f6,#2563eb); transform:translateY(-1px); }

  /* Number balls */
  .ball-b1 {
      display:inline-flex; align-items:center; justify-content:center;
      width:42px; height:42px; border-radius:50%;
      background:linear-gradient(135deg,#2563eb,#1d4ed8);
      color:white; font-weight:700; font-size:1.1rem;
      margin:3px; box-shadow:0 4px 12px rgba(37,99,235,.5);
      border:2px solid rgba(96,165,250,.4);
  }
  .ball-b2 {
      display:inline-flex; align-items:center; justify-content:center;
      width:42px; height:42px; border-radius:50%;
      background:linear-gradient(135deg,#059669,#047857);
      color:white; font-weight:700; font-size:1.1rem;
      margin:3px; box-shadow:0 4px 12px rgba(5,150,105,.5);
      border:2px solid rgba(52,211,153,.4);
  }
  .ball-hit {
      background:linear-gradient(135deg,#d97706,#b45309) !important;
      box-shadow:0 4px 16px rgba(217,119,6,.6) !important;
      animation: pulse 1.5s infinite;
  }
  @keyframes pulse {
    0%,100% { box-shadow:0 4px 16px rgba(217,119,6,.6); }
    50%      { box-shadow:0 0 0 8px rgba(217,119,6,.15); }
  }

  /* Prediction card */
  .pred-card {
      background: linear-gradient(135deg,#0f2040 0%,#1a2d4f 100%);
      border:1px solid rgba(59,130,246,.35);
      border-radius:14px; padding:22px 26px;
      box-shadow:0 6px 24px rgba(0,0,0,.4);
      margin-bottom:18px;
  }
  .pred-label {
      font-size:.75rem; font-weight:700; text-transform:uppercase;
      letter-spacing:1.2px; color:#94a3b8; margin-bottom:10px;
  }

  /* Stat badge */
  .stat-badge {
      display:inline-block;
      background:rgba(99,102,241,.18);
      border:1px solid rgba(99,102,241,.35);
      border-radius:20px; padding:3px 12px;
      font-size:.78rem; color:#a5b4fc; font-weight:700;
      margin:2px;
  }
  .stat-badge-green { background:rgba(16,185,129,.15); border-color:rgba(16,185,129,.35); color:#34d399; }
  .stat-badge-amber { background:rgba(245,158,11,.15); border-color:rgba(245,158,11,.35); color:#fbbf24; }
  .stat-badge-red   { background:rgba(239,68,68,.15);  border-color:rgba(239,68,68,.35);  color:#f87171; }

  /* Progress-like bar */
  .hit-bar { display:flex; gap:4px; align-items:center; margin-bottom:6px; }
  .bar-fill { height:8px; border-radius:4px; background:linear-gradient(90deg,#3b82f6,#60a5fa); }
  .bar-track { height:8px; border-radius:4px; background:rgba(255,255,255,.08); flex:1; overflow:hidden; }

  /* Log strip */
  .log-strip {
      background:#0a0f1e; border:1px solid #1e2d4a; border-radius:8px;
      padding:10px 14px; font-family:'JetBrains Mono',monospace;
      font-size:.75rem; color:#94a3b8; max-height:200px; overflow-y:auto;
  }
  .log-ok   { color:#34d399; }
  .log-warn { color:#fbbf24; }
  .log-info { color:#60a5fa; }

  /* Section headers */
  .section-hdr {
      display:flex; align-items:center; gap:8px;
      border-bottom:2px solid rgba(59,130,246,.25);
      padding-bottom:8px; margin:24px 0 16px;
  }
  .section-hdr-title { font-size:1.1rem; font-weight:700; color:#60a5fa; }

  /* Accuracy row */
  .acc-row {
      display:flex; align-items:center; gap:12px;
      padding:7px 0; border-bottom:1px solid rgba(255,255,255,.05);
  }
  .acc-draw-no { color:#64748b; font-size:.78rem; min-width:60px; }
  .acc-balls   { display:flex; gap:3px; flex:1; }
  .acc-ball    {
      width:26px; height:26px; border-radius:50%; display:inline-flex;
      align-items:center; justify-content:center; font-size:.72rem; font-weight:700;
      color:white;
  }
  .ab-hit   { background:#d97706; }
  .ab-miss  { background:#1e293b; color:#64748b; border:1px solid #334155; }
  .ab-act   { background:#1e3a5f; border:1px solid #3b82f6; }
  .acc-score{ font-weight:700; font-size:.9rem; min-width:40px; text-align:right; }
  .score-5  { color:#34d399; }
  .score-4  { color:#fbbf24; }
  .score-3  { color:#94a3b8; }
  .score-low{ color:#475569; }

  /* Chip / draw-block for HTML report */
  .chip {
      display:inline-block; background:rgba(59,130,246,.15);
      border:1px solid rgba(59,130,246,.3); border-radius:8px;
      padding:3px 8px; margin:2px; font-size:.75rem;
  }
  .pt { color:#a5b4fc; font-size:.7rem; margin-left:2px; }

  /* Agreement color badges */
  .agree-green { color:#34d399; font-weight:700; }
  .agree-amber { color:#fbbf24; font-weight:700; }
  .agree-grey  { color:#64748b; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════
#  CORE ENGINE  (inline — same logic as lp_v130.py)
# ════════════════════════════════════════════════════════════════════════

# Текущее расписание (с 17.12.2025, тираж #12121):
# STD (стандартные): 10:00, 13:00, 18:00, 22:00
# RNG (ГСЧ): 12:07, 13:52, 16:07, 16:22, 20:07, 23:22
STD_TIMES = {'10:00', '13:00', '18:00', '22:00'}
RNG_TIMES = {'12:07', '13:52', '16:07', '16:22', '20:07', '23:22'}
# Исторические времена (больше не используются):
LEGACY_TIMES = {'08:20', '12:00', '15:10', '16:00', '16:35', '16:50', '16:52', '20:00'}
ALL_SCHEDULE_TIMES = STD_TIMES | RNG_TIMES

# Порядок тиражей в течение дня (для определения следующего):
DAILY_SCHEDULE_ORDER = [
    '10:00', '12:07', '13:00', '13:52', '16:07', '16:22',
    '18:00', '20:07', '22:00', '23:22'
]

class Draw:
    __slots__ = ('date','draw_no','block1','block2','all_numbers','draw_type','draw_hm')
    def __init__(self, date, draw_no, block1, block2):
        self.date=date; self.draw_no=draw_no
        self.block1=block1; self.block2=block2
        self.all_numbers=block1+block2
        hm=re.search(r'(\d{2}:\d{2})',date)
        self.draw_hm=hm.group(1) if hm else ''
        if self.draw_hm in RNG_TIMES:
            self.draw_type='rng'
        elif self.draw_hm in STD_TIMES:
            self.draw_type='std'
        elif self.draw_hm in LEGACY_TIMES:
            self.draw_type='legacy'
        else:
            self.draw_type='unknown'

class AccuracyEntry:
    __slots__=('draw_no','pred_b1','pred_b2','act_b1','act_b2','hits_b1','hits_b2','date')
    def __init__(self,draw_no,pb1,pb2,ab1,ab2,date=''):
        self.draw_no=draw_no; self.pred_b1=list(pb1); self.pred_b2=list(pb2)
        self.act_b1=list(ab1); self.act_b2=list(ab2)
        self.hits_b1=len(set(pb1)&set(ab1)); self.hits_b2=len(set(pb2)&set(ab2))
        self.date=date
    def total(self): return self.hits_b1+self.hits_b2

def parse_line(line):
    line=line.strip().replace('\r','')
    if not line: return None
    parts=line.split('||')
    if len(parts) < 3: return None
    try:
        # Parse block numbers from parts (skip the date and number fields)
        # Support both 3-part and 4-part formats:
        #   3-part: DATE||NUMBER||ALL_NUMBERS
        #   4-part: DATE||NUMBER||BLOCK1||BLOCK2
        #   5-part: DATE||NUMBER||BLOCK1||BLOCK2||EXTRA (ignore extra)
        if len(parts) >= 4 and parts[3].strip():
            # 4-part format: explicit block separation
            b1=[int(x.strip()) for x in parts[2].split(',') if x.strip()]
            b2=[int(x.strip()) for x in parts[3].split(',') if x.strip()]
        else:
            # 3-part format: split by default PICK_B1
            raw_nums=[x.strip() for x in parts[2].split(',') if x.strip()]
            if not raw_nums: return None
            nums=[int(x) for x in raw_nums]
            b1,b2=nums[:PICK_B1],nums[PICK_B1:]
        nums=b1+b2
        if len(nums)<2: return None
        # Skip duplicate check within blocks — some games legitimately
        # have overlapping number ranges between blocks
        # Allow empty block2 for single-block games (pick_b2=0)
        if len(b1)==0: return None
        # Accept any positive numbers — auto-detection in parse_text will set correct ranges
        if not all(n>=1 for n in nums): return None
        return Draw(parts[0].strip(),int(parts[1].strip()),b1,b2)
    except (ValueError, IndexError, AttributeError): return None

def parse_text(text, game_name=None):
    """Parse draw data text into Draw objects.

    Args:
        text: Draw data text (DATE||NUM||BLOCK1||BLOCK2 format)
        game_name: Optional game identifier (e.g. '6x45plus', '4x20').
                   If provided and found in GAME_FORMAT_HINTS, will pre-set
                   PICK_B1/PICK_B2/B1_MAX/B2_MAX before parsing 3-part lines.
    """
    global PICK_B1, PICK_B2, B1_MAX, B2_MAX, _game_hint_applied

    # ── Apply game format hints BEFORE parsing ──
    _game_hint_applied = False
    if game_name and _apply_game_hint(game_name):
        log(f'🎯 Формат из hints: PICK_B1={PICK_B1}, PICK_B2={PICK_B2}, '
            f'B1_MAX={B1_MAX}, B2_MAX={B2_MAX} (game={game_name})', 'ok')

    lines = text.split('\n')
    draws = []
    rejected = 0
    for line in lines:
        d = parse_line(line)
        if d:
            draws.append(d)
        elif line.strip():
            rejected += 1
    # Validate for duplicates
    seen = set()
    unique_draws = []
    dup_count = 0
    for d in draws:
        if d.draw_no in seen:
            dup_count += 1
        else:
            seen.add(d.draw_no)
            unique_draws.append(d)
    if dup_count > 0:
        log(f"⚠ Найдено {dup_count} дубликатов тиражей, удалено", 'warn')
    if rejected > 0:
        log(f"⚠ Отклонено {rejected} строк (неверный формат)", 'warn')
    # Auto-detect number ranges from data (only if no game hint was applied)
    if unique_draws and not _game_hint_applied:
        detected_b1_max = max(max(d.block1) for d in unique_draws)
        detected_b2_max = max(max(d.block2) for d in unique_draws) if any(d.block2 for d in unique_draws) else 1
        new_b1_max = max(detected_b1_max, 20)
        new_b2_max = detected_b2_max
        if new_b1_max != B1_MAX or new_b2_max != B2_MAX:
            B1_MAX = new_b1_max
            B2_MAX = new_b2_max
            log(f'📊 Авто-детекция диапазона: Б1 = 1-{B1_MAX}, Б2 = 1-{B2_MAX}', 'ok')
        else:
            log(f'📊 Диапазон данных: Б1 = 1-{B1_MAX}, Б2 = 1-{B2_MAX}', 'info')
        # Auto-detect pick counts from data using mode (most common block size)
        b1_sizes = Counter(len(d.block1) for d in unique_draws)
        b2_sizes = Counter(len(d.block2) for d in unique_draws if d.block2)
        detected_pick_b1 = b1_sizes.most_common(1)[0][0] if b1_sizes else PICK_B1
        detected_pick_b2 = b2_sizes.most_common(1)[0][0] if b2_sizes else PICK_B2
        if detected_pick_b1 != PICK_B1 or detected_pick_b2 != PICK_B2:
            PICK_B1 = detected_pick_b1
            PICK_B2 = detected_pick_b2
            log(f'📊 Авто-детекция PICK: Б1={PICK_B1}, Б2={PICK_B2} (total={PICK_B1+PICK_B2})', 'ok')
    elif unique_draws and _game_hint_applied:
        # Still validate max ranges from actual data (in case hint was conservative)
        detected_b1_max = max(max(d.block1) for d in unique_draws)
        _b2_vals = [max(d.block2) for d in unique_draws if d.block2]
        detected_b2_max = max(_b2_vals) if _b2_vals else B2_MAX
        if detected_b1_max > B1_MAX:
            B1_MAX = detected_b1_max
            log(f'📊 Корректировка B1_MAX: 1-{B1_MAX}', 'ok')
        if detected_b2_max > B2_MAX:
            B2_MAX = detected_b2_max
            log(f'📊 Корректировка B2_MAX: 1-{B2_MAX}', 'ok')
        log(f'✅ Формат подтверждён: PICK_B1={PICK_B1}, PICK_B2={PICK_B2}, '
            f'B1_MAX={B1_MAX}, B2_MAX={B2_MAX}', 'ok')
    unique_draws.sort(key=lambda d:d.draw_no)
    return unique_draws


def _check_data_quality(draws):
    """Analyze data quality: duplicates, gaps, missing draws."""
    if not draws:
        return None
    nos = [d.draw_no for d in draws]
    min_no, max_no = min(nos), max(nos)
    unique_nos = set(nos)
    expected_count = max_no - min_no + 1
    missing = sorted(set(range(min_no, max_no + 1)) - unique_nos)

    # Check time distribution
    type_counts = defaultdict(int)
    time_counts = Counter()
    for d in draws:
        type_counts[d.draw_type] += 1
        if d.draw_hm:
            time_counts[d.draw_hm] += 1

    return {
        'total_draws': len(draws),
        'min_no': min_no,
        'max_no': max_no,
        'expected_count': expected_count,
        'missing_count': len(missing),
        'missing_sample': missing[:20],
        'has_gaps': len(missing) > 0,
        'type_counts': dict(type_counts),
        'top_times': time_counts.most_common(15),
    }


def exp_w(age,tau=59.0): return math.exp(-age/tau)

def _compute_time_weights(n_draws, half_life=500):
    """Compute exponential time weights for recency-weighted frequency."""
    if n_draws <= 0: return []
    return [0.5 ** ((n_draws - 1 - i) / max(half_life, 1)) for i in range(n_draws)]

def _compute_next_draw_info(draws_list):
    """Compute next draw number, type, time from a list of Draw objects.
    Uses draws_list (draws_raw) which always has the latest uploaded data,
    unlike st.session_state.draws which requires training.
    Returns dict with next_draw_no, next_time, next_type, last_draw, etc.
    """
    if not draws_list:
        return None
    last_draw = draws_list[-1]  # sorted by draw_no, so last = highest draw_no
    last_hm = last_draw.draw_hm
    last_dt = last_draw.draw_type
    next_draw_no = last_draw.draw_no + 1
    
    # Determine next scheduled time and type
    if last_hm and last_hm in DAILY_SCHEDULE_ORDER:
        idx = DAILY_SCHEDULE_ORDER.index(last_hm)
        if idx < len(DAILY_SCHEDULE_ORDER) - 1:
            next_time = DAILY_SCHEDULE_ORDER[idx + 1]
        else:
            # Last draw of the day, next is first draw of next day
            next_time = DAILY_SCHEDULE_ORDER[0]
        next_type = 'RNG' if next_time in RNG_TIMES else ('STD' if next_time in STD_TIMES else 'Unknown')
    elif last_hm and last_hm in LEGACY_TIMES:
        # Legacy draw — can't reliably determine next; use full schedule
        next_time = DAILY_SCHEDULE_ORDER[0]
        next_type = 'STD'
    else:
        next_time = '—'
        next_type = last_dt.upper() if last_dt else '—'
    
    # Find next RNG time specifically
    next_rng_time = None
    if last_hm and last_hm in DAILY_SCHEDULE_ORDER:
        idx = DAILY_SCHEDULE_ORDER.index(last_hm)
        for t in DAILY_SCHEDULE_ORDER[idx+1:]:
            if t in RNG_TIMES:
                next_rng_time = t
                break
    if next_rng_time is None:
        # Next RNG is first RNG of the next day
        rng_times_sorted = sorted(RNG_TIMES, key=lambda t: DAILY_SCHEDULE_ORDER.index(t) if t in DAILY_SCHEDULE_ORDER else 99)
        next_rng_time = rng_times_sorted[0] if rng_times_sorted else None
    
    # Find next STD time specifically
    next_std_time = None
    if last_hm and last_hm in DAILY_SCHEDULE_ORDER:
        idx = DAILY_SCHEDULE_ORDER.index(last_hm)
        for t in DAILY_SCHEDULE_ORDER[idx+1:]:
            if t in STD_TIMES:
                next_std_time = t
                break
    if next_std_time is None:
        std_times_sorted = sorted(STD_TIMES, key=lambda t: DAILY_SCHEDULE_ORDER.index(t) if t in DAILY_SCHEDULE_ORDER else 99)
        next_std_time = std_times_sorted[0] if std_times_sorted else None
    
    return {
        'next_draw_no': next_draw_no,
        'next_time': next_time,
        'next_type': next_type,
        'next_rng_time': next_rng_time,
        'next_std_time': next_std_time,
        'last_draw': last_draw,
        'last_hm': last_hm,
        'last_type': last_dt,
    }

def b1b2_from_scores(sb1,sb2,b1_max=None,b2_max=None):
    if b1_max is None: b1_max = B1_MAX
    if b2_max is None: b2_max = B2_MAX
    # v9.0: Use os.urandom for truly unique noise seed per call (fixes deterministic id()-based noise)
    try:
        _seed = int.from_bytes(os.urandom(4), 'big')
    except Exception:
        _seed = 42
    _rng_noise = np.random.default_rng(_seed)
    _noise1 = _rng_noise.uniform(0, 0.001, size=b1_max)
    _noise2 = _rng_noise.uniform(0, 0.001, size=b2_max)
    top4b1=sorted(range(1,b1_max+1),key=lambda x,i=0:-(sb1.get(x,0)+_noise1[x-1]))[:PICK_B1]
    top4b1.sort()
    # v9.0: Allow overlap between B1 and B2 (B2 range 1-12 is subset of B1 range 1-35)
    top4b2=sorted(range(1,b2_max+1),key=lambda x:-(sb2.get(x,0)+_noise2[x-1]))[:PICK_B2]
    top4b2.sort()
    return sorted(top4b1),sorted(top4b2)

class FreqCache:
    def __init__(self,draws,b1_max=None,b2_max=None):
        self.b1_max = b1_max if b1_max is not None else B1_MAX
        self.b2_max = b2_max if b2_max is not None else B2_MAX
        self.b1f=defaultdict(int); self.b2f=defaultdict(int)
        self.ls1={}; self.ls2={}; self.n=len(draws)
        for i,d in enumerate(draws):
            for x in d.block1: self.b1f[x]+=1; self.ls1[x]=i
            for x in d.block2: self.b2f[x]+=1; self.ls2[x]=i
    def gap1(self,x): ls=self.ls1.get(x,-1); return self.n-ls-1 if ls>=0 else self.n
    def gap2(self,x): ls=self.ls2.get(x,-1); return self.n-ls-1 if ls>=0 else self.n
    def aff(self,x):
        b1=self.b1f.get(x,0); b2=self.b2f.get(x,0); tot=b1+b2
        return b1/tot if tot>0 else 0.5

def _primes_up_to(n):
    """Generate set of all primes up to n using Sieve of Eratosthenes."""
    if n < 2:
        return set()
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n**0.5) + 1):
        if sieve[i]:
            for j in range(i*i, n+1, i):
                sieve[j] = False
    return {x for x in range(2, n+1) if sieve[x]}

class LP132:
    """All 133 prediction models."""
    def __init__(self):
        self.draws=[]
        self.gfc=None
        self._c={}

    def update(self,draws):
        self.draws=draws; self.gfc=FreqCache(draws) if draws else None; self._c.clear()

    def _last(self): return self.draws[-1] if self.draws else None
    def _rec(self,n): return self.draws[-n:] if len(self.draws)>=n else self.draws[:]
    def _S(self,key,fn):
        if key not in self._c: self._c[key]=fn()
        return self._c[key]

    # ── 20 base models ──────────────────────────────────────────────────
    def m01_freq(self):
        def _r():
            n=len(self.draws); sb1=defaultdict(float); sb2=defaultdict(float)
            last3_b1=set(x for d in self.draws[-3:] for x in d.block1) if n>=3 else set()
            last3_b2=set(x for d in self.draws[-3:] for x in d.block2) if n>=3 else set()
            lastd_b1=set(self.draws[-1].block1) if n>=1 else set()
            lastd_b2=set(self.draws[-1].block2) if n>=1 else set()
            for i,d in enumerate(self.draws):
                w=exp_w(n-1-i)
                for x in d.block1: sb1[x]+=w
                for x in d.block2: sb2[x]+=w
            for x in lastd_b1: sb1[x]*=0.85
            for x in lastd_b2: sb2[x]*=0.85
            for x in (last3_b1-lastd_b1): sb1[x]*=0.93
            for x in (last3_b2-lastd_b2): sb2[x]*=0.93
            return b1b2_from_scores(sb1,sb2)
        return self._S('m01',_r)

    def m02_markov(self):
        def _r():
            n=len(self.draws)
            if n<3: return self.m01_freq()
            mb1=defaultdict(lambda:defaultdict(float)); mb2=defaultdict(lambda:defaultdict(float))
            for i in range(n-1):
                w=exp_w(n-1-i,30.0); p,c=self.draws[i],self.draws[i+1]
                for x in p.block1:
                    for y in c.block1: mb1[x][y]+=w
                for x in p.block2:
                    for y in c.block2: mb2[x][y]+=w
            last=self._last(); sb1=defaultdict(float); sb2=defaultdict(float)
            for x in last.block1:
                for y,wt in mb1[x].items(): sb1[y]+=wt
            for x in last.block2:
                for y,wt in mb2[x].items(): sb2[y]+=wt
            return b1b2_from_scores(sb1,sb2) if sb1 else self.m01_freq()
        return self._S('m02',_r)

    def m03_gap(self):
        def _r():
            if not self.gfc: return self.m01_freq()
            sb1={x:self.gfc.gap1(x) for x in range(1,B1_MAX+1)}
            sb2={x:self.gfc.gap2(x) for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S('m03',_r)

    def m04_pattern(self):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            last=self._last(); sb1=defaultdict(float); sb2=defaultdict(float)
            window=self._rec(30)
            for i,d in enumerate(window[:-1]):
                if len(set(d.block1)&set(last.block1))>=2:
                    nxt=window[i+1]
                    for x in nxt.block1: sb1[x]+=2.0
                    for x in nxt.block2: sb2[x]+=2.0
            return b1b2_from_scores(sb1,sb2) if sb1 else self.m01_freq()
        return self._S('m04',_r)

    def m05_neural(self):
        def _r():
            if len(self.draws)<5: return self.m01_freq()
            window=self._rec(10); sb1=defaultdict(float); sb2=defaultdict(float)
            for i,d in enumerate(window):
                w=((i+1)/len(window))**2
                for x in d.block1: sb1[x]+=w
                for x in d.block2: sb2[x]+=w
            return b1b2_from_scores(sb1,sb2)
        return self._S('m05',_r)

    def m06_monte(self):
        def _r():
            if not self.gfc: return self.m01_freq()
            n=len(self.draws)
            b1p=[self.gfc.b1f.get(x,0)+0.5 for x in range(1,B1_MAX+1)]
            b2p=[self.gfc.b2f.get(x,0)+0.5 for x in range(1,B2_MAX+1)]
            s1=sum(b1p); s2=sum(b2p)
            b1p=[p/s1 for p in b1p]; b2p=[p/s2 for p in b2p]
            seed=int(hashlib.md5(str(n).encode()).hexdigest()[:8],16)
            rng=np.random.default_rng(seed)
            sb1=defaultdict(int); sb2=defaultdict(int)
            for _ in range(500):
                c1=rng.choice(B1_MAX,PICK_B1,replace=False,p=b1p)+1
                c2=rng.choice(B2_MAX,PICK_B2,replace=False,p=b2p)+1
                for x in c1: sb1[x]+=1
                for x in c2: sb2[x]+=1
            return b1b2_from_scores(sb1,sb2)
        return self._S('m06',_r)

    def m07_genetic(self):
        def _r():
            if len(self.draws)<20: return self.m01_freq()
            last=self._last(); sb1=defaultdict(float); sb2=defaultdict(float)
            for d in self.draws[:-1]:
                fit=len(set(d.block1)&set(last.block1))+len(set(d.block2)&set(last.block2))
                if fit>=2:
                    for x in d.block1: sb1[x]+=fit
                    for x in d.block2: sb2[x]+=fit
            return b1b2_from_scores(sb1,sb2) if sb1 else self.m01_freq()
        return self._S('m07',_r)

    def m08_balance(self):
        def _r():
            if not self.gfc: return self.m01_freq()
            n=max(len(self.draws),1); exp_b1=n*PICK_B1/B1_MAX; exp_b2=n*PICK_B2/B2_MAX
            sb1={x:abs(self.gfc.b1f.get(x,0)-exp_b1) for x in range(1,B1_MAX+1)}
            sb2={x:abs(self.gfc.b2f.get(x,0)-exp_b2) for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S('m08',_r)

    def m09_deep(self):
        def _r():
            if len(self.draws)<5: return self.m01_freq()
            n=len(self.draws); last=self._last()
            sb1=defaultdict(float); sb2=defaultdict(float)
            for i in range(n-2):
                w=exp_w(n-2-i,40.0)
                d1,d3=self.draws[i],self.draws[i+2]
                # v1.4 fix: compare all 4 elements per block, not just first 2
                if len(set(d1.block1)&set(last.block1))>=2:
                    for x in d3.block1: sb1[x]+=w*2
                    for x in d3.block2: sb2[x]+=w*2
            return b1b2_from_scores(sb1,sb2) if sb1 else self.m02_markov()
        return self._S('m09',_r)
    def m10_fibonacci(self):
        def _r():
            if not self.gfc: return self.m01_freq()
            fib=[1,2,3,5,8,13,21,34]
            sb1=sorted(range(1,B1_MAX+1),key=lambda x:-self.gfc.b1f.get(x,0))
            sb2=sorted(range(1,B2_MAX+1),key=lambda x:-self.gfc.b2f.get(x,0))
            b1=set(sb1[(f-1)%B1_MAX] for f in fib[:PICK_B1])
            b2=set(sb2[(f-1)%B2_MAX] for f in fib[PICK_B1:PICK_B1+PICK_B2])
            b2 -= b1  # remove overlap
            if len(b1)<PICK_B1:
                for x in sb1:
                    if x not in b1: b1.add(x)
                    if len(b1)==PICK_B1: break
            if len(b2)<PICK_B2:
                for x in sb2:
                    if x not in b1 and x not in b2: b2.add(x)
                    if len(b2)==PICK_B2: break
            return sorted(b1),sorted(b2)
        return self._S('m10',_r)

    def m11_prime(self):
        def _r():
            PRIMES=_primes_up_to(max(B1_MAX, B2_MAX))
            if not self.gfc: return self.m01_freq()
            sb1={x:self.gfc.b1f.get(x,0)*(1.3 if x in PRIMES else 0.85) for x in range(1,B1_MAX+1)}
            sb2={x:self.gfc.b2f.get(x,0)*(1.3 if x in PRIMES else 0.85) for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S('m11',_r)

    def m12_momentum(self):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            r1=self.draws[-5:]; r2=self.draws[-10:-5]
            c1b1=Counter(x for d in r1 for x in d.block1)
            c1b2=Counter(x for d in r1 for x in d.block2)
            c2b1=Counter(x for d in r2 for x in d.block1)
            c2b2=Counter(x for d in r2 for x in d.block2)
            sb1={x:c1b1.get(x,0)/5-c2b1.get(x,0)/5+0.5 for x in range(1,B1_MAX+1)}
            sb2={x:c1b2.get(x,0)/5-c2b2.get(x,0)/5+0.5 for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S('m12',_r)

    def m13_zscore(self):
        def _r():
            if not self.gfc or len(self.draws)<10: return self.m01_freq()
            n=len(self.draws); mu_b1=n*PICK_B1/B1_MAX; std_b1=math.sqrt(n*PICK_B1/B1_MAX*(1-PICK_B1/B1_MAX))+0.01
            mu_b2=n*PICK_B2/B2_MAX; std_b2=math.sqrt(n*PICK_B2/B2_MAX*(1-PICK_B2/B2_MAX))+0.01
            sb1={x:abs(self.gfc.b1f.get(x,0)-mu_b1)/std_b1 for x in range(1,B1_MAX+1)}
            sb2={x:abs(self.gfc.b2f.get(x,0)-mu_b2)/std_b2 for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S('m13',_r)

    def m14_entropy(self):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            pb1=defaultdict(lambda:[0]*max(PICK_B1,1)); pb2=defaultdict(lambda:[0]*max(PICK_B2,1))
            for d in self.draws:
                for p,x in enumerate(d.block1): pb1[x][p]+=1
                for p,x in enumerate(d.block2): pb2[x][p]+=1
            def ent(c):
                tot=sum(c)
                if tot==0: return 0
                return -sum(v/tot*math.log(v/tot+1e-9) for v in c if v>0)
            sb1={x:ent(pb1[x]) for x in range(1,B1_MAX+1)}
            sb2={x:ent(pb2[x]) for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S('m14',_r)

    def m15_cyclic(self):
        def _r():
            if len(self.draws)<20: return self.m01_freq()
            n=len(self.draws); sb1=defaultdict(float); sb2=defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                g1=[]; g2=[]; l1=-1; l2=-1
                for i,d in enumerate(self.draws):
                    if num in d.block1:
                        if l1>=0: g1.append(i-l1)
                        l1=i
                    if num in d.block2:
                        if l2>=0: g2.append(i-l2)
                        l2=i
                if g1:
                    mean=float(np.mean(g1)); age=n-1-l1 if l1>=0 else n
                    sb1[num]+=max(0,1-abs(age-mean)/(mean+1))
                if g2:
                    mean=float(np.mean(g2)); age=n-1-l2 if l2>=0 else n
                    sb2[num]+=max(0,1-abs(age-mean)/(mean+1))
            return b1b2_from_scores(sb1,sb2) if any(sb1.values()) else self.m01_freq()
        return self._S('m15',_r)

    def m16_ensemble(self):
        def _r():
            sb1=defaultdict(float); sb2=defaultdict(float)
            for fn in [self.m01_freq,self.m02_markov,self.m03_gap,self.m12_momentum,self.m13_zscore]:
                try:
                    b1,b2=fn()
                    for x in b1: sb1[x]+=1
                    for x in b2: sb2[x]+=1
                except Exception: pass
            return b1b2_from_scores(sb1,sb2)
        return self._S('m16',_r)

    def m17_recency(self):
        def _r():
            n=len(self.draws); sb1=defaultdict(float); sb2=defaultdict(float)
            for i,d in enumerate(self.draws):
                w=((i+1)/max(n,1))**2
                for x in d.block1: sb1[x]+=w
                for x in d.block2: sb2[x]+=w
            return b1b2_from_scores(sb1,sb2)
        return self._S('m17',_r)

    def m18_pairs(self):
        def _r():
            if len(self.draws)<20: return self.m01_freq()
            last=self._last()
            pb1=defaultdict(int); pb2=defaultdict(int)
            for d in self.draws:
                for i,a in enumerate(d.block1):
                    for b in d.block1[i+1:]: pb1[(min(a,b),max(a,b))]+=1
                for i,a in enumerate(d.block2):
                    for b in d.block2[i+1:]: pb2[(min(a,b),max(a,b))]+=1
            sb1=defaultdict(float); sb2=defaultdict(float)
            for num in last.block1:
                for p in range(1,B1_MAX+1):
                    if p!=num: sb1[p]+=pb1.get((min(num,p),max(num,p)),0)
            for num in last.block2:
                for p in range(1,B2_MAX+1):
                    if p!=num: sb2[p]+=pb2.get((min(num,p),max(num,p)),0)
            return b1b2_from_scores(sb1,sb2) if sb1 else self.m01_freq()
        return self._S('m18',_r)

    def m19_regression_mean(self):
        def _r():
            if not self.gfc or len(self.draws)<20: return self.m01_freq()
            r20=self.draws[-20:]
            rb1=Counter(x for d in r20 for x in d.block1)
            rb2=Counter(x for d in r20 for x in d.block2)
            exp_b1=20*PICK_B1/B1_MAX; exp_b2=20*PICK_B2/B2_MAX
            sb1={x:max(0,2*exp_b1-rb1.get(x,0))+self.gfc.b1f.get(x,0)*0.1 for x in range(1,B1_MAX+1)}
            sb2={x:max(0,2*exp_b2-rb2.get(x,0))+self.gfc.b2f.get(x,0)*0.1 for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S('m19',_r)

    def m20_ewma(self,alpha=0.15,key='m20'):
        def _r():
            if len(self.draws)<5: return self.m01_freq()
            eb1={n:0.0 for n in range(1,B1_MAX+1)}; eb2={n:0.0 for n in range(1,B2_MAX+1)}
            for d in self.draws:
                for n in range(1, B1_MAX+1):
                    eb1[n]=alpha*(1.0 if n in d.block1 else 0.0)+(1-alpha)*eb1[n]
                for n in range(1, B2_MAX+1):
                    eb2[n]=alpha*(1.0 if n in d.block2 else 0.0)+(1-alpha)*eb2[n]
            return b1b2_from_scores(eb1,eb2)
        return self._S(key,_r)

    # ── Window variants ──────────────────────────────────────────────────
    def _window(self,w,key):
        def _r():
            sub=self.draws[-w:] if len(self.draws)>=w else self.draws
            sb1=Counter(x for d in sub for x in d.block1)
            sb2=Counter(x for d in sub for x in d.block2)
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    # ── Velocity / recency-zscore ────────────────────────────────────────
    # FIX (v1.3): window params to ensure unique predictions per call
    def _velocity(self,key,win_recent=10,win_old=20):
        def _r():
            n=len(self.draws)
            if n<15: return self.m01_freq()
            r1=self.draws[-win_recent:]
            r2=self.draws[-(win_recent+win_old):-win_recent] if n>=(win_recent+win_old) else self.draws[:win_old]
            c1b1=Counter(x for d in r1 for x in d.block1)
            c1b2=Counter(x for d in r1 for x in d.block2)
            c2b1=Counter(x for d in r2 for x in d.block1)
            c2b2=Counter(x for d in r2 for x in d.block2)
            b1f=self.gfc.b1f if self.gfc else {}
            b2f=self.gfc.b2f if self.gfc else {}
            sb1={x:c1b1.get(x,0)-c2b1.get(x,0)+b1f.get(x,0)*0.1 for x in range(1,B1_MAX+1)}
            sb2={x:c1b2.get(x,0)-c2b2.get(x,0)+b2f.get(x,0)*0.1 for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    def _recency_z(self,w,key):
        def _r():
            n=len(self.draws)
            if n<20: return self.m13_zscore()
            sub=self.draws[-min(w,n):]
            wb1=Counter(x for d in sub for x in d.block1)
            wb2=Counter(x for d in sub for x in d.block2)
            m1=len(sub)*PICK_B1/B1_MAX; std1=math.sqrt(len(sub)*PICK_B1/B1_MAX*(1-PICK_B1/B1_MAX))+0.01
            m2=len(sub)*PICK_B2/B2_MAX; std2=math.sqrt(len(sub)*PICK_B2/B2_MAX*(1-PICK_B2/B2_MAX))+0.01
            sb1={x:(wb1.get(x,0)-m1)/std1 for x in range(1,B1_MAX+1)}
            sb2={x:(wb2.get(x,0)-m2)/std2 for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    def _bayesian(self,alpha,key):
        def _r():
            if not self.gfc: return self.m01_freq()
            n=len(self.draws); a=alpha*5; b=5.0
            sb1={x:(self.gfc.b1f.get(x,0)+a)/(n+b) for x in range(1,B1_MAX+1)}
            sb2={x:(self.gfc.b2f.get(x,0)+a)/(n+b) for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    def _gap_freq(self,boost,key):
        def _r():
            if not self.gfc: return self.m01_freq()
            sb1={x:self.gfc.gap1(x)*boost+self.gfc.b1f.get(x,0)*0.3 for x in range(1,B1_MAX+1)}
            sb2={x:self.gfc.gap2(x)*boost+self.gfc.b2f.get(x,0)*0.3 for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    def _block_streak(self,key,window=30):
        def _r():
            sb1=defaultdict(float); sb2=defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                s1=s2=ms1=ms2=0
                for d in self.draws[-window:]:
                    if num in d.block1: s1+=1; ms1=max(ms1,s1)
                    else: s1=0
                    if num in d.block2: s2+=1; ms2=max(ms2,s2)
                    else: s2=0
                sb1[num]=ms1+(1 if s1==0 else 0)
                sb2[num]=ms2+(1 if s2==0 else 0)
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    def _draw_type_freq(self,key):
        def _r():
            last=self._last(); dt=last.draw_type if last else 'unknown'
            same=[d for d in self.draws if d.draw_type==dt]
            if len(same)<10: return self.m01_freq()
            sb1=defaultdict(float); sb2=defaultdict(float)
            for i,d in enumerate(same):
                w=exp_w(len(same)-1-i,30.0)
                for x in d.block1: sb1[x]+=w
                for x in d.block2: sb2[x]+=w
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    def _cross_block_gap(self,key):
        def _r():
            if not self.gfc: return self.m01_freq()
            sb1={n:self.gfc.gap1(n)*self.gfc.aff(n) for n in range(1,B1_MAX+1)}
            sb2={n:self.gfc.gap2(n)*(1-self.gfc.aff(n)) for n in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S(key,_r)

    def _fourier(self,key):
        def _r():
            if len(self.draws)<30: return self.m15_cyclic()
            try:
                sb1=defaultdict(float); sb2=defaultdict(float)
                for num in range(1,max(B1_MAX,B2_MAX)+1):
                    s1=np.array([1.0 if num in d.block1 else 0.0 for d in self.draws])
                    s2=np.array([1.0 if num in d.block2 else 0.0 for d in self.draws])
                    f1=np.abs(np.fft.rfft(s1)); f2=np.abs(np.fft.rfft(s2))
                    d1=np.argmax(f1[1:])+1; d2=np.argmax(f2[1:])+1
                    p1=len(s1)/d1; p2=len(s2)/d2
                    ls1=next((len(self.draws)-1-i for i,d in enumerate(reversed(self.draws)) if num in d.block1),len(self.draws))
                    ls2=next((len(self.draws)-1-i for i,d in enumerate(reversed(self.draws)) if num in d.block2),len(self.draws))
                    sb1[num]=1-abs(ls1%max(p1,1)-p1/2)/(p1/2+0.01)
                    sb2[num]=1-abs(ls2%max(p2,1)-p2/2)/(p2/2+0.01)
                return b1b2_from_scores(sb1,sb2)
            except Exception: return self.m15_cyclic()
        return self._S(key,_r)

    def _positional_drift(self, key, half_window=30):
        """v1.4: Position-specific frequency drift (recent vs older half)."""
        def _r():
            if len(self.draws) < half_window*2: return self.m01_freq()
            recent = self.draws[-half_window:]
            older = self.draws[-(half_window*2):-half_window]
            sb1=defaultdict(float); sb2=defaultdict(float)
            for pos in range(max(PICK_B1, PICK_B2)):
                pf_r1 = defaultdict(float); pf_o1 = defaultdict(float)
                pf_r2 = defaultdict(float); pf_o2 = defaultdict(float)
                for d in recent:
                    b1s = sorted(d.block1); b2s = sorted(d.block2)
                    if pos < len(b1s): pf_r1[b1s[pos]] += 1.0
                    if pos < len(b2s): pf_r2[b2s[pos]] += 1.0
                for d in older:
                    b1s = sorted(d.block1); b2s = sorted(d.block2)
                    if pos < len(b1s): pf_o1[b1s[pos]] += 1.0
                    if pos < len(b2s): pf_o2[b2s[pos]] += 1.0
                for num in range(1,max(B1_MAX,B2_MAX)+1):
                    drift1 = pf_r1.get(num,0) - pf_o1.get(num,0)
                    drift2 = pf_r2.get(num,0) - pf_o2.get(num,0)
                    if drift1 > 0: sb1[num] += drift1 * 2.0
                    if drift2 > 0: sb2[num] += drift2 * 2.0
            return b1b2_from_scores(sb1,sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)
    # ── NEW unique model methods (v1.3) ──────────────────────────────────

    def _hot_streak(self, key, window=10, min_appearances=3):
        def _r():
            if len(self.draws) < window: return self.m01_freq()
            recent = self.draws[-window:]
            sb1=defaultdict(float); sb2=defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                c1 = sum(1 for d in recent if num in d.block1)
                c2 = sum(1 for d in recent if num in d.block2)
                if c1 >= min_appearances: sb1[num] = c1 * 2.0
                if c2 >= min_appearances: sb2[num] = c2 * 2.0
            return b1b2_from_scores(sb1,sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)


    def _draw_type_specific(self, key):
        """v1.4: Separate frequency for std vs rng draws."""
        def _r():
            if not self.gfc or len(self.draws)<20: return self.m01_freq()
            last=self._last(); dt=last.draw_type if last else 'unknown'
            same=[d for d in self.draws if d.draw_type==dt]
            other=[d for d in self.draws if d.draw_type!=dt]
            if len(same)<10: return self.m01_freq()
            # Weight same-type draws 3x more than other-type
            sb1=defaultdict(float); sb2=defaultdict(float)
            for d in same:
                w = 3.0
                for x in d.block1: sb1[x]+=w
                for x in d.block2: sb2[x]+=w
            for d in other[-50:]:
                w = 1.0
                for x in d.block1: sb1[x]+=w
                for x in d.block2: sb2[x]+=w
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)
    def _gap_acceleration(self, key):
        """v1.4: Numbers with increasing gap are more likely to return."""
        def _r():
            if not self.gfc or len(self.draws)<20: return self.m01_freq()
            n=len(self.draws); sb1=defaultdict(float); sb2=defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                # Find current and previous gap for B1
                cur_gap1=0; prev_gap1=0; found1=0
                for idx in range(n-1, -1, -1):
                    if num in self.draws[idx].block1:
                        if found1==0:
                            cur_gap1 = n-1-idx; found1=1
                        elif found1==1:
                            prev_gap1 = n-1-idx; break
                # Same for B2
                cur_gap2=0; prev_gap2=0; found2=0
                for idx in range(n-1, -1, -1):
                    if num in self.draws[idx].block2:
                        if found2==0:
                            cur_gap2 = n-1-idx; found2=1
                        elif found2==1:
                            prev_gap2 = n-1-idx; break
                # Acceleration: positive means gap is growing (overdue)
                if prev_gap1 > 0:
                    accel1 = (cur_gap1 - prev_gap1) / max(prev_gap1, 1)
                    sb1[num] = cur_gap1 * (1.0 + max(accel1, 0) * 0.5)
                else:
                    sb1[num] = cur_gap1
                if prev_gap2 > 0:
                    accel2 = (cur_gap2 - prev_gap2) / max(prev_gap2, 1)
                    sb2[num] = cur_gap2 * (1.0 + max(accel2, 0) * 0.5)
                else:
                    sb2[num] = cur_gap2
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)
    def _sum_parity(self, key):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            sb1=defaultdict(float); sb2=defaultdict(float)
            for d in self.draws[-50:]:
                s1=sum(d.block1); s2=sum(d.block2)
                p1=s1%2; p2=s2%2
                for x in d.block1:
                    sb1[x] += 1.5 if x%2==p1 else 0.5
                for x in d.block2:
                    sb2[x] += 1.5 if x%2==p2 else 0.5
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _consecutive_pairs(self, key):
        def _r():
            if len(self.draws)<20: return self.m01_freq()
            sb1=defaultdict(float); sb2=defaultdict(float)
            for d in self.draws[-50:]:
                b1=sorted(d.block1); b2=sorted(d.block2)
                for i in range(len(b1)-1):
                    if abs(b1[i]-b1[i+1])==1:
                        for x in b1[i:min(i+3,len(b1))]:
                            sb1[x]+=1.0
                for i in range(len(b2)-1):
                    if abs(b2[i]-b2[i+1])==1:
                        for x in b2[i:min(i+3,len(b2))]:
                            sb2[x]+=1.0
            return b1b2_from_scores(sb1,sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _high_low_split(self, key):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            sb1=defaultdict(float); sb2=defaultdict(float)
            for d in self.draws[-50:]:
                lo1=sum(1 for x in d.block1 if x<=B1_MAX//2)
                hi1=sum(1 for x in d.block1 if x>B1_MAX//2)
                lo2=sum(1 for x in d.block2 if x<=B2_MAX//2)
                hi2=sum(1 for x in d.block2 if x>B2_MAX//2)
                bias1 = (lo1-hi1)*0.3
                bias2 = (lo2-hi2)*0.3
                for x in d.block1:
                    sb1[x] += 1.0 + (bias1 if x<=B1_MAX//2 else -bias1)
                for x in d.block2:
                    sb2[x] += 1.0 + (bias2 if x<=B2_MAX//2 else -bias2)
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _differential_freq(self, key):
        def _r():
            if len(self.draws)<20: return self.m01_freq()
            r1=self.draws[-10:]; r2=self.draws[-20:-10]
            sb1=defaultdict(float); sb2=defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                c1b1=sum(1 for d in r1 if num in d.block1)
                c2b1=sum(1 for d in r2 if num in d.block1)
                c1b2=sum(1 for d in r1 if num in d.block2)
                c2b2=sum(1 for d in r2 if num in d.block2)
                sb1[num]=(c1b1-c2b1)+0.5
                sb2[num]=(c1b2-c2b2)+0.5
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _triple_markov(self, key):
        def _r():
            if len(self.draws)<10: return self.m02_markov()
            n=len(self.draws)
            mb1=defaultdict(lambda:defaultdict(float))
            mb2=defaultdict(lambda:defaultdict(float))
            for i in range(n-2):
                w=exp_w(n-2-i,25.0)
                prev2, prev1, nxt = self.draws[i], self.draws[i+1], self.draws[i+2]
                for x in prev2.block1:
                    for y in prev1.block1:
                        for z in nxt.block1: mb1[(x,y)][z]+=w
                for x in prev2.block2:
                    for y in prev1.block2:
                        for z in nxt.block2: mb2[(x,y)][z]+=w
            last=self._last(); prev=self.draws[-2] if n>=2 else last
            sb1=defaultdict(float); sb2=defaultdict(float)
            for x in prev.block1:
                for y in last.block1:
                    for z,wt in mb1[(x,y)].items(): sb1[z]+=wt
            for x in prev.block2:
                for y in last.block2:
                    for z,wt in mb2[(x,y)].items(): sb2[z]+=wt
            return b1b2_from_scores(sb1,sb2) if sb1 else self.m02_markov()
        return self._S(key, _r)

    def _entropy_weighted(self, key):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            sb1=defaultdict(float); sb2=defaultdict(float)
            pb1=defaultdict(lambda:[0]*max(PICK_B1,1)); pb2=defaultdict(lambda:[0]*max(PICK_B2,1))
            for d in self.draws:
                for p,x in enumerate(d.block1): pb1[x][p]+=1
                for p,x in enumerate(d.block2): pb2[x][p]+=1
            def ent(c):
                tot=sum(c)
                if tot==0: return 0
                return -sum(v/tot*math.log(v/tot+1e-9) for v in c if v>0)
            max_ent = math.log(max(PICK_B1, PICK_B2, 2))
            for x in range(1,max(B1_MAX,B2_MAX)+1):
                e1 = ent(pb1[x]) / max_ent
                e2 = ent(pb2[x]) / max_ent
                sb1[x] = (1.0 - e1) * self.gfc.b1f.get(x,0) if self.gfc else (1.0 - e1)
                sb2[x] = (1.0 - e2) * self.gfc.b2f.get(x,0) if self.gfc else (1.0 - e2)
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _mean_reversion(self, key, window=50):
        def _r():
            if len(self.draws)<window: return self.m01_freq()
            sub=self.draws[-window:]
            freq1=Counter(x for d in sub for x in d.block1)
            freq2=Counter(x for d in sub for x in d.block2)
            expected_b1 = window * PICK_B1 / B1_MAX
            expected_b2 = window * PICK_B2 / B2_MAX
            sb1={x:max(0, 2*expected_b1-freq1.get(x,0)) for x in range(1,B1_MAX+1)}
            sb2={x:max(0, 2*expected_b2-freq2.get(x,0)) for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _lag_correlation(self, key):
        def _r():
            if len(self.draws)<30: return self.m01_freq()
            sb1=defaultdict(float); sb2=defaultdict(float)
            n=len(self.draws)
            for lag in [1,2,3]:
                for i in range(n-lag):
                    w=exp_w(n-lag-i,40.0)/(lag)
                    d_cur=self.draws[i+lag]; d_prev=self.draws[i]
                    for x in d_prev.block1:
                        if x in d_cur.block1: sb1[x]+=w
                    for x in d_prev.block2:
                        if x in d_cur.block2: sb2[x]+=w
            return b1b2_from_scores(sb1,sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _position_specific(self, key, position=0):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            pf1=defaultdict(float); pf2=defaultdict(float)
            for d in self.draws[-100:]:
                b1=sorted(d.block1); b2=sorted(d.block2)
                if position < len(b1): pf1[b1[position]] += 1.0
                if position < len(b2): pf2[b2[position]] += 1.0
            return b1b2_from_scores(pf1,pf2)
        return self._S(key, _r)

    def _block_sum_trend(self, key):
        def _r():
            if len(self.draws)<20: return self.m01_freq()
            sums_b1=[sum(d.block1) for d in self.draws[-30:]]
            sums_b2=[sum(d.block2) for d in self.draws[-30:]]
            avg1=np.mean(sums_b1); avg2=np.mean(sums_b2)
            target1=(1+B1_MAX)*PICK_B1/2
            target2=(1+B2_MAX)*PICK_B2/2
            mid1=(1+B1_MAX)/2; mid2=(1+B2_MAX)/2
            bias1=(avg1-target1)/10.0; bias2=(avg2-target2)/10.0
            sb1={x:1.0-bias1*(x-mid1)/mid1 for x in range(1,B1_MAX+1)}
            sb2={x:1.0-bias2*(x-mid2)/mid2 for x in range(1,B2_MAX+1)}
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _monte_carlo_bayesian(self, key):
        def _r():
            if not self.gfc: return self.m01_freq()
            n=len(self.draws)
            b1p=np.array([self.gfc.b1f.get(x,0)+1.0 for x in range(1,B1_MAX+1)], dtype=float)
            b2p=np.array([self.gfc.b2f.get(x,0)+1.0 for x in range(1,B2_MAX+1)], dtype=float)
            for x in range(max(B1_MAX, B2_MAX)):
                gap1=self.gfc.gap1(x+1); gap2=self.gfc.gap2(x+1)
                b1p[x]*=1.0+gap1*0.05
                b2p[x]*=1.0+gap2*0.05
            s1=b1p.sum(); s2=b2p.sum()
            b1p/=s1; b2p/=s2
            rng=np.random.default_rng(42+n)
            sb1=defaultdict(int); sb2=defaultdict(int)
            for _ in range(1000):
                c1=rng.choice(B1_MAX,PICK_B1,replace=False,p=b1p)+1
                c2=rng.choice(B2_MAX,PICK_B2,replace=False,p=b2p)+1
                for x in c1: sb1[x]+=1
                for x in c2: sb2[x]+=1
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _adaptive_ewma(self, key):
        def _r():
            if len(self.draws)<10: return self.m01_freq()
            n=len(self.draws)
            eb1={num:0.0 for num in range(1,B1_MAX+1)}; eb2={num:0.0 for num in range(1,B2_MAX+1)}
            for idx,d in enumerate(self.draws):
                # v1.4 fix: alpha grows per-draw from 0.05 to 0.30
                progress = idx / max(n-1, 1)
                alpha = 0.05 + 0.25 * progress
                for num in range(1, B1_MAX+1):
                    eb1[num]=alpha*(1.0 if num in d.block1 else 0.0)+(1-alpha)*eb1[num]
                for num in range(1, B2_MAX+1):
                    eb2[num]=alpha*(1.0 if num in d.block2 else 0.0)+(1-alpha)*eb2[num]
            return b1b2_from_scores(eb1,eb2)
        return self._S(key, _r)
    def _gap_burst(self, key):
        def _r():
            if not self.gfc or len(self.draws)<20: return self.m01_freq()
            n=len(self.draws)
            avg_gap_b1=n*PICK_B1/B1_MAX; avg_gap_b2=n*PICK_B2/B2_MAX
            sb1=defaultdict(float); sb2=defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                g1=self.gfc.gap1(num); g2=self.gfc.gap2(num)
                if g1 > avg_gap_b1*1.5 and g1 < avg_gap_b1*2.5:
                    sb1[num] = 3.0 / (g1+1)
                elif g1 < avg_gap_b1*0.5:
                    sb1[num] = 2.0
                if g2 > avg_gap_b2*1.5 and g2 < avg_gap_b2*2.5:
                    sb2[num] = 3.0 / (g2+1)
                elif g2 < avg_gap_b2*0.5:
                    sb2[num] = 2.0
            return b1b2_from_scores(sb1,sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _cluster_analysis(self, key):
        def _r():
            if len(self.draws)<20: return self.m01_freq()
            sb1=defaultdict(float); sb2=defaultdict(float)
            last=self._last()
            for d in self.draws[-50:]:
                for x in d.block1:
                    for y in last.block1:
                        dist=abs(x-y)
                        if dist<=2: sb1[x]+=1.5
                        elif dist<=4: sb1[x]+=0.5
                for x in d.block2:
                    for y in last.block2:
                        dist=abs(x-y)
                        if dist<=2: sb2[x]+=1.5
                        elif dist<=4: sb2[x]+=0.5
            return b1b2_from_scores(sb1,sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)


    def _anti_majority(self, key, boost=2.0):
        """v3.0: Predict numbers that the MAJORITY of base models do NOT pick."""
        def _r():
            if len(self.draws) < 10: return self.m01_freq()
            sb1_maj = defaultdict(float); sb2_maj = defaultdict(float)
            for d in self.draws[-50:]:
                w = exp_w(len(self.draws) - self.draws.index(d) - 1, 30.0)
                for x in d.block1: sb1_maj[x] += w
                for x in d.block2: sb2_maj[x] += w
            top_b1 = set(sorted(range(1,B1_MAX+1), key=lambda x: -sb1_maj.get(x, 0))[:8])
            top_b2 = set(sorted(range(1,B2_MAX+1), key=lambda x: -sb2_maj.get(x, 0))[:8])
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            if self.gfc:
                for num in range(1,max(B1_MAX,B2_MAX)+1):
                    gap1 = self.gfc.gap1(num)
                    gap2 = self.gfc.gap2(num)
                    if num in top_b1:
                        sb1[num] = self.gfc.b1f.get(num, 0) * 0.3 + gap1 * 0.1
                    else:
                        sb1[num] = self.gfc.b1f.get(num, 0) * 0.8 + gap1 * boost
                    if num in top_b2:
                        sb2[num] = self.gfc.b2f.get(num, 0) * 0.3 + gap2 * 0.1
                    else:
                        sb2[num] = self.gfc.b2f.get(num, 0) * 0.8 + gap2 * boost
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _cold_focus(self, key, window=30):
        """v3.0: Focus on cold numbers (haven't appeared recently)."""
        def _r():
            if not self.gfc or len(self.draws) < window: return self.m01_freq()
            recent = self.draws[-window:]
            recent_b1 = set(x for d in recent for x in d.block1)
            recent_b2 = set(x for d in recent for x in d.block2)
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                gap1 = self.gfc.gap1(num)
                gap2 = self.gfc.gap2(num)
                cold_b1 = 1.5 if num not in recent_b1 else 0.3
                cold_b2 = 1.5 if num not in recent_b2 else 0.3
                sb1[num] = gap1 * cold_b1 + self.gfc.b1f.get(num, 0) * 0.2
                sb2[num] = gap2 * cold_b2 + self.gfc.b2f.get(num, 0) * 0.2
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _cold_number_focus(self, key, window=20):
        """v6.0: Focus exclusively on cold numbers (not appeared in recent window).
        These models increase diversity by exploring underrepresented numbers."""
        def _r():
            if not self.gfc or len(self.draws) < window: return self.m01_freq()
            recent = self.draws[-window:]
            recent_b1 = Counter(x for d in recent for x in d.block1)
            recent_b2 = Counter(x for d in recent for x in d.block2)
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                # Strong penalty for recently appeared numbers
                gap1 = self.gfc.gap1(num)
                gap2 = self.gfc.gap2(num)
                penalty1 = max(0, window - gap1) * 0.5 if gap1 < window else 0
                penalty2 = max(0, window - gap2) * 0.5 if gap2 < window else 0
                sb1[num] = self.gfc.b1f.get(num,0) * 0.2 + gap1 * 2.0 - penalty1
                sb2[num] = self.gfc.b2f.get(num,0) * 0.2 + gap2 * 2.0 - penalty2
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    def _sum_target_model(self, key, target_sum=42):
        """v6.0: Pick numbers that would produce a specific target sum.
        Different target sums produce completely different number sets."""
        def _r():
            if not self.gfc or len(self.draws) < 10: return self.m01_freq()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            target_sum_b1=(1+B1_MAX)*PICK_B1/2
            target_sum_b2=(1+B2_MAX)*PICK_B2/2
            for num in range(1,max(B1_MAX,B2_MAX)+1):
                # Score based on how close num contributes to target sum
                b1_score = self.gfc.b1f.get(num,0) * 0.5
                b2_score = self.gfc.b2f.get(num,0) * 0.5
                # Bias toward numbers that help reach target sum
                avg_num_b1 = target_sum_b1 / max(PICK_B1, 1)
                avg_num_b2 = target_sum_b2 / max(PICK_B2, 1)
                dist_from_avg_b1 = abs(num - avg_num_b1)
                dist_from_avg_b2 = abs(num - avg_num_b2)
                if dist_from_avg_b1 < 5:
                    b1_score += (5 - dist_from_avg_b1) * 0.3
                if dist_from_avg_b2 < 5:
                    b2_score += (5 - dist_from_avg_b2) * 0.3
                sb1[num] = b1_score + self.gfc.gap1(num) * 0.3
                sb2[num] = b2_score + self.gfc.gap2(num) * 0.3
            return b1b2_from_scores(sb1,sb2)
        return self._S(key, _r)

    # ── NEW IMPROVED MODELS (v14.0) ─────────────────────────────────
    def _enhanced_differential(self, key, win_recent=10, win_old=20):
        """Enhanced Differential with configurable windows and gap bonus."""
        def _r():
            if len(self.draws) < win_recent + win_old: return self.m01_freq()
            r1 = self.draws[-win_recent:]
            r2 = self.draws[-(win_recent+win_old):-win_recent]
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            if self.gfc:
                for num in range(1, B1_MAX+1):
                    c1 = sum(1 for d in r1 if num in d.block1)
                    c2 = sum(1 for d in r2 if num in d.block1)
                    gap = self.gfc.gap1(num)
                    score = (c1 - c2) + 0.5 + gap * 0.15
                    sb1[num] = max(score, 0)
                for num in range(1, B2_MAX+1):
                    c1 = sum(1 for d in r1 if num in d.block2)
                    c2 = sum(1 for d in r2 if num in d.block2)
                    gap = self.gfc.gap2(num)
                    score = (c1 - c2) + 0.5 + gap * 0.15
                    sb2[num] = max(score, 0)
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _freq_gap_hybrid(self, key, freq_weight=0.6, gap_weight=0.4):
        """Hybrid: combines frequency analysis with gap/overdue analysis."""
        def _r():
            if not self.gfc or len(self.draws) < 10: return self.m01_freq()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            n = len(self.draws)
            exp_b1 = n * PICK_B1 / B1_MAX
            exp_b2 = n * PICK_B2 / B2_MAX
            for num in range(1, B1_MAX+1):
                freq_score = self.gfc.b1f.get(num, 0) / max(exp_b1, 1)
                gap = self.gfc.gap1(num)
                gap_score = min(gap / max(B1_MAX / PICK_B1, 1), 3.0) / 3.0
                sb1[num] = freq_weight * freq_score + gap_weight * gap_score
            for num in range(1, B2_MAX+1):
                freq_score = self.gfc.b2f.get(num, 0) / max(exp_b2, 1)
                gap = self.gfc.gap2(num)
                gap_score = min(gap / max(B2_MAX / max(PICK_B2, 1), 1), 3.0) / 3.0
                sb2[num] = freq_weight * freq_score + gap_weight * gap_score
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _recency_gap(self, key, half_life=100):
        """Gap analysis with exponential recency weighting."""
        def _r():
            if not self.gfc or len(self.draws) < 10: return self.m01_freq()
            n = len(self.draws)
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            weights = _compute_time_weights(n, half_life)
            b1_weighted_freq = defaultdict(float)
            b2_weighted_freq = defaultdict(float)
            for i, d in enumerate(self.draws):
                w = weights[i] if i < len(weights) else 1.0
                for x in d.block1: b1_weighted_freq[x] += w
                for x in d.block2: b2_weighted_freq[x] += w
            for num in range(1, B1_MAX+1):
                gap = self.gfc.gap1(num)
                freq = b1_weighted_freq.get(num, 0)
                sb1[num] = freq * 0.7 + gap * 0.3
            for num in range(1, B2_MAX+1):
                gap = self.gfc.gap2(num)
                freq = b2_weighted_freq.get(num, 0)
                sb2[num] = freq * 0.7 + gap * 0.3
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _adaptive_window(self, key):
        """Auto-select window size based on data size and volatility."""
        def _r():
            n = len(self.draws)
            if n < 20: return self.m01_freq()
            recent = min(50, n)
            last_nums = set()
            for d in self.draws[-recent:]:
                last_nums.update(d.block1)
                last_nums.update(d.block2)
            coverage = len(last_nums) / max(B1_MAX, 1)
            if coverage > 0.7:
                w = min(n, int(n * 0.05))
            elif coverage > 0.4:
                w = min(n, int(n * 0.1))
            else:
                w = min(n, int(n * 0.2))
            w = max(w, 10)
            sub = self.draws[-w:]
            sb1 = Counter(x for d in sub for x in d.block1)
            sb2 = Counter(x for d in sub for x in d.block2)
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _constrained_sum(self, key, target_percentile=0.5):
        """Pick numbers that produce sums close to historical median."""
        def _r():
            if len(self.draws) < 20 or not self.gfc: return self.m01_freq()
            sums_b1 = [sum(d.block1) for d in self.draws[-100:]]
            if not sums_b1: return self.m01_freq()
            target_b1 = sorted(sums_b1)[int(len(sums_b1) * target_percentile)]
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for num in range(1, B1_MAX+1):
                freq = self.gfc.b1f.get(num, 0)
                sb1[num] = freq
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _hot_cold_balance(self, key, window=30):
        """Balance between hot (frequent) and cold (overdue) numbers."""
        def _r():
            if not self.gfc or len(self.draws) < window: return self.m01_freq()
            recent = self.draws[-window:]
            recent_b1 = Counter(x for d in recent for x in d.block1)
            recent_b2 = Counter(x for d in recent for x in d.block2)
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            n = len(self.draws)
            for num in range(1, B1_MAX+1):
                hot = recent_b1.get(num, 0) / max(window * PICK_B1 / B1_MAX, 1)
                gap = self.gfc.gap1(num)
                avg_gap = max(n * PICK_B1 / B1_MAX, 1)
                cold = min(gap / avg_gap, 2.0) / 2.0
                balance_score = 1.0 - abs(hot - cold)
                sb1[num] = self.gfc.b1f.get(num, 0) * 0.5 + balance_score * 2.0
            for num in range(1, B2_MAX+1):
                hot = recent_b2.get(num, 0) / max(window * PICK_B2 / B2_MAX, 1)
                gap = self.gfc.gap2(num)
                avg_gap = max(n * PICK_B2 / B2_MAX, 1)
                cold = min(gap / avg_gap, 2.0) / 2.0
                balance_score = 1.0 - abs(hot - cold)
                sb2[num] = self.gfc.b2f.get(num, 0) * 0.5 + balance_score * 2.0
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _streak_reversal(self, key, window=20):
        """Detect streaks and predict reversals."""
        def _r():
            if len(self.draws) < window * 2: return self.m01_freq()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            recent = self.draws[-window:]
            older = self.draws[-(window*2):-window]
            recent_b1 = Counter(x for d in recent for x in d.block1)
            older_b1 = Counter(x for d in older for x in d.block1)
            recent_b2 = Counter(x for d in recent for x in d.block2)
            older_b2 = Counter(x for d in older for x in d.block2)
            for num in range(1, max(B1_MAX, B2_MAX)+1):
                r1 = recent_b1.get(num, 0)
                o1 = older_b1.get(num, 0)
                if o1 > r1 + 1:
                    sb1[num] = (o1 - r1) * 1.5 + 0.5
                elif r1 > 0:
                    sb1[num] = 0.5
                r2 = recent_b2.get(num, 0)
                o2 = older_b2.get(num, 0)
                if o2 > r2 + 1:
                    sb2[num] = (o2 - r2) * 1.5 + 0.5
                elif r2 > 0:
                    sb2[num] = 0.5
            return b1b2_from_scores(sb1, sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _modular_pattern(self, key):
        """Analyze numbers by modular arithmetic patterns (mod 3, mod 5)."""
        def _r():
            if len(self.draws) < 20: return self.m01_freq()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for d in self.draws[-50:]:
                for x in d.block1:
                    sb1[x] += 1.0
                for x in d.block2:
                    sb2[x] += 1.0
            if self.gfc:
                for num in range(1, B1_MAX+1):
                    sb1[num] = sb1.get(num, 0) + self.gfc.b1f.get(num, 0) * 0.3
                for num in range(1, B2_MAX+1):
                    sb2[num] = sb2.get(num, 0) + self.gfc.b2f.get(num, 0) * 0.3
            return b1b2_from_scores(sb1, sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _number_affinity(self, key):
        """Find numbers that frequently appear together with last draw numbers."""
        def _r():
            if len(self.draws) < 20 or not self.gfc: return self.m01_freq()
            last = self._last()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            co_occurrence_b1 = defaultdict(int)
            co_occurrence_b2 = defaultdict(int)
            for d in self.draws[-100:]:
                for x in d.block1:
                    for y in last.block1:
                        if x != y:
                            co_occurrence_b1[x] += 1
            for d in self.draws[-100:]:
                for x in d.block2:
                    for y in last.block2:
                        if x != y:
                            co_occurrence_b2[x] += 1
            for num in range(1, B1_MAX+1):
                sb1[num] = co_occurrence_b1.get(num, 0) + self.gfc.b1f.get(num, 0) * 0.2
            for num in range(1, B2_MAX+1):
                sb2[num] = co_occurrence_b2.get(num, 0) + self.gfc.b2f.get(num, 0) * 0.2
            return b1b2_from_scores(sb1, sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _period_detection(self, key):
        """Simple period detection: find dominant period for each number."""
        def _r():
            if len(self.draws) < 30: return self.m01_freq()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for num in range(1, max(B1_MAX, B2_MAX)+1):
                appearances = []
                for i, d in enumerate(self.draws):
                    if num in d.block1:
                        appearances.append(i)
                if len(appearances) >= 3:
                    gaps = [appearances[j] - appearances[j-1] for j in range(1, len(appearances))]
                    if gaps:
                        gap_mode = Counter(gaps).most_common(1)[0][0]
                        age = len(self.draws) - 1 - appearances[-1]
                        diff = abs(age - gap_mode) / max(gap_mode, 1)
                        score = max(0, 1.0 - diff)
                        sb1[num] = score * 2.0
                appearances_b2 = []
                for i, d in enumerate(self.draws):
                    if num in d.block2:
                        appearances_b2.append(i)
                if len(appearances_b2) >= 3:
                    gaps_b2 = [appearances_b2[j] - appearances_b2[j-1] for j in range(1, len(appearances_b2))]
                    if gaps_b2:
                        gap_mode_b2 = Counter(gaps_b2).most_common(1)[0][0]
                        age_b2 = len(self.draws) - 1 - appearances_b2[-1]
                        diff_b2 = abs(age_b2 - gap_mode_b2) / max(gap_mode_b2, 1)
                        score_b2 = max(0, 1.0 - diff_b2)
                        sb2[num] = score_b2 * 2.0
            return b1b2_from_scores(sb1, sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _adaptive_zscore(self, key):
        """Z-Score that auto-adapts window based on data size."""
        def _r():
            n = len(self.draws)
            if n < 20: return self.m01_freq()
            w = max(30, min(200, n // 5))
            sub = self.draws[-w:]
            wb1 = Counter(x for d in sub for x in d.block1)
            wb2 = Counter(x for d in sub for x in d.block2)
            m1 = len(sub)*PICK_B1/B1_MAX
            std1 = math.sqrt(len(sub)*PICK_B1/B1_MAX*(1-PICK_B1/B1_MAX)) + 0.01
            m2 = len(sub)*PICK_B2/B2_MAX
            std2 = math.sqrt(len(sub)*PICK_B2/B2_MAX*(1-PICK_B2/B2_MAX)) + 0.01
            sb1 = {x: (wb1.get(x,0)-m1)/std1 for x in range(1, B1_MAX+1)}
            sb2 = {x: (wb2.get(x,0)-m2)/std2 for x in range(1, B2_MAX+1)}
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _gap_momentum(self, key):
        """Gap analysis with momentum — accelerating gaps get higher scores."""
        def _r():
            if not self.gfc or len(self.draws) < 30: return self.m01_freq()
            n = len(self.draws)
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for num in range(1, max(B1_MAX, B2_MAX)+1):
                gaps_b1 = []
                last_seen = -1
                for i in range(n-1, -1, -1):
                    if num in self.draws[i].block1:
                        if last_seen == -1:
                            cur_gap = n - 1 - i
                            last_seen = i
                        else:
                            prev_gap = last_seen - i
                            gaps_b1 = [prev_gap, cur_gap]
                            break
                if len(gaps_b1) == 2:
                    momentum = gaps_b1[1] / max(gaps_b1[0], 1)
                    sb1[num] = gaps_b1[1] * min(momentum, 2.0)
                elif len(gaps_b1) == 1:
                    sb1[num] = gaps_b1[0]
                gaps_b2 = []
                last_seen_b2 = -1
                for i in range(n-1, -1, -1):
                    if num in self.draws[i].block2:
                        if last_seen_b2 == -1:
                            cur_gap_b2 = n - 1 - i
                            last_seen_b2 = i
                        else:
                            prev_gap_b2 = last_seen_b2 - i
                            gaps_b2 = [prev_gap_b2, cur_gap_b2]
                            break
                if len(gaps_b2) == 2:
                    momentum_b2 = gaps_b2[1] / max(gaps_b2[0], 1)
                    sb2[num] = gaps_b2[1] * min(momentum_b2, 2.0)
                elif len(gaps_b2) == 1:
                    sb2[num] = gaps_b2[0]
            return b1b2_from_scores(sb1, sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _run_length(self, key):
        """Analyze run-length patterns in sorted number sequences."""
        def _r():
            if len(self.draws) < 20: return self.m01_freq()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for d in self.draws[-50:]:
                sorted_b1 = sorted(d.block1)
                runs = []
                if sorted_b1:
                    run_start = sorted_b1[0]
                    run_end = sorted_b1[0]
                    for x in sorted_b1[1:]:
                        if x == run_end + 1:
                            run_end = x
                        else:
                            runs.append((run_start, run_end))
                            run_start = x
                            run_end = x
                    runs.append((run_start, run_end))
                for start, end in runs:
                    for num in range(max(1, start-1), min(B1_MAX+1, end+2)):
                        sb1[num] += 1.5
                for x in d.block1:
                    sb1[x] += 0.5
            if self.gfc:
                for num in range(1, B1_MAX+1):
                    sb1[num] += self.gfc.b1f.get(num, 0) * 0.2
                for num in range(1, B2_MAX+1):
                    sb2[num] += self.gfc.b2f.get(num, 0) * 0.2
            return b1b2_from_scores(sb1, sb2) if any(sb1.values()) else self.m01_freq()
        return self._S(key, _r)

    def _smart_monte_carlo(self, key):
        """Monte Carlo with gap-aware probability adjustment."""
        def _r():
            if not self.gfc: return self.m01_freq()
            n = len(self.draws)
            b1p = np.array([self.gfc.b1f.get(x, 0) + 1.0 for x in range(1, B1_MAX+1)], dtype=float)
            b2p = np.array([self.gfc.b2f.get(x, 0) + 1.0 for x in range(1, B2_MAX+1)], dtype=float)
            for x in range(B1_MAX):
                gap = self.gfc.gap1(x+1)
                b1p[x] *= 1.0 + gap * 0.08
            for x in range(B2_MAX):
                gap = self.gfc.gap2(x+1)
                b2p[x] *= 1.0 + gap * 0.08
            b1p /= b1p.sum()
            b2p /= b2p.sum()
            rng = np.random.default_rng(42 + n)
            sb1 = defaultdict(int); sb2 = defaultdict(int)
            for _ in range(1000):
                if B1_MAX >= PICK_B1 and b1p.sum() > 0:
                    c1 = rng.choice(B1_MAX, PICK_B1, replace=False, p=b1p) + 1
                    for x in c1: sb1[x] += 1
                if B2_MAX >= PICK_B2 and b2p.sum() > 0:
                    c2 = rng.choice(B2_MAX, PICK_B2, replace=False, p=b2p) + 1
                    for x in c2: sb2[x] += 1
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _enhanced_ensemble(self, key):
        """Enhanced ensemble using top-performing base models with higher weights."""
        def _r():
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            top_models = [
                (self.m01_freq, 3.0),
                (self._differential_freq, 3.0),
                (lambda: self._window(70, '__tmp70'), 2.5),
                (self.m14_entropy, 1.5),
                (self.m12_momentum, 2.0),
                (self.m15_cyclic, 2.0),
                (lambda: self._mean_reversion('__tmp_mrev', 50), 1.5),
            ]
            for fn, w in top_models:
                try:
                    b1, b2 = fn()
                    for x in b1: sb1[x] += w
                    for x in b2: sb2[x] += w
                except Exception: pass
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    def _enhanced_markov(self, key):
        """Enhanced Markov chain with Laplace smoothing."""
        def _r():
            n = len(self.draws)
            if n < 5: return self.m01_freq()
            mb1 = defaultdict(lambda: defaultdict(float))
            mb2 = defaultdict(lambda: defaultdict(float))
            for i in range(n-1):
                w = exp_w(n-1-i, 30.0)
                p, c = self.draws[i], self.draws[i+1]
                for x in p.block1:
                    for y in c.block1: mb1[x][y] += w
                for x in p.block2:
                    for y in c.block2: mb2[x][y] += w
            last = self._last()
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for x in last.block1:
                total = sum(mb1[x].values()) + 0.1 * B1_MAX
                for y in range(1, B1_MAX+1):
                    prob = (mb1[x].get(y, 0) + 0.1) / total
                    sb1[y] += prob * 2.0
            for x in last.block2:
                total = sum(mb2[x].values()) + 0.1 * B2_MAX
                for y in range(1, B2_MAX+1):
                    prob = (mb2[x].get(y, 0) + 0.1) / total
                    sb2[y] += prob * 2.0
            if self.gfc:
                for num in range(1, B1_MAX+1):
                    sb1[num] += self.gfc.b1f.get(num, 0) * 0.1
                for num in range(1, B2_MAX+1):
                    sb2[num] += self.gfc.b2f.get(num, 0) * 0.1
            return b1b2_from_scores(sb1, sb2) if sb1 else self.m01_freq()
        return self._S(key, _r)

    def _enhanced_gap(self, key):
        """Enhanced gap model with mean-reversion component."""
        def _r():
            if not self.gfc: return self.m01_freq()
            n = len(self.draws)
            avg_gap_b1 = max(n * PICK_B1 / B1_MAX, 1)
            avg_gap_b2 = max(n * PICK_B2 / B2_MAX, 1)
            sb1 = defaultdict(float); sb2 = defaultdict(float)
            for num in range(1, B1_MAX+1):
                gap = self.gfc.gap1(num)
                freq = self.gfc.b1f.get(num, 0)
                overdue_score = gap / avg_gap_b1
                freq_score = freq / max(n * PICK_B1 / B1_MAX, 1)
                sb1[num] = overdue_score * 1.5 + freq_score * 0.5
            for num in range(1, B2_MAX+1):
                gap = self.gfc.gap2(num)
                freq = self.gfc.b2f.get(num, 0)
                overdue_score = gap / avg_gap_b2
                freq_score = freq / max(n * PICK_B2 / B2_MAX, 1)
                sb2[num] = overdue_score * 1.5 + freq_score * 0.5
            return b1b2_from_scores(sb1, sb2)
        return self._S(key, _r)

    # ── ALL PREDICTIONS ───────────────────────────────────────────────
    def all_predictions(self):
        if not self.draws:
            _fb1 = list(range(1, PICK_B1+1))
            _fb2 = list(range(PICK_B1+1, PICK_B1+PICK_B2+1))
            return [(_fb1, _fb2)] * TOTAL_MODELS

        def safe(fn):
            try:
                r=fn()
                if r and len(r)==2 and len(r[0])==PICK_B1 and len(r[1])==PICK_B2:
                    return (sorted(r[0]),sorted(r[1]))
            except Exception: pass
            _fb1 = list(range(1, PICK_B1+1))
            _fb2 = list(range(PICK_B1+1, PICK_B1+PICK_B2+1))
            return (_fb1, _fb2)

        p=[]
        # G1: 20 base models (p0-p19)
        p+=[safe(self.m01_freq),safe(lambda:self._enhanced_markov('emarkov1')),safe(lambda:self._enhanced_gap('egap1')),
            safe(self.m04_pattern),safe(self.m05_neural),safe(self.m06_monte),
            safe(self.m07_genetic),safe(self.m08_balance),safe(self.m09_deep),
            safe(self.m10_fibonacci),safe(lambda:self._modular_pattern('modpat1')),safe(self.m12_momentum),
            safe(self.m13_zscore),safe(self.m14_entropy),safe(self.m15_cyclic),
            safe(lambda:self._enhanced_ensemble('eens1')),safe(self.m17_recency),safe(lambda:self._number_affinity('naffin1')),
            safe(self.m19_regression_mean),safe(lambda:self.m20_ewma(0.15,'ew15'))]

        # G2: Window variants (p20-p31) — 12 unique
        for w in [5,10,15,20,30,50,70,100,150,200,300,500]:
            p.append(safe(lambda w=w:self._window(w,f'win{w}')))

        # G3: Gap+freq hybrids (p32-p44) — 13 unique
        for b in [0.8,1.0,1.2,1.5,2.0,0.5,1.8,2.5,0.3,3.0,0.6,1.3,0.9]:
            p.append(safe(lambda b=b:self._gap_freq(b,f'gf{b}')))

        # G4: EWMA alphas (p45-p56) — 12 unique
        for a in [0.05,0.10,0.20,0.25,0.30,0.35,0.40,0.50,0.60,0.08,0.12,0.18]:
            p.append(safe(lambda a=a:self.m20_ewma(a,f'ew{a}')))

        # G5: velocity/zscore/Bayes/drawtype (p57-p69) — 13 models (some replaced)
        p.append(safe(lambda:self._enhanced_differential('ediff1', 5, 15)))       # was Velocity-10/20
        p.append(safe(lambda:self._enhanced_differential('ediff2', 15, 30)))      # was Velocity-5/15
        p.append(safe(lambda:self._recency_z(30,'rz30')))
        p.append(safe(lambda:self._recency_z(50,'rz50')))
        p.append(safe(lambda:self._recency_z(80,'rz80')))
        p.append(safe(lambda:self._bayesian(0.3,'bay3')))
        p.append(safe(lambda:self._bayesian(0.5,'bay5')))
        p.append(safe(lambda:self._bayesian(0.8,'bay8')))
        p.append(safe(lambda:self._streak_reversal('srev1')))                      # was Streak-30
        p.append(safe(lambda:self._streak_reversal('srev2')))                      # was Streak-50
        p.append(safe(lambda:self._draw_type_freq('dtf')))
        p.append(safe(lambda:self._freq_gap_hybrid('fghyb1')))                     # was CrossBlockGap
        p.append(safe(lambda:self._period_detection('perdet1')))                   # was Fourier

        # G6: Weighted ensembles / new models (p70-p98) — 29 models (many replaced)
        base=[self.m01_freq,self.m02_markov,self.m03_gap,self.m12_momentum]
        weight_sets=[[2,1,1,1],[1,2,1,1],[1,1,2,1],[1,1,1,2],
                     [3,1,0,0],[0,3,1,0],[1,0,3,0],[1,0,0,3],
                     [2,2,0,0],[0,2,2,0],[2,0,2,0],[2,1,1,0],
                     [0,2,1,1],[1,1,0,2],[1.5,1.5,1,0],[1,1.5,1.5,0],
                     [0,1,1.5,1.5],[1.5,0,1,1.5],[1,1,1,1],[2,2,1,1],
                     [3,2,0,0],[0,3,2,0],[2,0,3,0],[1,3,0,1],
                     [0,1,3,1],[3,0,1,2],[0,2,0,3],[2,0,2,1],[1,2,1,2]]
        for i,ws in enumerate(weight_sets[:29]):
            def _ens(ws=ws,i=i):
                sb1=defaultdict(float); sb2=defaultdict(float)
                for fn,w in zip(base,ws):
                    try:
                        b1,b2=fn()
                        for x in b1: sb1[x]+=w
                        for x in b2: sb2[x]+=w
                    except Exception: pass
                return b1b2_from_scores(sb1,sb2)
            if i == 1:   # ID 71 (Ens-2)
                p.append(safe(lambda:self._enhanced_differential('ediff3', 30, 50)))
            elif i == 5:  # ID 75 (Ens-6)
                p.append(safe(lambda:self._recency_gap('rgap1', 100)))
            elif i == 6:  # ID 76 (Ens-7)
                p.append(safe(lambda:self._recency_gap('rgap2', 200)))
            elif i == 9:  # ID 79 (Ens-10)
                p.append(safe(lambda:self._freq_gap_hybrid('fghyb2', 0.5, 0.5)))
            elif i == 12: # ID 82 (Ens-13)
                p.append(safe(lambda:self._recency_gap('rgap3', 50)))
            elif i == 15: # ID 85 (Ens-16)
                p.append(safe(lambda:self._hot_cold_balance('hcbal1')))
            elif i == 18: # ID 88 (Ens-19)
                p.append(safe(lambda:self._adaptive_window('adwin1')))
            elif i == 19: # ID 89 (Ens-20)
                p.append(safe(lambda:self._adaptive_window('adwin2')))
            elif i == 21: # ID 91 (Ens-22)
                p.append(safe(lambda:self._constrained_sum('csum1')))
            elif i == 22: # ID 92 (Ens-23)
                p.append(safe(lambda:self._constrained_sum('csum2', 0.75)))
            elif i == 23: # ID 93 (Ens-24)
                p.append(safe(lambda:self._hot_cold_balance('hcbal2')))
            elif i == 24: # ID 94 (Ens-25)
                p.append(safe(lambda:self._hot_cold_balance('hcbal3')))
            elif i == 28: # ID 98 (Ens-29)
                p.append(safe(lambda:self._streak_reversal('srev3')))
            else:
                p.append(safe(lambda ws=ws,i=i:_ens(ws,i)))

        # G7: NEW unique models (p99-p119) — 21 unique
        p.append(safe(lambda:self._positional_drift('pdrift1')))
        p.append(safe(lambda:self._window(25,'w25')))
        p.append(safe(lambda:self._adaptive_zscore('azs1')))                        # was Z-100
        p.append(safe(lambda:self._bayesian(0.2,'bay2')))
        # Hot/Cold streaks
        p.append(safe(lambda:self._hot_streak('hot1', 10, 3)))
        p.append(safe(lambda:self._hot_streak('hot2', 15, 4)))
        p.append(safe(lambda:self._gap_momentum('gmoment1')))                       # was GapAccel
        # Sum parity
        p.append(safe(lambda:self._sum_parity('spar1')))
        # Consecutive pairs
        p.append(safe(lambda:self._run_length('runlen1')))                          # was ConsecPairs
        # High/Low split
        p.append(safe(lambda:self._high_low_split('hilo1')))
        # Differential frequency
        p.append(safe(lambda:self._differential_freq('diff1')))
        # Triple Markov
        p.append(safe(lambda:self._enhanced_markov('emarkov2')))                    # was TripleMarkov
        # Entropy weighted
        p.append(safe(lambda:self._entropy_weighted('entw1')))
        # Mean reversion (3 variants)
        p.append(safe(lambda:self._mean_reversion('mrev1', 50)))
        p.append(safe(lambda:self._mean_reversion('mrev2', 100)))
        p.append(safe(lambda:self._mean_reversion('mrev3', 150)))
        # Lag correlation
        p.append(safe(lambda:self._lag_correlation('lagc1')))
        # Block sum trend
        p.append(safe(lambda:self._block_sum_trend('bsum1')))
        # Monte Carlo Bayesian
        p.append(safe(lambda:self._smart_monte_carlo('smc1')))                      # was MonteBayes
        # RecencyZ and Bayesian additional
        p.append(safe(lambda:self._adaptive_zscore('azs2')))                        # was RecencyZ-150
        p.append(safe(lambda:self._bayesian(1.0,'bay10')))

        # G8: More new models (p120-p132) — 13 unique
        p.append(safe(lambda:self._adaptive_ewma('adew1')))
        p.append(safe(lambda:self._gap_momentum('gmoment2')))                       # was GapBurst
        p.append(safe(lambda:self._cluster_analysis('clust1')))
        # Position-specific models (P0-P3)
        p.append(safe(lambda:self._position_specific('pos0', 0)))
        p.append(safe(lambda:self._position_specific('pos1', 1)))
        p.append(safe(lambda:self._position_specific('pos2', 2)))
        p.append(safe(lambda:self._position_specific('pos3', 3)))
        # More windows not in G2
        p.append(safe(lambda:self._window(8,'w8')))
        p.append(safe(lambda:self._window(12,'w12')))
        p.append(safe(lambda:self._window(40,'w40')))
        p.append(safe(lambda:self._window(250,'w250')))
        # Additional bayesian
        p.append(safe(lambda:self._bayesian(1.5,'bay15')))
        # v1.4: Draw-type specific frequency (R3)
        p.append(safe(lambda:self._draw_type_specific('dtfreq1')))

        # Safety: fill to TOTAL_MODELS if short
        while len(p) < TOTAL_MODELS:
            p.append(safe(self.m16_ensemble))
        p = p[:TOTAL_MODELS]

        # v25.1: Zero out disabled models — they keep their slot but contribute
        # no votes to consensus, reducing noise from consistently bad models.
        for i in _DISABLED_MODELS:
            if i < len(p):
                p[i] = ([], [])

        return p

    def consensus(self, weights=None, draw_type='all'):
        all_p=self.all_predictions()

        # Collect active (non-disabled) models with their weights
        active = []
        for i, (b1, b2) in enumerate(all_p):
            _bl1 = len(b1) if hasattr(b1, '__len__') else 0
            _bl2 = len(b2) if hasattr(b2, '__len__') else 0
            if _bl1 == 0 and _bl2 == 0:
                continue  # skip disabled models (empty predictions)
            w = float(weights[i]) if weights is not None and i < len(weights) else 1.0
            active.append((i, b1, b2, w))

        n_active = len(active)

        # If too few active models, use all equally (original behavior)
        if n_active < 10:
            sb1=defaultdict(float); sb2=defaultdict(float)
            for i, b1, b2, w in active:
                for x in b1: sb1[x]+=w
                for x in b2: sb2[x]+=w
            return b1b2_from_scores(sb1,sb2)

        # v39.2.1: Filter to top 40% of models by weight (was 50%)
        # This increases consensus by excluding the noisiest bottom models
        active.sort(key=lambda x: -x[3])
        top_share = max(n_active * 40 // 100, 10)
        top_filtered = active[:top_share]

        # Build vote counter with 2x weight for boosted models
        sb1=defaultdict(float); sb2=defaultdict(float)
        for i, b1, b2, w in top_filtered:
            boost = 2.0 if i in _BOOSTED_MODELS else 1.0
            for x in b1: sb1[x]+=w*boost
            for x in b2: sb2[x]+=w*boost

        return b1b2_from_scores(sb1,sb2)


class DualBayesRing:
    """Separate BayesRing for STD and RNG draw types with weight decay."""
    def __init__(self, n=TOTAL_MODELS, maxr=200, tau=30.0):
        self.n=n; self.maxr=maxr; self.tau=tau
        self._rings = {'std': [], 'rng': [], 'all': []}
        self.draws = 0
        
    def update(self, preds, ab1, ab2, draw_type='all'):
        self.draws += 1
        sb1=set(ab1); sb2=set(ab2)
        h1=np.array([len(set(b1)&sb1) for b1,b2 in preds],dtype=np.float32)
        h2=np.array([len(set(b2)&sb2) for b1,b2 in preds],dtype=np.float32)
        entry = {'h1':h1,'h2':h2,'h':h1+h2}
        self._rings['all'].insert(0, entry)
        if draw_type in ('std', 'rng'):
            self._rings[draw_type].insert(0, entry)
        for key in self._rings:
            if len(self._rings[key]) > self.maxr:
                self._rings[key].pop()
    
    def weights(self, draw_type='all'):
        """Get weights for specific draw type. Falls back to 'all' if not enough data."""
        ring = self._rings.get(draw_type, self._rings['all'])
        if len(ring) < 10:
            ring = self._rings['all']  # Fall back to combined
        w1=np.ones(self.n,np.float32); w2=np.ones(self.n,np.float32)
        for age, e in enumerate(ring[:self.maxr]):
            d = math.exp(-age/self.tau)
            w1 += e['h1']/4.0*d
            w2 += e['h2']/4.0*d
        # Apply weight decay: penalize models with zero recent hits
        if ring:
            recent_hits1 = np.zeros(self.n, dtype=np.float32)
            recent_hits2 = np.zeros(self.n, dtype=np.float32)
            decay_window = min(20, len(ring))
            for e in ring[:decay_window]:
                recent_hits1 += (e['h1'] > 0).astype(np.float32)
                recent_hits2 += (e['h2'] > 0).astype(np.float32)
            decay_factor = 0.5
            no_hit_mask1 = recent_hits1 == 0
            no_hit_mask2 = recent_hits2 == 0
            w1[no_hit_mask1] *= decay_factor
            w2[no_hit_mask2] *= decay_factor
        return w1, w2


# ════════════════════════════════════════════════════════════════════════
#  HELPER: Compute match positions between prediction and actual
# ════════════════════════════════════════════════════════════════════════

def _compute_match_positions(pred_block, act_block):
    """
    Compare sorted prediction vs sorted actual position-by-position.
    Returns list of 1-based positions where numbers match at the same
    sorted index. E.g. pred=[3,7,12,18] act=[3,12,15,18] → [1,4].
    """
    pred_sorted = sorted(pred_block)
    act_sorted = sorted(act_block)
    positions = []
    for pos_idx, (p_num, a_num) in enumerate(zip(pred_sorted, act_sorted)):
        if p_num == a_num:
            positions.append(pos_idx + 1)  # 1-based
    return positions


# ════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ════════════════════════════════════════════════════════════════════════

def init_state():
    defaults = {
        'draws':            [],
        'predictor':        LP132(),
        'bayes':            DualBayesRing(),
        'accuracy_history': [],
        'last_pred':        None,
        'last_all_preds':   None,
        'trained':          False,
        'log_lines':        [],
        'training_running': False,
        'model_report_data': [],   # v1.1: list of dicts for HTML report
        'training_time':    0.0,   # v1.1: elapsed training time in seconds
        '_last_upload_hash': None,  # v1.6: prevent re-parse on widget rerun
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def log(msg, kind='info'):
    try:
        ts = datetime.now().strftime('%H:%M:%S')
        lines = st.session_state.log_lines
        lines.append((ts, kind, msg))
        if len(lines) > 200:
            del lines[:len(lines) - 200]
    except Exception:
        pass  # Safe no-op when called from non-Streamlit context (predict.py mock)


# ════════════════════════════════════════════════════════════════════════
#  UI HELPERS
# ════════════════════════════════════════════════════════════════════════

def render_balls(block1, block2, hit_b1=None, hit_b2=None):
    html = '<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">'
    html += '<div style="display:flex;gap:6px;">'
    for x in block1:
        extra = ' ball-hit' if (hit_b1 and x in hit_b1) else ''
        html += f'<div class="ball-b1{extra}">{x}</div>'
    html += '</div>'
    html += '<div style="color:#475569;font-weight:700;font-size:1.1rem;">|</div>'
    html += '<div style="display:flex;gap:6px;">'
    for x in block2:
        extra = ' ball-hit' if (hit_b2 and x in hit_b2) else ''
        html += f'<div class="ball-b2{extra}">{x}</div>'
    html += '</div></div>'
    st.markdown(html, unsafe_allow_html=True)


# TASK 2 FIX: render_stat_badges — proper kwargs iteration
def render_stat_badges(*args):
    """Render stat badges. Accepts either positional tuples (label, val, kind)
    or keyword arguments where each value is a (label, val, kind) tuple."""
    html = ''
    badges = []
    if args:
        for item in args:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                badges.append(item)
    if not badges:
        return
    for label, val, kind in badges:
        html += f'<span class="stat-badge stat-badge-{kind}">{label}: {val}</span> '
    st.markdown(html, unsafe_allow_html=True)


def section_header(icon, title):
    st.markdown(f'''
    <div class="section-hdr">
      <span style="font-size:1.3rem">{icon}</span>
      <span class="section-hdr-title">{title}</span>
    </div>''', unsafe_allow_html=True)


def format_elapsed(seconds):
    """Format seconds as MM:SS or HH:MM:SS."""
    s = int(seconds)
    if s < 3600:
        return f"{s // 60:02d}:{s % 60:02d}"
    else:
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:02d}"


# ════════════════════════════════════════════════════════════════════════
#  TRAINING ENGINE
# ════════════════════════════════════════════════════════════════════════

def do_train(draws, seed_size=100, batch_step=100, full_every=20, progress_bar=None, timer_placeholder=None):
    """Train the model with all 132 predictors, BayesRing weights, and collect model_report_data."""
    t_start = time.time()

    try:
        sorted_draws = sorted(draws, key=lambda d: d.draw_no)
        n_total = len(sorted_draws)
        seed_size = min(seed_size, n_total)
        seed = sorted_draws[:seed_size]
        remaining = sorted_draws[seed_size:]

        st.session_state.accuracy_history = []
        st.session_state.bayes = DualBayesRing()
        st.session_state.model_report_data = []  # v1.1: reset model report

        # Seed
        st.session_state.draws = list(seed)
        st.session_state.predictor = LP132()
        st.session_state.predictor.update(st.session_state.draws)
        all_p = st.session_state.predictor.all_predictions()
        st.session_state.last_all_preds = all_p
        st.session_state.last_pred = st.session_state.predictor.consensus()
        log(f'Прогрев: {seed_size} тиражей (#{seed[0].draw_no}--#{seed[-1].draw_no})', 'ok')

        n_batches = math.ceil(len(remaining) / batch_step) if remaining else 0

        for batch_idx in range(n_batches):
            bs = batch_idx * batch_step
            be = min(bs + batch_step, len(remaining))
            batch = remaining[bs:be]

            for draw in batch:
                # Track accuracy BEFORE adding
                if st.session_state.last_pred and st.session_state.last_all_preds:
                    entry = AccuracyEntry(
                        draw.draw_no,
                        st.session_state.last_pred[0],
                        st.session_state.last_pred[1],
                        draw.block1, draw.block2,
                        date=getattr(draw, 'date', '')
                    )
                    st.session_state.accuracy_history.append(entry)

                    # v1.1: Store model report data (all 155 predictions vs actual)
                    # v13.0: Cap at MAX 3000 entries
                    st.session_state.model_report_data.append({
                        'draw_no': draw.draw_no,
                        'draw_type': getattr(draw, 'draw_type', 'unknown'),
                        'all_model_predictions': list(st.session_state.last_all_preds),
                        'act_b1': list(draw.block1),
                        'act_b2': list(draw.block2),
                    })
                    # v7.0: Increased cap to 3000 (was 1000) for richer LPD_DATA
                    if len(st.session_state.model_report_data) > 3000:
                        st.session_state.model_report_data = st.session_state.model_report_data[-3000:]

                    # Bayes update (block-specific v130 fix)
                    st.session_state.bayes.update(
                        st.session_state.last_all_preds, draw.block1, draw.block2,
                        draw_type=getattr(draw, 'draw_type', 'all'))

                st.session_state.draws.append(draw)
                st.session_state.predictor.update(st.session_state.draws)

                # Fast per-draw prediction
                try:
                    ep = _fast_pred(st.session_state.predictor, st.session_state.bayes, draw_type=getattr(draw, 'draw_type', 'all'))
                    st.session_state.last_pred = ep
                except Exception: pass

            # Full ensemble every N batches
            is_last = (batch_idx == n_batches - 1)
            if not is_last and batch_idx % full_every == 0:
                st.session_state.predictor._c.clear()
                all_p = st.session_state.predictor.all_predictions()
                st.session_state.last_all_preds = all_p
                last_batch_draw_type = getattr(batch[-1], 'draw_type', 'all') if batch else 'all'
                w1, w2 = st.session_state.bayes.weights(last_batch_draw_type)
                combined = np.sqrt(w1 * w2)
                st.session_state.last_pred = _weighted_consensus(
                    st.session_state.predictor, combined)

            # Update progress
            if progress_bar:
                pct = (seed_size + (batch_idx + 1) * batch_step) / n_total
                progress_bar.progress(min(pct, 0.95))

            # Update timer
            if timer_placeholder:
                elapsed = time.time() - t_start
                batch_no = batch_idx + 1
                pct_val = min(pct * 100, 95)
                timer_placeholder.markdown(
                    f"⏱ **{format_elapsed(elapsed)}** | "
                    f"Пакет {batch_no}/{n_batches} ({pct_val:.0f}%)"
                )

        # Final full ensemble
        st.session_state.predictor._c.clear()
        final_p = st.session_state.predictor.all_predictions()
        st.session_state.last_all_preds = final_p
        last_draw_type = getattr(remaining[-1], 'draw_type', 'all') if remaining else 'all'
        w1, w2 = st.session_state.bayes.weights(last_draw_type)
        combined = np.sqrt(w1 * w2)
        st.session_state.last_pred = _weighted_consensus(st.session_state.predictor, combined)
        st.session_state.trained = True
        # Cross-validation
        if len(st.session_state.draws) > 500:
            try:
                cv_results = _cross_validate(draws, k=5, seed_size=seed_size)
                if cv_results:
                    st.session_state.cv_results = cv_results
                    avg_cv = sum(r['avg_hits'] for r in cv_results) / len(cv_results)
                    log(f'📊 k-fold CV: среднее {avg_cv:.2f}/{PICK_B1+PICK_B2} по {len(cv_results)} фолдам', 'ok')
            except Exception as ex:
                log(f'⚠ CV ошибка: {ex}', 'warn')
        elapsed_total = time.time() - t_start
        st.session_state.training_time = elapsed_total
        if progress_bar:
            progress_bar.progress(1.0)
        if timer_placeholder:
            timer_placeholder.markdown(
                f"⏱ **{format_elapsed(elapsed_total)}** | Завершено"
            )
        log(f'Обучение завершено. Данных: {len(st.session_state.draws):,} | '
            f'Время: {format_elapsed(elapsed_total)}', 'ok')

    except Exception as ex:
        elapsed_total = time.time() - t_start
        log(f'ОШИБКА обучения: {ex}', 'warn')
        st.session_state.training_time = elapsed_total
        raise


def _position_aware_consensus(predictor, bayes, draw_type='all'):
    """Position-specific weighted consensus: different model weights per position."""
    all_p = predictor.all_predictions()
    w1, w2 = bayes.weights(draw_type)
    
    final_b1 = []
    b1_used = set()
    for pos in range(PICK_B1):
        votes = defaultdict(float)
        for i, (pb1, pb2) in enumerate(all_p):
            if i >= len(w1): continue
            if pos < len(pb1):
                num = pb1[pos]
                votes[num] += w1[i]
        best = max(votes, key=votes.get) if votes else 1
        final_b1.append(best)
        b1_used.add(best)
    final_b1 = sorted(final_b1)
    
    final_b2 = []
    for pos in range(PICK_B2):
        votes = defaultdict(float)
        for i, (pb1, pb2) in enumerate(all_p):
            if i >= len(w2): continue
            if pos < len(pb2):
                num = pb2[pos]
                votes[num] += w2[i]
        best = max(votes, key=votes.get) if votes else 1
        final_b2.append(best)
    final_b2 = sorted(final_b2)
    
    return final_b1, final_b2


def _cross_validate(draws, k=5, seed_size=100):
    """K-fold cross-validation to measure prediction accuracy stability."""
    if len(draws) < seed_size + k * 20:
        return None
    sorted_draws = sorted(draws, key=lambda d: d.draw_no)
    fold_size = (len(sorted_draws) - seed_size) // k
    results = []
    for fold_idx in range(k):
        test_start = seed_size + fold_idx * fold_size
        test_end = min(test_start + fold_size, len(sorted_draws))
        if test_end <= test_start:
            continue
        train = sorted_draws[:test_start]
        test = sorted_draws[test_start:test_end]
        if len(train) < seed_size or len(test) < 5:
            continue
        pred = LP132()
        pred.update(train)
        b1, b2 = pred.consensus()
        fold_hits = []
        for d in test:
            hits = len(set(b1) & set(d.block1)) + len(set(b2) & set(d.block2))
            fold_hits.append(hits)
        results.append({
            'fold': fold_idx + 1,
            'train_size': len(train),
            'test_size': len(test),
            'avg_hits': sum(fold_hits) / len(fold_hits),
            'max_hits': max(fold_hits),
            'ge5_count': sum(1 for h in fold_hits if h >= 5),
        })
    return results


def _monte_carlo_confidence(predictor, n_simulations=5000):
    """Estimate confidence intervals for predictions using Monte Carlo simulation."""
    all_p = predictor.all_predictions()
    if not all_p or not predictor.draws:
        return None
    b1_votes = Counter(x for pb1, _ in all_p for x in pb1)
    b2_votes = Counter(x for _, pb2 in all_p for x in pb2)
    total = len(all_p)
    b1_probs = {n: c/total for n, c in b1_votes.items()}
    b2_probs = {n: c/total for n, c in b2_votes.items()}
    b1_numbers = list(range(1, B1_MAX+1))
    b2_numbers = list(range(1, B2_MAX+1))
    b1_p = np.array([b1_probs.get(n, 0.01) for n in b1_numbers])
    b2_p = np.array([b2_probs.get(n, 0.01) for n in b2_numbers])
    b1_p /= b1_p.sum()
    b2_p /= b2_p.sum()
    rng = np.random.default_rng(42)
    hit_dist = []
    # v13.0: Compute consensus ONCE outside the loop (deterministic — predictor state doesn't change during simulation)
    cons_b1, cons_b2 = predictor.consensus()
    for _ in range(n_simulations):
        sim_b1 = set(rng.choice(B1_MAX, PICK_B1, replace=False, p=b1_p) + 1)
        sim_b2 = set(rng.choice(B2_MAX, PICK_B2, replace=False, p=b2_p) + 1)
        hits = len(sim_b1 & set(cons_b1)) + len(sim_b2 & set(cons_b2))
        hit_dist.append(hits)
    hit_dist = np.array(hit_dist)
    return {
        'mean': float(np.mean(hit_dist)),
        'std': float(np.std(hit_dist)),
        'p5': float(np.percentile(hit_dist, 5)),
        'p95': float(np.percentile(hit_dist, 95)),
        'p_ge5': float(np.mean(hit_dist >= 5)),
        'distribution': dict(Counter(hit_dist.tolist())),
    }


def _dynamic_model_weights(bayes, min_performance=0.8):
    """Exclude models performing below threshold compared to random baseline."""
    w1, w2 = bayes.weights()
    baseline_b1 = 4 * (4.0 / B1_MAX)
    baseline_b2 = 4 * (4.0 / B2_MAX)
    threshold_b1 = max(w1) * 0.02
    threshold_b2 = max(w2) * 0.02
    w1_mod = w1.copy()
    w2_mod = w2.copy()
    w1_mod[w1 < threshold_b1] = 0.01
    w2_mod[w2 < threshold_b2] = 0.01
    return w1_mod, w2_mod



def _fast_pred(predictor, bayes, draw_type='all'):
    """Calibration ensemble -- 18 diverse models with DualBayesRing weights (v14.0).
    
    v14.0: Updated model indices to match new all_predictions() enumeration.
    Replaced underperforming models with top new variants.
    Uses DualBayesRing with draw_type-specific weights.
    """
    fns = [
        # Base models (G1) — using new replacements where applicable
        (0, predictor.m01_freq),
        (1, lambda: predictor._enhanced_markov('emarkov1')),   # was m02_markov
        (2, lambda: predictor._enhanced_gap('egap1')),         # was m03_gap
        (4, predictor.m05_neural),
        (7, predictor.m08_balance),
        (14, predictor.m15_cyclic),
        (9, predictor.m10_fibonacci),                         # Fibonacci — top cross-game
        (15, lambda: predictor._enhanced_ensemble('eens1')),  # was m16_ensemble
        (16, predictor.m17_recency),
        # Top new models
        (109, lambda: predictor._differential_freq('diff_fp1')),  # Differential — #1 cross-game
        (26, lambda: predictor._window(70, 'win_fp70')),          # Window-70 — best on 4x20
        (108, lambda: predictor._high_low_split('hilo_fp1')),    # HighLow — stable
        (115, lambda: predictor._lag_correlation('lagc_fp1')),    # LagCorrel — stable
        # Position-specific (G8)
        (123, lambda: predictor._position_specific('pos_fp0', 0)),
        (124, lambda: predictor._position_specific('pos_fp1', 1)),
        # Entropy-weighted (G7)
        (111, lambda: predictor._entropy_weighted('entw_fp1')),
        # Gap+Freq (G3)
        (32, lambda: predictor._gap_freq(0.8, 'gf_fp1')),
        # Draw-type-specific (G8)
        (132, lambda: predictor._draw_type_specific('dt_fp1')),
        # Enhanced Differential (G5)
        (57, lambda: predictor._enhanced_differential('ediff_fp1', 10, 20)),
    ]
    w1, w2 = bayes.weights(draw_type)
    sb1 = defaultdict(float); sb2 = defaultdict(float)
    for idx, fn in fns:
        try:
            b1, b2 = fn()
            wt1 = float(w1[idx]) if idx < len(w1) else 1.0
            wt2 = float(w2[idx]) if idx < len(w2) else 1.0
            for x in b1: sb1[x] += wt1
            for x in b2: sb2[x] += wt2
        except Exception: pass
    # v38.2: Adaptive recency blend — more draws → less recency noise
    # Short datasets (<200): higher recency (0.40) to capture recent patterns
    # Medium datasets (200-1000): moderate (0.30)
    # Large datasets (>1000): lower (0.20) to prioritize model consensus
    n_draws = len(predictor.draws)
    if n_draws < 200:
        recency_weight = 0.40
    elif n_draws < 1000:
        recency_weight = 0.30
    else:
        recency_weight = 0.20
    model_weight = 1.0 - recency_weight
    print(f'[INFO] _fast_pred: n_draws={n_draws}, recency_weight={recency_weight:.2f}, model_weight={model_weight:.2f}', file=sys.stderr)
    recent = predictor.draws[-50:] if len(predictor.draws) >= 50 else predictor.draws
    rb1 = defaultdict(float); rb2 = defaultdict(float)
    for i, d in enumerate(recent):
        w = (i + 1) / max(len(recent), 1)
        for x in d.block1: rb1[x] += w
        for x in d.block2: rb2[x] += w
    mR1 = max(rb1.values()) if rb1 else 1; mR2 = max(rb2.values()) if rb2 else 1
    for n in range(1, max(B1_MAX, B2_MAX)+1):
        sb1[n] = model_weight * sb1[n] + recency_weight * (rb1.get(n, 0) / max(mR1, 1e-9))
        sb2[n] = model_weight * sb2[n] + recency_weight * (rb2.get(n, 0) / max(mR2, 1e-9))
    return b1b2_from_scores(sb1, sb2)


def _weighted_consensus(predictor, weights, draw_type='all'):
    """v39.2.1: Top-N weighted consensus — excludes bottom 40% models by weight.
    
    Uses BayesRing weights but filters out low-weight models to reduce noise
    from consistently underperforming models.
    - Skips disabled models (empty predictions from _DISABLED_MODELS)
    - Gives 1.5x weight to boosted models (_BOOSTED_MODELS)
    - v39.2.1: Stricter 40% threshold (was 30%) for better consensus
    """
    all_p = predictor.all_predictions()
    if not all_p or (weights is not None and hasattr(weights, '__len__') and len(weights) == 0):
        return predictor.consensus()
    # weights is a 1D array of length TOTAL_MODELS (combined sqrt(w1*w2) from BayesRing)
    model_weights = []
    for i in range(min(len(all_p), len(weights)) if hasattr(weights, '__len__') else 0):
        model_weights.append(float(weights[i]))
    # v39.2.1: Filter: only use models with weight >= 40th percentile (was 30%)
    if model_weights:
        threshold = sorted(model_weights)[len(model_weights) * 40 // 100]
    else:
        threshold = 1.0
    sb1 = defaultdict(float); sb2 = defaultdict(float)
    for i, (b1, b2) in enumerate(all_p):
        _wl1 = len(b1) if hasattr(b1, '__len__') else 0
        _wl2 = len(b2) if hasattr(b2, '__len__') else 0
        if _wl1 == 0 and _wl2 == 0:
            continue  # skip disabled models (empty predictions)
        w = model_weights[i] if i < len(model_weights) else 1.0
        if model_weights and w < threshold:
            continue  # Skip low-weight models
        # 1.5x boost for cross-game top performers
        if i in _BOOSTED_MODELS:
            w *= 1.5
        for x in b1: sb1[x] += w
        for x in b2: sb2[x] += w
    if not sb1 and not sb2:
        # Fallback: use all models with equal weight
        for b1, b2 in all_p:
            for x in b1: sb1[x] += 1.0
            for x in b2: sb2[x] += 1.0
    return b1b2_from_scores(sb1, sb2)


# ════════════════════════════════════════════════════════════════════════
#  HTML REPORT & CSV GENERATORS (for lottery_pipeline.py compatibility)
# ════════════════════════════════════════════════════════════════════════

def generate_html_report():
    """Generate HTML report v3.0 — per-draw per-model per-block position accuracy.

    Structure:
    1. Summary statistics
    2. Per-model per-block position accuracy tables (aggregated)
    3. Per-draw model hit detail (last 100 draws, shows which positions each model hit)
    4. LPD_DATA section: structured per-draw per-model position match data for pipeline
    Compatible with lottery_pipeline.py v3.0.
    """
    mrd = st.session_state.model_report_data
    if not mrd:
        return ""

    MODEL_NAMES = _get_model_names()
    total_draws = len(mrd)
    recent_count = min(200, total_draws)
    recent_start = total_draws - recent_count

    # ── Compute per-model per-block per-position accuracy ──────────────
    model_b1_stats = {}
    model_b2_stats = {}
    for mi in range(TOTAL_MODELS):
        model_b1_stats[mi] = {'pos1_hits': 0, 'pos2_hits': 0, 'pos3_hits': 0, 'pos4_hits': 0, 'total_hits': 0}
        model_b2_stats[mi] = {'pos1_hits': 0, 'pos2_hits': 0, 'pos3_hits': 0, 'pos4_hits': 0, 'total_hits': 0}

    # LPD_DATA: structured per-draw per-model position matches
    lpd_lines = []

    # Per-draw model hit data for visual display (last 100 draws)
    draw_model_data = []  # [{draw_no, draw_type, act_b1, act_b2, model_hits: {mi: {b1: [positions], b2: [positions]}}}]

    for idx, item in enumerate(mrd):
        preds = item['all_model_predictions']
        act_b1 = item['act_b1']
        act_b2 = item['act_b2']
        draw_no = item['draw_no']
        draw_type = item.get('draw_type', 'unknown')

        dmd = {'draw_no': draw_no, 'draw_type': draw_type,
               'act_b1': sorted(act_b1), 'act_b2': sorted(act_b2), 'model_hits': {}}

        for mi, (pb1, pb2) in enumerate(preds):
            if mi >= TOTAL_MODELS:
                break
            b1_positions = _compute_match_positions(pb1, act_b1)
            b2_positions = _compute_match_positions(pb2, act_b2)

            # Add to LPD structured data
            b1_pos_str = ','.join(map(str, b1_positions)) if b1_positions else ''
            b2_pos_str = ','.join(map(str, b2_positions)) if b2_positions else ''
            if b1_pos_str or b2_pos_str:
                lpd_lines.append(f'{draw_no}|{draw_type}|{mi}|b1|{b1_pos_str}')
                lpd_lines.append(f'{draw_no}|{draw_type}|{mi}|b2|{b2_pos_str}')

            # Aggregated stats
            for p in b1_positions:
                key = f'pos{p}_hits'
                if key in model_b1_stats[mi]:
                    model_b1_stats[mi][key] += 1
                model_b1_stats[mi]['total_hits'] += 1

            for p in b2_positions:
                key = f'pos{p}_hits'
                if key in model_b2_stats[mi]:
                    model_b2_stats[mi][key] += 1
                model_b2_stats[mi]['total_hits'] += 1

            # Visual data (only for models with hits)
            if b1_positions or b2_positions:
                dmd['model_hits'][mi] = {'b1': b1_positions, 'b2': b2_positions}

        if idx >= total_draws - 100:
            draw_model_data.append(dmd)

    # ── Summary statistics ──────────────────────────────────────────────
    total_hits_all = sum(s['total_hits'] for s in model_b1_stats.values()) + \
                    sum(s['total_hits'] for s in model_b2_stats.values())
    avg_per_draw = total_hits_all / max(total_draws * 2, 1)
    avg_per_model_b1 = np.mean([s['total_hits'] for s in model_b1_stats.values()]) if model_b1_stats else 0
    avg_per_model_b2 = np.mean([s['total_hits'] for s in model_b2_stats.values()]) if model_b2_stats else 0
    five_plus = sum(1 for d in draw_model_data
                    if sum(len(d['model_hits'].get(mi, {}).get('b1', [])) +
                           len(d['model_hits'].get(mi, {}).get('b2', []))
                           for mi in d['model_hits']) >= 5)

    best_b1 = {}
    best_b2 = {}
    for pos in range(1, 5):
        key = f'pos{pos}_hits'
        best_b1[pos] = max(model_b1_stats.items(), key=lambda x: x[1][key])
        best_b2[pos] = max(model_b2_stats.items(), key=lambda x: x[1][key])

    # ── Build HTML ──────────────────────────────────────────────────────
    html = []
    html.append('<!DOCTYPE html>')
    html.append('<html lang="ru"><head><meta charset="UTF-8">')
    html.append('<title>LP-v130 Report v3.0</title>')
    html.append('<style>')
    html.append('body{font-family:Arial,sans-serif;background:#0d1117;color:#e2e8f0;font-size:13px;margin:20px}')
    html.append('h1{color:#60a5fa}h2{color:#60a5fa;border-bottom:1px solid #1e2d4a;padding-bottom:6px}')
    html.append('table{border-collapse:collapse;width:100%;margin:12px 0}')
    html.append('th{background:#1e2d4a;padding:8px;text-align:left;color:#94a3b8;font-size:.8rem;position:sticky;top:0}')
    html.append('td{padding:6px 8px;border-bottom:1px solid #1e2d4a;font-size:.8rem}')
    html.append('.hit{color:#34d399;font-weight:700}.miss{color:#64748b}')
    html.append('.draw-detail{margin:8px 0;padding:10px;border:1px solid #1e2d4a;border-radius:6px;background:rgba(30,45,74,.15)}')
    html.append('.draw-no{font-weight:700;color:#60a5fa}.type-rng{color:#f59e0b}.type-std{color:#34d399}')
    html.append('.act-b1,.act-b2{font-weight:700;color:#e2e8f0}')
    html.append('.model-hit{color:#34d399;font-weight:700;font-size:.75rem}')
    html.append('.model-row td{font-size:.72rem}')
    html.append('.pos-tag{display:inline-block;background:rgba(52,211,153,.15);border:1px solid rgba(52,211,153,.3);border-radius:4px;padding:1px 6px;margin:1px;font-size:.7rem;color:#34d399}')
    html.append('</style></head><body>')
    html.append(f'<h1>LP-v130 Model Report v3.0</h1>')
    html.append(f'<p>Generated: {datetime.now().strftime("%d.%m.%Y %H:%M")} | '
                f'Draws analyzed: {total_draws} | Models: {TOTAL_MODELS} (v25.0)</p>')

    # ── 1. Summary table ───────────────────────────────────────────────
    html.append('<h2>Summary</h2><table>')
    for label, val in [
        ('Total Draws Analyzed', str(total_draws)),
        ('Total Position Hits (B1+B2)', str(total_hits_all)),
        ('Avg Hits per Block per Draw', f'{avg_per_draw:.2f}'),
        ('Avg Total Hits per Model (B1)', f'{avg_per_model_b1:.1f}'),
        ('Avg Total Hits per Model (B2)', f'{avg_per_model_b2:.1f}'),
        ('Draws with Best Model >=5 pos hits', str(five_plus)),
    ]:
        html.append(f'<tr><td>{label}</td><td>{val}</td></tr>')
    html.append('</table>')

    # ── 2. Best model per position ─────────────────────────────────────
    html.append('<h2>Best Model per Position</h2><table>')
    html.append('<tr><th>Block</th><th>Position</th><th>Model</th><th>Name</th><th>Hits</th></tr>')
    for pos in range(1, 5):
        mi_b1, s1 = best_b1[pos]
        html.append(f'<tr><td>B1</td><td>P{pos}</td><td>p{mi_b1+1}</td>'
                    f'<td>{MODEL_NAMES[mi_b1] if mi_b1 < len(MODEL_NAMES) else "p"+str(mi_b1+1)}</td>'
                    f'<td>{s1[f"pos{pos}_hits"]}</td></tr>')
    for pos in range(1, 5):
        mi_b2, s2 = best_b2[pos]
        html.append(f'<tr><td>B2</td><td>P{pos}</td><td>p{mi_b2+1}</td>'
                    f'<td>{MODEL_NAMES[mi_b2] if mi_b2 < len(MODEL_NAMES) else "p"+str(mi_b2+1)}</td>'
                    f'<td>{s2[f"pos{pos}_hits"]}</td></tr>')
    html.append('</table>')

    # ── 3. Per-model B1 accuracy table ─────────────────────────────────
    html.append('<h2>Per-Model Accuracy - Block 1 (B1)</h2><table>')
    html.append('<tr><th>Model</th><th>Name</th><th>P1</th><th>P2</th><th>P3</th><th>P4</th>'
                '<th>Total</th><th>Rate%</th></tr>')
    sorted_b1 = sorted(model_b1_stats.items(), key=lambda x: -x[1]['total_hits'])
    for mi, stats in sorted_b1:
        name = MODEL_NAMES[mi] if mi < len(MODEL_NAMES) else f'p{mi+1}'
        rate = (stats['total_hits'] / max(total_draws, 1)) * 100
        html.append(
            f'<tr data-model="p{mi+1}"><td>p{mi+1}</td><td>{name}</td>'
            f'<td>{stats["pos1_hits"]}</td><td>{stats["pos2_hits"]}</td>'
            f'<td>{stats["pos3_hits"]}</td><td>{stats["pos4_hits"]}</td>'
            f'<td>{stats["total_hits"]}</td><td>{rate:.1f}</td></tr>')
    html.append('</table>')

    # ── 4. Per-model B2 accuracy table ─────────────────────────────────
    html.append('<h2>Per-Model Accuracy - Block 2 (B2)</h2><table>')
    html.append('<tr><th>Model</th><th>Name</th><th>P1</th><th>P2</th><th>P3</th><th>P4</th>'
                '<th>Total</th><th>Rate%</th></tr>')
    sorted_b2 = sorted(model_b2_stats.items(), key=lambda x: -x[1]['total_hits'])
    for mi, stats in sorted_b2:
        name = MODEL_NAMES[mi] if mi < len(MODEL_NAMES) else f'p{mi+1}'
        rate = (stats['total_hits'] / max(total_draws, 1)) * 100
        html.append(
            f'<tr data-model="p{mi+1}"><td>p{mi+1}</td><td>{name}</td>'
            f'<td>{stats["pos1_hits"]}</td><td>{stats["pos2_hits"]}</td>'
            f'<td>{stats["pos3_hits"]}</td><td>{stats["pos4_hits"]}</td>'
            f'<td>{stats["total_hits"]}</td><td>{rate:.1f}</td></tr>')
    html.append('</table>')

    # ── 5. Per-draw model hit detail (last 100 draws) ──────────────────
    html.append('<h2>Per-Draw Model Position Hits (last 100 draws)</h2>')
    html.append('<p>For each draw: actual numbers and which models correctly predicted which '
                'sorted positions.</p>')
    for dmd in draw_model_data:
        draw_no = dmd['draw_no']
        draw_type = dmd['draw_type']
        act_b1 = dmd['act_b1']
        act_b2 = dmd['act_b2']
        model_hits = dmd['model_hits']

        html.append(f'<div class="draw-detail">')
        html.append(f'<span class="draw-no">#{draw_no}</span> '
                    f'<span class="type-{draw_type}">{draw_type}</span> '
                    f'B1: <span class="act-b1">{",".join(map(str, act_b1))}</span> '
                    f'B2: <span class="act-b2">{",".join(map(str, act_b2))}</span>')

        if model_hits:
            # Show models with hits, sorted by total hits descending
            sorted_models = sorted(model_hits.items(),
                                   key=lambda x: -(len(x[1]['b1']) + len(x[1]['b2'])),
                                   reverse=True)
            html.append(f'<div style="margin-top:4px;font-size:.75rem;color:#94a3b8">'
                        f'Models with hits ({len(sorted_models)}):</div>')
            # Show top 20 models for this draw
            for mi, hits in sorted_models[:20]:
                name = MODEL_NAMES[mi] if mi < len(MODEL_NAMES) else f'p{mi+1}'
                b1_tags = ''.join(f'<span class="pos-tag">B1-P{p}</span>' for p in hits['b1'])
                b2_tags = ''.join(f'<span class="pos-tag">B2-P{p}</span>' for p in hits['b2'])
                total_h = len(hits['b1']) + len(hits['b2'])
                html.append(f'<div class="model-row" style="margin:2px 0 2px 12px">'
                            f'<span style="color:#64748b">p{mi+1}</span> '
                            f'<span style="color:#94a3b8">{name}</span> '
                            f'{b1_tags}{b2_tags}'
                            f'<span style="color:#475569;margin-left:4px">({total_h})</span>'
                            f'</div>')
            if len(sorted_models) > 20:
                html.append(f'<div style="color:#475569;font-size:.7rem;margin-left:12px">'
                            f'...and {len(sorted_models)-20} more models</div>')
        else:
            html.append(f'<div style="color:#475569;font-size:.75rem">No model hits</div>')

        html.append('</div>')

    # ── 6. LPD_DATA section (structured data for lottery_pipeline.py) ──
    html.append('<!-- LPD_DATA v3.0 -->')
    html.append('<!-- Format: draw_no|draw_type|model_idx|block|positions -->')
    for line in lpd_lines:
        html.append(f'<!-- {line} -->')
    html.append('<!-- LPD_END -->')

    html.append('</body></html>')
    return '\n'.join(html)


def generate_model_predictions_csv():
    """Generate predictions.csv v2.0 — all model predictions for next draw.

    Format: Модель|Название|Б1_П1|Б1_П2|Б1_П3|Б1_П4|Б2_П1|Б2_П2|Б2_П3|Б2_П4
    Numbers are sorted within each block (П1=smallest, П4=largest).
    Compatible with lottery_pipeline.py v2.0 parse_predictions_csv().
    """
    all_preds = st.session_state.last_all_preds
    if not all_preds:
        return ""

    MODEL_NAMES = _get_model_names()
    output = io.StringIO()
    writer = csv.writer(output, delimiter='|', lineterminator='\n')

    # Header
    writer.writerow(['Модель', 'Название', 'Б1_П1', 'Б1_П2', 'Б1_П3', 'Б1_П4',
                     'Б2_П1', 'Б2_П2', 'Б2_П3', 'Б2_П4'])

    # Each model's prediction (sorted within block)
    for mi, (pb1, pb2) in enumerate(all_preds):
        model_id = f'p{mi+1}'
        name = MODEL_NAMES[mi] if mi < len(MODEL_NAMES) else model_id
        b1_sorted = sorted(pb1)
        b2_sorted = sorted(pb2)
        writer.writerow([model_id, name] + b1_sorted + b2_sorted)

    return output.getvalue()


def _get_model_names():
    """Return list of model names (133 entries). v14.0 — updated names for replaced models."""
    # G1 (p0-p19): 20 base models
    g1 = [
        'Frequency','EnhancedMarkov','EnhancedGap','Patterns','Neural',
        'MonteCarlo','Genetic','Balance','Deep','Fibonacci',
        'ModularPattern','Momentum','Z-Score','Entropy','Cyclic',
        'EnhancedEnsemble','Recency','NumberAffinity','RegrMean','EWMA',
    ]
    # G2 (p20-p31): 12 window variants
    g2 = [f'Window-{w}' for w in [5,10,15,20,30,50,70,100,150,200,300,500]]
    # G3 (p32-p44): 13 gap+freq hybrids
    g3 = [f'Gap+Freq-{b:.1f}' for b in [0.8,1.0,1.2,1.5,2.0,0.5,1.8,2.5,0.3,3.0,0.6,1.3,0.9]]
    # G4 (p45-p56): 12 EWMA alphas
    g4 = [f'EWMA-a{a}' for a in [0.05,0.10,0.20,0.25,0.30,0.35,0.40,0.50,0.60,0.08,0.12,0.18]]
    # G5 (p57-p69): 13 models (some replaced in v14.0)
    g5 = ['EnhDiff-5/15','EnhDiff-15/30','Z-30','Z-50','Z-80',
          'Bayesian-0.3','Bayesian-0.5','Bayesian-0.8',
          'StreakReversal','StreakReversal2','DrawType','FreqGapHybrid','PeriodDetect']
    # G6 (p70-p98): 29 models (some replaced in v14.0)
    g6_orig = [f'Ensemble-{i+1}' for i in range(29)]
    # Replace specific indices with new model names
    g6_names = list(g6_orig)  # copy
    g6_names[1]  = 'EnhDiff-30/50'      # was Ensemble-2
    g6_names[5]  = 'RecencyGap-100'     # was Ensemble-6
    g6_names[6]  = 'RecencyGap-200'     # was Ensemble-7
    g6_names[9]  = 'FreqGapHybrid-0.5'  # was Ensemble-10
    g6_names[12] = 'RecencyGap-50'      # was Ensemble-13
    g6_names[15] = 'HotColdBalance'      # was Ensemble-16
    g6_names[18] = 'AdaptWindow'         # was Ensemble-19
    g6_names[19] = 'AdaptWindow2'        # was Ensemble-20
    g6_names[21] = 'ConstrainedSum'      # was Ensemble-22
    g6_names[22] = 'ConstrainedSum-0.75' # was Ensemble-23
    g6_names[23] = 'HotColdBalance2'     # was Ensemble-24
    g6_names[24] = 'HotColdBalance3'     # was Ensemble-25
    g6_names[28] = 'StreakReversal3'     # was Ensemble-29
    # G7 (p99-p119): 21 unique models
    g7 = ['PosDrift','Window-25','AdaptiveZScore','Bayesian-0.2',
          'HotStreak-10','HotStreak-15','GapMomentum',
          'SumParity','RunLength','HighLow','Differential',
          'EnhancedMarkov2','EntropyWeighted',
          'MeanRevert-50','MeanRevert-100','MeanRevert-150',
          'LagCorrel','BlockSumTrend','SmartMonteCarlo',
          'AdaptiveZScore2','Bayesian-1.0']
    # G8 (p120-p132): 13 unique models
    g8 = ['AdaptEWMA','GapMomentum2','Cluster',
          'Pos-P0','Pos-P1','Pos-P2','Pos-P3',
          'Window-8','Window-12','Window-40','Window-250',
          'Bayesian-1.5','DrawTypeFreq']
    return g1 + g2 + g3 + g4 + g5 + g6_names + g7 + g8


# ════════════════════════════════════════════════════════════════════════
#  MAIN UI
# ════════════════════════════════════════════════════════════════════════

# ── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:16px 0 10px">
      <div style="font-size:2.2rem">🎲</div>
      <div style="font-size:1.3rem;font-weight:700;color:#60a5fa;font-family:'Rajdhani',sans-serif">LP-v130</div>
      <div style="font-size:.72rem;color:#64748b;margin-top:2px">133 моделей · Python v25.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # File upload
    uploaded = st.file_uploader("📂 Загрузить tirazh.txt", type=['txt'],
                                 help="Формат: DATE||NUM||n1,n2,...,n8")
    if uploaded:
        content = uploaded.read().decode('utf-8', errors='replace')
        content_hash = hashlib.md5(content.encode()).hexdigest()
        # Only parse if file changed (avoid duplicate log messages on widget rerun)
        if st.session_state._last_upload_hash != content_hash:
            st.session_state._last_upload_hash = content_hash
            draws = parse_text(content)
            if draws:
                st.session_state.draws_raw = draws
                st.success(f"✅ {len(draws):,} тиражей загружено")
                # v6.1: Data quality diagnostics
                quality = _check_data_quality(draws)
                if quality:
                    if quality['has_gaps']:
                        st.warning(
                            f"⚠ Обнаружены пробелы в нумерации: "
                            f"тиражи #{quality['min_no']}–#{quality['max_no']}, "
                            f"ожидается {quality['expected_count']:,}, "
                            f"загружено {quality['total_draws']:,}, "
                            f"отсутствует {quality['missing_count']:,} тиражей. "
                            f"Примеры отсутствующих: {quality['missing_sample'][:5]}"
                        )
                    with st.expander("📊 Диагностика данных", expanded=quality['has_gaps']):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Диапазон", f"#{quality['min_no']}–#{quality['max_no']}")
                        c2.metric("Тиражей", f"{quality['total_draws']:,}")
                        c3.metric("Пробелов", f"{quality['missing_count']:,}")
                        st.markdown("**Распределение по типам:**")
                        for dtype, cnt in sorted(quality['type_counts'].items()):
                            st.markdown(f"  • {dtype.upper()}: {cnt:,} тиражей")
                        if quality['top_times']:
                            st.markdown("**Топ-15 времён:**")
                            st.markdown(", ".join(f"{t} ({c})" for t, c in quality['top_times']))
            else:
                st.error("Ошибка парсинга файла")

    # Or paste data
    with st.expander("✏️ Вставить данные вручную"):
        raw_input = st.text_area("Данные (один тираж на строку):", height=120,
                                  placeholder="29.03.2026 23:22||13150||14,12,7,13,18,14,7,5")
        if st.button("📥 Загрузить вставленные", width="stretch"):
            draws = parse_text(raw_input)
            if draws:
                st.session_state.draws_raw = draws
                st.success(f"✅ {len(draws):,} тиражей")
            else:
                st.error("Нет корректных строк")

    st.divider()

    # Training params
    st.markdown("**⚙️ Параметры обучения**")
    seed_size  = st.slider("Seed (прогрев)", 50, 500, 100, 50)
    batch_step = st.selectbox("Размер пакета", [50, 100, 200, 500], index=1)
    full_every = st.slider("Полный ансамбль каждые N пакетов", 5, 50, 20, 5)

    st.divider()

    # Stats summary
    h = st.session_state.accuracy_history
    if h:
        totals = [e.total() for e in h]
        st.metric("Проверено тиражей", f"{len(h):,}")
        st.metric("Среднее попаданий", f"{np.mean(totals):.2f}/{PICK_B1+PICK_B2}")
        five_plus = sum(1 for t in totals if t >= PICK_B1)
        nh = max(len(h), 1)
        st.metric(f"Успехов >={PICK_B1}", f"{five_plus} ({five_plus/nh*100:.1f}%)")

    # v1.1: Show training time
    if st.session_state.training_time > 0:
        st.metric("Время обучения", format_elapsed(st.session_state.training_time))

    # Model report data count
    mrd = st.session_state.model_report_data
    if mrd:
        st.metric("Данных для LSTM", f"{len(mrd)} тиражей")


# ── Main content ─────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:14px;margin-bottom:2px">
  <h1 style="margin:0">LP-v130 · Lottery Predictor</h1>
  <span style="background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.4);
        border-radius:20px;padding:4px 14px;font-size:.8rem;color:#93c5fd;font-weight:700">
    133 моделей · Статистический анализ · Python v25.0
  </span>
</div>
<p style="color:#64748b;font-size:.88rem;margin-bottom:20px">
  Обучение --> Прогноз --> Проверка · Полный аналог LP-v130.html на Python/Streamlit
</p>
""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────
tab_train, tab_pred, tab_acc, tab_models, tab_verify, tab_export, tab_lstm = st.tabs([
    "🔮 Обучение", "🎯 Прогноз", "📊 Точность", "🤖 Модели", "✅ Проверка", "💾 Экспорт", "🧠 LSTM Pipeline"
])


# ════════════════════════════════════════════════════
# TAB 1 — TRAINING
# ════════════════════════════════════════════════════
with tab_train:
    section_header("🔮", "Обучение и генерация прогноза")

    draws_available = getattr(st.session_state, 'draws_raw', [])
    if not draws_available:
        st.info("Загрузите данные tirazh.txt через боковое меню")
    else:
        d0, d1 = draws_available[0], draws_available[-1]
        col1, col2, col3 = st.columns(3)
        col1.metric("Тиражей загружено", f"{len(draws_available):,}")
        col2.metric("Первый тираж", f"#{d0.draw_no}")
        col3.metric("Последний тираж", f"#{d1.draw_no}")

        st.markdown("")
        c1, c2 = st.columns(2)
        btn_train = c1.button("🔮 Обучить & Предсказать", width="stretch",
                               type="primary")
        btn_predict = c2.button("⚡ Только прогноз (быстро)", width="stretch")

        if btn_predict:
            timer_ph = st.empty()
            timer_ph.markdown("⏱ **00:00** | Генерация прогноза...")
            t0 = time.time()
            with st.spinner("Генерация прогноза..."):
                pred = LP132()
                pred.update(draws_available)
                b1, b2 = pred.consensus()
                st.session_state.last_pred = (b1, b2)
                st.session_state.predictor = pred
                st.session_state.last_all_preds = pred.all_predictions()
                st.session_state.trained = True
            elapsed = time.time() - t0
            timer_ph.markdown(f"⏱ **{format_elapsed(elapsed)}** | Прогноз готов")
            log("Быстрый прогноз без обучения выполнен", 'ok')

        if btn_train:
            progress = st.progress(0.0, "Инициализация...")
            timer_ph = st.empty()
            timer_ph.markdown("⏱ **00:00** | Подготовка...")
            status = st.empty()
            with st.spinner(""):
                try:
                    status.info(f"Обучение на {len(draws_available):,} тиражах...")
                    do_train(draws_available, seed_size, batch_step, full_every,
                             progress, timer_ph)
                    status.success("✅ Обучение завершено!")
                except Exception as ex:
                    status.error(f"❌ Ошибка: {ex}")
                    log(f"❌ {ex}", 'warn')

    # Log strip
    if st.session_state.log_lines:
        st.markdown("<div class='section-hdr'><span class='section-hdr-title'>📋 Лог</span></div>",
                    unsafe_allow_html=True)
        log_html = '<div class="log-strip">'
        for ts, kind, msg in reversed(st.session_state.log_lines[-30:]):
            log_html += f'<div class="log-{kind}">[{ts}] {msg}</div>'
        log_html += '</div>'
        st.markdown(log_html, unsafe_allow_html=True)

    # Submit actual draw
    if st.session_state.trained and st.session_state.last_pred:
        st.divider()
        section_header("✅", "Ввести фактический результат")
        st.info("**Рабочий процесс в реальном времени:** Эта секция принимает ТЕКУЩИЙ активный прогноз (после обучения), "
               "сравнивает его с вручную введённым фактическим результатом, обновляет веса BayesRing и генерирует НОВЫЙ прогноз. "
               "Используется для итеративного цикла: обучить → прогноз → ждать результат → ввести результат → повторить.\n\n"
               "Для ретроспективного анализа ('какой прогноз LP-v130 дал бы для тиража #13151?') используйте вкладку «✅ Проверка».")
        act_input = st.text_input("Формат: DATE||NUM||n1,n2,n3,n4,n5,n6,n7,n8",
                                   placeholder="30.03.2026 10:00||13151||2,18,13,14,5,10,8,19")
        if st.button("✅ Подтвердить и обновить", width="stretch"):
            actual = parse_line(act_input)
            if actual:
                pred_b1, pred_b2 = st.session_state.last_pred
                entry = AccuracyEntry(actual.draw_no, pred_b1, pred_b2,
                                       actual.block1, actual.block2,
                                       date=getattr(actual, 'date', ''))
                st.session_state.accuracy_history.insert(0, entry)

                # v1.1: Also store model report data for manual results
                # v1.5: Cap at MAX 1000 entries
                if st.session_state.last_all_preds:
                    st.session_state.model_report_data.append({
                        'draw_no': actual.draw_no,
                        'draw_type': getattr(actual, 'draw_type', 'unknown'),
                        'all_model_predictions': list(st.session_state.last_all_preds),
                        'act_b1': list(actual.block1),
                        'act_b2': list(actual.block2),
                    })
                    # v7.0: Increased cap to 3000 (was 1000)
                    if len(st.session_state.model_report_data) > 3000:
                        st.session_state.model_report_data = st.session_state.model_report_data[-3000:]
                    st.session_state.bayes.update(
                        st.session_state.last_all_preds, actual.block1, actual.block2,
                        draw_type=getattr(actual, 'draw_type', 'all'))

                # Add to draws and regenerate prediction
                st.session_state.draws.append(actual)
                st.session_state.predictor.update(st.session_state.draws)
                new_b1, new_b2 = st.session_state.predictor.consensus()
                st.session_state.last_pred = (new_b1, new_b2)
                t = entry.total()
                st.success(f"✅ Тираж #{actual.draw_no}: {t}/{PICK_B1+PICK_B2} попаданий "
                           f"(Б1={entry.hits_b1}/{PICK_B1}, Б2={entry.hits_b2}/{PICK_B2})")
                log(f"✅ #{actual.draw_no}: {t}/{PICK_B1+PICK_B2} (Б1={entry.hits_b1}, Б2={entry.hits_b2})", 'ok')
                st.rerun()
            else:
                st.error("Ошибка формата")


# ════════════════════════════════════════════════════
# TAB 2 — PREDICTION
# ════════════════════════════════════════════════════
with tab_pred:
    section_header("🎯", "Финальный прогноз")

    if not st.session_state.last_pred:
        st.info("Сначала выполните обучение во вкладке «Обучение»")
    else:
        b1, b2 = st.session_state.last_pred

        # Main prediction card
        st.markdown('<div class="pred-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="pred-label">ПРОГНОЗ СЛЕДУЮЩЕГО ТИРАЖА · {datetime.now().strftime("%d.%m.%Y")}</div>',
                    unsafe_allow_html=True)

        # ── Next draw info (v6.0) — uses draws_raw for correct numbering ──
        draws_raw = getattr(st.session_state, 'draws_raw', [])
        ndi = _compute_next_draw_info(draws_raw)
        if ndi:
            next_type_color = '#f59e0b' if ndi['next_type'] == 'RNG' else ('#34d399' if ndi['next_type'] == 'STD' else '#94a3b8')
            info_html = (
                f'<div style="display:flex;gap:20px;align-items:center;margin-bottom:14px;'
                f'padding:8px 12px;background:rgba(59,130,246,.08);border-radius:8px;'
                f'border:1px solid rgba(59,130,246,.15);flex-wrap:wrap">'
                f'<div style="font-size:.82rem"><span style="color:#94a3b8">Тираж:</span> '
                f'<span style="color:#60a5fa;font-weight:700">#{ndi["next_draw_no"]}</span></div>'
                f'<div style="font-size:.82rem"><span style="color:#94a3b8">Тип:</span> '
                f'<span style="color:{next_type_color};font-weight:700">{ndi["next_type"]}</span></div>'
                f'<div style="font-size:.82rem"><span style="color:#94a3b8">Ориентир. время:</span> '
                f'<span style="color:#e2e8f0;font-weight:700">{ndi["next_time"]}</span></div>'
                f'<div style="font-size:.82rem"><span style="color:#94a3b8">ГСЧ:</span> '
                f'<span style="color:#f59e0b;font-weight:700">{ndi["next_rng_time"] or "—"}</span></div>'
                f'<div style="font-size:.82rem"><span style="color:#94a3b8">STD:</span> '
                f'<span style="color:#34d399;font-weight:700">{ndi["next_std_time"] or "—"}</span></div>'
                f'</div>'
            )
            st.markdown(info_html, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="pred-label" style="color:#60a5fa">БЛОК 1</div>',
                        unsafe_allow_html=True)
            b1_html = ''.join(f'<div class="ball-b1">{x}</div>' for x in b1)
            st.markdown(f'<div style="display:flex;gap:8px">{b1_html}</div>',
                        unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="pred-label" style="color:#34d399">БЛОК 2</div>',
                        unsafe_allow_html=True)
            b2_html = ''.join(f'<div class="ball-b2">{x}</div>' for x in b2)
            st.markdown(f'<div style="display:flex;gap:8px">{b2_html}</div>',
                        unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Model agreement charts
        if st.session_state.last_all_preds:
            all_p = st.session_state.last_all_preds
            total = len(all_p)

            votes_b1 = Counter(x for pb1, _ in all_p for x in pb1)
            votes_b2 = Counter(x for _, pb2 in all_p for x in pb2)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Блок 1 -- согласие моделей**")
                nums_b1 = [x for x, _ in votes_b1.most_common(10)]
                cnts_b1 = [votes_b1[x] for x in nums_b1]
                colors_b1 = ['#d97706' if x in set(b1) else '#3b82f6' for x in nums_b1]
                fig1 = go.Figure(go.Bar(
                    x=[str(n) for n in nums_b1], y=cnts_b1,
                    marker_color=colors_b1,
                    text=[f'{c/total*100:.0f}%' for c in cnts_b1],
                    textposition='outside',
                ))
                fig1.update_layout(
                    height=260, margin=dict(l=0,r=0,t=10,b=0),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#e2e8f0', showlegend=False,
                    xaxis=dict(gridcolor='#1e2d4a'), yaxis=dict(gridcolor='#1e2d4a'),
                )
                st.plotly_chart(fig1, width="stretch")

            with col2:
                st.markdown("**Блок 2 -- согласие моделей**")
                nums_b2 = [x for x, _ in votes_b2.most_common(10)]
                cnts_b2 = [votes_b2[x] for x in nums_b2]
                colors_b2 = ['#d97706' if x in set(b2) else '#059669' for x in nums_b2]
                fig2 = go.Figure(go.Bar(
                    x=[str(n) for n in nums_b2], y=cnts_b2,
                    marker_color=colors_b2,
                    text=[f'{c/total*100:.0f}%' for c in cnts_b2],
                    textposition='outside',
                ))
                fig2.update_layout(
                    height=260, margin=dict(l=0,r=0,t=10,b=0),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font_color='#e2e8f0', showlegend=False,
                    xaxis=dict(gridcolor='#1e2d4a'), yaxis=dict(gridcolor='#1e2d4a'),
                )
                st.plotly_chart(fig2, width="stretch")

            # Consensus strength
            agree_b1 = votes_b1.most_common(1)[0][1]/max(total,1)*100
            agree_b2 = votes_b2.most_common(1)[0][1]/max(total,1)*100
            c1,c2,c3 = st.columns(3)
            c1.metric("Б1 согласие", f"{agree_b1:.1f}%")
            c2.metric("Б2 согласие", f"{agree_b2:.1f}%")
            strength = "✅ Высокий" if (agree_b1>40 or agree_b2>40) else ("⚠️ Слабый" if (agree_b1<15 or agree_b2<15) else "🆗 Средний")
            c3.metric("Консенсус", strength)

            # Monte Carlo confidence
            try:
                if st.session_state.predictor and st.session_state.draws:
                    mc = _monte_carlo_confidence(st.session_state.predictor)
                    if mc:
                        st.markdown("**🎲 Доверительный интервал (Monte Carlo):**")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Среднее", f"{mc['mean']:.2f}/{PICK_B1+PICK_B2}")
                        c2.metric("90% интервал", f"{mc['p5']:.1f} — {mc['p95']:.1f}")
                        c3.metric(f"P(>={PICK_B1})", f"{mc['p_ge5']*100:.1f}%")
            except Exception: pass

            # Heatmap
            st.markdown("**Тепловая карта -- вероятности чисел**")
            hm_data = [[votes_b1.get(n,0)/max(total,1)*100 for n in range(1,B1_MAX+1)],
                       [votes_b2.get(n,0)/max(total,1)*100 for n in range(1,B2_MAX+1)]]
            fig_hm = go.Figure(go.Heatmap(
                z=hm_data,
                x=[str(n) for n in range(1,B1_MAX+1)],
                y=['Блок 1','Блок 2'],
                colorscale='Blues',
                text=[[f'{v:.0f}%' for v in row] for row in hm_data],
                texttemplate='%{text}',
                showscale=True,
            ))
            fig_hm.update_layout(
                height=160, margin=dict(l=60,r=0,t=10,b=30),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e2e8f0',
            )
            st.plotly_chart(fig_hm, width="stretch")

        # ── Schedule Detection ──
        st.divider()
        section_header("📅", "Расписание тиражей")

        draws_raw = getattr(st.session_state, 'draws_raw', [])
        if draws_raw:
            # Analyze time distribution
            time_counts = Counter()
            rng_count = 0
            std_count = 0
            legacy_count = 0
            for d in draws_raw:
                time_counts[d.draw_hm] += 1
                if d.draw_type == 'rng':
                    rng_count += 1
                elif d.draw_type == 'std':
                    std_count += 1
                else:
                    legacy_count += 1

            schedule_info = (
                f"**Текущее расписание (с 17.12.2025):** 10 тиражей/день\n"
                f"• STD: 10:00, 13:00, 18:00, 22:00 ({std_count} тиражей)\n"
                f"• ГСЧ: 12:07, 13:52, 16:07, 16:22, 20:07, 23:22 ({rng_count} тиражей)\n"
                f"• Legacy: {legacy_count} тиражей"
            )
            st.markdown(schedule_info)

            # v6.0: Fixed — use draws_raw for correct draw numbering
            ndi = _compute_next_draw_info(draws_raw)
            if ndi:
                next_color = '#f59e0b' if ndi['next_type'] == 'RNG' else '#34d399'
                next_label = 'ГСЧ' if ndi['next_type'] == 'RNG' else 'STD'
                st.markdown(f"""
                <div style="background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.15);
                            border-radius:8px;padding:12px 16px;margin-top:8px">
                  <div style="font-size:.85rem">
                    <span style="color:#94a3b8">Следующий тираж:</span>
                    <span style="color:#60a5fa;font-weight:700">#{ndi['next_draw_no']}</span> в
                    <span style="color:{next_color};font-weight:700">{ndi['next_time']}</span>
                    (<span style="color:{next_color}">{next_label}</span>)
                  </div>
                  <div style="font-size:.85rem;margin-top:4px">
                    <span style="color:#94a3b8">Следующий ГСЧ:</span> 
                    <span style="color:#f59e0b;font-weight:700">{ndi['next_rng_time'] or '—'}</span>
                    <span style="color:#475569;margin:0 8px">|</span>
                    <span style="color:#94a3b8">Следующий STD:</span>
                    <span style="color:#34d399;font-weight:700">{ndi['next_std_time'] or '—'}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # ── RNG-Specific Prediction ──
                rng_time_display = ndi['next_rng_time'] if ndi else '—'
                if rng_time_display:
                    st.divider()
                    section_header("🎰", f"Прогноз для ГСЧ тиража ({rng_time_display})")

                    # Train on RNG draws only
                    rng_draws = [d for d in draws_raw if d.draw_type == 'rng']
                    if len(rng_draws) >= 50:
                        rng_predictor = LP132()
                        rng_predictor.update(rng_draws)
                        rng_b1, rng_b2 = rng_predictor.consensus()

                        st.markdown(f'<div class="pred-card">', unsafe_allow_html=True)
                        st.markdown(
                            f'<div class="pred-label">ПРОГНОЗ ГСЧ · {rng_time_display} · '
                            f'Обучено на {len(rng_draws)} ГСЧ-тиражах</div>',
                            unsafe_allow_html=True
                        )

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown('<div class="pred-label" style="color:#f59e0b">БЛОК 1 (ГСЧ)</div>',
                                        unsafe_allow_html=True)
                            b1_html = ''.join(f'<div class="ball-b1" style="background:linear-gradient(135deg,#d97706,#b45309);box-shadow:0 4px 12px rgba(217,119,6,.5);border-color:rgba(251,191,36,.4)">{x}</div>' for x in rng_b1)
                            st.markdown(f'<div style="display:flex;gap:8px">{b1_html}</div>',
                                        unsafe_allow_html=True)
                        with col2:
                            st.markdown('<div class="pred-label" style="color:#f59e0b">БЛОК 2 (ГСЧ)</div>',
                                        unsafe_allow_html=True)
                            b2_html = ''.join(f'<div class="ball-b2" style="background:linear-gradient(135deg,#d97706,#b45309);box-shadow:0 4px 12px rgba(217,119,6,.5);border-color:rgba(251,191,36,.4)">{x}</div>' for x in rng_b2)
                            st.markdown(f'<div style="display:flex;gap:8px">{b2_html}</div>',
                                        unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                        # RNG model agreement
                        rng_all = rng_predictor.all_predictions()
                        rng_total = len(rng_all)
                        rng_votes_b1 = Counter(x for pb1, _ in rng_all for x in pb1)
                        rng_votes_b2 = Counter(x for _, pb2 in rng_all for x in pb2)

                        rng_agree_b1 = rng_votes_b1.most_common(1)[0][1]/max(rng_total,1)*100
                        rng_agree_b2 = rng_votes_b2.most_common(1)[0][1]/max(rng_total,1)*100
                        c1, c2 = st.columns(2)
                        c1.metric("ГСЧ Б1 согласие", f"{rng_agree_b1:.1f}%")
                        c2.metric("ГСЧ Б2 согласие", f"{rng_agree_b2:.1f}%")
                    else:
                        st.warning(f"Недостаточно ГСЧ-тиражей для обучения ({len(rng_draws)} из мин. 50). "
                                  "ГСЧ-тиражи появились с 15.10.2025.")

                # ── STD-Specific Prediction (v6.1) ──
                std_time_display = ndi['next_std_time'] if ndi else '—'
                if std_time_display:
                    st.divider()
                    section_header("📋", f"Прогноз для STD тиража ({std_time_display})")

                    # Train on STD draws only
                    std_draws = [d for d in draws_raw if d.draw_type == 'std']
                    if len(std_draws) >= 50:
                        std_predictor = LP132()
                        std_predictor.update(std_draws)
                        std_b1, std_b2 = std_predictor.consensus()

                        st.markdown(f'<div class="pred-card">', unsafe_allow_html=True)
                        st.markdown(
                            f'<div class="pred-label">ПРОГНОЗ STD · {std_time_display} · '
                            f'Обучено на {len(std_draws)} STD-тиражах</div>',
                            unsafe_allow_html=True
                        )

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown('<div class="pred-label" style="color:#34d399">БЛОК 1 (STD)</div>',
                                        unsafe_allow_html=True)
                            b1_html = ''.join(f'<div class="ball-b1" style="background:linear-gradient(135deg,#059669,#047857);box-shadow:0 4px 12px rgba(5,150,105,.5);border-color:rgba(52,211,153,.4)">{x}</div>' for x in std_b1)
                            st.markdown(f'<div style="display:flex;gap:8px">{b1_html}</div>',
                                        unsafe_allow_html=True)
                        with col2:
                            st.markdown('<div class="pred-label" style="color:#34d399">БЛОК 2 (STD)</div>',
                                        unsafe_allow_html=True)
                            b2_html = ''.join(f'<div class="ball-b2" style="background:linear-gradient(135deg,#059669,#047857);box-shadow:0 4px 12px rgba(5,150,105,.5);border-color:rgba(52,211,153,.4)">{x}</div>' for x in std_b2)
                            st.markdown(f'<div style="display:flex;gap:8px">{b2_html}</div>',
                                        unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)

                        # STD model agreement
                        std_all = std_predictor.all_predictions()
                        std_total = len(std_all)
                        std_votes_b1 = Counter(x for pb1, _ in std_all for x in pb1)
                        std_votes_b2 = Counter(x for _, pb2 in std_all for x in pb2)

                        std_agree_b1 = std_votes_b1.most_common(1)[0][1]/max(std_total,1)*100
                        std_agree_b2 = std_votes_b2.most_common(1)[0][1]/max(std_total,1)*100
                        c1, c2 = st.columns(2)
                        c1.metric("STD Б1 согласие", f"{std_agree_b1:.1f}%")
                        c2.metric("STD Б2 согласие", f"{std_agree_b2:.1f}%")
                    else:
                        st.warning(f"Недостаточно STD-тиражей для обучения ({len(std_draws)} из мин. 50).")


# ════════════════════════════════════════════════════
# TAB 3 — ACCURACY
# ════════════════════════════════════════════════════
with tab_acc:
    section_header("📊", "История точности")

    h = st.session_state.accuracy_history
    if not h:
        st.info("История пуста. Выполните обучение или введите фактические результаты.")
    else:
        totals = [e.total() for e in h]
        n = len(h)

        # Stats row
        col1,col2,col3,col4,col5,col6 = st.columns(6)
        col1.metric("Проверок",   f"{n:,}")
        col2.metric("Среднее",    f"{np.mean(totals):.2f}/{PICK_B1+PICK_B2}")
        col3.metric("Лучший",     f"{max(totals)}/{PICK_B1+PICK_B2}")
        col4.metric(f">={PICK_B1} попад",   f"{sum(1 for t in totals if t>=PICK_B1)} ({sum(1 for t in totals if t>=PICK_B1)/max(n,1)*100:.1f}%)")
        col5.metric(">=6 попад",   f"{sum(1 for t in totals if t>=6)}")
        col6.metric(f"{PICK_B1+PICK_B2}/{PICK_B1+PICK_B2} идеал",  f"{sum(1 for t in totals if t==PICK_B1+PICK_B2)}")

        # v6.0: Random baseline comparison
        # For random prediction: E[hits per block] = 4*(4/20) = 0.8, total = 1.6
        # P(>=5 hits) ~ 0.5% for random
        random_ge5_pct = 0.5  # approximate theoretical P(>=5) for random
        actual_ge5 = sum(1 for t in totals if t>=5)
        actual_ge5_pct = actual_ge5/max(n,1)*100
        baseline_ratio = actual_ge5_pct / random_ge5_pct if random_ge5_pct > 0 else 0
        st.markdown(f'<div style="font-size:.75rem;color:#64748b;margin-top:4px">'
                   f'📊 Случайная базовая линия: ~1.6/8 среднее, ~0.5% ≥5 попаданий | '
                   f'Текущий результат: {"выше" if baseline_ratio > 1 else "ниже"} случайного в {baseline_ratio:.1f}x</div>',
                   unsafe_allow_html=True)

        # Cross-validation results
        if hasattr(st.session_state, 'cv_results') and st.session_state.cv_results:
            cv = st.session_state.cv_results
            st.markdown("**📊 k-fold перекрёстная валидация:**")
            cv_df = pd.DataFrame(cv)
            st.markdown(cv_df.to_html(index=False, escape=False), unsafe_allow_html=True)
            avg_cv = sum(r['avg_hits'] for r in cv) / len(cv)
            st.metric("CV среднее", f"{avg_cv:.2f}/{PICK_B1+PICK_B2}")

        # v7.0: Draw-type accuracy breakdown (STD vs RNG)
        draws_raw = getattr(st.session_state, 'draws_raw', [])
        draw_type_map = {}
        if draws_raw:
            for d in draws_raw:
                draw_type_map[d.draw_no] = d.draw_type
        
        std_entries = [e for e in h if draw_type_map.get(e.draw_no) == 'std']
        rng_entries = [e for e in h if draw_type_map.get(e.draw_no) == 'rng']
        
        if std_entries or rng_entries:
            st.markdown("**Разбивка по типу тиража:**")
            c_std, c_rng, c_unk = st.columns(3)
            if std_entries:
                std_totals = [e.total() for e in std_entries]
                std_ge5 = sum(1 for t in std_totals if t >= 5)
                c_std.metric("STD тиражи", 
                             f"{len(std_entries):,} | ≥5: {std_ge5} ({std_ge5/max(len(std_entries),1)*100:.1f}%) | "
                             f"Сред: {np.mean(std_totals):.2f}/{PICK_B1+PICK_B2}",
                             help="Точность на стандартных тиражах")
            else:
                c_std.metric("STD тиражи", "Нет данных")
            if rng_entries:
                rng_totals = [e.total() for e in rng_entries]
                rng_ge5 = sum(1 for t in rng_totals if t >= 5)
                c_rng.metric("RNG (ГСЧ) тиражи",
                             f"{len(rng_entries):,} | ≥5: {rng_ge5} ({rng_ge5/max(len(rng_entries),1)*100:.1f}%) | "
                             f"Сред: {np.mean(rng_totals):.2f}/{PICK_B1+PICK_B2}",
                             help="Точность на ГСЧ-тиражах")
            else:
                c_rng.metric("RNG (ГСЧ) тиражи", "Нет данных")
            unk_entries = n - len(std_entries) - len(rng_entries)
            c_unk.metric("Другие/неизвестные", f"{unk_entries:,}")

        # Trend chart
        st.markdown("**Тренд попаданий**")
        window = min(200, n)
        recent = h[:window]
        fig_trend = go.Figure()
        draw_nos = [e.draw_no for e in reversed(recent)]
        hit_vals  = [e.total() for e in reversed(recent)]
        fig_trend.add_trace(go.Scatter(
            x=draw_nos, y=hit_vals,
            mode='lines+markers', name='Попаданий',
            line=dict(color='#3b82f6', width=1.5),
            marker=dict(size=3, color=['#d97706' if v>=PICK_B1 else '#3b82f6' for v in hit_vals]),
        ))
        fig_trend.add_hline(y=1.6, line_dash='dash', line_color='#64748b',
                             annotation_text='Базовая линия (случайно=1.6)')
        fig_trend.add_hline(y=PICK_B1, line_dash='dot', line_color='#34d399',
                             annotation_text=f'Успех (>={PICK_B1})')
        fig_trend.update_layout(
            height=280, margin=dict(l=0,r=0,t=10,b=0),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color='#e2e8f0', showlegend=False,
            xaxis=dict(gridcolor='#1e2d4a'), yaxis=dict(gridcolor='#1e2d4a',range=[0,8.5]),
        )
        st.plotly_chart(fig_trend, width="stretch")

        # Distribution
        st.markdown("**Распределение попаданий**")
        dist = Counter(totals)
        dist_x = list(range(9))
        dist_y = [dist.get(i,0) for i in dist_x]
        colors_dist = ['#d97706' if i>=PICK_B1 else '#3b82f6' for i in dist_x]
        fig_dist = go.Figure(go.Bar(
            x=dist_x, y=dist_y, marker_color=colors_dist,
            text=dist_y, textposition='outside',
        ))
        fig_dist.update_layout(
            height=220, margin=dict(l=0,r=0,t=10,b=0),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color='#e2e8f0',
            xaxis=dict(title='Попаданий', gridcolor='#1e2d4a'),
            yaxis=dict(title='Тиражей',   gridcolor='#1e2d4a'),
        )
        st.plotly_chart(fig_dist, width="stretch")

        # View selector: how many entries to show
        view_count_label = st.selectbox(
            "Показать:", [100, 200, 500, 0],
            format_func=lambda x: f'Последние {x}' if x > 0 else 'Все записи',
            key='acc_view_count'
        )

        # Filter by minimum hits
        c_filt, c_view = st.columns([1, 2])
        with c_filt:
            filter_min = st.selectbox("Мин. попаданий:", [0,3,4,5,6,7,8],
                                       format_func=lambda x: 'Все' if x==0 else f'>= {x}',
                                       key='acc_filter_min')

        # Sort by draw_no descending (most recent first), apply filters
        sorted_h = sorted(h, key=lambda e: e.draw_no, reverse=True)
        filtered = [e for e in sorted_h if e.total() >= filter_min]

        # Limit to view count (0 = all)
        if view_count_label > 0:
            show_only = filtered[:view_count_label]
        else:
            show_only = filtered

        st.markdown(f"Показано {len(show_only)} из {len(filtered)} записей (всего: {n})")

        # Render accuracy rows
        acc_html = ''
        for e in show_only:
            t = e.total()
            score_cls = 'score-5' if t>=PICK_B1 else ('score-4' if t>=4 else ('score-3' if t>=3 else 'score-low'))

            # Show date if available
            date_str = f' <span style="color:#475569;font-size:.68rem">{e.date}</span>' if e.date else ''

            b1_balls = ''.join(
                f'<div class="acc-ball {"ab-hit" if x in set(e.act_b1) else "ab-miss"}">{x}</div>'
                for x in e.pred_b1)
            b2_balls = ''.join(
                f'<div class="acc-ball {"ab-hit" if x in set(e.act_b2) else "ab-miss"}">{x}</div>'
                for x in e.pred_b2)
            ab1 = ''.join(f'<div class="acc-ball ab-act">{x}</div>' for x in e.act_b1)
            ab2 = ''.join(f'<div class="acc-ball ab-act">{x}</div>' for x in e.act_b2)

            acc_html += f'''
            <div class="acc-row">
              <div class="acc-draw-no">#{e.draw_no}{date_str}</div>
              <div class="acc-balls" title="Прогноз Б1">{b1_balls}</div>
              <div style="color:#334155;font-size:.7rem">|</div>
              <div class="acc-balls" title="Прогноз Б2">{b2_balls}</div>
              <div style="color:#334155;font-size:.7rem;margin:0 4px">-&gt;</div>
              <div class="acc-balls" title="Факт Б1">{ab1}</div>
              <div style="color:#334155;font-size:.7rem">|</div>
              <div class="acc-balls" title="Факт Б2">{ab2}</div>
              <div class="acc-score {score_cls}">{t}/{PICK_B1+PICK_B2}</div>
            </div>'''

        st.markdown(acc_html, unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# TAB 4 — MODELS
# ════════════════════════════════════════════════════
with tab_models:
    section_header("🤖", f"Анализ {TOTAL_MODELS} моделей")

    MODEL_NAMES = [
        'Частота','Марков','Gap (Интервалы)','Паттерны','Нейронная сеть',
        'Монте-Карло','Генетика','Баланс блоков','Глубокое обуч.','Фибоначчи',
        'Простые числа','Импульс','Z-Score','Энтропия','Цикличность',
        'Ансамбль','Recency','Попарные корр.','Регр. к среднему','EWMA',
    ] + [f'Window-{w}' for w in [5,10,15,20,30,50,70,100,150,200,300,500]] \
      + [f'Gap+Freq-{b:.1f}' for b in [0.8,1.0,1.2,1.5,2.0,0.5,1.8,2.5,0.3,3.0,0.6,1.3,0.9]] \
      + [f'EWMA-a{a}' for a in [0.05,0.10,0.20,0.25,0.30,0.35,0.40,0.50,0.60,0.08,0.12,0.18]] \
      + ['Velocity-10/20','Velocity-5/15','Z-30','Z-50','Z-80',
         'Bayesian-0.3','Bayesian-0.5','Bayesian-0.8',
         'Streak-30','Streak-50','DrawType','CrossBlockGap','Fourier'] \
      + [f'Ensemble-{i+1}' for i in range(29)] \
      + ['PosDrift','Window-25','Z-100','Bayesian-0.2',
         'HotStreak-10','HotStreak-15','GapAccel',
         'SumParity','ConsecPairs','HighLow','Differential',
         'TripleMarkov','EntropyWeighted',
         'MeanRevert-50','MeanRevert-100','MeanRevert-150',
         'LagCorrel','BlockSumTrend','MonteBayes',
         'RecencyZ-150','Bayesian-1.0'] \
      + ['AdaptEWMA','GapBurst','Cluster',
         'Pos-P0','Pos-P1','Pos-P2','Pos-P3',
         'Window-8','Window-12','Window-40','Window-250',
         'Bayesian-1.5','DrawTypeFreq']

    if not st.session_state.last_all_preds:
        st.info("Сначала выполните обучение")
    else:
        all_p = st.session_state.last_all_preds
        total = len(all_p)

        # Build model agreement table
        if st.session_state.last_pred:
            final_b1, final_b2 = st.session_state.last_pred
        else:
            final_b1, final_b2 = [], []

        rows = []
        for i, (b1, b2) in enumerate(all_p):
            name = MODEL_NAMES[i] if i < len(MODEL_NAMES) else f'p{i+1}'
            agree_b1 = len(set(b1) & set(final_b1))
            agree_b2 = len(set(b2) & set(final_b2))
            rows.append({
                '#': i+1,
                'Название': name,
                'Б1 прогноз': ' '.join(map(str, b1)),
                'Б2 прогноз': ' '.join(map(str, b2)),
                'Совп. Б1': agree_b1,
                'Совп. Б2': agree_b2,
                'Итого': agree_b1 + agree_b2,
            })

        df = pd.DataFrame(rows)
        df_sorted = df.sort_values('Итого', ascending=False)

        # v1.2: Color-code agreement levels via HTML table (no jinja2 needed)
        def _render_models_html(dataframe, max_height=300):
            """Render models dataframe as styled HTML table with color-coded agreement."""
            cols = list(dataframe.columns)
            html = '<div style="max-height:%dpx;overflow-y:auto;border:1px solid #1e2d4a;border-radius:8px;">' % max_height
            html += '<table style="width:100%;border-collapse:collapse;font-size:.8rem;color:#e2e8f0;">'
            # Header
            html += '<thead><tr style="background:rgba(30,58,110,.35);position:sticky;top:0;">'
            for c in cols:
                html += f'<th style="padding:8px 10px;text-align:left;border-bottom:1px solid #1e2d4a;white-space:nowrap;">{c}</th>'
            html += '</tr></thead><tbody>'
            # Rows
            for idx, row in dataframe.iterrows():
                bg = 'rgba(255,255,255,.02)' if idx % 2 == 0 else 'transparent'
                html += f'<tr style="background:{bg};">'
                for c in cols:
                    val = row[c]
                    if c in ('Совп. Б1', 'Совп. Б2'):
                        if val >= 2:
                            cls = 'color:#34d399;font-weight:700;'
                        elif val >= 1:
                            cls = 'color:#fbbf24;font-weight:700;'
                        else:
                            cls = 'color:#64748b;'
                        html += f'<td style="padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.04);{cls}">{val}</td>'
                    else:
                        html += f'<td style="padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.04);white-space:nowrap;">{val}</td>'
                html += '</tr>'
            html += '</tbody></table></div>'
            return html

        # Top models with agreement color coding
        st.markdown("**Топ-10 моделей по совпадению с итоговым прогнозом**")
        top10 = df_sorted.head(10).reset_index(drop=True)
        st.markdown(_render_models_html(top10, max_height=300), unsafe_allow_html=True)

        # Search
        search = st.text_input("🔍 Поиск по названию модели:")
        if search:
            filtered = df[df['Название'].str.contains(search, case=False)]
        else:
            filtered = df

        st.markdown(f"**Все {len(filtered)} моделей**")
        st.markdown(_render_models_html(filtered, max_height=400), unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# TAB 5 — VERIFY
# ════════════════════════════════════════════════════
with tab_verify:
    section_header("✅", "Проверка конкретного тиража")

    st.info("**Ретроспективный анализ:** Введите тираж для проверки. Система ПЕРЕОБУЧАЕТСЯ с нуля, "
               "используя ТОЛЬКО тиражи ДО указанного номера, генерирует прогноз и сравнивает его с фактом. "
               "Используется для анализа: 'какой прогноз LP-v130 дал бы для тиража #13151?'\n\n"
               "Для рабочего процесса в реальном времени (обучить → прогноз → ввести результат) используйте вкладку «🔮 Обучение».")

    st.markdown("""
    Введите тираж который хотите проверить.
    Система покажет какой прогноз давал LP-v130 **до** этого тиража.
    """)

    verify_input = st.text_input(
        "Тираж для проверки:",
        value="30.03.2026 10:00||13151||2,18,13,14,5,10,8,19",
        help="Формат: DATE||NUM||b1a,b1b,b1c,b1d,b2a,b2b,b2c,b2d"
    )

    draws_raw = getattr(st.session_state, 'draws_raw', [])
    if st.button("🔍 Проверить", type="primary"):
        actual = parse_line(verify_input)
        if not actual:
            st.error("Ошибка формата тиража")
        elif not draws_raw:
            st.error("Сначала загрузите данные")
        else:
            timer_ph = st.empty()
            timer_ph.markdown("⏱ **00:00** | Проверка...")
            t0 = time.time()
            train_draws = [d for d in draws_raw if d.draw_no < actual.draw_no]
            if not train_draws:
                st.error(f"Нет данных до тиража #{actual.draw_no}")
            else:
                with st.spinner(f"Прогнозирование для #{actual.draw_no}..."):
                    pred = LP132()
                    pred.update(train_draws)
                    b1, b2 = pred.consensus()
                elapsed = time.time() - t0

                hits_b1 = len(set(b1) & set(actual.block1))
                hits_b2 = len(set(b2) & set(actual.block2))
                total   = hits_b1 + hits_b2

                timer_ph.markdown(
                    f"⏱ **{format_elapsed(elapsed)}** | "
                    f"Тираж #{actual.draw_no}: {total}/{PICK_B1+PICK_B2} попаданий"
                )

                # Results card
                st.markdown(f"""
                <div class="pred-card">
                  <div class="pred-label">РЕЗУЛЬТАТ ПРОВЕРКИ · ТИРАЖ #{actual.draw_no} · {actual.date}</div>
                </div>""", unsafe_allow_html=True)

                col1, col2, col3 = st.columns(3)
                col1.metric("Попаданий Б1", f"{hits_b1}/{PICK_B1}")
                col2.metric("Попаданий Б2", f"{hits_b2}/{PICK_B2}")
                col3.metric("Итого", f"{total}/{PICK_B1+PICK_B2}",
                            delta="✅ Успех!" if total >= PICK_B1 else None)

                st.markdown("**Прогноз LP-v130 (до тиража):**")
                render_balls(b1, b2, set(actual.block1), set(actual.block2))

                st.markdown("**Фактический результат:**")
                act_b1_html = ''.join(
                    f'<div class="ball-b1{"" if x not in set(b1) else " ball-hit"}">{x}</div>'
                    for x in actual.block1)
                act_b2_html = ''.join(
                    f'<div class="ball-b2{"" if x not in set(b2) else " ball-hit"}">{x}</div>'
                    for x in actual.block2)
                st.markdown(
                    f'<div style="display:flex;gap:8px">{act_b1_html}</div>'
                    f'<div style="display:flex;gap:8px;margin-top:8px">{act_b2_html}</div>',
                    unsafe_allow_html=True)

                st.markdown(f"""
                **Обучено на:** {len(train_draws):,} тиражей (#{train_draws[0].draw_no}--#{train_draws[-1].draw_no})
                **Базовая линия (случайно):** ~1.6/{PICK_B1+PICK_B2}
                **Результат:** {'🎉 Выше среднего!' if total > 2 else ('📊 В пределах нормы' if total >= 2 else '📉 Ниже среднего')}
                """)


# ════════════════════════════════════════════════════
# TAB 6 — EXPORT
# ════════════════════════════════════════════════════
with tab_export:
    section_header("💾", "Экспорт данных (v3.0)")

    st.markdown("""
    **Два файла для lottery_pipeline.py v3.0:**
    1. **report.html** — пер-модельная точность + per-draw позиционные данные
    2. **predictions.csv** — предсказания всех моделей для следующего тиража

    Скачайте оба файла и запустите:
    ```
    python lottery_pipeline.py --html report.html --csv predictions.csv
    python lottery_pipeline.py --html report.html --csv predictions.csv --type std
    python lottery_pipeline.py --html report.html --csv predictions.csv --type rng
    ```
    """)

    mrd = st.session_state.model_report_data
    has_preds = bool(st.session_state.last_all_preds)

    if not mrd and not has_preds:
        st.warning("⚠️ Сначала выполните обучение для генерации файлов.")
    else:
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**📊 report.html**")
            st.caption("Пер-модельная точность по блокам Б1 и Б2, позициям П1-П4")
            if mrd:
                html_report = generate_html_report()
                if html_report:
                    st.success(f"✅ {len(mrd)} тиражей обработано")
                    st.download_button(
                        "⬇️ Скачать report.html",
                        html_report.encode('utf-8'),
                        f"report_{datetime.now().strftime('%Y-%m-%d_%H%M')}.html",
                        "text/html",
                        width="stretch",
                        type="primary",
                    )
                else:
                    st.error("Ошибка генерации HTML")
            else:
                st.info("Нет данных. Выполните обучение.")

        with c2:
            st.markdown("**📋 predictions.csv**")
            st.caption("Предсказания всех моделей для следующего тиража (Б1_П1-П4, Б2_П1-П4)")
            if has_preds:
                csv_data = generate_model_predictions_csv()
                if csv_data:
                    st.success(f"✅ {TOTAL_MODELS} моделей")
                    st.download_button(
                        "⬇️ Скачать predictions.csv",
                        csv_data.encode('utf-8-sig'),
                        f"predictions_{datetime.now().strftime('%Y-%m-%d_%H%M')}.csv",
                        "text/csv",
                        width="stretch",
                        type="primary",
                    )
            else:
                st.info("Нет прогнозов. Выполните обучение.")

    # Additional exports
    st.divider()
    section_header("📥", "Дополнительные экспорты")

    # Accuracy history CSV
    h = st.session_state.accuracy_history
    if h:
        st.markdown("**📈 История точности CSV**")
        n_acc_exp = st.selectbox("Записей:", [100, 200, 500, 1000], index=2, key='acc_exp')
        if st.button("📈 Экспорт истории точности", width="stretch"):
            entries = h[:min(n_acc_exp, len(h))]
            out = io.StringIO()
            w = csv.writer(out)
            w.writerow(['Тираж','Пред_Б1','Пред_Б2','Факт_Б1','Факт_Б2','Б1','Б2','Итого','Успех'])
            for e in entries:
                t = e.total()
                w.writerow([e.draw_no,
                            ','.join(map(str,e.pred_b1)),
                            ','.join(map(str,e.pred_b2)),
                            ','.join(map(str,e.act_b1)),
                            ','.join(map(str,e.act_b2)),
                            e.hits_b1, e.hits_b2, t,
                            '✓' if t>=5 else ''])
            st.download_button(
                "⬇️ Скачать историю",
                out.getvalue().encode('utf-8-sig'),
                f"accuracy_{datetime.now().strftime('%Y-%m-%d')}.csv",
                "text/csv",
            )
    else:
        st.info("История пуста.")

    # Current prediction text
    if st.session_state.last_pred:
        st.divider()
        st.markdown("**🎯 Текущий прогноз**")
        b1, b2 = st.session_state.last_pred
        pred_text = (f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                     f"Блок 1: {', '.join(map(str, b1))}\n"
                     f"Блок 2: {', '.join(map(str, b2))}\n")
        st.code(pred_text)
        st.download_button("⬇️ Скачать прогноз TXT",
                           pred_text.encode('utf-8'),
                           f"prediction_{datetime.now().strftime('%Y-%m-%d')}.txt",
                           "text/plain")


# ════════════════════════════════════════════════════
# TAB 7 — LSTM PIPELINE
# ════════════════════════════════════════════════════
with tab_lstm:
    section_header("🧠", "lottery_pipeline.py v3.0")

    st.markdown("""
    ### Инструкция по использованию lottery_pipeline.py v3.0

    **Recency-Weighted Position-Specific Ensemble:**

    1. **Скачайте report.html и predictions.csv** из вкладки «Экспорт»
    2. **Запустите анализ:**
       ```bash
       python lottery_pipeline.py --html report.html --csv predictions.csv
       python lottery_pipeline.py --html report.html --csv predictions.csv --type std
       python lottery_pipeline.py --html report.html --csv predictions.csv --type rng
       ```
    3. Pipeline v3.0 проанализирует:
       - Per-draw per-model position match data (LPD_DATA)
       - Recency-weighted model accuracy (recent draws weighted more)
       - Draw-type awareness (STD vs RNG)
       - Для каждого блока (Б1, Б2) и позиции (П1-П4):
         взвешенное голосование лучших моделей

    **Совместимость:** Файлы report.html и predictions.csv из этой программы
    полностью совместимы с lottery_pipeline.py v3.0.
    """)

    # Import and run pipeline if available
    try:
        upload_dir = os.path.dirname(os.path.abspath(__file__))
        pipeline_path = os.path.join(upload_dir, 'lottery_pipeline.py')
        if os.path.exists(pipeline_path):
            st.success(f"✅ lottery_pipeline.py найден: {pipeline_path}")

            if mrd and has_preds:
                st.markdown("**Запуск прямо из приложения:**")
                if st.button("🧠 Запустить pipeline", type="primary", width="stretch"):
                    with st.spinner("Анализ моделей..."):
                        import tempfile
                        html_report = generate_html_report()
                        csv_data = generate_model_predictions_csv()

                        if html_report and csv_data:
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f_html:
                                f_html.write(html_report)
                                html_path = f_html.name
                            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f_csv:
                                f_csv.write(csv_data)
                                csv_path = f_csv.name

                            try:
                                from lottery_pipeline import analyze_and_predict
                                result = analyze_and_predict(html_path, csv_path)

                                if result.get('error'):
                                    st.error(f"Ошибка: {result['error']}")
                                else:
                                    fb1 = result['final_b1']
                                    fb2 = result['final_b2']
                                    st.success("✅ Pipeline выполнен!")

                                    st.markdown('<div class="pred-card">', unsafe_allow_html=True)
                                    st.markdown('<div class="pred-label">PIPELINE ФИНАЛЬНЫЙ ПРОГНОЗ</div>',
                                                unsafe_allow_html=True)

                                    pc1, pc2 = st.columns(2)
                                    with pc1:
                                        st.markdown('<div class="pred-label" style="color:#c084fc">БЛОК 1</div>',
                                                    unsafe_allow_html=True)
                                        b1h = ''.join(f'<div class="ball-b1" style="background:linear-gradient(135deg,#7c3aed,#6d28d9);box-shadow:0 4px 12px rgba(124,58,237,.5);border-color:rgba(167,139,250,.4)">{x}</div>' for x in (fb1 or []))
                                        st.markdown(f'<div style="display:flex;gap:8px">{b1h}</div>',
                                                    unsafe_allow_html=True)
                                    with pc2:
                                        st.markdown('<div class="pred-label" style="color:#c084fc">БЛОК 2</div>',
                                                    unsafe_allow_html=True)
                                        b2h = ''.join(f'<div class="ball-b2" style="background:linear-gradient(135deg,#7c3aed,#6d28d9);box-shadow:0 4px 12px rgba(124,58,237,.5);border-color:rgba(167,139,250,.4)">{x}</div>' for x in (fb2 or []))
                                        st.markdown(f'<div style="display:flex;gap:8px">{b2h}</div>',
                                                    unsafe_allow_html=True)
                                    st.markdown('</div>', unsafe_allow_html=True)

                                    # Show position details
                                    details = result.get('position_details', {})
                                    if details:
                                        st.markdown("**Детали по позициям:**")
                                        for block_name, block_label in [('b1', 'Блок 1'), ('b2', 'Блок 2')]:
                                            bd = details.get(block_name, {})
                                            if bd:
                                                cols = st.columns(4)
                                                for i, (pos_name, pos_data) in enumerate(bd.items()):
                                                    with cols[i]:
                                                        sel = pos_data.get('selected', '?')
                                                        st.metric(f"{block_label} {pos_name}", str(sel))
                            except Exception as ex:
                                st.error(f"Ошибка импорта: {ex}")

                            os.unlink(html_path)
                            os.unlink(csv_path)
                        else:
                            st.error("Не удалось создать временные файлы")
            else:
                st.info("Сначала скачайте report.html и predictions.csv из вкладки «Экспорт»")
        else:
            st.warning("lottery_pipeline.py не найден рядом с lp_v130_app.py")
    except Exception as ex:
        st.info("Поместите lottery_pipeline.py рядом с lp_v130_app.py")
