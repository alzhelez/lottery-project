#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LP132 Prediction Engine CLI  (v39.4.0-ml — 14-feature meta-learner with accuracy-weighted consensus)

Runs the full prediction pipeline: parse draws → train 133 models (107 active with meta-learner stacking) →
generate prediction via numpy-based stacking meta-learner with 14 features:
  F1: score_vectors, F2: freq_100, F3: freq_20, F4: overdue, F5: pagerank,
  F6: last_draw_hot, F7: pair_cooccurrence (P1-6), F8: autoregressive (P2-12),
  F9: entropy, F10: ngram, F11: clustering, F12: streak,
  F13: positional_stability, F14: volatility
Outputs comprehensive JSON with prediction, accuracy, cross-validation, and Monte Carlo data.

Usage:
    python3 predict.py --file /tmp/draws_4x20.txt
    python3 predict.py --file /tmp/draws_4x20.txt --seed-size 100 --batch-step 100

Output (JSON to stdout):
    {
      "status": "ok",
      "game_format": {...},
      "data_quality": {...},
      "next_draw": {...},
      "training": {...},
      "prediction": {...},
      "meta_learner": {...},
      "accuracy": {...},
      "cross_validation": {...},
      "monte_carlo": {...},
      "model_report_data_file": "/tmp/model_report_4x20.json",
      "pipeline_data_file": "/tmp/pipeline_data_4x20.json"
    }

Also saves:
    /tmp/model_report_{game}.json — model report data for pipeline
    /tmp/pipeline_data_{game}.json — pipeline analysis data
"""

import sys
import os
import json
import time
import math
import argparse
import signal
from datetime import datetime
from collections import defaultdict, Counter

# ═══════════════════════════════════════════════════════════════════════════
#  MOCK STREAMLIT MODULE (must be done BEFORE importing lp_v130_app)
# ═══════════════════════════════════════════════════════════════════════════
from _streamlit_mock import st_mock  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
#  NOW IMPORT FROM lp_v130_app
# ═══════════════════════════════════════════════════════════════════════════

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)
# Fallback: look for lp_v130_app in upload/ only if NOT found in python/
_lp_in_python = os.path.exists(os.path.join(_SCRIPT_DIR, 'lp_v130_app.py'))
if not _lp_in_python:
    _upload_dir = os.path.join(_PROJECT_ROOT, 'upload')
    if os.path.isdir(_upload_dir) and os.path.exists(os.path.join(_upload_dir, 'lp_v130_app.py')):
        sys.path.insert(0, _upload_dir)

# Suppress TF warnings
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')

from lp_v130_app import (
    parse_text, LP132, DualBayesRing, Draw, AccuracyEntry,
    TOTAL_MODELS, PICK_B1, PICK_B2, B1_MAX, B2_MAX,
    GAME_FORMAT_HINTS,
    _compute_next_draw_info, _check_data_quality,
    _cross_validate, _monte_carlo_confidence,
    _get_model_names, _compute_match_positions,
    _fast_pred, _weighted_consensus,
    generate_html_report, generate_model_predictions_csv,
    FreqCache,
    _DISABLED_MODELS, _BOOSTED_MODELS, _LOW_DATA_THRESHOLD,
)

import numpy as np
import requests as _requests
import tempfile

# Отключаем системный прокси для прямого доступа к stoloto.ru
for _pv in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
    os.environ.pop(_pv, None)


# ═══════════════════════════════════════════════════════════════════════════
#  A6: Top-5 model cache (pre-load from previous run)
# ═══════════════════════════════════════════════════════════════════════════

_TOP5_CACHE_TTL = 24 * 60 * 60  # 24 hours in seconds


def _save_top5_cache(game_key, top5_data):
    """A6: Save top-5 model cache to /tmp/ for next run pre-loading.

    Args:
        game_key: normalized game key (e.g. '4x20')
        top5_data: list of dicts with {id, name, avg_hits} from model_ranking
    """
    try:
        cache = {
            'game': game_key,
            'top5': [
                {'id': m['model_id'], 'name': m['name'], 'avg_hits': m['avg_hits']}
                for m in top5_data
            ],
            'timestamp': time.time(),
        }
        cache_path = os.path.join(tempfile.gettempdir(), f'lp_top5_models_{game_key}.json')
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
        print(f'[INFO] Saved top-5 model cache for {game_key}', file=sys.stderr)
    except Exception as e:
        print(f'[WARN] Failed to save top-5 cache: {e}', file=sys.stderr)


def _load_top5_cache(game_key):
    """A6: Load top-5 model cache from previous run.

    Returns list of model IDs (int) if cache exists and is fresh (<24h), else None.
    """
    try:
        cache_path = os.path.join(tempfile.gettempdir(), f'lp_top5_models_{game_key}.json')
        if not os.path.exists(cache_path):
            return None
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        # Check age
        age = time.time() - cache.get('timestamp', 0)
        if age > _TOP5_CACHE_TTL:
            return None
        top5 = cache.get('top5', [])
        if not top5:
            return None
        model_ids = [m['id'] for m in top5]
        names = [m['name'] for m in top5]
        print(f'[INFO] Pre-loaded top-5 models from previous run: {names}', file=sys.stderr)
        return model_ids
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  A7: Cross-game correlation analysis
# ═══════════════════════════════════════════════════════════════════════════


def build_cross_game_analysis(game_key, b1_max, b2_max, data_dir):
    """A7: Analyze number frequency across OTHER games sharing number pools.

    Scans draw files for other games in data_dir, reads last 50 draws per game,
    counts how many times each number in the current game's range appears across
    all other games. Numbers appearing >1.2x expected frequency are flagged as
    "cross_game_hot".

    Args:
        game_key: current game key (e.g. '4x20')
        b1_max: current game's block1 max number
        b2_max: current game's block2 max number
        data_dir: directory containing draws_*.txt files

    Returns dict with:
        hot_numbers: list of int numbers that are cross-game hot
        source_games: list of game keys that were scanned
        method: description string
        number_stats: per-number frequency data for block1
    """
    result = {
        'hot_numbers': [],
        'source_games': [],
        'method': 'cross-game frequency',
        'number_stats': [],
    }

    if not os.path.isdir(data_dir):
        return result

    try:
        # Collect number counts across all OTHER games
        cross_counts = defaultdict(int)  # number -> total appearances
        total_numbers_drawn = 0
        source_games = []

        # Scan all draw files in data_dir
        for fname in os.listdir(data_dir):
            if not fname.startswith('draws_') or not fname.endswith('.txt'):
                continue
            # Extract game key from filename
            other_game = fname.replace('draws_', '').replace('.txt', '')
            if other_game == game_key:
                continue  # Skip the current game

            fpath = os.path.join(data_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    lines = [l.strip() for l in f if l.strip()]
            except Exception:
                continue

            if not lines:
                continue

            # Take last 50 draws
            recent_lines = lines[-50:]
            parsed_count = 0

            for line in recent_lines:
                parts = line.split('||')
                if len(parts) < 3:
                    continue
                try:
                    # Handle 3-part (DATE||NUM||ALL) and 4-part (DATE||NUM||B1||B2) formats
                    if len(parts) == 4:
                        # 4-part format: block1 in parts[2], block2 in parts[3]
                        b1_str = parts[2].strip()
                        b2_str = parts[3].strip()
                    else:
                        # 3-part format: all numbers in parts[2]
                        b1_str = parts[2].strip()
                        b2_str = ''

                    if not b1_str:
                        continue

                    nums = [int(x.strip()) for x in b1_str.split(',') if x.strip()]
                    for n in nums:
                        # Only count numbers within current game's block1 range
                        if 1 <= n <= b1_max:
                            cross_counts[n] += 1
                    total_numbers_drawn += len([n for n in nums if 1 <= n <= b1_max])

                    # Also count block2 numbers for 4-part format
                    if b2_str:
                        nums_b2 = [int(x.strip()) for x in b2_str.split(',') if x.strip()]
                        for n in nums_b2:
                            if 1 <= n <= b2_max:
                                cross_counts[n] += 1
                            elif 1 <= n <= b1_max:
                                # Numbers in b1 range also counted (overlap allowed)
                                cross_counts[n] += 1
                        total_numbers_drawn += len(nums_b2)
                    parsed_count += 1
                except (ValueError, IndexError):
                    continue

            if parsed_count > 0:
                source_games.append(other_game)

        if not source_games or total_numbers_drawn == 0:
            return result

        # Compute expected frequency per number
        expected_freq = total_numbers_drawn / b1_max
        threshold = expected_freq * 1.2

        # Build stats and identify hot numbers
        hot_numbers = []
        number_stats = []
        for num in range(1, b1_max + 1):
            count = cross_counts.get(num, 0)
            is_hot = count > threshold
            entry = {
                'number': num,
                'cross_count': count,
                'expected': round(expected_freq, 1),
                'ratio': round(count / max(expected_freq, 0.1), 2),
                'hot': is_hot,
            }
            number_stats.append(entry)
            if is_hot:
                hot_numbers.append(num)

        # Sort by cross_count descending
        number_stats.sort(key=lambda x: -x['cross_count'])

        result['hot_numbers'] = sorted(hot_numbers)
        result['source_games'] = sorted(source_games)
        result['number_stats'] = number_stats

        print(
            f'[INFO] Cross-game analysis: scanned {len(source_games)} games, '
            f'found {len(hot_numbers)} hot numbers',
            file=sys.stderr,
        )

    except Exception as e:
        print(f'[WARN] Cross-game analysis failed: {e}', file=sys.stderr)

    return result


def _compute_baseline_random(b1_max, b2_max, pick_b1, pick_b2):
    """Expected random hits: E[hits] = pick_b1^2/b1_max + pick_b2^2/b2_max."""
    return (pick_b1 ** 2 / b1_max) + (pick_b2 ** 2 / b2_max)


def _compute_time_weights(n_draws, half_life=500):
    """A5: Compute exponential decay time weights for draw recency.

    Most recent draw (index n_draws-1) gets weight 1.0.
    Older draws decay: weight_i = 0.5^(age / half_life)
    half_life=500 means a draw from 500 draws ago has half the influence.

    Returns list of length n_draws, index 0 = oldest, index n-1 = newest.
    """
    if n_draws <= 0:
        return []
    weights = []
    for i in range(n_draws):
        age = n_draws - 1 - i  # 0 for newest, n-1 for oldest
        w = 0.5 ** (age / max(half_life, 1))
        weights.append(w)
    return weights


def run_training(draws, seed_size=100, batch_step=50, full_every=10, priority_models=None):
    """Training pipeline adapted from do_train() — no Streamlit dependency.

    Args:
        draws: list of Draw objects
        seed_size: initial training seed
        batch_step: draws per batch
        full_every: full ensemble every N batches
        priority_models: optional list of model IDs (A6) to log as priority hints
    """
    t_start = time.time()

    # A6: Log priority models if provided
    if priority_models:
        model_names = _get_model_names()
        names = [model_names[i] if i < len(model_names) else f'Model-{i+1}' for i in priority_models]
        print(f'[INFO] Priority models (top-5 from cache): {names}', file=sys.stderr)

    sorted_draws = sorted(draws, key=lambda d: d.draw_no)
    n_total = len(sorted_draws)
    seed_size = min(seed_size, n_total)
    seed = sorted_draws[:seed_size]
    remaining = sorted_draws[seed_size:]

    # Initialize
    predictor = LP132()
    bayes = DualBayesRing()
    model_report_data = []
    accuracy_history = []

    # Seed phase
    current_draws = list(seed)
    predictor.update(current_draws)
    all_p = predictor.all_predictions()
    last_pred = predictor.consensus()

    n_batches = math.ceil(len(remaining) / batch_step) if remaining else 0

    # Training loop
    for batch_idx in range(n_batches):
        bs = batch_idx * batch_step
        be = min(bs + batch_step, len(remaining))
        batch = remaining[bs:be]

        for draw in batch:
            # Track accuracy BEFORE adding draw
            if last_pred is not None and all_p is not None:
                entry = AccuracyEntry(
                    draw.draw_no,
                    last_pred[0], last_pred[1],
                    draw.block1, draw.block2,
                    date=getattr(draw, 'date', '')
                )
                accuracy_history.append(entry)

                # Store model report data
                model_report_data.append({
                    'draw_no': draw.draw_no,
                    'draw_type': getattr(draw, 'draw_type', 'unknown'),
                    'all_model_predictions': list(all_p),
                    'act_b1': list(draw.block1),
                    'act_b2': list(draw.block2),
                })
                if len(model_report_data) > 3000:
                    model_report_data = model_report_data[-3000:]

                # Bayes update
                bayes.update(
                    all_p, draw.block1, draw.block2,
                    draw_type=getattr(draw, 'draw_type', 'all')
                )

            current_draws.append(draw)
            predictor.update(current_draws)

            # Fast per-draw prediction (v39.3.1: skip in god-mode for speed)
            try:
                if not args.god_mode:
                    ep = _fast_pred(predictor, bayes, draw_type=getattr(draw, 'draw_type', 'all'))
                    last_pred = ep
            except Exception:
                pass

        # Full ensemble every N batches
        is_last = (batch_idx == n_batches - 1)
        # NOTE: all_p is refreshed every batch so model_report_data stores
        # reasonably fresh predictions. Previously all_p was only updated every
        # full_every batches, causing stale predictions in model_report_data
        # entries between full-ensemble refreshes.
        predictor._c.clear()
        all_p = predictor.all_predictions()

        if not is_last and batch_idx % full_every == 0:
            # Full ensemble with weighted consensus using Bayes weights.
            # v25.1: Fall back to simple majority vote when training data is
            # too small for reliable BayesRing weight estimation.
            last_batch_draw_type = getattr(batch[-1], 'draw_type', 'all') if batch else 'all'
            n_draws_so_far = len(current_draws)
            if n_draws_so_far < _LOW_DATA_THRESHOLD:
                # Simple majority vote (equal weight) — disabled models already
                # excluded by all_predictions() returning empty preds for them.
                last_pred = predictor.consensus()
            else:
                w1, w2 = bayes.weights(last_batch_draw_type)
                combined = np.sqrt(w1 * w2)
                last_pred = _weighted_consensus(predictor, combined)

    # Final full ensemble
    predictor._c.clear()
    final_p = predictor.all_predictions()
    last_draw_type = getattr(remaining[-1], 'draw_type', 'all') if remaining else 'all'
    # v25.1: Low-data fallback — use simple majority vote when total draws
    # are below threshold, avoiding unreliable BayesRing weights.
    n_total_draws = len(draws)
    if n_total_draws < _LOW_DATA_THRESHOLD:
        last_pred = predictor.consensus()
    else:
        w1, w2 = bayes.weights(last_draw_type)
        combined = np.sqrt(w1 * w2)
        last_pred = _weighted_consensus(predictor, combined)

    elapsed = time.time() - t_start

    return {
        'predictor': predictor,
        'bayes': bayes,
        'last_pred': last_pred,
        'final_p': final_p,
        'accuracy_history': accuracy_history,
        'model_report_data': model_report_data,
        'training_time': elapsed,
        'seed_size': seed_size,
        'total_trained': len(current_draws) - seed_size,
    }


def compute_accuracy_stats(accuracy_history, last_n_list=None):
    """Compute average hits for last N draws."""
    if last_n_list is None:
        last_n_list = [50, 100, 200]
    stats = {}
    for n in last_n_list:
        if len(accuracy_history) >= n:
            recent = accuracy_history[-n:]
            avg = sum(e.total() for e in recent) / len(recent)
            stats[f'last_{n}_avg'] = round(avg, 3)
        else:
            stats[f'last_{n}_avg'] = None
    return stats


# v26.0: In-memory cache for game schedule results
_game_schedule_cache: dict = {}


def _fetch_game_schedule(game_key):
    """v26.0: Fetch game schedule info from stoloto.ru rules page.

    Uses in-memory cache (_game_schedule_cache) to avoid repeated requests.
    Falls back to "unknown" for games without a /rules page.

    Returns dict with:
        - next_estimated: approximate next draw datetime string
        - draw_type: "rng"|"stand"|"unknown"
        - draw_type_label: Russian description
        - is_predictable: True if RNG, False if TV stand
    """
    default = {"draw_type": "unknown", "is_predictable": True, "draw_type_label": "Не удалось определить", "next_estimated": None}
    # Check cache first
    if game_key in _game_schedule_cache:
        return _game_schedule_cache[game_key]
    try:
        r = _requests.get(
            f"https://www.stoloto.ru/{game_key}/rules",
            headers={"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "accept": "text/html"},
            timeout=5,
        )
        if r.status_code != 200:
            # Fallback for games without /rules page
            _game_schedule_cache[game_key] = default
            return default
        text = r.text.lower()
        # Detect redirect (e.g. klava → 5x36plus)
        if game_key not in r.url:
            _game_schedule_cache[game_key] = default
            return default
        draw_type = "unknown"
        draw_type_label = "Не удалось определить"
        # Check for RNG/ГСЧ indicators
        rng_indicators = ['генератор', 'гсч', 'случайных чисел', 'random number generator']
        stand_indicators = ['стенд', 'телевизионный', 'телевизион', 'студия', 'эфир']
        rng_hits = sum(1 for kw in rng_indicators if kw in text)
        stand_hits = sum(1 for kw in stand_indicators if kw in text)
        if rng_hits > stand_hits:
            draw_type = "rng"
            draw_type_label = "Генератор случайных чисел (ГСЧ)"
        elif stand_hits > 0:
            draw_type = "stand"
            draw_type_label = "Телевизионный стенд"
        else:
            draw_type_label = "Не удалось определить тип розыгрыша"
        # Try to extract schedule patterns
        import re as _re
        next_estimated = None
        time_patterns = _re.findall(r'(\d{1,2})\s*[:\.]\s*\d{2}', text)
        day_patterns = _re.findall(r'(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье|ежедневно|каждый день)', text)
        if day_patterns and time_patterns:
            next_estimated = f"{' '.join(day_patterns[:2])}, {' '.join(time_patterns[:3])}"
        elif time_patterns:
            next_estimated = f"Время розыгрышей: {' '.join(time_patterns[:4])}"
        is_predictable = (draw_type != "stand")
        result = {
            "next_estimated": next_estimated,
            "draw_type": draw_type,
            "draw_type_label": draw_type_label,
            "is_predictable": is_predictable,
        }
        _game_schedule_cache[game_key] = result
        return result
    except Exception:
        _game_schedule_cache[game_key] = default
        return default


def build_frequency_analysis(draws, b1_max, b2_max, time_weights=None):
    """v25.0: Build frequency analysis for each number across all draws.

    A5: When time_weights is provided, uses weighted counts so recent draws
    contribute more. Also returns a 'weighted_count' field per entry.

    Returns dict with block1 and block2 frequency data sorted by count descending.
    Each entry: {number, count, last_seen, weighted_count} where last_seen=0 means most recent draw.
    """
    if not draws:
        return {"block1": [], "block2": []}
    b1_counts = defaultdict(int)
    b2_counts = defaultdict(int)
    b1_weighted = defaultdict(float)
    b2_weighted = defaultdict(float)
    b1_last_seen = {}  # number -> draws ago (0 = most recent)
    b2_last_seen = {}
    total = len(draws)
    use_weights = time_weights is not None and len(time_weights) == total
    for i in range(total - 1, -1, -1):
        d = draws[i]
        draws_ago = total - 1 - i
        w = time_weights[i] if use_weights else 1.0
        for x in d.block1:
            if x not in b1_last_seen:
                b1_last_seen[x] = draws_ago
            b1_counts[x] += 1
            b1_weighted[x] += w
        for x in d.block2:
            if x not in b2_last_seen:
                b2_last_seen[x] = draws_ago
            b2_counts[x] += 1
            b2_weighted[x] += w
    block1 = []
    for num in range(1, b1_max + 1):
        if b1_counts[num] > 0:
            block1.append({
                "number": num,
                "count": b1_counts[num],
                "weighted_count": round(b1_weighted[num], 2),
                "last_seen": b1_last_seen.get(num, total),
            })
    block1.sort(key=lambda x: -x["weighted_count"] if use_weights else -x["count"])
    block2 = []
    for num in range(1, b2_max + 1):
        if b2_counts[num] > 0:
            block2.append({
                "number": num,
                "count": b2_counts[num],
                "weighted_count": round(b2_weighted[num], 2),
                "last_seen": b2_last_seen.get(num, total),
            })
    block2.sort(key=lambda x: -x["weighted_count"] if use_weights else -x["count"])
    return {"block1": block1, "block2": block2}


def build_pair_analysis(draws, b1_max, pick_count=10):
    """Analyze co-occurrence of number pairs in block1 draws.
    
    Returns top N most frequent pairs: [{pair: [n1, n2], count, last_seen}, ...]
    Only analyzes block1 numbers for efficiency.
    """
    if not draws or len(draws) < 10:
        return {"pairs": [], "total_draws": len(draws) if draws else 0}
    
    pair_counts = defaultdict(int)
    pair_last_seen = {}
    total = len(draws)
    
    for i, d in enumerate(draws):
        draws_ago = total - 1 - i
        nums = sorted(d.block1)
        # Generate all 2-combinations
        for a_idx in range(len(nums)):
            for b_idx in range(a_idx + 1, len(nums)):
                pair = (nums[a_idx], nums[b_idx])
                pair_counts[pair] += 1
                if pair not in pair_last_seen:
                    pair_last_seen[pair] = draws_ago
    
    # Sort by count descending, take top N
    sorted_pairs = sorted(pair_counts.items(), key=lambda x: -x[1])[:pick_count]
    result = []
    for pair, count in sorted_pairs:
        result.append({
            "pair": list(pair),
            "count": count,
            "last_seen": pair_last_seen.get(pair, total),
        })
    
    return {"pairs": result, "total_draws": total}


def build_gap_analysis(draws, b1_max, b2_max, time_weights=None):
    """Analyze gap/overdue for each number — how many draws since last appearance.
    
    A5: When time_weights provided, adjusts overdue_score with recency weighting.
    Recent gaps matter more: a gap of 20 in the last 50 draws is more significant
    than a gap of 20 from 2000 draws ago.
    
    Enhanced version of frequency analysis focusing on recency.
    Returns block1 and block2 data sorted by overdue_score (most overdue first).
    Each entry: {number, gap, avg_gap, frequency, overdue_score, recency_score}
    overdue_score: higher = more overdue than average (unweighted)
    recency_score: A5 recency-adjusted overdue score (weighted by time decay)
    """
    if not draws:
        return {"block1": [], "block2": []}
    
    total = len(draws)
    b1_appearances = defaultdict(list)  # number -> [draw_indices]
    b2_appearances = defaultdict(list)
    
    for i, d in enumerate(draws):
        for x in d.block1:
            b1_appearances[x].append(i)
        for x in d.block2:
            b2_appearances[x].append(i)
    
    use_weights = time_weights is not None and len(time_weights) == total
    
    def _analyze_block(appearances, max_num, total_draws):
        result = []
        for num in range(1, max_num + 1):
            indices = appearances.get(num, [])
            if not indices:
                result.append({
                    "number": num, "gap": total_draws, "avg_gap": None,
                    "frequency": 0, "overdue_score": 0.0, "recency_score": 0.0,
                })
                continue
            
            gap = total_draws - 1 - indices[-1]
            
            # Calculate average gap between appearances
            gaps = []
            for j in range(1, len(indices)):
                gaps.append(indices[j] - indices[j - 1])
            if gaps:
                avg_gap = round(sum(gaps) / len(gaps), 1)
            else:
                avg_gap = None
            
            freq = len(indices) / total_draws
            
            # Overdue score: how many average-gaps overdue is this number?
            overdue_score = 0.0
            if avg_gap and avg_gap > 0:
                overdue_score = round(max(0, gap / avg_gap - 1), 2)
            
            # A5: Recency score — weighted overdue incorporating time decay
            recency_score = 0.0
            if use_weights and avg_gap and avg_gap > 0:
                # Weight the current gap by recency: recent draws have higher weight
                # The gap starts from the most recent draw, so its recency weight = 1.0
                # Scale by the average recency weight of past appearances
                if len(indices) >= 2:
                    past_recency_avg = sum(time_weights[idx] for idx in indices[:-1]) / len(indices[:-1])
                    recency_weight_ratio = 1.0 / max(past_recency_avg, 0.01)
                    # A number whose past appearances were in low-weight (old) territory
                    # gets a higher recency_score (more "surprising" absence)
                    recency_score = round(overdue_score * min(recency_weight_ratio, 5.0), 2)
                else:
                    recency_score = round(overdue_score, 2)
            elif use_weights:
                recency_score = round(overdue_score, 2)
            
            result.append({
                "number": num,
                "gap": gap,
                "avg_gap": avg_gap,
                "frequency": round(freq, 4),
                "overdue_score": overdue_score,
                "recency_score": recency_score,
            })
        
        # Sort by recency_score if available, otherwise by overdue_score
        if use_weights:
            result.sort(key=lambda x: -x["recency_score"])
        else:
            result.sort(key=lambda x: -x["overdue_score"])
        return result
    
    return {
        "block1": _analyze_block(b1_appearances, b1_max, total),
        "block2": _analyze_block(b2_appearances, b2_max, total),
    }


def build_sum_range_stats(draws, pick_b1, pick_b2, b1_max, b2_max):
    """Analyze historical sum and range distributions of draws.
    
    Returns statistics for block1 and block2:
      - sum_mean, sum_std: average and std of number sums
      - range_mean, range_std: average and std of (max-min) ranges
      - sum_p5, sum_p95: 5th and 95th percentile of sums
    """
    if not draws:
        return {}
    
    b1_sums = []
    b1_ranges = []
    b2_sums = []
    
    for d in draws:
        if d.block1:
            s = sum(d.block1)
            b1_sums.append(s)
            b1_ranges.append(max(d.block1) - min(d.block1))
        if d.block2:
            b2_sums.append(sum(d.block2))
    
    def _stats(values):
        if not values:
            return {}
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = variance ** 0.5
        sorted_v = sorted(values)
        p5 = sorted_v[max(0, int(n * 0.05))]
        p95 = sorted_v[min(n - 1, int(n * 0.95))]
        return {
            "mean": round(mean, 1),
            "std": round(std, 1),
            "p5": p5,
            "p95": p95,
            "min": min(values),
            "max": max(values),
            "count": n,
        }
    
    result = {"block1": _stats(b1_sums), "block2": _stats(b2_sums)}
    if b1_ranges:
        result["block1"]["range_mean"] = round(sum(b1_ranges) / len(b1_ranges), 1)
        b1_mean = sum(b1_ranges) / len(b1_ranges)
        result["block1"]["range_std"] = round(
            (sum((r - b1_mean) ** 2 for r in b1_ranges) / len(b1_ranges)) ** 0.5, 1
        )
    return result


def build_backtest_heatmap(accuracy_history, final_p, max_draws=30, model_report_data=None, model_names=None):
    """Build heatmap data for backtest visualization.

    v26.0: Optimized best_model calculation — precomputes per-model hit totals
    instead of iterating all models for every draw (O(draws * models) → O(draws * models)
    with vectorized set operations).

    Returns:
        heatmap: list of {draw_no, pred_b1, pred_b2, act_b1, act_b2, hits_b1, hits_b2, total, date, best_model}
    """
    if not accuracy_history or not final_p:
        return []

    # Heatmap: last N draws
    heatmap_data = []
    recent = accuracy_history[-max_draws:]

    # v26.0: Build lookup and precompute best model using set intersection
    if model_report_data and model_names:
        _mrd_by_draw = {}
        for item in model_report_data:
            _mrd_by_draw[item.get('draw_no')] = item

        for e in reversed(recent):  # Most recent first
            entry = {
                'draw_no': e.draw_no,
                'pred_b1': list(e.pred_b1),
                'pred_b2': list(e.pred_b2),
                'act_b1': list(e.act_b1),
                'act_b2': list(e.act_b2),
                'hits_b1': e.hits_b1,
                'hits_b2': e.hits_b2,
                'total': e.total(),
                'date': e.date,
                'best_model': None,
            }
            if e.draw_no in _mrd_by_draw:
                mrd_item = _mrd_by_draw[e.draw_no]
                preds = mrd_item.get('all_model_predictions', [])
                if preds:
                    act_b1_set = set(e.act_b1)
                    act_b2_set = set(e.act_b2)
                    best_mi = 0
                    best_hits = -1
                    for mi, (pb1, pb2) in enumerate(preds):
                        h = len(set(pb1) & act_b1_set) + len(set(pb2) & act_b2_set)
                        if h > best_hits:
                            best_hits = h
                            best_mi = mi
                    entry['best_model'] = {
                        'id': best_mi,
                        'name': model_names[best_mi] if best_mi < len(model_names) else f'Model-{best_mi+1}',
                        'hits': best_hits,
                    }
            heatmap_data.append(entry)
    else:
        for e in reversed(recent):
            heatmap_data.append({
                'draw_no': e.draw_no,
                'pred_b1': list(e.pred_b1),
                'pred_b2': list(e.pred_b2),
                'act_b1': list(e.act_b1),
                'act_b2': list(e.act_b2),
                'hits_b1': e.hits_b1,
                'hits_b2': e.hits_b2,
                'total': e.total(),
                'date': e.date,
                'best_model': None,
            })

    return heatmap_data


def compute_top5_models(model_report_data, model_names):
    """Identify top 5 best-performing models and their latest predictions.
    
    Returns:
        model_ranking: list of {model_id, name, score, avg_hits, ...}
        top5_predictions: list of {model_id, name, b1, b2, score}
    """
    if not model_report_data:
        return [], []
    
    # Per-model hit tracking
    model_hits = defaultdict(lambda: {'total_hits': 0, 'count': 0, 'b1_hits': 0, 'b2_hits': 0})
    for item in model_report_data:
        preds = item.get('all_model_predictions', [])
        act_b1 = set(item.get('act_b1', []))
        act_b2 = set(item.get('act_b2', []))
        for mi, (pb1, pb2) in enumerate(preds):
            h1 = len(set(pb1) & act_b1)
            h2 = len(set(pb2) & act_b2)
            model_hits[mi]['total_hits'] += h1 + h2
            model_hits[mi]['b1_hits'] += h1
            model_hits[mi]['b2_hits'] += h2
            model_hits[mi]['count'] += 1
    
    # Rank models by average hits per draw
    ranked = []
    for mi, stats in model_hits.items():
        if stats['count'] >= 5:
            avg = stats['total_hits'] / stats['count']
            ranked.append({
                'model_id': mi,
                'name': model_names[mi] if mi < len(model_names) else f'Model-{mi+1}',
                'score': round(avg, 3),
                'avg_hits': round(avg, 3),
                'b1_avg': round(stats['b1_hits'] / stats['count'], 3),
                'b2_avg': round(stats['b2_hits'] / stats['count'], 3),
                'draws_tested': stats['count'],
            })
    
    ranked.sort(key=lambda x: -x['score'])
    model_ranking = ranked[:5]
    
    # Get predictions from top 5 models (from last entry)
    top5_predictions = []
    if model_report_data:
        last_preds = model_report_data[-1].get('all_model_predictions', [])
        for entry in model_ranking:
            mi = entry['model_id']
            if mi < len(last_preds):
                pb1, pb2 = last_preds[mi]
                top5_predictions.append({
                    'model_id': mi,
                    'name': entry['name'],
                    'b1': sorted(list(pb1)),
                    'b2': sorted(list(pb2)),
                    'score': entry['score'],
                })
    
    return model_ranking, top5_predictions


def build_consensus_votes(final_p, model_weights=None):
    """Build consensus vote dictionaries from all model predictions.
    
    v25.1: Skips disabled models (empty predictions).
    v39.2.1: Three improvements for higher consensus.
    v39.4.0: Consensus Engine v2 — four major improvements:
      1. Adaptive weight threshold (70% cumulative) instead of fixed 50%
      2. Agreement concentration bonus — top numbers get amplified
      3. Model diversity scoring — unique predictions from diverse models get bonus
      4. Stability-aware voting — penalize models with erratic predictions
    
    Args:
        final_p: list of (pb1, pb2) tuples from all_predictions()
        model_weights: optional dict mapping model_index → float weight (from
            build_weighted_consensus_with_gap). When None, uses equal weighting.
    
    Returns:
        b1_votes, b2_votes: {number_str: vote_count}
        b1_agreement, b2_agreement: percentage of models that included the top-voted number (0.0-1.0)
    """
    if not final_p:
        return {}, {}, 0.0, 0.0
    b1_votes = defaultdict(float)
    b2_votes = defaultdict(float)
    active_count = 0
    total_weight = 0.0
    use_weights = model_weights is not None and len(model_weights) > 0

    # v39.4.0: Adaptive weight threshold — include models that collectively
    # account for top 70% of weight mass (instead of fixed 50% percentile).
    # This adapts to weight distribution — if weights are evenly distributed,
    # more models are included; if concentrated, fewer but better ones are used.
    weight_threshold = 0.0
    if use_weights:
        valid_weights = [w for mi, w in model_weights.items()
                         if mi not in _DISABLED_MODELS and w > 0]
        if len(valid_weights) >= 4:
            sorted_ws = sorted(valid_weights, reverse=True)
            cumsum = 0.0
            total_ws = sum(sorted_ws)
            # Find threshold for top 70% cumulative weight
            cutoff_idx = 0
            for idx, w in enumerate(sorted_ws):
                cumsum += w
                cutoff_idx = idx
                if cumsum >= total_ws * 0.70:
                    break
            # Threshold = weight at the cutoff point
            weight_threshold = sorted_ws[min(cutoff_idx + 1, len(sorted_ws) - 1)]
            weight_threshold = max(weight_threshold, 0.01)  # floor to avoid excluding all

    # v39.2.1: Rank weights — position in model's pick list.
    _RANK_WEIGHTS = [2.0, 1.5, 1.2, 1.0]  # for pick=4

    def _rank_weight(pos, pick_count):
        if pick_count <= 1:
            return 1.0
        if pick_count <= len(_RANK_WEIGHTS) and pos < len(_RANK_WEIGHTS):
            return _RANK_WEIGHTS[pos]
        return 1.0 + 1.0 * (1.0 - pos / max(pick_count - 1, 1))

    # v39.4.0: Pre-compute model diversity metric.
    # Track which numbers each model picks uniquely (not picked by previous models).
    # Models that add unique numbers get a diversity bonus.
    _model_unique_picks_b1 = {}  # mi -> count of numbers unique to this model (among top picks)
    _global_picked_b1 = set()    # running set of all picked numbers so far

    for mi, (pb1, pb2) in enumerate(final_p):
        pb1_list = list(pb1) if hasattr(pb1, '__len__') else []
        if not pb1_list:
            _model_unique_picks_b1[mi] = 0
            continue
        pb1_set = set(int(x) if hasattr(x, '__index__') or isinstance(x, (int, float)) else x for x in pb1_list)
        unique_count = len(pb1_set - _global_picked_b1)
        _model_unique_picks_b1[mi] = unique_count
        _global_picked_b1 |= pb1_set

    # Now compute votes with all improvements
    for mi, (pb1, pb2) in enumerate(final_p):
        pb1_len = len(pb1) if hasattr(pb1, '__len__') else 0
        pb2_len = len(pb2) if hasattr(pb2, '__len__') else 0
        if pb1_len == 0 and pb2_len == 0:
            continue  # v25.1: skip disabled models

        w = 1.0
        if use_weights:
            raw_w = model_weights.get(mi, 1.0)
            if raw_w <= 0:
                continue
            if raw_w < weight_threshold:
                continue
            # v39.4.0: Softened power transform (1.3 instead of 1.5) — less extreme concentration
            w = raw_w ** 1.3

        # v39.4.0: Diversity bonus — models contributing unique numbers get +10%
        diversity_bonus = 1.0
        unique_count = _model_unique_picks_b1.get(mi, 0)
        if unique_count > 0:
            diversity_bonus = 1.0 + min(unique_count * 0.05, 0.15)  # max +15%
        w *= diversity_bonus

        active_count += 1
        total_weight += w

        for pos, x in enumerate(pb1):
            rw = _rank_weight(pos, pb1_len)
            val = int(x) if hasattr(x, '__index__') or isinstance(x, (int, float)) else x
            b1_votes[val] += w * rw

        for pos, x in enumerate(pb2):
            rw = _rank_weight(pos, pb2_len)
            val = int(x) if hasattr(x, '__index__') or isinstance(x, (int, float)) else x
            b2_votes[val] += w * rw

    # v39.4.0: Agreement concentration bonus — amplify the gap between
    # top numbers and the rest. Numbers in top-K get a small additional
    # boost proportional to how much they lead over the next number.
    first_b1 = final_p[0][0] if final_p and final_p[0] else None
    first_b2 = final_p[0][1] if final_p and final_p[0] else None
    pick_b1 = len(first_b1) if first_b1 is not None and hasattr(first_b1, '__len__') and len(first_b1) > 0 else 4
    pick_b2 = len(first_b2) if first_b2 is not None and hasattr(first_b2, '__len__') and len(first_b2) > 0 else 4

    # Apply concentration bonus: top-pick numbers get +5% boost
    b1_sorted_items = sorted(b1_votes.items(), key=lambda x: -x[1])
    b2_sorted_items = sorted(b2_votes.items(), key=lambda x: -x[1])
    for num, _ in b1_sorted_items[:pick_b1]:
        b1_votes[num] *= 1.05
    for num, _ in b2_sorted_items[:pick_b2]:
        b2_votes[num] *= 1.05

    # Convert to sorted dict with rounded values
    b1_sorted = {str(k): round(v, 1) for k, v in sorted(b1_votes.items(), key=lambda x: -x[1])}
    b2_sorted = {str(k): round(v, 1) for k, v in sorted(b2_votes.items(), key=lambda x: -x[1])}

    # Compute agreement metric
    total_b1_votes = sum(b1_votes.values()) if b1_votes else 1.0
    total_b2_votes = sum(b2_votes.values()) if b2_votes else 1.0

    b1_top_support = sum(v for _, v in sorted(b1_votes.items(), key=lambda x: -x[1])[:pick_b1])
    b1_agreement = b1_top_support / total_b1_votes if total_b1_votes > 0 else 0.0

    b2_top_support = sum(v for _, v in sorted(b2_votes.items(), key=lambda x: -x[1])[:pick_b2])
    b2_agreement = b2_top_support / total_b2_votes if total_b2_votes > 0 else 0.0

    print(f'[INFO] Consensus v39.4.0: active={active_count}/{len(final_p)}, '
          f'adaptive_thresh={weight_threshold:.2f}, '
          f'b1_agree={b1_agreement:.4f}, b2_agree={b2_agreement:.4f}', file=sys.stderr)

    return b1_sorted, b2_sorted, round(b1_agreement, 4), round(b2_agreement, 4)


def build_weighted_consensus(final_p, model_report_data, baseline_random):
    """A4: Build weighted consensus using per-model accuracy scores.

    Weight each model's vote by its recent accuracy relative to random baseline.
    v39.2.1: Uses power-transformed weights and top-50% model filtering.

    v25.1: Skips disabled models and gives 2x boost to top cross-game performers.

    Returns:
        consensus_weighted_b1: sorted list of top numbers from block1
        consensus_weighted_b2: sorted list of top numbers from block2
        model_weights: dict of {model_id: weight} for transparency
    """
    if not final_p or not model_report_data:
        return [], [], {}

    total_models = len(final_p)
    n_recent = min(200, len(model_report_data))
    recent_mrd = model_report_data[-n_recent:]

    # Compute per-model average hits over recent backtest draws
    model_hits = defaultdict(lambda: {'total': 0, 'count': 0})
    for item in recent_mrd:
        preds = item.get('all_model_predictions', [])
        act_b1 = set(item.get('act_b1', []))
        act_b2 = set(item.get('act_b2', []))
        for mi, (pb1, pb2) in enumerate(preds):
            h1 = len(set(pb1) & act_b1)
            h2 = len(set(pb2) & act_b2)
            model_hits[mi]['total'] += h1 + h2
            model_hits[mi]['count'] += 1

    # v39.2.1: Compute weights with power transform
    weights = {}
    for mi in range(total_models):
        # v25.1: Disabled models get zero weight
        if mi in _DISABLED_MODELS:
            weights[mi] = 0.0
            continue
        stats = model_hits.get(mi, {'total': 0, 'count': 0})
        if stats['count'] > 0:
            avg_hits = stats['total'] / stats['count']
            raw_ratio = avg_hits / max(baseline_random, 0.01)
            w = max(0.2, raw_ratio) ** 1.3  # v39.2.1: power transform
        else:
            w = 0.5  # No data — lower default
        # v25.1: 2x boost for top cross-game performers
        if mi in _BOOSTED_MODELS:
            w *= 2.0
        weights[mi] = round(w, 3)

    # v39.2.1: Pre-filter to top 50%
    valid_ws = [w for mi, w in weights.items() if w > 0]
    if len(valid_ws) >= 4:
        weight_threshold = sorted(valid_ws)[len(valid_ws) * 50 // 100]
    else:
        weight_threshold = 0.0

    # Weighted voting
    b1_scores = defaultdict(float)
    b2_scores = defaultdict(float)
    for mi, (pb1, pb2) in enumerate(final_p):
        _l1 = len(pb1) if hasattr(pb1, '__len__') else 0
        _l2 = len(pb2) if hasattr(pb2, '__len__') else 0
        if _l1 == 0 and _l2 == 0:
            continue  # v25.1: skip disabled models (empty predictions)
        w = weights.get(mi, 1.0)
        if w <= 0:
            continue
        if w < weight_threshold:
            continue  # v39.2.1: Skip bottom 50%
        for x in pb1:
            b1_scores[x] += w
        for x in pb2:
            b2_scores[x] += w

    # Select top numbers by weighted score
    # Determine pick count from first non-empty prediction's block sizes
    pick_b1 = PICK_B1
    pick_b2 = PICK_B2
    for pb1, pb2 in final_p:
        if pb1 and pb2:
            pick_b1 = len(pb1)
            pick_b2 = len(pb2)
            break
    pick_b1 = max(pick_b1, 1)
    pick_b2 = max(pick_b2, 1)

    weighted_b1 = sorted(b1_scores, key=lambda x: -b1_scores[x])[:pick_b1]
    weighted_b2 = sorted(b2_scores, key=lambda x: -b2_scores[x])[:pick_b2]

    return sorted(weighted_b1), sorted(weighted_b2), weights


# ═══════════════════════════════════════════════════════════════════════════
#  P0-1: Score Vectors — full probability scores for ALL numbers
# ═══════════════════════════════════════════════════════════════════════════


def build_score_vectors(final_p, b1_max, b2_max):
    """Build full probability score vectors for ALL numbers in each block.

    For each of the b1_max (b2_max) numbers, count how many models predicted
    it and with what rank weight. Numbers appearing earlier in a model's pick
    list get higher weight (rank 1 → weight 4.0, rank 2 → 3.0, etc).

    Args:
        final_p: list of (pb1, pb2) tuples from all_predictions()
        b1_max: maximum number in block1
        b2_max: maximum number in block2

    Returns:
        dict with 'b1' and 'b2' keys, each mapping number → score (float)
        e.g. {'b1': {1: 5.2, 2: 3.1, ...}, 'b2': {1: 4.0, ...}}
    """
    b1_scores = defaultdict(float)
    b2_scores = defaultdict(float)

    if not final_p:
        return {'b1': {}, 'b2': {}}

    for pb1, pb2 in final_p:
        pb1_len = len(pb1) if hasattr(pb1, '__len__') else 0
        pb2_len = len(pb2) if hasattr(pb2, '__len__') else 0
        if pb1_len == 0 and pb2_len == 0:
            continue  # skip disabled models

        # Rank-weighted scoring: rank 1 (first pick) gets highest weight
        for rank_idx, x in enumerate(pb1):
            rank_weight = max(0.5, pb1_len - rank_idx)  # 4, 3, 2, 1, ...
            b1_scores[int(x)] += rank_weight

        for rank_idx, x in enumerate(pb2):
            rank_weight = max(0.5, pb2_len - rank_idx)
            b2_scores[int(x)] += rank_weight

    # Build output with ALL numbers (even those with 0 score)
    b1_out = {}
    for num in range(1, b1_max + 1):
        b1_out[str(num)] = round(b1_scores.get(num, 0.0), 2)

    b2_out = {}
    for num in range(1, b2_max + 1):
        b2_out[str(num)] = round(b2_scores.get(num, 0.0), 2)

    return {'b1': b1_out, 'b2': b2_out}


# ═══════════════════════════════════════════════════════════════════════════
#  P0-2: Constraint-Based Post-Filter
# ═══════════════════════════════════════════════════════════════════════════


def apply_constraint_filter(pred_b1, pred_b2, sum_range_stats, score_vectors,
                            pick_b1, pick_b2, b1_max, b2_max):
    """Post-filter: validate prediction against historical constraints.

    v39.4.0: Constraint Filter v2 — five validation rules:
      1. Sum range (P5-P95) — existing rule, unchanged
      2. Spread range — max-min difference must be within historical P10-P90
      3. Odd/Even ratio — must be within historical P10-P90 ratio
      4. Consecutive count — no more than 2 consecutive numbers (e.g. 5,6,7)
      5. Composite swap scoring — best replacement maximizes ALL constraint scores

    Args:
        pred_b1: list of predicted block1 numbers
        pred_b2: list of predicted block2 numbers
        sum_range_stats: output from build_sum_range_stats()
        score_vectors: output from build_score_vectors()
        pick_b1: numbers to pick from block1
        pick_b2: numbers to pick from block2
        b1_max: maximum block1 number
        b2_max: maximum block2 number

    Returns:
        (filtered_b1, filtered_b2, filter_applied, swaps_list)
    """
    filtered_b1 = list(pred_b1)
    filtered_b2 = list(pred_b2)
    swaps = []
    filter_applied = False

    if not sum_range_stats or 'block1' not in sum_range_stats:
        return filtered_b1, filtered_b2, False, []

    b1_stats = sum_range_stats.get('block1', {})
    b2_stats = sum_range_stats.get('block2', {})
    p5 = b1_stats.get('p5')
    p95 = b1_stats.get('p95')
    if p5 is None or p95 is None:
        return filtered_b1, filtered_b2, False, []

    b1_scores = score_vectors.get('b1', {}) if score_vectors else {}
    b2_scores = score_vectors.get('b2', {}) if score_vectors else {}

    # v39.4.0: Compute historical spread and odd/even stats from sum_range_stats
    # (These are computed in build_sum_range_stats via range_mean/range_std)
    spread_mean = b1_stats.get('range_mean')
    spread_std = b1_stats.get('range_std')
    spread_p10 = None
    spread_p90 = None
    if spread_mean is not None and spread_std is not None:
        spread_p10 = max(1, spread_mean - 1.5 * spread_std)
        spread_p90 = spread_mean + 1.5 * spread_std

    def _compute_constraint_score(b1_list, stats_dict):
        """Compute composite constraint violation score (lower = better)."""
        score = 0.0
        n = len(b1_list)
        if n < 2:
            return score

        # Rule 1: Sum range violation (normalized to [0,1])
        s = sum(b1_list)
        if p5 is not None and p95 is not None:
            if s < p5:
                score += (p5 - s) / max(p5, 1)
            elif s > p95:
                score += (s - p95) / max(p95, 1)

        # Rule 2: Spread range violation
        if spread_p10 is not None and spread_p90 is not None:
            spread = max(b1_list) - min(b1_list)
            if spread < spread_p10:
                score += (spread_p10 - spread) / max(spread_p10, 1) * 0.5
            elif spread > spread_p90:
                score += (spread - spread_p90) / max(spread_p90, 1) * 0.5

        # Rule 3: Odd/Even ratio violation (ideal: close to 50/50 for pick=4)
        odd_count = sum(1 for x in b1_list if x % 2 == 1)
        even_count = n - odd_count
        expected_ratio = 0.5
        actual_ratio = odd_count / max(n, 1)
        ratio_deviation = abs(actual_ratio - expected_ratio)
        # Penalize if deviation > 0.25 (more than 1 number off from 50/50)
        if ratio_deviation > 0.25:
            score += (ratio_deviation - 0.25) * 0.5

        # Rule 4: Consecutive count violation (max 2 consecutive allowed)
        sorted_nums = sorted(b1_list)
        max_consecutive = 0
        current_consecutive = 1
        for i in range(1, len(sorted_nums)):
            if sorted_nums[i] == sorted_nums[i - 1] + 1:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        if max_consecutive > 2:
            score += (max_consecutive - 2) * 0.3

        return score

    # ── Phase 1: Sum constraint (existing logic, preserved) ────────────────
    for _attempt in range(3):
        current_sum = sum(filtered_b1)
        if p5 <= current_sum <= p95:
            break

        filter_applied = True
        pred_set = set(filtered_b1)

        median = (p5 + p95) / 2
        if current_sum > p95:
            extreme_num = max(filtered_b1, key=lambda x: (x - median))
        else:
            extreme_num = min(filtered_b1, key=lambda x: (median - x))

        best_replacement = None
        best_score = -1
        for num_str, score in b1_scores.items():
            num = int(num_str)
            if num not in pred_set and score > best_score:
                best_score = score
                best_replacement = num

        if best_replacement is not None:
            swaps.append({
                'block': 'b1', 'rule': 'sum_range',
                'removed': extreme_num, 'added': best_replacement,
                'attempt': _attempt + 1,
                'sum_before': current_sum,
                'sum_after': current_sum - extreme_num + best_replacement,
            })
            filtered_b1.remove(extreme_num)
            filtered_b1.append(best_replacement)
            filtered_b1.sort()
        else:
            break

    # ── Phase 2: v39.4.0 — Composite constraint optimization ─────────────
    # Try swapping each number with each candidate to minimize total violation
    # Only perform if initial violation score > 0
    initial_score = _compute_constraint_score(filtered_b1, b1_stats)
    if initial_score > 0.05:
        pred_set = set(filtered_b1)
        best_swap = None
        best_improvement = 0.0

        for current_num in list(filtered_b1):
            for num_str, sv_score in b1_scores.items():
                candidate = int(num_str)
                if candidate in pred_set or candidate == current_num:
                    continue
                # Simulate swap
                trial = sorted([n if n != current_num else candidate for n in filtered_b1])
                new_score = _compute_constraint_score(trial, b1_stats)
                improvement = initial_score - new_score
                # Factor in score_vector quality (don't swap for a much worse number)
                sv_quality = b1_scores.get(str(candidate), 0) / max(b1_scores.get(str(current_num), 1), 0.01)
                if improvement > best_improvement and sv_quality > 0.3:
                    best_improvement = improvement
                    best_swap = (current_num, candidate, trial, new_score)

        if best_swap is not None and best_improvement > 0.02:
            old_num, new_num, new_list, _ = best_swap
            swaps.append({
                'block': 'b1', 'rule': 'composite_v2',
                'removed': old_num, 'added': new_num,
                'score_before': round(initial_score, 3),
                'score_after': round(best_swap[3], 3),
                'improvement': round(best_improvement, 3),
            })
            filtered_b1 = new_list
            filter_applied = True

    # ── Phase 3: Block2 sum constraint (existing logic, preserved) ─────────
    if pick_b2 > 0 and filtered_b2 and 'block2' in sum_range_stats:
        b2_stats_actual = sum_range_stats['block2']
        p5_b2 = b2_stats_actual.get('p5')
        p95_b2 = b2_stats_actual.get('p95')
        if p5_b2 is not None and p95_b2 is not None:
            for _attempt in range(3):
                current_sum_b2 = sum(filtered_b2)
                if p5_b2 <= current_sum_b2 <= p95_b2:
                    break
                filter_applied = True
                pred_set_b2 = set(filtered_b2)
                median_b2 = (p5_b2 + p95_b2) / 2
                if current_sum_b2 > p95_b2:
                    extreme_b2 = max(filtered_b2, key=lambda x: (x - median_b2))
                else:
                    extreme_b2 = min(filtered_b2, key=lambda x: (median_b2 - x))
                best_repl_b2 = None
                best_score_b2 = -1
                for num_str, score in b2_scores.items():
                    num = int(num_str)
                    if num not in pred_set_b2 and score > best_score_b2:
                        best_score_b2 = score
                        best_repl_b2 = num
                if best_repl_b2 is not None:
                    swaps.append({
                        'block': 'b2', 'rule': 'sum_range',
                        'removed': extreme_b2, 'added': best_repl_b2,
                        'attempt': _attempt + 1,
                        'sum_before': current_sum_b2,
                        'sum_after': current_sum_b2 - extreme_b2 + best_repl_b2,
                    })
                    filtered_b2.remove(extreme_b2)
                    filtered_b2.append(best_repl_b2)
                    filtered_b2.sort()
                else:
                    break

    return filtered_b1, filtered_b2, filter_applied, swaps


# ═══════════════════════════════════════════════════════════════════════════
#  P0-3: Pair Co-occurrence Bonus
# ═══════════════════════════════════════════════════════════════════════════


def apply_pair_bonus(pred_b1, pair_analysis, score_vectors):
    """Check if prediction contains a frequent pair; if not, try swapping 4th number.

    After computing the final top-N prediction for block1, check if any pair
    from the prediction appears in the top pairs list. If yes, boost confidence.
    If no pair appears, try swapping the last number with one that forms a
    frequent pair with the 1st number.

    Args:
        pred_b1: list of predicted block1 numbers (sorted)
        pair_analysis: output from build_pair_analysis()
        score_vectors: output from build_score_vectors()

    Returns:
        (adjusted_b1, bonus_applied, swap_info)
    """
    if not pred_b1 or len(pred_b1) < 2 or not pair_analysis:
        return list(pred_b1), False, None

    pairs = pair_analysis.get('pairs', [])
    if not pairs:
        return list(pred_b1), False, None

    # Build set of top frequent pairs for quick lookup
    top_pair_set = set()
    for p in pairs[:5]:  # Only check against top 5 pairs
        top_pair_set.add((p['pair'][0], p['pair'][1]))
        top_pair_set.add((p['pair'][1], p['pair'][0]))

    # Check if any pair from prediction is in top pairs
    pred_set = set(pred_b1)
    found_pair = None
    for i in range(len(pred_b1)):
        for j in range(i + 1, len(pred_b1)):
            pair_key = (pred_b1[i], pred_b1[j])
            if pair_key in top_pair_set:
                found_pair = pair_key
                break
            pair_key_rev = (pred_b1[j], pred_b1[i])
            if pair_key_rev in top_pair_set:
                found_pair = pair_key_rev
                break
        if found_pair:
            break

    if found_pair:
        return list(pred_b1), True, {'action': 'pair_found', 'pair': list(found_pair)}

    # No pair found — try swapping 4th number
    if len(pred_b1) < 4:
        return list(pred_b1), False, None

    # Find best number to pair with pred_b1[0] (1st pick)
    first_num = pred_b1[0]
    b1_scores = score_vectors.get('b1', {}) if score_vectors else {}

    best_swap = None
    best_pair_count = 0
    best_swap_score = -1

    for p in pairs:
        pair_nums = p['pair']
        if first_num in pair_nums:
            other_num = pair_nums[0] if pair_nums[1] == first_num else pair_nums[1]
            if other_num not in pred_set:
                score = b1_scores.get(str(other_num), 0)
                if p['count'] > best_pair_count or (p['count'] == best_pair_count and score > best_swap_score):
                    best_swap = other_num
                    best_pair_count = p['count']
                    best_swap_score = score

    if best_swap is not None:
        old_4th = pred_b1[-1]
        new_pred = list(pred_b1[:-1]) + [best_swap]
        new_pred.sort()
        swap_info = {
            'action': 'swapped_4th',
            'removed': old_4th,
            'added': best_swap,
            'pair_with': first_num,
            'pair_count': best_pair_count,
        }
        return new_pred, True, swap_info

    return list(pred_b1), False, None


# ═══════════════════════════════════════════════════════════════════════════
#  P1-4: Full Transition Matrix + PageRank
# ═══════════════════════════════════════════════════════════════════════════


def build_transition_pagerank(draws, b1_max, b2_max):
    """Build 20×20 transition matrix and run PageRank for number scoring.

    Builds a transition matrix from historical draws: probability of number j
    appearing after number i in consecutive draws. Then runs 3 iterations of
    PageRank to propagate probabilities and identify "centrally important"
    numbers.

    Args:
        draws: list of Draw objects
        b1_max: maximum block1 number
        b2_max: maximum block2 number

    Returns:
        dict with 'b1_top' and 'b2_top': top numbers by PageRank score,
        'b1_scores' and 'b2_scores': full score dictionaries
    """
    result = {
        'b1_top': [],
        'b2_top': [],
        'b1_scores': {},
        'b2_scores': {},
    }

    if len(draws) < 10:
        return result

    def _build_and_pagerank(block_attr, max_num):
        """Build transition matrix and run PageRank for one block."""
        # Build transition matrix
        matrix = np.zeros((max_num, max_num), dtype=np.float64)
        for i in range(len(draws) - 1):
            curr_nums = set(getattr(draws[i], block_attr))
            next_nums = set(getattr(draws[i + 1], block_attr))
            for c in curr_nums:
                if 1 <= c <= max_num:
                    for n in next_nums:
                        if 1 <= n <= max_num:
                            matrix[c - 1][n - 1] += 1.0

        # Row-normalize (each row sums to 1 if any transitions exist)
        row_sums = matrix.sum(axis=1, keepdims=True)
        # Avoid division by zero
        row_sums = np.where(row_sums > 0, row_sums, 1.0)
        matrix = matrix / row_sums

        # Initialize PageRank with uniform distribution
        pr = np.ones(max_num, dtype=np.float64) / max_num

        # Damping factor
        d = 0.85

        # Run 3 iterations of PageRank
        for _ in range(3):
            new_pr = np.copy(pr)
            total_influence = 0.0
            for j in range(max_num):
                influence = 0.0
                for i in range(max_num):
                    influence += matrix[i][j] * pr[i]
                total_influence += influence
                new_pr[j] = (1 - d) / max_num + d * influence

            # Normalize
            s = new_pr.sum()
            if s > 0:
                new_pr /= s
            pr = new_pr

        # Build output
        scores = {}
        for num in range(1, max_num + 1):
            scores[str(num)] = round(float(pr[num - 1]), 4)

        # Top 10 numbers by PageRank score
        sorted_nums = sorted(range(1, max_num + 1), key=lambda x: -pr[x - 1])
        top = sorted_nums[:10]

        return top, scores

    try:
        b1_top, b1_scores = _build_and_pagerank('block1', b1_max)
        b2_top, b2_scores = _build_and_pagerank('block2', b2_max)
        result['b1_top'] = b1_top
        result['b2_top'] = b2_top
        result['b1_scores'] = b1_scores
        result['b2_scores'] = b2_scores
    except Exception as e:
        print(f'[WARN] Transition PageRank failed: {e}', file=sys.stderr)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  P1-5: Gap Overdue Scoring in Weighted Consensus
# ═══════════════════════════════════════════════════════════════════════════


def build_weighted_consensus_with_gap(final_p, model_report_data, baseline_random,
                                      gap_analysis_data=None):
    """Build weighted consensus with gap overdue scoring boost.

    Extends build_weighted_consensus by adding a bonus for numbers with high
    overdue_score from gap analysis.
    - Numbers with overdue_score > 1.0 get 1.5x weight boost
    - Numbers with overdue_score > 2.0 get 2.0x weight boost

    v39.2.1 improvements:
    - Lower minimum weight (0.2 instead of 0.5) to let bad models contribute less
    - Power transform (weight^1.3) for better concentration on top models
    - Top-50% model pre-filter before voting (same as build_consensus_votes)

    Args:
        final_p: list of (pb1, pb2) from all_predictions()
        model_report_data: backtest model report data
        baseline_random: expected random hits baseline
        gap_analysis_data: output from build_gap_analysis(), optional

    Returns:
        Same as build_weighted_consensus: (weighted_b1, weighted_b2, model_weights)
    """
    if not final_p or not model_report_data:
        return [], [], {}

    total_models = len(final_p)
    n_recent = min(200, len(model_report_data))
    recent_mrd = model_report_data[-n_recent:]

    # Compute per-model average hits
    model_hits = defaultdict(lambda: {'total': 0, 'count': 0})
    for item in recent_mrd:
        preds = item.get('all_model_predictions', [])
        act_b1 = set(item.get('act_b1', []))
        act_b2 = set(item.get('act_b2', []))
        for mi, (pb1, pb2) in enumerate(preds):
            h1 = len(set(pb1) & act_b1)
            h2 = len(set(pb2) & act_b2)
            model_hits[mi]['total'] += h1 + h2
            model_hits[mi]['count'] += 1

    # v39.2.1: Compute model weights with stronger concentration
    weights = {}
    for mi in range(total_models):
        if mi in _DISABLED_MODELS:
            weights[mi] = 0.0
            continue
        stats = model_hits.get(mi, {'total': 0, 'count': 0})
        if stats['count'] > 0:
            avg_hits = stats['total'] / stats['count']
            # v39.2.1: Lower minimum (0.2) + power transform (^1.3)
            raw_ratio = avg_hits / max(baseline_random, 0.01)
            w = max(0.2, raw_ratio) ** 1.3
        else:
            w = 0.5  # No data — lower default
        if mi in _BOOSTED_MODELS:
            w *= 2.0
        weights[mi] = round(w, 3)

    # v39.2.1: Pre-filter to top 50% of models (same as build_consensus_votes)
    valid_ws = [w for mi, w in weights.items() if w > 0]
    if len(valid_ws) >= 4:
        weight_threshold = sorted(valid_ws)[len(valid_ws) * 50 // 100]
    else:
        weight_threshold = 0.0

    # Weighted voting with top-50% filtering
    b1_scores = defaultdict(float)
    b2_scores = defaultdict(float)
    active_count = 0
    for mi, (pb1, pb2) in enumerate(final_p):
        _l1 = len(pb1) if hasattr(pb1, '__len__') else 0
        _l2 = len(pb2) if hasattr(pb2, '__len__') else 0
        if _l1 == 0 and _l2 == 0:
            continue
        w = weights.get(mi, 1.0)
        if w <= 0:
            continue
        # v39.2.1: Skip bottom 50% of models
        if w < weight_threshold:
            continue
        active_count += 1
        for x in pb1:
            b1_scores[x] += w
        for x in pb2:
            b2_scores[x] += w

    print(f'[INFO] WeightedConsensus: active={active_count}/{total_models}, '
          f'w_thresh={weight_threshold:.2f}', file=sys.stderr)

    # Apply gap overdue bonus
    if gap_analysis_data:
        b1_gap_data = gap_analysis_data.get('block1', [])
        b2_gap_data = gap_analysis_data.get('block2', [])

        # Build overdue lookup for block1
        b1_overdue = {}
        for entry in b1_gap_data:
            overdue = entry.get('overdue_score', 0)
            b1_overdue[entry['number']] = overdue

        # Apply boost to block1 scores
        for num, score in b1_scores.items():
            overdue = b1_overdue.get(num, 0)
            if overdue > 2.0:
                b1_scores[num] = score * 2.0
            elif overdue > 1.0:
                b1_scores[num] = score * 1.5

        # Build overdue lookup for block2
        b2_overdue = {}
        for entry in b2_gap_data:
            overdue = entry.get('overdue_score', 0)
            b2_overdue[entry['number']] = overdue

        # Apply boost to block2 scores
        for num, score in b2_scores.items():
            overdue = b2_overdue.get(num, 0)
            if overdue > 2.0:
                b2_scores[num] = score * 2.0
            elif overdue > 1.0:
                b2_scores[num] = score * 1.5

    # Select top numbers
    pick_b1 = PICK_B1
    pick_b2 = PICK_B2
    for pb1, pb2 in final_p:
        if pb1 and pb2:
            pick_b1 = len(pb1)
            pick_b2 = len(pb2)
            break
    pick_b1 = max(pick_b1, 1)
    pick_b2 = max(pick_b2, 1)

    weighted_b1 = sorted(b1_scores, key=lambda x: -b1_scores[x])[:pick_b1]
    weighted_b2 = sorted(b2_scores, key=lambda x: -b2_scores[x])[:pick_b2]

    return sorted(weighted_b1), sorted(weighted_b2), weights


# ═══════════════════════════════════════════════════════════════════════════
#  P1-6: 2nd-Order Markov Chains
# ═══════════════════════════════════════════════════════════════════════════


def build_second_order_markov(draws, b1_max):
    """Build 2nd-order Markov chain for block1 predictions.

    Tracks frequency of (prev_num, curr_num) → next_num triplets.
    For the last draw's numbers, predicts which numbers are most likely next
    based on consecutive number pairs in the most recent draws.

    Args:
        draws: list of Draw objects
        b1_max: maximum block1 number

    Returns:
        dict with 'scores': {number: score}, 'top': [top_numbers]
    """
    result = {'scores': {}, 'top': []}

    if len(draws) < 20:
        return result

    try:
        # Track triplet frequencies: (num_at_n, num_at_n+1) → num_at_n+2
        triplet_counts = defaultdict(lambda: defaultdict(int))
        pair_counts = defaultdict(int)

        for i in range(len(draws) - 2):
            curr_nums = sorted(draws[i].block1)
            next_nums = sorted(draws[i + 1].block1)
            next2_nums = sorted(draws[i + 2].block1)

            for c in curr_nums:
                for n in next_nums:
                    pair_key = (c, n)
                    pair_counts[pair_key] += 1
                    for n2 in next2_nums:
                        triplet_counts[pair_key][n2] += 1

        # Use last two draws to predict
        last_nums = sorted(draws[-1].block1)
        prev_nums = sorted(draws[-2].block1)

        scores = defaultdict(float)
        for p in prev_nums:
            for l in last_nums:
                pair_key = (p, l)
                if pair_key in triplet_counts:
                    next_counts = triplet_counts[pair_key]
                    total = sum(next_counts.values())
                    if total > 0:
                        for num, count in next_counts.items():
                            # Weight by pair frequency (more common pairs = more reliable)
                            pair_freq = pair_counts.get(pair_key, 1)
                            scores[num] += (count / total) * min(pair_freq, 10)

        if scores:
            # Normalize
            total_score = sum(scores.values())
            if total_score > 0:
                for num in scores:
                    scores[num] = round(scores[num] / total_score * 100, 2)

            # Top 10
            sorted_nums = sorted(scores.keys(), key=lambda x: -scores[x])[:10]
            result['scores'] = {str(k): v for k, v in sorted(scores.items(), key=lambda x: -x[1])}
            result['top'] = sorted_nums

    except Exception as e:
        print(f'[WARN] 2nd-order Markov failed: {e}', file=sys.stderr)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  P2-7: Autocorrelation Analysis
# ═══════════════════════════════════════════════════════════════════════════


def build_autocorrelation(draws, b1_max, b2_max):
    """Compute autocorrelation at lags 1..10 for each number.

    For each number 1..b1_max, compute autocorrelation at lags 1..10.
    Numbers with significant positive autocorrelation at lag 1 are
    identified as "hot streak" numbers — they tend to appear in
    consecutive draws.

    Args:
        draws: list of Draw objects
        b1_max: maximum block1 number
        b2_max: maximum block2 number

    Returns:
        dict with 'block1' and 'block2' data:
        - hot_streak_numbers: numbers with positive lag-1 autocorrelation
        - number_details: per-number autocorrelation data
    """
    result = {'block1': {'hot_streak_numbers': [], 'number_details': []},
             'block2': {'hot_streak_numbers': [], 'number_details': []}}

    if len(draws) < 30:
        return result

    def _analyze_block(block_attr, max_num, min_draws=30):
        # Build binary time series for each number
        series = defaultdict(list)
        for d in draws:
            nums_set = set(getattr(d, block_attr))
            for num in range(1, max_num + 1):
                series[num].append(1 if num in nums_set else 0)

        hot_streak = []
        details = []

        for num in range(1, max_num + 1):
            data = np.array(series[num], dtype=np.float64)
            n = len(data)
            mean = np.mean(data)
            var = np.var(data)
            if var < 1e-10:
                continue  # Constant series, skip

            # Compute autocorrelation at lags 1..10
            acf_values = []
            for lag in range(1, min(11, n)):
                # Pearson autocorrelation
                if lag >= n:
                    acf_values.append(0.0)
                    continue
                x1 = data[:n - lag]
                x2 = data[lag:]
                c = np.mean((x1 - mean) * (x2 - mean))
                acf = c / var
                acf_values.append(round(float(acf), 4))

            # Check for hot streak (positive lag-1 autocorrelation)
            is_hot = len(acf_values) > 0 and acf_values[0] > 0.05

            entry = {
                'number': num,
                'acf_lag1': acf_values[0] if acf_values else 0.0,
                'acf_max': max(acf_values) if acf_values else 0.0,
                'acf_max_lag': acf_values.index(max(acf_values)) + 1 if acf_values else 0,
                'acf_values': acf_values,
                'is_hot_streak': is_hot,
            }
            details.append(entry)
            if is_hot:
                hot_streak.append(num)

        # Sort by acf_lag1 descending
        details.sort(key=lambda x: -x['acf_lag1'])
        return sorted(hot_streak), details

    try:
        b1_hot, b1_details = _analyze_block('block1', b1_max)
        b2_hot, b2_details = _analyze_block('block2', b2_max)

        result['block1']['hot_streak_numbers'] = b1_hot
        result['block1']['number_details'] = b1_details[:b1_max]  # Cap output size
        result['block2']['hot_streak_numbers'] = b2_hot
        result['block2']['number_details'] = b2_details[:b2_max]
    except Exception as e:
        print(f'[WARN] Autocorrelation analysis failed: {e}', file=sys.stderr)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  P2-9: Day-of-Week Patterns Analysis
# ═══════════════════════════════════════════════════════════════════════════

_DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def build_day_of_week_patterns(draws):
    """Analyze frequency patterns by day of week.

    For each day of week (0=Monday .. 6=Sunday), computes which numbers
    appear most and least frequently in draws on that day.

    Args:
        draws: list of Draw objects (each has .date string in DD.MM.YYYY format
               possibly with time, and .block1/.block2 lists of numbers)

    Returns:
        dict with 'by_day' (per-day hot/cold/total_draws),
        'current_day', 'current_day_name', 'recommendation_hot'
    """
    result = {
        'by_day': {},
        'current_day': 0,
        'current_day_name': 'Monday',
        'recommendation_hot': [],
    }

    if len(draws) < 10:
        return result

    # Collect numbers per day of week
    day_numbers = defaultdict(list)  # dow -> list of all numbers seen
    day_draw_counts = defaultdict(int)

    for draw in draws:
        date_str = getattr(draw, 'date', '')
        if not date_str:
            continue
        try:
            # Parse DD.MM.YYYY (possibly with time after)
            date_part = date_str.strip().split()[0]  # Take first part before any time
            dt = datetime.strptime(date_part, '%d.%m.%Y')
            dow = dt.weekday()  # 0=Monday .. 6=Sunday
        except (ValueError, IndexError):
            continue

        all_nums = list(getattr(draw, 'block1', [])) + list(getattr(draw, 'block2', []))
        day_numbers[dow].extend(all_nums)
        day_draw_counts[dow] += 1

    if not day_numbers:
        return result

    # Compute hot/cold for each day
    for dow in range(7):
        nums = day_numbers.get(dow, [])
        total = day_draw_counts.get(dow, 0)

        if total < 3:
            result['by_day'][str(dow)] = {
                'hot': [], 'cold': [], 'total_draws': total,
            }
            continue

        freq = Counter(nums)
        # Sort by frequency descending for hot, ascending for cold
        sorted_nums = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
        hot = [n for n, c in sorted_nums[:5]]
        cold = [n for n, c in sorted_nums[-5:]]

        result['by_day'][str(dow)] = {
            'hot': hot,
            'cold': cold,
            'total_draws': total,
        }

    # Determine current day
    now = datetime.now()
    current_dow = now.weekday()
    result['current_day'] = current_dow
    result['current_day_name'] = _DAY_NAMES[current_dow]
    result['recommendation_hot'] = result['by_day'].get(str(current_dow), {}).get('hot', [])

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  P2-10: Simplified ARIMA-like Trend Detection
# ═══════════════════════════════════════════════════════════════════════════


def build_autoregressive_trend(draws, b1_max):
    """Detect trending numbers using simple linear regression on appearance indices.

    For each number 1..b1_max, finds the last 20 draw indices where the number
    appeared, then fits a linear regression. A positive slope means the number
    is appearing more recently (trending up/hot); negative slope means it is
    appearing less recently (trending down/cold).

    Args:
        draws: list of Draw objects
        b1_max: maximum block1 number

    Returns:
        dict with 'trending_up', 'trending_down', 'number_details'
    """
    result = {
        'trending_up': [],
        'trending_down': [],
        'number_details': {},
    }

    if len(draws) < 30:
        return result

    try:
        # Build index of appearances for each number
        number_appearances = defaultdict(list)  # number -> [draw_index, ...]
        for idx, draw in enumerate(draws):
            all_nums = set(getattr(draw, 'block1', []))
            for num in all_nums:
                if 1 <= num <= b1_max:
                    number_appearances[num].append(idx)

        trending_up = []
        trending_down = []
        number_details = {}

        for num in range(1, b1_max + 1):
            appearances = number_appearances.get(num, [])
            if len(appearances) < 5:
                number_details[str(num)] = {'slope': 0.0, 'r2': 0.0}
                continue

            # Take the last 20 appearances
            recent = appearances[-20:]
            x = np.arange(len(recent), dtype=np.float64)  # 0, 1, 2, ...
            y = np.array(recent, dtype=np.float64)  # draw indices

            # Simple linear regression: y = slope * x + intercept
            n_pts = len(x)
            x_mean = np.mean(x)
            y_mean = np.mean(y)
            ss_xx = np.sum((x - x_mean) ** 2)
            ss_xy = np.sum((x - x_mean) * (y - y_mean))
            ss_yy = np.sum((y - y_mean) ** 2)

            if ss_xx < 1e-10:
                slope = 0.0
                r2 = 0.0
            else:
                slope = float(ss_xy / ss_xx)
                # R-squared
                ss_res = np.sum((y - (slope * x + (y_mean - slope * x_mean))) ** 2)
                r2 = float(1.0 - ss_res / ss_yy) if ss_yy > 1e-10 else 0.0
                r2 = max(0.0, min(1.0, r2))  # Clamp

            slope_rounded = round(slope, 4)
            r2_rounded = round(r2, 4)
            number_details[str(num)] = {'slope': slope_rounded, 'r2': r2_rounded}

            if slope > 0:
                trending_up.append((num, slope_rounded))
            elif slope < 0:
                trending_down.append((num, slope_rounded))

        # Sort: trending_up by slope descending, trending_down by slope ascending
        trending_up.sort(key=lambda x: -x[1])
        trending_down.sort(key=lambda x: x[1])

        result['trending_up'] = [n for n, s in trending_up]
        result['trending_down'] = [n for n, s in trending_down]
        result['number_details'] = number_details

    except Exception as e:
        print(f'[WARN] Autoregressive trend analysis failed: {e}', file=sys.stderr)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  P2-8: Regime Detection
# ═══════════════════════════════════════════════════════════════════════════


def detect_market_regime(draws):
    """Detect the current market regime from the last 50 draws.

    Analyzes last 50 draws to determine the current state:
    - 'stable': low variance of sums → numbers cluster around mean
    - 'volatile': high variance of sums → numbers spread widely
    - 'hot': mean sum trending up over last 50 → higher numbers appearing
    - 'cold': mean sum trending down over last 50 → lower numbers appearing

    Also computes a confidence score based on how clear the signal is.

    Args:
        draws: list of Draw objects

    Returns:
        dict with 'regime', 'confidence', 'sum_trend', 'sum_variance', 'details'
    """
    result = {
        'regime': 'unknown',
        'confidence': 0.0,
        'sum_trend': None,
        'sum_variance': None,
        'details': {},
    }

    if len(draws) < 50:
        return result

    try:
        window = draws[-50:]
        sums = [sum(d.block1) for d in window if d.block1]

        if len(sums) < 20:
            return result

        sums_arr = np.array(sums, dtype=np.float64)
        mean_sum = np.mean(sums_arr)
        var_sum = np.var(sums_arr)
        std_sum = np.std(sums_arr)

        # Compute trend: linear regression slope on last 50 draws
        x = np.arange(len(sums_arr), dtype=np.float64)
        x_mean = np.mean(x)
        slope = np.sum((x - x_mean) * (sums_arr - mean_sum)) / max(np.sum((x - x_mean) ** 2), 1)

        # Normalize slope relative to std
        slope_normalized = slope / max(std_sum, 1)

        # Normalize variance relative to mean
        cv = std_sum / max(mean_sum, 1)  # coefficient of variation

        result['sum_trend'] = round(float(slope), 2)
        result['sum_variance'] = round(float(var_sum), 2)
        result['details'] = {
            'mean_sum': round(float(mean_sum), 1),
            'std_sum': round(float(std_sum), 1),
            'slope': round(float(slope), 3),
            'slope_normalized': round(float(slope_normalized), 3),
            'cv': round(float(cv), 3),
        }

        # Determine regime
        # Thresholds based on coefficient of variation and slope
        if cv < 0.05:
            regime = 'stable'
            confidence = min(1.0, 0.5 + (0.05 - cv) * 10)
        elif cv > 0.10:
            regime = 'volatile'
            confidence = min(1.0, 0.5 + (cv - 0.10) * 10)
        elif slope_normalized > 0.3:
            regime = 'hot'
            confidence = min(1.0, 0.5 + abs(slope_normalized) * 0.5)
        elif slope_normalized < -0.3:
            regime = 'cold'
            confidence = min(1.0, 0.5 + abs(slope_normalized) * 0.5)
        else:
            regime = 'stable'
            confidence = 0.3  # Low confidence neutral

        result['regime'] = regime
        result['confidence'] = round(float(confidence), 3)

    except Exception as e:
        print(f'[WARN] Regime detection failed: {e}', file=sys.stderr)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  P3-0: Meta-Learner — "From chaos comes order" (v39.1.0)
# ═══════════════════════════════════════════════════════════════════════════


def build_meta_learner_prediction(draws, final_p, model_report_data, score_vectors,
                                   b1_max, b2_max, pick_b1, pick_b2, sum_range_stats,
                                   gap_analysis_data=None, transition_pagerank_data=None,
                                   pair_analysis_data=None):
    """v39.1.0 → v39.4.0-ml: numpy-based stacking meta-learner.

    Combines multiple feature signals into a single meta-score using backtest-learned
    weights.  "From chaos comes order" — the meta-learner finds structure in the
    noise of 107 competing model signals.

    v39.1.0-ml: Expanded from 6 to 8 features — added pair_cooccurrence (P1-6)
    and autoregressive_trend (P2-12) for improved prediction accuracy.
    v39.4.0-ml: Expanded from 8 to 14 features — added entropy (F9), ngram (F10),
    clustering (F11), streak (F12), positional_stability (F13), volatility (F14).

    Steps:
      1. Build a 14-feature matrix for every number in block1 and block2.
      2. Learn feature weights via correlation with backtest hit rates.
      3. Weighted sum → meta_score per number.
      4. Select top picks and apply constraint filter.

    Args:
        draws: list of Draw objects (chronological)
        final_p: list of (pb1, pb2) from all_predictions()
        model_report_data: backtest data with actual draws and model predictions
        score_vectors: output of build_score_vectors()
        b1_max, b2_max: maximum numbers per block
        pick_b1, pick_b2: how many numbers to pick per block
        sum_range_stats: output of build_sum_range_stats()
        gap_analysis_data: optional, output of build_gap_analysis()
        transition_pagerank_data: optional, output of build_transition_pagerank()
        pair_analysis_data: optional, output of build_pair_analysis() (P1-6)

    Returns:
        (meta_b1, meta_b2, feature_weights, success)
        On failure: (None, None, {}, False)
    """
    # ── Edge-case guard ──────────────────────────────────────────────────
    if not draws or len(draws) < 20:
        return None, None, {}, False
    if not model_report_data or len(model_report_data) < 30:
        return None, None, {}, False
    if not score_vectors or not score_vectors.get('b1'):
        return None, None, {}, False

    try:
        # ═══════════════════════════════════════════════════════════════════
        #  Step 1 — Build Feature Matrix (expanded: 6 → 8 → 14 features)
        # ═══════════════════════════════════════════════════════════════════
        FEATURE_NAMES = [
            'score_vectors',      # F1 — model consensus score
            'freq_100',           # F2 — frequency in last 100 draws
            'freq_20',            # F3 — frequency in last 20 draws (recency)
            'overdue',            # F4 — gap overdue score
            'pagerank',           # F5 — transition PageRank score
            'last_draw_hot',      # F6 — appeared in last draw
            'pair_cooccurrence',  # F7 — pair co-occurrence bonus (P1-6)
            'autoregressive',     # F8 — AR trend: freq slope last 50 draws (P2-12)
            'entropy',            # F9 — Shannon entropy of appearance pattern
            'ngram',              # F10 — 3-draw pattern matching score
            'clustering',         # F11 — degree centrality in co-occurrence graph
            'streak',             # F12 — consecutive appearance bonus
            'positional_stability', # F13 — rank consistency across models
            'volatility',         # F14 — frequency stability across windows
        ]

        # ── Pre-compute pair co-occurrence scores (P1-6) ────────────────
        # Numbers that appear in frequent pairs get a bonus
        pair_score_b1 = defaultdict(float)
        if pair_analysis_data and pair_analysis_data.get('pairs'):
            max_pair_count = max((p['count'] for p in pair_analysis_data['pairs']), default=1)
            for p in pair_analysis_data['pairs']:
                pair = p['pair']
                count = p['count']
                # Bonus proportional to pair frequency
                bonus = (count / max(max_pair_count, 1)) * 0.5
                for num in pair:
                    if 1 <= num <= b1_max:
                        pair_score_b1[num] += bonus

        def _build_features(block_max, sv_key, block_attr, gap_key=None, tp_key=None):
            """Build a (14, block_max) normalised feature matrix for one block."""
            sv = score_vectors.get(sv_key, {})

            # F1: model consensus score
            f1 = np.array([sv.get(str(n), 0.0) for n in range(1, block_max + 1)],
                          dtype=np.float64)

            # F2: frequency in last 100 draws
            recent_100 = draws[-100:]
            f2 = np.zeros(block_max, dtype=np.float64)
            for d in recent_100:
                for n in getattr(d, block_attr, []):
                    if 1 <= n <= block_max:
                        f2[n - 1] += 1.0
            f2 /= max(len(recent_100), 1)

            # F3: frequency in last 20 draws (recency)
            recent_20 = draws[-20:]
            f3 = np.zeros(block_max, dtype=np.float64)
            for d in recent_20:
                for n in getattr(d, block_attr, []):
                    if 1 <= n <= block_max:
                        f3[n - 1] += 1.0
            f3 /= max(len(recent_20), 1)

            # F4: gap overdue score
            f4 = np.zeros(block_max, dtype=np.float64)
            if gap_analysis_data and gap_key:
                for entry in gap_analysis_data.get(gap_key, []):
                    num = entry.get('number', 0)
                    if 1 <= num <= block_max:
                        f4[num - 1] = entry.get('overdue_score', 0.0)

            # F5: transition pagerank score
            f5 = np.zeros(block_max, dtype=np.float64)
            if transition_pagerank_data and tp_key:
                tp_scores = transition_pagerank_data.get(tp_key, {})
                for n in range(1, block_max + 1):
                    f5[n - 1] = tp_scores.get(str(n), 0.0)

            # F6: 1 if number appeared in the very last draw
            f6 = np.zeros(block_max, dtype=np.float64)
            if draws:
                last_nums = set(getattr(draws[-1], block_attr, []))
                for n in last_nums:
                    if 1 <= n <= block_max:
                        f6[n - 1] = 1.0

            # F7: pair co-occurrence bonus (P1-6)
            # Numbers that appear in frequently co-occurring pairs get a bonus
            f7 = np.zeros(block_max, dtype=np.float64)
            for num in range(1, block_max + 1):
                f7[num - 1] = pair_score_b1.get(num, 0.0)

            # F8: autoregressive trend (P2-12)
            # Compute frequency slope over last 50 draws vs previous 50 draws.
            # Positive slope = number is trending UP (increasingly popular).
            f8 = np.zeros(block_max, dtype=np.float64)
            if len(draws) >= 60:
                recent_50 = draws[-50:]
                prev_50 = draws[-100:-50] if len(draws) >= 100 else draws[:-50]
                recent_counts = defaultdict(float)
                prev_counts = defaultdict(float)
                for d in recent_50:
                    for n in getattr(d, block_attr, []):
                        if 1 <= n <= block_max:
                            recent_counts[n] += 1.0
                for d in prev_50:
                    for n in getattr(d, block_attr, []):
                        if 1 <= n <= block_max:
                            prev_counts[n] += 1.0
                for num in range(1, block_max + 1):
                    r_freq = recent_counts[num] / max(len(recent_50), 1)
                    p_freq = prev_counts[num] / max(len(prev_50), 1)
                    f8[num - 1] = r_freq - p_freq  # positive = trending up

            # F9: entropy score — information entropy of appearance pattern
            f9 = np.zeros(block_max, dtype=np.float64)
            if len(draws) >= 50:
                window = 100
                recent_w = draws[-window:]
                w_len = len(recent_w)
                for num in range(1, block_max + 1):
                    appearances = sum(1 for d in recent_w if num in getattr(d, block_attr, []))
                    p = appearances / max(w_len, 1)
                    if 0 < p < 1:
                        ent = -p * math.log2(p) - (1 - p) * math.log2(1 - p)
                        max_ent = math.log2(max(w_len, 2))
                        f9[num - 1] = ent / max(max_ent, 1)
                    else:
                        f9[num - 1] = 0.0  # Always or never appears → zero entropy

            # F10: N-gram co-occurrence — 3-draw pattern matching
            f10 = np.zeros(block_max, dtype=np.float64)
            if len(draws) >= 30:
                # Build transition map: (prev_num, curr_num) → {next_nums}
                transition_map = defaultdict(lambda: defaultdict(int))
                for i in range(len(draws) - 2):
                    prev_nums = set(getattr(draws[i], block_attr, []))
                    curr_nums = set(getattr(draws[i + 1], block_attr, []))
                    next_nums = set(getattr(draws[i + 2], block_attr, []))
                    for p in prev_nums:
                        for c in curr_nums:
                            if 1 <= p <= block_max and 1 <= c <= block_max:
                                for n in next_nums:
                                    if 1 <= n <= block_max:
                                        transition_map[p][c] += 1
                # Score: for each number, how many transitions from last 2 draws point to it
                if len(draws) >= 2:
                    last1 = set(getattr(draws[-1], block_attr, []))
                    last2 = set(getattr(draws[-2], block_attr, []))
                    for num in range(1, block_max + 1):
                        score = 0
                        for p in last2:
                            if 1 <= p <= block_max and p in transition_map:
                                for c in last1:
                                    if 1 <= c <= block_max:
                                        score += transition_map[p].get(c, 0)
                        f10[num - 1] = score

            # F11: clustering coefficient — centrality in co-occurrence graph
            f11 = np.zeros(block_max, dtype=np.float64)
            if len(draws) >= 20:
                cooccurrence = defaultdict(lambda: defaultdict(int))
                recent_c = draws[-100:]
                for d in recent_c:
                    nums = sorted([n for n in getattr(d, block_attr, []) if 1 <= n <= block_max])
                    for i_idx in range(len(nums)):
                        for j_idx in range(i_idx + 1, len(nums)):
                            cooccurrence[nums[i_idx]][nums[j_idx]] += 1
                            cooccurrence[nums[j_idx]][nums[i_idx]] += 1
                # Degree centrality normalized
                max_deg = 0
                for num in range(1, block_max + 1):
                    deg = sum(cooccurrence[num].values())
                    f11[num - 1] = deg
                    if deg > max_deg:
                        max_deg = deg
                if max_deg > 0:
                    f11 /= max_deg

            # F12: streak score — consecutive appearance bonus
            f12 = np.zeros(block_max, dtype=np.float64)
            if len(draws) >= 10:
                lookback = min(50, len(draws))
                for num in range(1, block_max + 1):
                    streak_count = 0
                    max_streak = 0
                    current_streak = 0
                    for d in draws[-lookback:]:
                        if num in getattr(d, block_attr, []):
                            current_streak += 1
                            max_streak = max(max_streak, current_streak)
                        else:
                            streak_count += (1 if current_streak >= 2 else 0)
                            current_streak = 0
                    # Score combines max recent streak + number of multi-streaks
                    f12[num - 1] = max_streak * 0.7 + streak_count * 0.3

            # F13: positional stability — rank consistency across models
            f13 = np.zeros(block_max, dtype=np.float64)
            if final_p:
                for num in range(1, block_max + 1):
                    positions = []
                    for pb1, _ in final_p:
                        pb1_list = list(pb1) if hasattr(pb1, '__len__') else []
                        if not pb1_list:
                            continue
                        if num in pb1_list:
                            positions.append(pb1_list.index(num))
                        else:
                            positions.append(len(pb1_list))  # penalty for not being picked
                    if positions:
                        # Lower variance in position = higher stability score
                        pos_arr = np.array(positions, dtype=np.float64)
                        mean_pos = pos_arr.mean()
                        if mean_pos > 0:
                            cv = pos_arr.std() / mean_pos  # coefficient of variation
                            # Lower CV = more stable → higher score
                            f13[num - 1] = max(0, 1.0 - cv)

            # F14: volatility score — frequency stability across windows
            f14 = np.zeros(block_max, dtype=np.float64)
            if len(draws) >= 40:
                window_size = 10
                n_windows = min(10, len(draws) // window_size)
                if n_windows >= 3:
                    for num in range(1, block_max + 1):
                        window_freqs = []
                        for w in range(n_windows):
                            start = len(draws) - (w + 1) * window_size
                            end = len(draws) - w * window_size
                            if start < 0:
                                start = 0
                            segment = draws[start:end]
                            freq = sum(1 for d in segment if num in getattr(d, block_attr, [])) / max(len(segment), 1)
                            window_freqs.append(freq)
                        # Lower volatility = lower std → more predictable → higher score
                        freq_arr = np.array(window_freqs, dtype=np.float64)
                        if freq_arr.std() > 1e-10:
                            cv = freq_arr.std() / max(freq_arr.mean(), 1e-10)
                            f14[num - 1] = 1.0 / (1.0 + cv)  # inverse: lower vol = higher score
                        else:
                            f14[num - 1] = 1.0  # perfectly stable

            # Stack: shape (14, block_max)
            raw = np.stack([f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13, f14], axis=0)

            # Normalise each feature row to [0, 1]
            for i in range(raw.shape[0]):
                rmin, rmax = raw[i].min(), raw[i].max()
                if rmax - rmin > 1e-10:
                    raw[i] = (raw[i] - rmin) / (rmax - rmin)
                else:
                    raw[i] = 0.5

            return raw  # (14, block_max)

        feat_b1 = _build_features(b1_max, 'b1', 'block1', 'block1', 'b1_scores')
        feat_b2 = _build_features(b2_max, 'b2', 'block2', 'block2', 'b2_scores')

        # ═══════════════════════════════════════════════════════════════════
        #  Step 2 — Learn Feature Weights via Backtest (v39.4.0: enhanced)
        # ═══════════════════════════════════════════════════════════════════
        # v39.4.0 improvements over v39.3.1:
        #   (a) Recency-weighted hit rates — recent draws matter more
        #   (b) Multi-objective scoring — Pearson + Spearman + top-K accuracy
        #   (c) L2 regularization — prevents over-fitting to noise
        #   (d) Minimum weight floor — ensures feature diversity

        n_bt = len(model_report_data)
        n_features = len(FEATURE_NAMES)  # 14

        # (a) Recency-weighted hit rates: exponential decay, recent draws get more weight
        _RECENCY_WEIGHTS = np.array(
            [0.5 ** (n_bt - 1 - i) / max(n_bt * 0.3, 1) for i in range(n_bt)],
            dtype=np.float64,
        )
        # Normalize recency weights to sum to 1
        if _RECENCY_WEIGHTS.sum() > 0:
            _RECENCY_WEIGHTS /= _RECENCY_WEIGHTS.sum()

        hit_counts_b1 = np.zeros(b1_max, dtype=np.float64)
        hit_counts_b2 = np.zeros(b2_max, dtype=np.float64)
        topk_hits_b1 = np.zeros(b1_max, dtype=np.float64)  # "in top-K" bonus
        topk_hits_b2 = np.zeros(b2_max, dtype=np.float64)

        for idx, item in enumerate(model_report_data):
            rw = _RECENCY_WEIGHTS[idx]
            for n in item.get('act_b1', []):
                if 1 <= n <= b1_max:
                    hit_counts_b1[n - 1] += rw
                    # Top-K bonus: was this number in any model's top picks?
                    preds = item.get('all_model_predictions', [])
                    for pb1, _ in preds[:20]:  # Check first 20 models
                        if n in pb1[:max(pick_b1, 1)]:
                            topk_hits_b1[n - 1] += rw * 0.3
                            break
            for n in item.get('act_b2', []):
                if 1 <= n <= b2_max:
                    hit_counts_b2[n - 1] += rw
                    preds = item.get('all_model_predictions', [])
                    for _, pb2 in preds[:20]:
                        if n in pb2[:max(pick_b2, 1)]:
                            topk_hits_b2[n - 1] += rw * 0.3
                            break

        hit_rate_b1 = hit_counts_b1 / max(_RECENCY_WEIGHTS.sum(), 1)
        hit_rate_b2 = hit_counts_b2 / max(_RECENCY_WEIGHTS.sum(), 1)

        # (b) Multi-objective feature scoring:
        #   Score_i = alpha * pearson(f_i, hit_rate) + beta * spearman(f_i, hit_rate)
        #            + gamma * pearson(f_i, topK_rate)
        _ALPHA, _BETA, _GAMMA = 0.5, 0.3, 0.2

        def _spearman_corr(x, y):
            """Compute Spearman rank correlation between two arrays."""
            if len(x) < 3:
                return 0.0
            rx = np.argsort(np.argsort(x))
            ry = np.argsort(np.argsort(y))
            std_rx, std_ry = rx.std(), ry.std()
            if std_rx < 1e-10 or std_ry < 1e-10:
                return 0.0
            c = np.corrcoef(rx.astype(np.float64), ry.astype(np.float64))[0, 1]
            return float(c) if not np.isnan(c) else 0.0

        raw_scores_b1 = np.zeros(n_features, dtype=np.float64)
        raw_scores_b2 = np.zeros(n_features, dtype=np.float64)

        for fi in range(n_features):
            # Block 1
            if feat_b1[fi].std() > 1e-10 and hit_rate_b1.std() > 1e-10:
                pearson = float(np.corrcoef(feat_b1[fi], hit_rate_b1)[0, 1])
                spearman = _spearman_corr(feat_b1[fi], hit_rate_b1)
                # Top-K component
                topk_rate_b1 = topk_hits_b1 / max(_RECENCY_WEIGHTS.sum(), 1)
                pearson_topk = 0.0
                if feat_b1[fi].std() > 1e-10 and topk_rate_b1.std() > 1e-10:
                    pt = float(np.corrcoef(feat_b1[fi], topk_rate_b1)[0, 1])
                    if not np.isnan(pt):
                        pearson_topk = pt
                raw_scores_b1[fi] = max(0, _ALPHA * pearson + _BETA * spearman + _GAMMA * pearson_topk)

            # Block 2
            if feat_b2[fi].std() > 1e-10 and hit_rate_b2.std() > 1e-10:
                pearson = float(np.corrcoef(feat_b2[fi], hit_rate_b2)[0, 1])
                spearman = _spearman_corr(feat_b2[fi], hit_rate_b2)
                topk_rate_b2 = topk_hits_b2 / max(_RECENCY_WEIGHTS.sum(), 1)
                pearson_topk = 0.0
                if feat_b2[fi].std() > 1e-10 and topk_rate_b2.std() > 1e-10:
                    pt = float(np.corrcoef(feat_b2[fi], topk_rate_b2)[0, 1])
                    if not np.isnan(pt):
                        pearson_topk = pt
                raw_scores_b2[fi] = max(0, _ALPHA * pearson + _BETA * spearman + _GAMMA * pearson_topk)

        # (c) L2 regularization: shrink extreme weights toward uniform
        # Prevents any single feature from dominating due to spurious correlation
        _L2_LAMBDA = 0.15  # Regularization strength (0=no reg, 1=fully uniform)
        _uniform_weight = 1.0 / n_features

        def _regularize(raw_weights, lam):
            """Apply L2 regularization: w_i = raw_i - lambda * (raw_i - uniform)."""
            return raw_weights * (1 - lam) + _uniform_weight * lam

        weights_b1 = _regularize(raw_scores_b1, _L2_LAMBDA)
        weights_b2 = _regularize(raw_scores_b2, _L2_LAMBDA)

        # (d) Minimum weight floor: every feature gets at least 2% weight
        # This ensures diversity — even "weak" features contribute a little
        _MIN_WEIGHT = 0.02
        for fi in range(n_features):
            weights_b1[fi] = max(weights_b1[fi], _MIN_WEIGHT)
            weights_b2[fi] = max(weights_b2[fi], _MIN_WEIGHT)

        # Normalise so weights sum to 1
        s1 = weights_b1.sum()
        weights_b1 = weights_b1 / s1 if s1 > 1e-10 else np.ones(n_features) / n_features
        s2 = weights_b2.sum()
        weights_b2 = weights_b2 / s2 if s2 > 1e-10 else np.ones(n_features) / n_features

        feature_weights = {
            FEATURE_NAMES[i]: {
                'b1': round(float(weights_b1[i]), 4),
                'b2': round(float(weights_b2[i]), 4),
            }
            for i in range(n_features)
        }

        # ═══════════════════════════════════════════════════════════════════
        #  Step 3 — Combine Features into Meta-Score
        # ═══════════════════════════════════════════════════════════════════
        meta_b1_scores = weights_b1 @ feat_b1  # shape (b1_max,)
        meta_b2_scores = weights_b2 @ feat_b2  # shape (b2_max,)

        # ═══════════════════════════════════════════════════════════════════
        #  Step 4 — Select Top Picks
        # ═══════════════════════════════════════════════════════════════════
        top_b1_idx = np.argsort(-meta_b1_scores)[:pick_b1]
        top_b2_idx = np.argsort(-meta_b2_scores)[:pick_b2]

        meta_b1 = sorted([int(i + 1) for i in top_b1_idx])
        meta_b2 = sorted([int(i + 1) for i in top_b2_idx])

        # ═══════════════════════════════════════════════════════════════════
        #  Step 5 — Apply Constraint Filter
        # ═══════════════════════════════════════════════════════════════════
        meta_b1, meta_b2, _, _ = apply_constraint_filter(
            meta_b1, meta_b2, sum_range_stats, score_vectors,
            pick_b1, pick_b2, b1_max, b2_max,
        )

        print(f'[INFO] Meta-learner v39.4.0 (14-feat recency-weighted): b1={meta_b1}, b2={meta_b2}', file=sys.stderr)

        return meta_b1, meta_b2, feature_weights, True

    except Exception as exc:
        print(f'[WARN] Meta-learner failed, falling back to consensus: {exc}',
              file=sys.stderr)
        return None, None, {}, False


def main():
    parser = argparse.ArgumentParser(description='LP132 Prediction Engine CLI')
    parser.add_argument('--file', required=True, help='Path to draw data file (DATE||NUM||n1,n2,...)')
    parser.add_argument('--seed-size', type=int, default=100, help='Training seed size (default: 100)')
    parser.add_argument('--batch-step', type=int, default=50, help='Training batch step (default: 50)')
    parser.add_argument('--full-every', type=int, default=10, help='Full ensemble every N batches (default: 10)')
    parser.add_argument('--no-cv', action='store_true', help='Skip cross-validation')
    parser.add_argument('--no-mc', action='store_true', help='Skip Monte Carlo simulation')
    parser.add_argument('--god-mode', action='store_true', help='God Mode optimizations: use fewer draws, skip per-draw fast_pred')
    args = parser.parse_args()

    # Game name derived from filename
    game_name = os.path.splitext(os.path.basename(args.file))[0]
    game_name_raw = game_name.replace('draws_', '').replace('tirazh', '').strip() or 'unknown'
    game_key = game_name_raw.lower()  # normalized key for GAME_FORMAT_HINTS lookup
    # Use game_key (e.g. '4x20') for file names so pipeline.py can find them
    file_game_key = game_key

    result = {
        "status": "error",
        "game": file_game_key,
    }

    # Timeout handler (10 minutes max)
    def timeout_handler(signum, frame):
        raise TimeoutError("Training exceeded 10 minute timeout")

    try:
        # Cross-platform timeout: use SIGALRM on Unix; on Windows, Node.js
        # spawnSync already provides its own timeout parameter.
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(600)  # 10 minutes

        # 1. Read and parse draw data
        if not os.path.exists(args.file):
            raise FileNotFoundError(f"Draw data file not found: {args.file}")

        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()

        draws = parse_text(text, game_name=game_key)
        if not draws:
            # Provide diagnostic info for debugging
            lines = [l for l in text.split('\n') if l.strip()]
            file_size = len(text)
            sample_lines = lines[:5]
            # Analyze why lines failed to parse
            reasons = []
            for sl in sample_lines:
                parts = sl.split('||')
                if len(parts) < 3:
                    reasons.append(f"  <3 parts: '{sl[:80]}'")
                elif len(parts) == 3:
                    nums_str = parts[2].strip()
                    if not nums_str:
                        reasons.append(f"  Empty numbers: '{sl[:80]}'")
                    else:
                        try:
                            nums = [int(x.strip()) for x in nums_str.split(',')]
                            reasons.append(f"  OK: {len(nums)} nums")
                        except ValueError as e:
                            reasons.append(f"  Bad numbers: '{nums_str[:60]}' ({e})")
                elif len(parts) == 4:
                    reasons.append(f"  4-part format: b1='{parts[2][:30]}' b2='{parts[3][:30]}'")
            raise ValueError(
                f"No valid draws parsed from file. "
                f"File size: {file_size} bytes, lines: {len(lines)}. "
                f"Sample analysis:\n" + "\n".join(reasons)
            )

        # v39.3.1: Cap draws — use fewer in god-mode for speed
        # With 13.7k draws, iterating each with _fast_pred is extremely slow.
        # God Mode runs 50 sequential runs, so speed is critical.
        MAX_DRAWS = 2000 if args.god_mode else 5000
        original_count = len(draws)
        if len(draws) > MAX_DRAWS:
            draws = draws[-MAX_DRAWS:]
            print(f'[INFO] Using last {MAX_DRAWS} of {original_count} draws for performance', file=sys.stderr)

        # Access the auto-detected globals from lp_v130_app after parse_text
        # (parse_text updates lp_v130_app module globals via _apply_game_hint,
        #  but our `from lp_v130_app import PICK_B1` bindings are stale copies)
        import lp_v130_app as _lp
        b1_max = _lp.B1_MAX
        b2_max = _lp.B2_MAX
        pick_b1 = _lp.PICK_B1
        pick_b2 = _lp.PICK_B2

        # 2. Data quality check
        data_quality = _check_data_quality(draws)
        if data_quality is None:
            data_quality = {'total_draws': len(draws), 'missing': 0, 'type_counts': {}}

        # 3. Next draw info
        next_draw_info = _compute_next_draw_info(draws)
        next_draw = {}

        # 3b. v25.0: Fetch game schedule info
        # v39.3.1: Skip in god-mode — network request, not needed for prediction
        if args.god_mode:
            draw_schedule = {"draw_type": "unknown", "is_predictable": True, "draw_type_label": "skipped", "next_estimated": None}
        else:
            draw_schedule = _fetch_game_schedule(game_key)
        if next_draw_info:
            next_draw = {
                'number': next_draw_info['next_draw_no'],
                'type': next_draw_info['next_type'],
                'time': next_draw_info['next_time'],
                'last_draw_no': next_draw_info['last_draw'].draw_no if next_draw_info['last_draw'] else None,
                'last_type': next_draw_info['last_type'],
                'next_rng_time': next_draw_info.get('next_rng_time'),
                'next_std_time': next_draw_info.get('next_std_time'),
            }

        # 3c. A6: Load top-5 model cache from previous run for priority training
        priority_model_ids = _load_top5_cache(file_game_key)

        # 4. Run training
        training_result = run_training(
            draws,
            seed_size=args.seed_size,
            batch_step=args.batch_step,
            full_every=args.full_every,
            priority_models=priority_model_ids,
        )

        predictor = training_result['predictor']
        bayes = training_result['bayes']
        last_pred = training_result['last_pred']
        final_p = training_result['final_p']
        accuracy_history = training_result['accuracy_history']
        model_report_data = training_result['model_report_data']
        training_time = training_result['training_time']

        # 5. Build prediction output
        pred_b1 = sorted(last_pred[0]) if last_pred and last_pred[0] else []
        pred_b2 = sorted(last_pred[1]) if last_pred and last_pred[1] else []

        # 6. Accuracy statistics
        accuracy_stats = compute_accuracy_stats(accuracy_history)
        baseline = _compute_baseline_random(b1_max, b2_max, pick_b1, pick_b2)
        
        # 6b. Build backtest heatmap and top 5 models
        # v39.3.1: Skip in god-mode — expensive, only needed for UI display
        if args.god_mode:
            heatmap_data = []
            model_ranking = []
            top5_predictions = []
        else:
            model_names_list = _get_model_names()
            heatmap_data = build_backtest_heatmap(
                accuracy_history, final_p, max_draws=30,
                model_report_data=model_report_data, model_names=model_names_list
            )
            model_ranking, top5_predictions = compute_top5_models(model_report_data, model_names_list)

        # 6g. A6: Save top-5 model cache for next run
        # v39.3.1: Skip in god-mode — not needed when running sequential batch
        if not args.god_mode:
            _save_top5_cache(file_game_key, model_ranking)

        # A5: Compute time weights for recency weighting
        RECENCY_HALF_LIFE = 500
        time_weights = _compute_time_weights(len(draws), half_life=RECENCY_HALF_LIFE)

        # 6c. v25.0: Build frequency analysis (A5: with time weights)
        # v39.3.1: Skip in god-mode — not needed for prediction pipeline
        if args.god_mode:
            frequency_analysis = {"block1": [], "block2": []}
        else:
            frequency_analysis = build_frequency_analysis(draws, b1_max, b2_max, time_weights=time_weights)

        # 6d. v27.1: Pair analysis
        # v39.3.1: Skip in god-mode — saves ~0.5s
        if args.god_mode:
            pair_analysis = {"pairs": [], "total_draws": len(draws) if draws else 0}
        else:
            pair_analysis = build_pair_analysis(draws, b1_max, pick_count=10)

        # 6e. v27.1: Gap analysis (A5: with time-weighted recency)
        gap_analysis = build_gap_analysis(draws, b1_max, b2_max, time_weights=time_weights)

        # P1-5: Weighted consensus with gap overdue scoring boost
        consensus_weighted_b1, consensus_weighted_b2, model_weights = build_weighted_consensus_with_gap(
            final_p, model_report_data, baseline, gap_analysis_data=gap_analysis
        )

        # v39.2.1: Compute consensus votes AFTER model_weights is available.
        # Passing model_weights to build_consensus_votes enables accuracy-weighted
        # agreement, which produces higher effective consensus (top models agree more).
        b1_votes, b2_votes, b1_agreement, b2_agreement = build_consensus_votes(
            final_p, model_weights=model_weights
        )

        # 6f. v27.1: Sum/range statistics
        sum_range_stats = build_sum_range_stats(draws, pick_b1, pick_b2, b1_max, b2_max)

        # 6g. A7: Cross-game correlation analysis
        # v39.3.1: Skip in god-mode — expensive file I/O scanning all game files
        if args.god_mode:
            cross_game_analysis = {"hot_numbers": [], "source_games": [], "method": "skipped", "number_stats": []}
        else:
            _data_dir = os.path.join(_PROJECT_ROOT, 'data', 'draws')
            cross_game_analysis = build_cross_game_analysis(file_game_key, b1_max, b2_max, _data_dir)

        # P0-1: Build score vectors for ALL numbers (right after consensus votes)
        score_vectors = build_score_vectors(final_p, b1_max, b2_max)

        # P1-4: Transition matrix + PageRank
        # v39.3.1: Skip in god-mode — expensive O(n²) computation, not in prediction pipeline
        if args.god_mode:
            transition_pagerank = {"b1": {}, "b2": {}}
        else:
            transition_pagerank = build_transition_pagerank(draws, b1_max, b2_max)

        # P1-6: 2nd-order Markov chains
        # v39.3.1: Skip in god-mode — expensive, not in prediction pipeline
        if args.god_mode:
            second_order_markov = {"transitions": {}, "top_predictions": []}
        else:
            second_order_markov = build_second_order_markov(draws, b1_max)

        # P2-7: Autocorrelation analysis
        # v39.3.1: Skip in god-mode
        if args.god_mode:
            autocorrelation = {"b1": [], "b2": []}
        else:
            autocorrelation = build_autocorrelation(draws, b1_max, b2_max)

        # P2-8: Regime detection
        # v39.3.1: Skip in god-mode
        if args.god_mode:
            regime_detection = {"regime": "unknown", "trend_strength": 0}
        else:
            regime_detection = detect_market_regime(draws)

        # P2-9: Day-of-week patterns
        # v39.3.1: Skip in god-mode
        if args.god_mode:
            day_of_week = {"hot": {}, "cold": {}, "current_day": None}
        else:
            day_of_week = build_day_of_week_patterns(draws)

        # P2-10: Autoregressive trend detection
        # v39.3.1: Skip in god-mode
        if args.god_mode:
            autoregressive_trend = {"trending_up": [], "trending_down": []}
        else:
            autoregressive_trend = build_autoregressive_trend(draws, b1_max)

        # P3-0: v39.1.0 — Meta-learner stacking prediction
        meta_learner_used = False
        meta_learner_output = {
            'b1': [], 'b2': [], 'feature_weights': {}, 'method': 'numpy_stacking',
        }
        meta_b1, meta_b2, meta_feature_weights, meta_success = build_meta_learner_prediction(
            draws, final_p, model_report_data, score_vectors,
            b1_max, b2_max, pick_b1, pick_b2, sum_range_stats,
            gap_analysis_data=gap_analysis,
            transition_pagerank_data=transition_pagerank,
            pair_analysis_data=pair_analysis,
        )

        if meta_success and meta_b1 and meta_b2:
            # Meta-learner produced a valid prediction — use it as the base
            pred_b1 = list(meta_b1)
            pred_b2 = list(meta_b2)
            meta_learner_used = True
            meta_learner_output['b1'] = pred_b1
            meta_learner_output['b2'] = pred_b2
            meta_learner_output['feature_weights'] = meta_feature_weights
            print('[INFO] Meta-learner v39.1.0 prediction adopted as final', file=sys.stderr)
        else:
            # Fallback to existing consensus (pred_b1/pred_b2 already set above)
            print('[INFO] Meta-learner unavailable, using consensus prediction', file=sys.stderr)

        # P0-3: Apply pair co-occurrence bonus (AFTER meta-learner)
        pair_bonus_applied = False
        pair_bonus_info = None
        pred_b1_adjusted, pair_bonus_applied, pair_bonus_info = apply_pair_bonus(
            pred_b1, pair_analysis, score_vectors
        )
        if pair_bonus_applied:
            pred_b1 = pred_b1_adjusted
            print(f'[INFO] Pair bonus applied: {pair_bonus_info}', file=sys.stderr)

        # P0-2: Apply constraint-based post-filter (LAST step before output)
        constraint_filter_applied = False
        constraint_swaps = []
        pred_b1_final, pred_b2_final, constraint_filter_applied, constraint_swaps = apply_constraint_filter(
            pred_b1, pred_b2, sum_range_stats, score_vectors,
            pick_b1, pick_b2, b1_max, b2_max
        )
        if constraint_filter_applied:
            pred_b1 = pred_b1_final
            pred_b2 = pred_b2_final
            print(f'[INFO] Constraint filter applied: {len(constraint_swaps)} swap(s)', file=sys.stderr)

        if accuracy_history:
            last_50_avg = accuracy_stats.get('last_50_avg')
            improvement_pct = None
            if last_50_avg is not None and baseline > 0:
                improvement_pct = round((last_50_avg - baseline) / baseline * 100, 1)
        else:
            last_50_avg = None
            improvement_pct = None

        # 7. Cross-validation (optional)
        # v39.3.1: Force-skip in god-mode — runs 5 extra training loops, each ~30-60s
        cv_result = None
        if not args.god_mode and not args.no_cv and len(draws) > 500:
            try:
                cv_results = _cross_validate(draws, k=5, seed_size=args.seed_size)
                if cv_results:
                    cv_result = {
                        'folds': len(cv_results),
                        'avg_hits': round(sum(r['avg_hits'] for r in cv_results) / len(cv_results), 3),
                        'max_hits': max(r['max_hits'] for r in cv_results),
                        'ge5_count': sum(r['ge5_count'] for r in cv_results),
                        'fold_details': cv_results,
                    }
            except Exception:
                pass

        # 8. Monte Carlo confidence (optional)
        mc_result = None
        # v39.3.1: skip Monte Carlo in god-mode for speed (saves ~3-5s per run)
        if not args.no_mc and not args.god_mode:
            try:
                mc = _monte_carlo_confidence(predictor, n_simulations=5000)
                if mc:
                    mc_result = {
                        'mean': round(mc['mean'], 3),
                        'std': round(mc['std'], 3),
                        'p5': int(mc['p5']),
                        'p95': int(mc['p95']),
                        'p_ge5': round(mc['p_ge5'], 4),
                        'distribution': mc.get('distribution', {}),
                    }
            except Exception:
                pass

        # 9-10. Save files (skip in god-mode for speed)
        if args.god_mode:
            model_report_file = ""
            pipeline_data_file = ""
        else:
            # 9. Save model report data to file (use game_key for naming consistency with pipeline.py)
            _tmpdir = tempfile.gettempdir()
            model_report_file = os.path.join(_tmpdir, f"model_report_{file_game_key}.json")
            try:
                # Convert model_report_data to serializable format
                serializable_mrd = []
                for item in model_report_data:
                    serializable_mrd.append({
                        'draw_no': item['draw_no'],
                        'draw_type': item['draw_type'],
                        'all_model_predictions': [
                            [list(pb1), list(pb2)] for pb1, pb2 in item['all_model_predictions']
                        ],
                        'act_b1': list(item['act_b1']),
                        'act_b2': list(item['act_b2']),
                    })
                with open(model_report_file, 'w', encoding='utf-8') as f:
                    json.dump(serializable_mrd, f, ensure_ascii=False, default=str)
            except Exception as e:
                print(f'[WARN] Failed to save model report file: {e}', file=sys.stderr)
                model_report_file = ""

            # 10. Build pipeline data file (predictions CSV + metadata)
            pipeline_data_file = os.path.join(_tmpdir, f"pipeline_data_{file_game_key}.json")
            try:
                # Build draw_no → draw_type lookup from model_report_data
                _mrd_draw_type_map = {
                    item['draw_no']: item.get('draw_type', 'unknown')
                    for item in model_report_data
                }
                # Generate model predictions for pipeline
                model_names = _get_model_names()
                predictions_list = []
                if final_p:
                    for mi, (pb1, pb2) in enumerate(final_p):
                        predictions_list.append({
                            'model_id': f'p{mi+1}',
                            'name': model_names[mi] if mi < len(model_names) else f'p{mi+1}',
                            'b1': sorted(list(pb1)),
                            'b2': sorted(list(pb2)),
                        })

                pipeline_data = {
                    'predictions': predictions_list,
                    'total_models': len(predictions_list),
                    'b1_max': b1_max,
                    'b2_max': b2_max,
                    'pick_b1': pick_b1,
                    'pick_b2': pick_b2,
                    'accuracy_history': [
                        {
                            'draw_no': e.draw_no,
                            'total': e.total(),
                            'hits_b1': e.hits_b1,
                            'hits_b2': e.hits_b2,
                            'pred_b1': list(e.pred_b1),
                            'pred_b2': list(e.pred_b2),
                            'act_b1': list(e.act_b1),
                            'act_b2': list(e.act_b2),
                            'draw_type': _mrd_draw_type_map.get(e.draw_no, 'unknown'),
                        }
                        for e in accuracy_history
                    ],
                    'training_time': training_time,
                    'game': file_game_key,
                }
                with open(pipeline_data_file, 'w', encoding='utf-8') as f:
                    json.dump(pipeline_data, f, ensure_ascii=False, default=str)
            except Exception as e:
                print(f'[WARN] Failed to save pipeline data file: {e}', file=sys.stderr)
                pipeline_data_file = ""

        # 11. Build final output
        result = {
            "status": "ok",
            "game": file_game_key,
            "game_format": {
                "pick_b1": pick_b1,
                "pick_b2": pick_b2,
                "b1_max": b1_max,
                "b2_max": b2_max,
                "total_models": TOTAL_MODELS,
            },
            "data_quality": {
                "total_draws": data_quality.get('total_draws', len(draws)),
                "missing": data_quality.get('missing', 0),
                "has_gaps": data_quality.get('has_gaps', False),
                "type_counts": data_quality.get('type_counts', {}),
                "min_no": data_quality.get('min_no'),
                "max_no": data_quality.get('max_no'),
            },
            "next_draw": next_draw,
            "prediction_info": {
                "total_draws_used": data_quality.get('total_draws', len(draws)),
                "draw_range": f"{data_quality.get('min_no', '?')}–{data_quality.get('max_no', '?')}" if data_quality.get('min_no') and data_quality.get('max_no') else None,
                "last_draw_no": next_draw.get('last_draw_no') if next_draw else None,
                "next_draw_no": next_draw.get('number') if next_draw else None,
                "game_key": file_game_key,
            },
            "training": {
                "time_seconds": round(training_time, 1),
                "seed_size": args.seed_size,
                "total_trained": training_result['total_trained'],
                "batch_step": args.batch_step,
                "full_ensemble_every": args.full_every,
            },
            "prediction": {
                "block1": pred_b1,
                "block2": pred_b2,
                "consensus_votes_b1": b1_votes,
                "consensus_votes_b2": b2_votes,
                "consensus_agreement_b1": b1_agreement,
                "consensus_agreement_b2": b2_agreement,
                "consensus_weighted_b1": consensus_weighted_b1,
                "consensus_weighted_b2": consensus_weighted_b2,
                "score_vectors": score_vectors,
                "_pair_bonus_applied": pair_bonus_applied,
                "_pair_bonus_info": pair_bonus_info,
                "_constraint_filter_applied": constraint_filter_applied,
                "_constraint_swaps": constraint_swaps,
                "_meta_learner_used": meta_learner_used,
            },
            "meta_learner": meta_learner_output,
            "accuracy": {
                "last_50_avg": accuracy_stats.get('last_50_avg'),
                "last_100_avg": accuracy_stats.get('last_100_avg'),
                "last_200_avg": accuracy_stats.get('last_200_avg'),
                "baseline_random": round(baseline, 3),
                "improvement_pct": improvement_pct,
                "total_entries": len(accuracy_history),
            },
            "backtest": {
                "heatmap": heatmap_data,
                "total_entries": len(accuracy_history),
            },
            "draw_schedule": draw_schedule,
            "frequency_analysis": frequency_analysis,
            "pair_analysis": pair_analysis,
            "gap_analysis": gap_analysis,
            "sum_range_stats": sum_range_stats,
            "cross_game_analysis": cross_game_analysis,
            "transition_pagerank": transition_pagerank,
            "second_order_markov": second_order_markov,
            "autocorrelation": autocorrelation,
            "regime_detection": regime_detection,
            "day_of_week": day_of_week,
            "autoregressive_trend": autoregressive_trend,
            "top5_models": {
                "ranking": model_ranking,
                "predictions": top5_predictions,
            },
            "cross_validation": cv_result,
            "monte_carlo": mc_result,
            "model_report_data_file": model_report_file,
            "pipeline_data_file": pipeline_data_file,
            "time_weights_applied": True,
            "recency_half_life": RECENCY_HALF_LIFE,
            "model_accuracy_weights": {str(k): v for k, v in sorted(model_weights.items())},
        }

        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)  # Cancel timeout

    except TimeoutError as e:
        result["status"] = "timeout"
        result["error"] = str(e)
        if hasattr(signal, 'SIGALRM'):
            try:
                signal.alarm(0)
            except Exception:
                pass
    except FileNotFoundError as e:
        result["status"] = "error"
        result["error"] = str(e)
        if hasattr(signal, 'SIGALRM'):
            try:
                signal.alarm(0)
            except Exception:
                pass
    except ValueError as e:
        result["status"] = "error"
        result["error"] = str(e)
        if hasattr(signal, 'SIGALRM'):
            try:
                signal.alarm(0)
            except Exception:
                pass
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {str(e)}"
        import traceback
        result["traceback"] = traceback.format_exc()
        if hasattr(signal, 'SIGALRM'):
            try:
                signal.alarm(0)
            except Exception:
                pass

    # Output only JSON to stdout
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
