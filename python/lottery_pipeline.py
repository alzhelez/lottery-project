#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lottery_pipeline.py v11.1 — Adaptive Model Analyzer & Final Predictor

Analyzes report.html (per-model per-block per-draw position accuracy) and
predictions.csv (model predictions for next draw) to produce optimized
final predictions with confidence scoring and dual STD/RNG modes.

v11.1 — Dynamic pick-count support, all bugs fixed, all improvements:
  - Dynamic PICK_B1/PICK_B2 support (configurable via CLI or CSV header)
  - Auto-detection of pick counts from CSV header (B1_P* and B2_P* columns)
  - Flexible HTML table regex supporting variable position counts
  - Fixed: model coverage uses TOTAL_MODELS constant instead of hardcoded 155
  - Fixed: fallback pos_scores division by total_draws instead of total_hits
  - Fixed: Block 1 section boundary correctly ends at Block 2 marker
  - Fixed: dead code removed (unused Counter import, last_type variable)
  - Fixed: --pick-b1/--pick-b2 default=None so CSV auto-detection works
  - Fixed: model_votes dead code removed from _select_position_number
  - Fixed: total_hits scoped to position range in _build_result
  - Fixed: no-op if/pass block removed
  - Fixed: dead global PICK_B1/PICK_B2 reassignment removed from main()
  - Confidence scoring with dynamic position counts
  - LPD_DATA position scores with dynamic range
  - Support for B1 (1-35) and B2 (1-12) number ranges
  - Auto-detection of number ranges from predictions data
  - Dual prediction mode: STD and RNG specific
  - Improved position-specific weighting with range awareness

CLI Usage:
    python lottery_pipeline.py --html report.html --csv predictions.csv
    python lottery_pipeline.py --html report.html --csv predictions.csv --min-confidence 0.3
    python lottery_pipeline.py --html report.html --csv predictions.csv --pick-b1 5 --pick-b2 3

Import Usage:
    from lottery_pipeline import analyze_and_predict
    result = analyze_and_predict(html_path, csv_path)

Requirements:
    Python 3.8+ (stdlib only — no external dependencies)
"""

import re
import argparse
import json
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple


# ════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════════

# Configurable pick counts (default: 4x20 format)
PICK_B1 = 4  # Numbers to pick from Block 1
PICK_B2 = 4  # Numbers to pick from Block 2
TOTAL_MODELS = 155


# ════════════════════════════════════════════════════════════════════════
#  HTML PARSER — Extract per-model accuracy + per-draw position data
# ════════════════════════════════════════════════════════════════════════

def _parse_model_rows(html_section: str) -> Dict[str, Dict[str, Any]]:
    """Parse model accuracy table rows from an HTML section.

    Uses a flexible regex that captures ALL TD cells between the model-id
    cell and the rate cell, supporting variable position counts.

    Returns dict {model_id: {model_name, pos_hits: [...], pos1_hits, pos2_hits, ...,
                             total_hits, rate_pct}}
    """
    model_row_pattern = re.compile(
        r'<tr[^>]*data-model="([^"]+)"[^>]*>(.*?)</tr>',
        re.DOTALL
    )
    td_pattern = re.compile(r'<td[^>]*>([^<]*)</td>')

    models = {}
    for m in model_row_pattern.finditer(html_section):
        model_id = m.group(1).strip()
        row_content = m.group(2)
        td_values = [t.group(1).strip() for t in td_pattern.finditer(row_content)]

        # Need at least: model-id, name, 1 position, total, rate
        if len(td_values) < 5:
            continue

        # td_values[0] = model-id (skip, we use data-model attr)
        model_name = td_values[1] if len(td_values) > 1 else model_id

        # Last TD is rate, second-to-last is total, everything between is positions
        try:
            rate_str = td_values[-1]
            rate_val = float(rate_str.replace(',', '.')) if rate_str else 0.0
        except ValueError:
            rate_val = 0.0

        try:
            total_hits = int(td_values[-2])
        except (ValueError, IndexError):
            continue

        # Position hits are between model name (td_values[1]) and total (td_values[-2])
        pos_hits = []
        for val in td_values[2:-2]:
            try:
                pos_hits.append(int(val))
            except ValueError:
                break  # Stop at non-numeric cell

        if not pos_hits:
            continue

        entry = {
            'model_name': model_name,
            'pos_hits': pos_hits,
            'total_hits': total_hits,
            'rate_pct': rate_val,
        }
        # Add backward-compatible pos1_hits, pos2_hits, etc. keys
        for i, hits in enumerate(pos_hits):
            entry[f'pos{i + 1}_hits'] = hits
        models[model_id] = entry

    return models


def parse_html_report(html_path: str) -> Dict[str, Any]:
    """Parse report.html v3.0+ and extract all model accuracy data.

    Returns dict with keys:
        summary: dict with total_draws, avg_hits, etc.
        model_b1: dict {model_id: {model_name, pos_hits, pos1_hits.., total_hits, rate_pct}}
        model_b2: same for block 2
        lpd_data: list of {draw_no, draw_type, model_idx, block, positions}
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    result = {
        'summary': {},
        'model_b1': {},
        'model_b2': {},
        'lpd_data': [],
    }

    # ── 1. Parse summary table ──────────────────────────────────────────
    summary_pattern = re.compile(
        r'<tr[^>]*>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>\s*</tr>',
        re.DOTALL
    )
    for m in summary_pattern.finditer(html):
        key = m.group(1).strip()
        val = m.group(2).strip()
        result['summary'][key] = val

    # ── 2. Parse per-model B1 and B2 accuracy tables ───────────────────
    for block_key in ['model_b1', 'model_b2']:
        # Find the correct section for each block
        if block_key == 'model_b1':
            section_start = html.find("Block 1")
            section_end = html.find("Block 2", section_start) if section_start >= 0 else len(html)
        else:
            section_start = html.find("Block 2")
            section_end = len(html)

        if section_start >= 0:
            search_area = html[section_start:section_end] if section_end > section_start else html[section_start:]
        else:
            search_area = html

        result[block_key] = _parse_model_rows(search_area)

    # ── 3. Parse LPD_DATA section (per-draw per-model positions) ───────
    lpd_start = html.find('LPD_DATA')
    if lpd_start >= 0:
        lpd_end = html.find('LPD_END', lpd_start)
        if lpd_end >= 0:
            data_section = html[lpd_start:lpd_end]
            lpd_pattern = re.compile(r'<!--\s*(\d+)\|(\w+)\|(\d+)\|(b[12])\|(.*)\s*-->')
            for m in lpd_pattern.finditer(data_section):
                pos_str = m.group(5).strip()
                positions = []
                if pos_str:
                    try:
                        positions = [int(x) for x in pos_str.split(',') if x.strip()]
                    except ValueError:
                        positions = []
                result['lpd_data'].append({
                    'draw_no': int(m.group(1)),
                    'draw_type': m.group(2),
                    'model_idx': int(m.group(3)),
                    'block': m.group(4),
                    'positions': positions,
                })

    return result


# ════════════════════════════════════════════════════════════════════════
#  CSV PARSER — Extract model predictions for next draw
# ════════════════════════════════════════════════════════════════════════

def parse_predictions_csv(csv_path: str) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
    """Parse predictions.csv (pipe-separated).

    Expected format (auto-detected from header):
        Model|Name|B1_P1|B1_P2|...|B2_P1|B2_P2|...

    Header B1_P* columns determine PICK_B1, B2_P* columns determine PICK_B2.

    Returns:
        (predictions_list, b1_max, b2_max, pick_b1, pick_b2)
    """
    predictions = []
    import csv as _csv

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = _csv.reader(f, delimiter='|')
        header = next(reader, None)
        if not header:
            return predictions, 35, 12, PICK_B1, PICK_B2

        # ── Auto-detect pick counts from header ─────────────────────────
        # Support both Latin (B1_P) and Cyrillic (Б1_П) column headers
        pick_b1 = sum(1 for col in header if col.strip().startswith('B1_P') or col.strip().startswith('Б1_П'))
        pick_b2 = sum(1 for col in header if col.strip().startswith('B2_P') or col.strip().startswith('Б2_П'))
        # Fallback to global defaults if header detection fails
        pick_b1 = pick_b1 if pick_b1 > 0 else PICK_B1
        pick_b2 = pick_b2 if pick_b2 > 0 else PICK_B2

        min_cols = 2 + pick_b1 + pick_b2

        for row in reader:
            if len(row) < min_cols:
                continue
            model_id = row[0].strip()
            name = row[1].strip() if len(row) > 1 else model_id
            try:
                b1 = [int(row[2 + i]) for i in range(pick_b1)]
                b2 = [int(row[2 + pick_b1 + i]) for i in range(pick_b2)]
            except (ValueError, IndexError):
                continue
            # Auto-detect ranges from predictions — accept any n >= 1
            if not all(1 <= n for n in b1 + b2):
                continue
            if len(set(b1)) != pick_b1 or len(set(b2)) != pick_b2:
                continue
            predictions.append({
                'model_id': model_id,
                'name': name,
                'b1': sorted(b1),
                'b2': sorted(b2),
            })

    # Auto-detect number ranges from parsed predictions
    b1_max = max((max(p['b1']) for p in predictions), default=35)
    b2_max = max((max(p['b2']) for p in predictions), default=12)

    return predictions, b1_max, b2_max, pick_b1, pick_b2


# ════════════════════════════════════════════════════════════════════════
#  CONFIDENCE SCORING
# ════════════════════════════════════════════════════════════════════════

def _compute_confidence(
    position_details: Dict[str, Any],
    total_models: int,
    b1_max: int = 35,
    b2_max: int = 12,
    pick_b1: int = 4,
    pick_b2: int = 4,
) -> Dict[str, float]:
    """Compute prediction confidence scores for B1, B2, and overall.

    Confidence is based on:
    - How many models contributed data
    - How strong the consensus is (top vote ratio)
    - Top model accuracy at each position

    Args:
        position_details: dict with 'b1' and 'b2' sub-dicts containing
                         per-position analysis data
        total_models: total number of models in the predictions file
        b1_max: detected maximum number for Block 1
        b2_max: detected maximum number for Block 2
        pick_b1: numbers to pick from Block 1
        pick_b2: numbers to pick from Block 2

    Returns:
        dict with b1_score, b2_score, overall, consensus_strength (0.0-1.0)
    """
    b1_details = position_details.get('b1', {})
    b2_details = position_details.get('b2', {})

    # Model coverage factor: what fraction of models have useful data
    model_coverage = min(total_models / max(TOTAL_MODELS, 1), 1.0) if total_models > 0 else 0.0

    def _block_score(block_details: Dict, n_range: int, pick_count: int) -> float:
        """Compute confidence score for a single block."""
        if not block_details:
            return 0.0
        score = 0.0
        positions_found = 0
        for pos_name in [f'P{i}' for i in range(1, pick_count + 1)]:
            pos_data = block_details.get(pos_name, {})
            if not pos_data:
                continue
            positions_found += 1
            top_accuracy = pos_data.get('top_accuracy', 0)
            # Expected random accuracy for position: pick_count / n_range
            random_baseline = float(pick_count) / n_range
            # How much better than random
            accuracy_lift = min(top_accuracy / max(random_baseline, 0.01), 2.0) / 2.0

            votes = pos_data.get('votes', {})
            consensus = 0.0
            if votes:
                top_vote = max(votes.values())
                total_votes = sum(votes.values())
                if total_votes > 0:
                    consensus = top_vote / total_votes

            # Weighted combination: 40% consensus + 60% accuracy lift
            score += (1.0 / pick_count) * (0.4 * consensus + 0.6 * accuracy_lift)

        if positions_found == 0:
            return 0.0
        # Scale by position completeness
        completeness = positions_found / float(pick_count)
        return score * completeness

    b1_score = _block_score(b1_details, b1_max, pick_b1)
    b2_score = _block_score(b2_details, b2_max, pick_b2)

    # Overall: weighted average with model coverage
    overall = (b1_score + b2_score) / 2.0 * (0.7 + 0.3 * model_coverage)

    # Consensus strength: how much the models agree overall
    total_consensus = 0.0
    total_positions = 0
    for block_details, pick_count in [(b1_details, pick_b1), (b2_details, pick_b2)]:
        for pos_name in [f'P{i}' for i in range(1, pick_count + 1)]:
            pos_data = block_details.get(pos_name, {})
            votes = pos_data.get('votes', {})
            if votes:
                top_vote = max(votes.values())
                total_votes = sum(votes.values())
                if total_votes > 0:
                    total_consensus += top_vote / total_votes
                    total_positions += 1
    consensus_strength = total_consensus / max(total_positions, 1)

    return {
        'b1_score': min(b1_score, 1.0),
        'b2_score': min(b2_score, 1.0),
        'overall': min(overall, 1.0),
        'consensus_strength': min(consensus_strength, 1.0),
    }


# ════════════════════════════════════════════════════════════════════════
#  CORE: Recency-Weighted Position-Specific Ensemble
# ════════════════════════════════════════════════════════════════════════

def _compute_recency_model_accuracy(
    lpd_data: List[Dict],
    draw_type_filter: Optional[str] = None,
    recency_window: int = 200,
    b1_max: int = 35,
    b2_max: int = 12,
    pick_b1: int = 4,
    pick_b2: int = 4,
) -> Tuple[Dict, Dict]:
    """Compute recency-weighted position accuracy per model per block.

    Args:
        lpd_data: list of per-draw per-model position matches
        draw_type_filter: 'std', 'rng', or None (all types)
        recency_window: only consider this many most recent draws
        b1_max: detected maximum number for Block 1 (for position score scaling)
        b2_max: detected maximum number for Block 2 (for position score scaling)
        pick_b1: numbers to pick from Block 1
        pick_b2: numbers to pick from Block 2

    Returns:
        (model_b1_acc, model_b2_acc) where each is:
        {model_idx: {pos_hits: [...], total_hits, total_draws,
                     pos_scores: {1: score, 2: score, ...}}}
    """
    if not lpd_data:
        return {}, {}

    all_draw_nos = sorted(set(d['draw_no'] for d in lpd_data))
    if recency_window < len(all_draw_nos):
        recent_draws = set(all_draw_nos[-recency_window:])
    else:
        recent_draws = set(all_draw_nos)

    b1_acc = defaultdict(lambda: {'pos_hits': defaultdict(int), 'total_draws': 0})
    b2_acc = defaultdict(lambda: {'pos_hits': defaultdict(int), 'total_draws': 0})

    draws_seen = set()
    for entry in lpd_data:
        if entry['draw_no'] not in recent_draws:
            continue
        if draw_type_filter and entry['draw_type'] != draw_type_filter:
            continue

        mi = entry['model_idx']
        block = entry['block']
        positions = entry['positions']

        acc = b1_acc[mi] if block == 'b1' else b2_acc[mi]
        draws_seen.add((mi, block, entry['draw_no']))

        for pos in positions:
            acc['pos_hits'][pos] += 1

    for mi, block, _ in draws_seen:
        acc = b1_acc[mi] if block == 'b1' else b2_acc[mi]
        acc['total_draws'] += 1

    def _build_result(acc_dict: Dict, pick_count: int) -> Dict:
        """Build result dict from accumulated accuracy data."""
        output = {}
        for mi, data in acc_dict.items():
            total = data['total_draws']
            pos_scores = {}
            for pos in range(1, pick_count + 1):
                hits = data['pos_hits'].get(pos, 0)
                pos_scores[pos] = hits / max(total, 1)
            total_hits = sum(data['pos_hits'].get(p, 0) for p in range(1, pick_count + 1))

            pos_hits_list = [data['pos_hits'].get(i, 0) for i in range(1, pick_count + 1)]
            entry = {
                'pos_hits': pos_hits_list,
                'total_hits': total_hits,
                'total_draws': total,
                'pos_scores': pos_scores,
                'overall_rate': total_hits / max(total * pick_count, 1),
            }
            # Backward-compatible keys
            for i, hits in enumerate(pos_hits_list):
                entry[f'pos{i + 1}_hits'] = hits
            output[mi] = entry
        return output

    b1_result = _build_result(b1_acc, pick_b1)
    b2_result = _build_result(b2_acc, pick_b2)

    return b1_result, b2_result


def _select_position_number(
    predictions: List[Dict],
    model_accuracy: Dict,
    position: int,  # 0-based index
    block: str,     # 'b1' or 'b2'
    exclude: set,
    top_n: int = 30,
    b1_max: int = 35,
    b2_max: int = 12,
    pick_b1: int = 4,
    pick_b2: int = 4,
) -> Tuple[Optional[int], Dict]:
    """Select the best number for a specific sorted position.

    Uses position-specific accuracy combined with overall model quality.
    Recency-weighted: models accurate in recent draws get higher weight.

    Args:
        predictions: list of model prediction dicts
        model_accuracy: per-model accuracy dict from _compute_recency_model_accuracy
        position: 0-based position index
        block: 'b1' or 'b2'
        exclude: set of numbers already selected (to avoid duplicates)
        top_n: number of top models to consider
        b1_max: detected B1 range maximum
        b2_max: detected B2 range maximum
        pick_b1: numbers to pick from Block 1
        pick_b2: numbers to pick from Block 2
    """
    votes = defaultdict(float)

    pos_num = position + 1  # 1-based
    pos_total = b1_max if block == 'b1' else b2_max

    # Rank models by accuracy at this specific position
    scored_models = []
    for mi, acc_data in model_accuracy.items():
        if acc_data['total_draws'] == 0:
            continue
        pos_score = acc_data['pos_scores'].get(pos_num, 0.0)
        overall = acc_data['overall_rate']
        # Combined weight: 70% position-specific, 30% overall
        combined = 0.7 * pos_score + 0.3 * overall
        scored_models.append((mi, combined, pos_score, overall))

    scored_models.sort(key=lambda x: -x[1])
    top_models = scored_models[:top_n]

    # Build prediction lookup: model_idx -> prediction
    pred_by_idx = {}
    for pred in predictions:
        mid = pred['model_id']
        try:
            idx = int(mid[1:]) - 1  # p1 -> 0, p2 -> 1, etc.
            # Validate numbers are within detected range
            pred_b1 = pred.get('b1', [])
            pred_b2 = pred.get('b2', [])
            if any(n < 1 or n > b1_max for n in pred_b1):
                continue
            if any(n < 1 or n > b2_max for n in pred_b2):
                continue
            pred_by_idx[idx] = pred
        except (ValueError, IndexError):
            pass

    for mi, combined, pos_score, overall in top_models:
        if mi not in pred_by_idx:
            continue
        pred = pred_by_idx[mi]
        pred_block = pred.get(block, [])
        if position >= len(pred_block):
            continue
        num = pred_block[position]
        if num in exclude:
            continue
        if num < 1 or num > pos_total:
            continue
        w = max(combined, 0.005)
        votes[num] += w

    if not votes:
        # Fallback: use all predictions with detected range
        for pred in predictions:
            pred_block = pred.get(block, [])
            if position >= len(pred_block):
                continue
            num = pred_block[position]
            if num in exclude:
                continue
            if num < 1 or num > pos_total:
                continue
            votes[num] += 0.005

    if not votes:
        return None, {}

    best_num = max(votes, key=votes.get)
    return best_num, dict(votes)


def _run_prediction(
    predictions: List[Dict],
    report: Dict[str, Any],
    top_models: int = 30,
    recency_window: int = 200,
    draw_type: Optional[str] = None,
    b1_max: int = 35,
    b2_max: int = 12,
    pick_b1: int = 4,
    pick_b2: int = 4,
) -> Dict[str, Any]:
    """Internal prediction engine (no dual-mode recursion).

    Runs the core position-specific ensemble algorithm to produce
    a single set of predictions. Used by both the main analyze_and_predict
    and the dual-mode STD/RNG wrapper.

    Args:
        predictions: list of model prediction dicts
        report: parsed HTML report dict
        top_models: how many top models per position
        recency_window: how many recent draws to weight
        draw_type: 'std', 'rng', or None (all types)
        b1_max: detected B1 range maximum
        b2_max: detected B2 range maximum
        pick_b1: numbers to pick from Block 1
        pick_b2: numbers to pick from Block 2

    Returns:
        dict with final_b1, final_b2, position_details, confidence, error
    """
    result = {
        'final_b1': [],
        'final_b2': [],
        'b1_max': b1_max,
        'b2_max': b2_max,
        'position_details': {},
        'confidence': {
            'b1_score': 0.0,
            'b2_score': 0.0,
            'overall': 0.0,
            'consensus_strength': 0.0,
        },
        'total_models': len(predictions),
        'draw_type_used': draw_type or 'all',
        'error': None,
    }

    if not predictions:
        result['error'] = 'No predictions found'
        return result

    # 1. Compute recency-weighted accuracy
    b1_acc, b2_acc = _compute_recency_model_accuracy(
        report.get('lpd_data', []),
        draw_type_filter=draw_type,
        recency_window=recency_window,
        b1_max=b1_max,
        b2_max=b2_max,
        pick_b1=pick_b1,
        pick_b2=pick_b2,
    )

    # Fall back to table data if no LPD_DATA
    total_draws_report = max(int(report['summary'].get('Total Draws Analyzed', '0')), 1)
    if not b1_acc and report.get('model_b1'):
        for mid, data in report['model_b1'].items():
            try:
                mi = int(mid[1:]) - 1
                pos_hits = data.get('pos_hits', [])
                pos_scores = {}
                for i, hits in enumerate(pos_hits):
                    pos_scores[i + 1] = hits / max(total_draws_report, 1)
                b1_acc[mi] = {
                    'pos_hits': pos_hits,
                    'total_hits': data['total_hits'],
                    'total_draws': total_draws_report,
                    'pos_scores': pos_scores,
                    'overall_rate': data['total_hits'] / max(total_draws_report * pick_b1, 1),
                }
                # Backward-compatible keys
                for i, hits in enumerate(pos_hits):
                    b1_acc[mi][f'pos{i + 1}_hits'] = hits
            except (ValueError, KeyError):
                pass

    if not b2_acc and report.get('model_b2'):
        for mid, data in report['model_b2'].items():
            try:
                mi = int(mid[1:]) - 1
                pos_hits = data.get('pos_hits', [])
                pos_scores = {}
                for i, hits in enumerate(pos_hits):
                    pos_scores[i + 1] = hits / max(total_draws_report, 1)
                b2_acc[mi] = {
                    'pos_hits': pos_hits,
                    'total_hits': data['total_hits'],
                    'total_draws': total_draws_report,
                    'pos_scores': pos_scores,
                    'overall_rate': data['total_hits'] / max(total_draws_report * pick_b2, 1),
                }
                # Backward-compatible keys
                for i, hits in enumerate(pos_hits):
                    b2_acc[mi][f'pos{i + 1}_hits'] = hits
            except (ValueError, KeyError):
                pass

    # 2. Position-Specific Ensemble for B1
    final_b1 = []
    b1_used = set()
    b1_details = {}

    for pos_idx in range(pick_b1):
        pos_num = pos_idx + 1
        best_num, votes = _select_position_number(
            predictions, b1_acc, pos_idx, 'b1', b1_used, top_models,
            b1_max=b1_max, b2_max=b2_max, pick_b1=pick_b1, pick_b2=pick_b2,
        )
        if best_num is not None:
            final_b1.append(best_num)
            b1_used.add(best_num)
            sorted_votes = sorted(votes.items(), key=lambda x: -x[1])[:5]
            top_model = max(b1_acc.items(),
                            key=lambda x: x[1]['pos_scores'].get(pos_num, 0)) if b1_acc else (0, {'pos_scores': {}})
            top_acc = top_model[1]['pos_scores'].get(pos_num, 0) if isinstance(top_model[1], dict) else 0
            b1_details[f'P{pos_num}'] = {
                'selected': best_num,
                'votes': dict(sorted_votes),
                'top_model': f'p{top_model[0] + 1}',
                'top_accuracy': top_acc,
            }
        else:
            # Fallback: pick first available number from predictions
            for pred in predictions:
                pb1 = pred.get('b1', [])
                if pos_idx < len(pb1) and pb1[pos_idx] not in b1_used:
                    if 1 <= pb1[pos_idx] <= b1_max:
                        final_b1.append(pb1[pos_idx])
                        b1_used.add(pb1[pos_idx])
                        b1_details[f'P{pos_num}'] = {
                            'selected': pb1[pos_idx],
                            'votes': {pb1[pos_idx]: 0.005},
                            'top_model': 'fallback',
                            'top_accuracy': 0.0,
                        }
                        break

    final_b1 = sorted(final_b1)
    result['final_b1'] = final_b1

    # 3. Position-Specific Ensemble for B2
    final_b2 = []
    b2_used = set(final_b1)  # Exclude B1 numbers
    b2_details = {}

    for pos_idx in range(pick_b2):
        pos_num = pos_idx + 1
        best_num, votes = _select_position_number(
            predictions, b2_acc, pos_idx, 'b2', b2_used, top_models,
            b1_max=b1_max, b2_max=b2_max, pick_b1=pick_b1, pick_b2=pick_b2,
        )
        if best_num is not None:
            final_b2.append(best_num)
            b2_used.add(best_num)
            sorted_votes = sorted(votes.items(), key=lambda x: -x[1])[:5]
            top_model = max(b2_acc.items(),
                            key=lambda x: x[1]['pos_scores'].get(pos_num, 0)) if b2_acc else (0, {'pos_scores': {}})
            top_acc = top_model[1]['pos_scores'].get(pos_num, 0) if isinstance(top_model[1], dict) else 0
            b2_details[f'P{pos_num}'] = {
                'selected': best_num,
                'votes': dict(sorted_votes),
                'top_model': f'p{top_model[0] + 1}',
                'top_accuracy': top_acc,
            }
        else:
            for pred in predictions:
                pb2 = pred.get('b2', [])
                if pos_idx < len(pb2) and pb2[pos_idx] not in b2_used:
                    if 1 <= pb2[pos_idx] <= b2_max:
                        final_b2.append(pb2[pos_idx])
                        b2_used.add(pb2[pos_idx])
                        b2_details[f'P{pos_num}'] = {
                            'selected': pb2[pos_idx],
                            'votes': {pb2[pos_idx]: 0.005},
                            'top_model': 'fallback',
                            'top_accuracy': 0.0,
                        }
                        break

    final_b2 = sorted(final_b2)
    result['final_b2'] = final_b2
    result['position_details'] = {'b1': b1_details, 'b2': b2_details}

    # 4. Compute confidence scores
    result['confidence'] = _compute_confidence(
        result['position_details'], len(predictions),
        b1_max=b1_max, b2_max=b2_max,
        pick_b1=pick_b1, pick_b2=pick_b2,
    )

    # Summary fields
    result['models_with_b1_data'] = len(b1_acc)
    result['models_with_b2_data'] = len(b2_acc)
    result['recency_window'] = recency_window
    result['pick_b1'] = pick_b1
    result['pick_b2'] = pick_b2

    return result


def analyze_and_predict(
    html_path: str,
    csv_path: str,
    top_models: int = 30,
    recency_window: int = 200,
    draw_type: Optional[str] = None,
    _allow_dual: bool = True,
    pick_b1: Optional[int] = None,
    pick_b2: Optional[int] = None,
) -> Dict[str, Any]:
    """Main analysis: parse report + predictions, produce final prediction.

    Algorithm:
    1. Parse report.html for per-model accuracy (from tables + LPD_DATA)
    2. Parse predictions.csv for model predictions (auto-detect ranges & pick counts)
    3. Compute recency-weighted model accuracy from LPD_DATA
    4. For each block (B1, B2), for each position (P1..Pn):
       a. Rank models by recency-weighted position accuracy
       b. Take predictions from top N models
       c. Weight by combined position + overall accuracy
       d. Select number with highest weighted vote
    5. Ensure no overlap between B1 and B2
    6. Compute confidence scores
    7. Optionally produce dual STD/RNG predictions

    Args:
        html_path: path to report.html
        csv_path: path to predictions.csv
        top_models: how many top models per position
        recency_window: how many recent draws to weight
        draw_type: 'std', 'rng', or None (auto-detect from last draw)
        _allow_dual: internal flag to prevent infinite recursion in dual-mode
        pick_b1: override for numbers to pick from Block 1 (None = auto-detect)
        pick_b2: override for numbers to pick from Block 2 (None = auto-detect)

    Returns:
        dict with final_b1, final_b2, b1_max, b2_max, confidence,
        position_details, total_models, draw_type_used, error,
        and optionally std_prediction, rng_prediction
    """
    # Default result structure
    result = {
        'final_b1': [],
        'final_b2': [],
        'b1_max': 35,
        'b2_max': 12,
        'confidence': {
            'b1_score': 0.0,
            'b2_score': 0.0,
            'overall': 0.0,
            'consensus_strength': 0.0,
        },
        'position_details': {},
        'total_models': 0,
        'draw_type_used': draw_type or 'all',
        'error': None,
    }

    try:
        # 1. Parse inputs
        report = parse_html_report(html_path)
        predictions, b1_max, b2_max, csv_pick_b1, csv_pick_b2 = parse_predictions_csv(csv_path)

        # Determine pick counts: CLI override > CSV auto-detect > global defaults
        effective_pick_b1 = pick_b1 if pick_b1 is not None else csv_pick_b1
        effective_pick_b2 = pick_b2 if pick_b2 is not None else csv_pick_b2

        if not predictions:
            result['error'] = 'No predictions found in predictions.csv'
            return result

        result['total_models'] = len(predictions)
        result['b1_max'] = b1_max
        result['b2_max'] = b2_max
        result['pick_b1'] = effective_pick_b1
        result['pick_b2'] = effective_pick_b2

        # 2. Run main prediction (all draw types combined)
        result = _run_prediction(
            predictions, report,
            top_models=top_models,
            recency_window=recency_window,
            draw_type=draw_type,
            b1_max=b1_max,
            b2_max=b2_max,
            pick_b1=effective_pick_b1,
            pick_b2=effective_pick_b2,
        )

        # 3. Dual-mode: separate STD and RNG predictions
        if _allow_dual and draw_type is None and report.get('lpd_data'):
            # Check if there are both STD and RNG draws
            draw_types = set(d['draw_type'] for d in report['lpd_data'])
            has_std = 'std' in draw_types
            has_rng = 'rng' in draw_types

            if has_std:
                std_result = _run_prediction(
                    predictions, report,
                    top_models=top_models,
                    recency_window=recency_window,
                    draw_type='std',
                    b1_max=b1_max,
                    b2_max=b2_max,
                    pick_b1=effective_pick_b1,
                    pick_b2=effective_pick_b2,
                )
                result['std_prediction'] = {
                    'b1': std_result.get('final_b1', []),
                    'b2': std_result.get('final_b2', []),
                    'confidence': std_result.get('confidence', {}),
                }

            if has_rng:
                rng_result = _run_prediction(
                    predictions, report,
                    top_models=top_models,
                    recency_window=recency_window,
                    draw_type='rng',
                    b1_max=b1_max,
                    b2_max=b2_max,
                    pick_b1=effective_pick_b1,
                    pick_b2=effective_pick_b2,
                )
                result['rng_prediction'] = {
                    'b1': rng_result.get('final_b1', []),
                    'b2': rng_result.get('final_b2', []),
                    'confidence': rng_result.get('confidence', {}),
                }

    except FileNotFoundError as ex:
        result['error'] = f'File not found: {ex}'
    except Exception as ex:
        result['error'] = f'Analysis error: {ex}'

    return result


# ════════════════════════════════════════════════════════════════════════
#  FORMATTING: Print results
# ════════════════════════════════════════════════════════════════════════

def print_result(result: Dict[str, Any]):
    """Pretty-print the analysis result with confidence scores."""
    if result.get('error'):
        print(f"ERROR: {result['error']}")
        return

    pick_b1 = result.get('pick_b1', PICK_B1)
    pick_b2 = result.get('pick_b2', PICK_B2)

    print("\n" + "=" * 60)
    print("  LOTTERY PIPELINE v11.1 -- FINAL PREDICTION")
    print("=" * 60)

    b1 = result['final_b1']
    b2 = result['final_b2']
    confidence = result.get('confidence', {})

    b1_conf = confidence.get('b1_score', 0)
    b2_conf = confidence.get('b2_score', 0)
    overall_conf = confidence.get('overall', 0)
    consensus = confidence.get('consensus_strength', 0)
    b1_max = result.get('b1_max', 35)
    b2_max = result.get('b2_max', 12)

    if b1 and b2:
        dt = result.get('draw_type_used', 'all')
        print(f"\n  DRAW TYPE FILTER: {dt}")
        print(f"  PICK FORMAT:      {pick_b1}x{pick_b2}")
        print(f"  RECENCY WINDOW:   {result.get('recency_window', 200)} draws")
        print(f"  NUMBER RANGES:    B1=1-{b1_max}, B2=1-{b2_max}")
        print(f"\n  FINAL PREDICTION:")
        print(f"  Block 1: {', '.join(map(str, b1))}  (confidence: {b1_conf*100:.1f}%)")
        print(f"  Block 2: {', '.join(map(str, b2))}  (confidence: {b2_conf*100:.1f}%)")
        print(f"  FULL:    {', '.join(map(str, b1))} | {', '.join(map(str, b2))}")
        print(f"\n  OVERALL CONFIDENCE: {overall_conf*100:.1f}%  "
              f"(consensus: {consensus*100:.1f}%)")

    # Dual-mode predictions
    std_pred = result.get('std_prediction')
    rng_pred = result.get('rng_prediction')

    if std_pred or rng_pred:
        print(f"\n  DUAL-MODE PREDICTIONS:")
        if std_pred:
            sb1 = std_pred.get('b1', [])
            sb2 = std_pred.get('b2', [])
            sc = std_pred.get('confidence', {})
            print(f"  STD:  {', '.join(map(str, sb1))} | {', '.join(map(str, sb2))}  "
                  f"(conf: {sc.get('overall', 0)*100:.1f}%)")
        if rng_pred:
            rb1 = rng_pred.get('b1', [])
            rb2 = rng_pred.get('b2', [])
            rc = rng_pred.get('confidence', {})
            print(f"  RNG:  {', '.join(map(str, rb1))} | {', '.join(map(str, rb2))}  "
                  f"(conf: {rc.get('overall', 0)*100:.1f}%)")

    details = result.get('position_details', {})
    if details:
        print(f"\n  POSITION ANALYSIS:")
        for block_name, block_label, pick_count in [('b1', 'Block 1', pick_b1), ('b2', 'Block 2', pick_b2)]:
            block_data = details.get(block_name, {})
            if block_data:
                print(f"\n  --- {block_label} ---")
                for pos_name in [f'P{i}' for i in range(1, pick_count + 1)]:
                    pos_data = block_data.get(pos_name, {})
                    selected = pos_data.get('selected', '?')
                    top_model = pos_data.get('top_model', '?')
                    top_acc = pos_data.get('top_accuracy', 0)
                    votes = pos_data.get('votes', {})
                    print(f"  {pos_name}: number {selected:>2} "
                          f"(best model: {top_model}, "
                          f"pos accuracy: {top_acc*100:.1f}%)")
                    sorted_v = sorted(votes.items(), key=lambda x: -x[1])[:3]
                    if sorted_v:
                        candidates = ', '.join(f"{n}({v:.3f})" for n, v in sorted_v)
                        print(f"         Candidates: {candidates}")

    print(f"\n  Total models: {result.get('total_models', 0)}")
    print(f"  Models with B1 data: {result.get('models_with_b1_data', 0)}")
    print(f"  Models with B2 data: {result.get('models_with_b2_data', 0)}")
    print("\n" + "=" * 60)


# ════════════════════════════════════════════════════════════════════════
#  CLI INTERFACE
# ════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Lottery Pipeline v11.1 -- Adaptive Model Analyzer & Final Predictor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python lottery_pipeline.py --html report.html --csv predictions.csv
  python lottery_pipeline.py --html report.html --csv predictions.csv --type std
  python lottery_pipeline.py --html report.html --csv predictions.csv --type rng
  python lottery_pipeline.py --html report.html --csv predictions.csv --min-confidence 0.3
  python lottery_pipeline.py --html report.html --csv predictions.csv --pick-b1 5 --pick-b2 3

Output:
  B1: [n1, n2, ...]  (confidence: XX%)
  B2: [n(n+1), n(n+2), ...]  (confidence: XX%)
        """
    )
    parser.add_argument('--html', type=str, required=True,
                        help='Path to report.html')
    parser.add_argument('--csv', type=str, required=True,
                        help='Path to predictions.csv')
    parser.add_argument('--top', type=int, default=30,
                        help='Top models per position (default: 30)')
    parser.add_argument('--recency', type=int, default=200,
                        help='Recency window in draws (default: 200)')
    parser.add_argument('--type', type=str, default=None,
                        choices=['std', 'rng'],
                        help='Filter by draw type (std/rng)')
    parser.add_argument('--min-confidence', type=float, default=0.0,
                        help='Minimum confidence threshold (0.0-1.0)')
    parser.add_argument('--output', type=str, default=None,
                        help='Save result as JSON')
    parser.add_argument('--pick-b1', type=int, default=None,
                        help='Numbers per Block 1 (default: auto-detect from CSV)')
    parser.add_argument('--pick-b2', type=int, default=None,
                        help='Numbers per Block 2 (default: auto-detect from CSV)')

    args = parser.parse_args()

    print(f"Lottery Pipeline v11.1")
    print(f"Report: {args.html}")
    print(f"Predictions: {args.csv}")
    if args.pick_b1 is not None or args.pick_b2 is not None:
        print(f"Pick format override: B1={args.pick_b1}, B2={args.pick_b2}")
    if args.type:
        print(f"Draw type filter: {args.type}")
    if args.min_confidence > 0:
        print(f"Minimum confidence: {args.min_confidence*100:.1f}%")

    result = analyze_and_predict(
        args.html, args.csv,
        top_models=args.top,
        recency_window=args.recency,
        draw_type=args.type,
        pick_b1=args.pick_b1,
        pick_b2=args.pick_b2,
    )

    print_result(result)

    # Check confidence threshold
    if args.min_confidence > 0 and not result.get('error'):
        overall = result.get('confidence', {}).get('overall', 0)
        if overall < args.min_confidence:
            print(f"\n  WARNING: Overall confidence ({overall*100:.1f}%) "
                  f"is below threshold ({args.min_confidence*100:.1f}%)")
            print(f"  Consider using draw-type-specific predictions (--type std or --type rng)")

    if args.output and not result.get('error'):
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nResult saved to: {args.output}")


if __name__ == '__main__':
    main()
