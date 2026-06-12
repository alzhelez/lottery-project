#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive model-by-model accuracy evaluation on real draw data.

Usage:
    python3 evaluate_accuracy.py --game 4x20
    python3 evaluate_accuracy.py --game 6x45plus
    python3 evaluate_accuracy.py --game 4x20 --test-draws 50
    python3 evaluate_accuracy.py --game rapido --skip-disabled

Outputs JSON to stdout and saves to data/eval_results_{game}.json

Flags:
    --game <key>          Any game key (4x20, 6x45plus, rapido, etc.)
    --test-draws <N>      Number of test draws (default: 50)
    --skip-disabled       Exclude disabled models from per-model results
    --output-dir <dir>    Output directory (default: data/)
"""

import sys
import os
import json
import time
import math
import argparse
from collections import defaultdict, Counter
import numpy as np

# ═══════════════════════════════════════════════════════════════════════════
#  MOCK STREAMLIT MODULE (must be done BEFORE importing lp_v130_app)
# ═══════════════════════════════════════════════════════════════════════════
from _streamlit_mock import st_mock  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
#  IMPORTS FROM lp_v130_app
# ═══════════════════════════════════════════════════════════════════════════

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)
_lp_in_python = os.path.exists(os.path.join(_SCRIPT_DIR, 'lp_v130_app.py'))
if not _lp_in_python:
    _upload_dir = os.path.join(_PROJECT_ROOT, 'upload')
    if os.path.isdir(_upload_dir) and os.path.exists(os.path.join(_upload_dir, 'lp_v130_app.py')):
        sys.path.insert(0, _upload_dir)

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')

import lp_v130_app as _lp_mod
from lp_v130_app import (
    parse_text, LP132, DualBayesRing, Draw, AccuracyEntry,
    TOTAL_MODELS, GAME_FORMAT_HINTS,
    _get_model_names, FreqCache,
    _DISABLED_MODELS, _LOW_DATA_THRESHOLD,
)


def compute_random_baseline(b1_max, b2_max, pick_b1, pick_b2):
    """Expected random hits: E[hits] = pick_b1^2/b1_max + pick_b2^2/b2_max."""
    return (pick_b1 ** 2 / b1_max) + (pick_b2 ** 2 / b2_max)


def compute_std(values):
    """Compute population standard deviation."""
    if not values or len(values) < 2:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return variance ** 0.5


def format_vs_random(value, baseline):
    """Format difference from random baseline as +/- string."""
    diff = value - baseline
    if diff >= 0:
        return f"+{diff:.3f}"
    else:
        return f"{diff:.3f}"


def majority_vote_prediction(all_preds, pick_b1, pick_b2):
    """Simple majority vote: count votes across all models, pick top numbers."""
    if not all_preds:
        return [], []
    b1_votes = Counter()
    b2_votes = Counter()
    for pb1, pb2 in all_preds:
        for x in pb1:
            b1_votes[x] += 1
        for x in pb2:
            b2_votes[x] += 1
    b1_sorted = b1_votes.most_common()
    b2_sorted = b2_votes.most_common()
    b1 = sorted([x for x, _ in b1_sorted[:pick_b1]])
    b2 = sorted([x for x, _ in b2_sorted[:pick_b2]])
    return b1, b2


def run_evaluation(game, test_draws_override=None, skip_disabled=False):
    """Run comprehensive model-by-model evaluation."""
    t_start = time.time()

    # ── Load draw data ──
    data_dir = os.path.join(_PROJECT_ROOT, 'data', 'draws')
    filepath = os.path.join(data_dir, f'draws_{game}.txt')

    print(f'[INFO] Loading draw data from: {filepath}', file=sys.stderr)
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    draws = parse_text(text, game_name=game)

    # Capture game format AFTER parse_text modifies the module globals
    b1_max = _lp_mod.B1_MAX
    b2_max = _lp_mod.B2_MAX
    pick_b1 = _lp_mod.PICK_B1
    pick_b2 = _lp_mod.PICK_B2

    print(f'[INFO] Loaded {len(draws)} draws for game {game}', file=sys.stderr)
    print(f'[INFO] Format: B1=1-{b1_max} (pick {pick_b1}), B2=1-{b2_max} (pick {pick_b2})', file=sys.stderr)

    # ── Split train/test ──
    n_test = test_draws_override if test_draws_override is not None else 50
    # Use ALL available draws for training (no artificial cap)
    n_train = len(draws) - n_test
    if n_train < n_test:
        n_test = len(draws) - 1
        n_train = 1
    n_test = min(n_test, len(draws) - n_train)

    train_draws = draws[:n_train]
    test_draws = draws[n_train:n_train + n_test]

    print(f'[INFO] Training on {len(train_draws)} draws, testing on {len(test_draws)} draws', file=sys.stderr)

    # ── Initialize predictor ──
    predictor = LP132()
    model_names = _get_model_names()

    # ── Train on all training draws (batch processing) ──
    print(f'[INFO] Training predictor on {len(train_draws)} draws...', file=sys.stderr)
    t_train_start = time.time()

    # Phase 1: Seed
    seed_size = 100
    batch_step = 50
    seed_size = min(seed_size, len(train_draws))

    current_draws = list(train_draws[:seed_size])
    predictor.update(current_draws)

    # Phase 2: Batch training through remaining training draws
    remaining_train = train_draws[seed_size:]
    n_batches = math.ceil(len(remaining_train) / batch_step)

    for batch_idx in range(n_batches):
        bs = batch_idx * batch_step
        be = min(bs + batch_step, len(remaining_train))
        batch = remaining_train[bs:be]

        for draw in batch:
            current_draws.append(draw)

        # Update predictor with all draws so far
        predictor.update(current_draws)

        # Periodic status
        if (batch_idx + 1) % 50 == 0 or batch_idx == n_batches - 1:
            elapsed = time.time() - t_train_start
            print(f'  [TRAIN] Batch {batch_idx+1}/{n_batches} ({len(current_draws)} draws, {elapsed:.1f}s)', file=sys.stderr)

    t_train_elapsed = time.time() - t_train_start
    print(f'[INFO] Training complete in {t_train_elapsed:.1f}s', file=sys.stderr)

    # ── Evaluate on test draws ──
    print(f'[INFO] Starting evaluation on {len(test_draws)} test draws...', file=sys.stderr)
    t_eval_start = time.time()

    # Per-model tracking
    model_total_hits = [0] * TOTAL_MODELS
    model_b1_hits = [0] * TOTAL_MODELS
    model_b2_hits = [0] * TOTAL_MODELS
    model_tested = [0] * TOTAL_MODELS
    model_hit_history = [[] for _ in range(TOTAL_MODELS)]  # per-draw hit counts for std dev

    # Consensus tracking
    consensus_total_hits = 0
    consensus_b1_hits = 0
    consensus_b2_hits = 0
    consensus_tested = 0

    # Majority vote tracking
    majority_total_hits = 0
    majority_b1_hits = 0
    majority_b2_hits = 0
    majority_tested = 0

    random_baseline = compute_random_baseline(b1_max, b2_max, pick_b1, pick_b2)

    for test_idx, draw in enumerate(test_draws):
        draw_no = draw.draw_no

        try:
            # Get all model predictions
            all_preds = predictor.all_predictions()

            if not all_preds or len(all_preds) == 0:
                print(f'  [WARN] No predictions for draw #{draw_no}', file=sys.stderr)
                # Still add draw and continue
                current_draws.append(draw)
                predictor.update(current_draws)
                continue

            act_b1_set = set(draw.block1)
            act_b2_set = set(draw.block2)

            # Evaluate each model
            for mi, (pb1, pb2) in enumerate(all_preds):
                if mi >= TOTAL_MODELS:
                    break
                try:
                    pred_b1_set = set(pb1)
                    pred_b2_set = set(pb2)
                    h1 = len(pred_b1_set & act_b1_set)
                    h2 = len(pred_b2_set & act_b2_set)
                    total_h = h1 + h2

                    model_total_hits[mi] += total_h
                    model_b1_hits[mi] += h1
                    model_b2_hits[mi] += h2
                    model_tested[mi] += 1
                    model_hit_history[mi].append(total_h)
                except Exception as e:
                    if test_idx == 0:
                        print(f'  [WARN] Model {mi} failed for draw #{draw_no}: {e}', file=sys.stderr)

            # Evaluate consensus — use majority vote when training data is
            # below _LOW_DATA_THRESHOLD (matching predict.py's behavior)
            try:
                n_draws_so_far = len(current_draws)
                if n_draws_so_far < _LOW_DATA_THRESHOLD:
                    cons_b1, cons_b2 = majority_vote_prediction(all_preds, pick_b1, pick_b2)
                else:
                    cons_b1, cons_b2 = predictor.consensus()
                c_h1 = len(set(cons_b1) & act_b1_set)
                c_h2 = len(set(cons_b2) & act_b2_set)
                consensus_total_hits += c_h1 + c_h2
                consensus_b1_hits += c_h1
                consensus_b2_hits += c_h2
                consensus_tested += 1
            except Exception as e:
                if test_idx == 0:
                    print(f'  [WARN] Consensus failed for draw #{draw_no}: {e}', file=sys.stderr)

            # Evaluate simple majority vote
            try:
                mv_b1, mv_b2 = majority_vote_prediction(all_preds, pick_b1, pick_b2)
                mv_h1 = len(set(mv_b1) & act_b1_set)
                mv_h2 = len(set(mv_b2) & act_b2_set)
                majority_total_hits += mv_h1 + mv_h2
                majority_b1_hits += mv_h1
                majority_b2_hits += mv_h2
                majority_tested += 1
            except Exception as e:
                if test_idx == 0:
                    print(f'  [WARN] Majority vote failed for draw #{draw_no}: {e}', file=sys.stderr)

        except Exception as e:
            print(f'  [ERROR] all_predictions() failed for draw #{draw_no}: {e}', file=sys.stderr)

        # Add draw to training data and update
        current_draws.append(draw)
        predictor.update(current_draws)

        # Progress
        if (test_idx + 1) % 10 == 0 or test_idx == len(test_draws) - 1:
            elapsed = time.time() - t_eval_start
            avg_all = sum(model_total_hits) / max(sum(model_tested), 1)
            print(f'  [EVAL] Draw {test_idx+1}/{len(test_draws)} '
                  f'(#{draw_no}, {elapsed:.1f}s, '
                  f'avg_model_hits={avg_all:.3f}, '
                  f'baseline={random_baseline:.3f})', file=sys.stderr)

    t_eval_elapsed = time.time() - t_eval_start
    t_total = time.time() - t_start

    print(f'[INFO] Evaluation complete in {t_eval_elapsed:.1f}s (total: {t_total:.1f}s)', file=sys.stderr)

    # ── Build results ──
    per_model = []
    disabled_count = 0
    for mi in range(TOTAL_MODELS):
        # Skip disabled models if --skip-disabled flag is set
        if skip_disabled and mi in _DISABLED_MODELS:
            disabled_count += 1
            continue
        tested = model_tested[mi]
        if tested == 0:
            avg_hits = 0
            avg_b1 = 0
            avg_b2 = 0
            stability = 0
        else:
            avg_hits = model_total_hits[mi] / tested
            avg_b1 = model_b1_hits[mi] / tested
            avg_b2 = model_b2_hits[mi] / tested
            stability = compute_std(model_hit_history[mi])

        name = model_names[mi] if mi < len(model_names) else f'Model-{mi+1}'
        is_disabled = mi in _DISABLED_MODELS

        per_model.append({
            'id': mi,
            'name': name,
            'avg_hits': round(avg_hits, 4),
            'avg_hits_b1': round(avg_b1, 4),
            'avg_hits_b2': round(avg_b2, 4),
            'total_hits': model_total_hits[mi],
            'total_hits_b1': model_b1_hits[mi],
            'total_hits_b2': model_b2_hits[mi],
            'stability': round(stability, 4),
            'vs_random': format_vs_random(avg_hits, random_baseline),
            'tested_on': tested,
            'disabled': is_disabled,
        })

    # Sort by avg_hits descending for ranking
    ranked = sorted(per_model, key=lambda x: -x['avg_hits'])

    # Top 20
    top_20 = ranked[:20]

    # Bottom 20
    bottom_20 = ranked[-20:]
    bottom_20_sorted = sorted(bottom_20, key=lambda x: x['avg_hits'])

    # Consensus results
    consensus_avg = consensus_total_hits / max(consensus_tested, 1)
    consensus_b1_avg = consensus_b1_hits / max(consensus_tested, 1)
    consensus_b2_avg = consensus_b2_hits / max(consensus_tested, 1)

    # Majority vote results
    majority_avg = majority_total_hits / max(majority_tested, 1)
    majority_b1_avg = majority_b1_hits / max(majority_tested, 1)
    majority_b2_avg = majority_b2_hits / max(majority_tested, 1)

    # Stats
    all_avgs = [m['avg_hits'] for m in per_model if m['tested_on'] > 0]
    models_beating_random = sum(1 for a in all_avgs if a > random_baseline)
    models_below_random = sum(1 for a in all_avgs if a < random_baseline)
    best_model_avg = max(all_avgs) if all_avgs else 0
    worst_model_avg = min(all_avgs) if all_avgs else 0
    sorted_avgs = sorted(all_avgs)
    median_avg = sorted_avgs[len(sorted_avgs) // 2] if sorted_avgs else 0

    # Consensus stability
    # (we didn't track per-draw consensus hits, skip)

    result = {
        'game': game,
        'test_draws': len(test_draws),
        'training_draws': len(train_draws),
        'random_baseline': round(random_baseline, 4),
        'per_model': per_model,
        'model_ranking': top_20,
        'worst_models': bottom_20_sorted,
        'consensus': {
            'avg_hits': round(consensus_avg, 4),
            'avg_hits_b1': round(consensus_b1_avg, 4),
            'avg_hits_b2': round(consensus_b2_avg, 4),
            'vs_random': format_vs_random(consensus_avg, random_baseline),
            'tested_on': consensus_tested,
        },
        'majority_vote': {
            'avg_hits': round(majority_avg, 4),
            'avg_hits_b1': round(majority_b1_avg, 4),
            'avg_hits_b2': round(majority_b2_avg, 4),
            'vs_random': format_vs_random(majority_avg, random_baseline),
            'tested_on': majority_tested,
        },
        'stats': {
            'models_beating_random': models_beating_random,
            'models_below_random': models_below_random,
            'models_at_random': len(per_model) - models_beating_random - models_below_random,
            'best_model_avg': round(best_model_avg, 4),
            'worst_model_avg': round(worst_model_avg, 4),
            'median_avg': round(median_avg, 4),
            'total_models': TOTAL_MODELS,
            'active_models': TOTAL_MODELS - disabled_count if skip_disabled else TOTAL_MODELS,
            'disabled_models_skipped': disabled_count,
            'skip_disabled': skip_disabled,
            'consensus_method': 'majority_vote' if n_train < _LOW_DATA_THRESHOLD else 'consensus',
            'training_time_s': round(t_train_elapsed, 1),
            'eval_time_s': round(t_eval_elapsed, 1),
            'total_time_s': round(t_total, 1),
        },
        'game_format': {
            'pick_b1': pick_b1,
            'pick_b2': pick_b2,
            'b1_max': b1_max,
            'b2_max': b2_max,
        },
    }

    return result


def main():
    parser = argparse.ArgumentParser(description='Model accuracy evaluation')
    parser.add_argument('--game', required=True,
                        help='Game to evaluate (any game key, e.g. 4x20, 6x45plus, rapido)')
    parser.add_argument('--test-draws', type=int, default=None,
                        help='Number of test draws (default: 50)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Output directory (default: data/)')
    parser.add_argument('--skip-disabled', action='store_true',
                        help='Exclude disabled models from per-model results')
    args = parser.parse_args()

    result = run_evaluation(args.game, test_draws_override=args.test_draws,
                            skip_disabled=args.skip_disabled)

    # Output JSON to stdout
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Save to file
    output_dir = args.output_dir or os.path.join(_PROJECT_ROOT, 'data')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f'eval_results_{args.game}.json')

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f'\n[INFO] Results saved to {output_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
