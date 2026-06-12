#!/usr/bin/env python3
"""
Step-by-step lottery analysis engine.
v36.0 — Sequential predictions on historical draws with comprehensive report.

Algorithm (N=5, total=1000):
  Step 1: Train on 1-995, predict #996, compare with real #996
  Step 2: Train on 1-996, predict #997, compare with real #997
  ...
  Step 5: Train on 1-999, predict #1000, compare with real #1000
  Final:  Train on 1-1000, predict #1001 (no real data)

Key performance: bulk train on first (total-N) draws, then incremental
update([draw]) per step (~10x speedup vs re-training from scratch).
"""

import argparse
import json
import math
import sys
import os
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════════════════════════════════════════
#  MOCK STREAMLIT MODULE (must be done BEFORE importing lp_v130_app)
# ═══════════════════════════════════════════════════════════════════════════
from _streamlit_mock import st_mock  # noqa: E402

from lp_v130_app import (
    LP132, DualBayesRing, parse_text,
    GAME_FORMAT_HINTS, B1_MAX, B2_MAX, TOTAL_MODELS,
    _fast_pred,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def compute_hits(pred_b1, pred_b2, act_b1, act_b2):
    """Count matching numbers between prediction and actual."""
    h1 = len(set(pred_b1) & set(act_b1))
    h2 = len(set(pred_b2) & set(act_b2)) if act_b2 else 0
    return h1, h2, h1 + h2


def safe_prediction(predictor, bayes, draw_type='all'):
    """Get prediction with multiple fallback strategies."""
    # Strategy 1: Weighted consensus via _fast_pred
    try:
        pred = _fast_pred(predictor, bayes, draw_type)
        if pred and isinstance(pred, tuple) and len(pred) == 2:
            b1, b2 = pred
            if b1 and len(b1) > 0:
                return list(b1), list(b2) if b2 else []
    except Exception:
        pass

    # Strategy 2: Regular consensus
    try:
        pred = predictor.consensus(draw_type=draw_type)
        if pred and isinstance(pred, tuple) and len(pred) == 2:
            b1, b2 = pred
            if b1 and len(b1) > 0:
                return list(b1), list(b2) if b2 else []
    except Exception:
        pass

    # v35.2.0: Strategy 3: Top-voted numbers from all_predictions
    try:
        all_p = predictor.all_predictions()
        if all_p and len(all_p) > 0:
            b1_votes = defaultdict(float)
            b2_votes = defaultdict(float)
            n_valid = 0
            for b1, b2 in all_p:
                if b1 and len(b1) > 0:
                    n_valid += 1
                    for x in b1:
                        b1_votes[x] += 1.0
                    if b2:
                        for x in b2:
                            b2_votes[x] += 1.0
            if n_valid > 0 and b1_votes:
                from lp_v130_app import PICK_B1, PICK_B2
                top_b1 = sorted(b1_votes, key=b1_votes.get, reverse=True)[:PICK_B1]
                top_b2 = sorted(b2_votes, key=b2_votes.get, reverse=True)[:PICK_B2] if b2_votes else []
                return sorted(top_b1), sorted(top_b2)
    except Exception:
        pass

    return [], []


def compute_consensus_info(predictor, draw_type='all'):
    """Compute consensus strength, model count, and top voted numbers."""
    try:
        all_p = predictor.all_predictions()
        valid = [(i, b1, b2) for i, (b1, b2) in enumerate(all_p) if b1 and len(b1) > 0]
        if not valid:
            return 0, 0, 0, [], []

        n_models = len(valid)

        # Block 1 votes
        b1_votes = defaultdict(float)
        for i, b1, b2 in valid:
            for x in b1:
                b1_votes[x] += 1.0
        top_b1 = sorted(b1_votes, key=b1_votes.get, reverse=True)
        cons_b1 = b1_votes[top_b1[0]] / n_models if top_b1 else 0

        # Block 2 votes
        b2_votes = defaultdict(float)
        for i, b1, b2 in valid:
            if b2:
                for x in b2:
                    b2_votes[x] += 1.0
        top_b2 = sorted(b2_votes, key=b2_votes.get, reverse=True)
        cons_b2 = b2_votes[top_b2[0]] / n_models if top_b2 else 0

        return round(cons_b1, 3), round(cons_b2, 3), n_models, top_b1[:10], top_b2[:10]
    except Exception:
        return 0, 0, TOTAL_MODELS, [], []


def compute_consistency(hits_list):
    """Compute consistency score (0..1). High = stable hits, low = erratic."""
    if len(hits_list) < 2:
        return 0.5
    mean = sum(hits_list) / len(hits_list)
    if mean == 0:
        return 1.0  # All zeros is perfectly consistent
    variance = sum((h - mean) ** 2 for h in hits_list) / len(hits_list)
    std = math.sqrt(variance)
    # Coefficient of variation, inverted and scaled to 0..1
    cv = std / mean if mean > 0 else 0
    # Map: cv=0 -> 1.0, cv=1.0 -> 0.3, cv>=2.0 -> 0.0
    consistency = max(0.0, min(1.0, 1.0 - cv * 0.7))
    return round(consistency, 2)


def compute_trend(hits_list):
    """Determine trend: improving, declining, or stable."""
    if len(hits_list) < 3:
        return "insufficient_data"
    mid = len(hits_list) // 2
    first_half_avg = sum(hits_list[:mid]) / mid
    second_half_avg = sum(hits_list[mid:]) / (len(hits_list) - mid)
    diff = second_half_avg - first_half_avg
    if diff > 0.3:
        return "improving"
    elif diff < -0.3:
        return "declining"
    else:
        return "stable"


def find_most_reliable_numbers(steps_results, final_pred_b1, final_pred_b2):
    """
    Identify most reliable predicted numbers: those that appear consistently
    in top predictions across steps AND are in the final prediction.
    """
    # Count how many times each number appears in predictions across steps
    b1_appearances = defaultdict(float)
    b2_appearances = defaultdict(float)
    b1_weighted_score = defaultdict(float)
    b2_weighted_score = defaultdict(float)

    for sr in steps_results:
        weight = 1.0 + (sr["hits"]["total"] * 0.2)
        for x in sr["predicted"]["block1"]:
            b1_appearances[x] += 1
            b1_weighted_score[x] += weight
        for x in sr["predicted"]["block2"]:
            b2_appearances[x] += 1
            b2_weighted_score[x] += weight

    n_steps = len(steps_results)

    # Numbers that appear in the final prediction AND are frequent across steps
    reliable_b1 = []
    final_b1_set = set(final_pred_b1)
    for num in final_b1_set:
        freq = b1_appearances.get(num, 0) / n_steps  # 0..1
        score = b1_weighted_score.get(num, 0)
        reliable_b1.append((num, round(freq, 3), round(score, 2)))

    # Sort by weighted score descending, take all that appeared in >=50% of steps
    reliable_b1.sort(key=lambda x: x[2], reverse=True)
    reliable_b1 = [num for num, freq, score in reliable_b1 if freq >= 0.5 or score >= n_steps * 0.8]

    reliable_b2 = []
    final_b2_set = set(final_pred_b2)
    for num in final_b2_set:
        freq = b2_appearances.get(num, 0) / n_steps if n_steps > 0 else 0
        score = b2_weighted_score.get(num, 0)
        reliable_b2.append((num, round(freq, 3), round(score, 2)))

    reliable_b2.sort(key=lambda x: x[2], reverse=True)
    reliable_b2 = [num for num, freq, score in reliable_b2 if freq >= 0.5 or score >= n_steps * 0.8]

    return sorted(reliable_b1), sorted(reliable_b2)


def compute_reliability_score(steps_results, final_pred_b1, final_pred_b2, consistency):
    """Compute overall reliability score (0..1) for the final prediction."""
    if not steps_results:
        return 0.0

    all_hits = [s["hits"]["total"] for s in steps_results]
    avg_hits = sum(all_hits) / len(all_hits)
    max_hits = max(all_hits) if all_hits else 0

    # Base: average hit rate normalized to ~0..0.5
    total_nums = len(steps_results[0]["actual"]["block1"]) + len(steps_results[0]["actual"]["block2"])
    hit_rate = avg_hits / max(total_nums, 1)

    # Consistency bonus (0..0.2)
    consistency_bonus = consistency * 0.2

    # Trend bonus (0..0.15)
    trend = compute_trend(all_hits)
    trend_bonus = {"improving": 0.15, "stable": 0.08, "declining": 0.02, "insufficient_data": 0.05}
    trend_bonus_val = trend_bonus.get(trend, 0.05)

    # Reliable numbers bonus (0..0.15)
    rel_b1, rel_b2 = find_most_reliable_numbers(steps_results, final_pred_b1, final_pred_b2)
    n_reliable = len(rel_b1) + len(rel_b2)
    n_total_pred = len(final_pred_b1) + len(final_pred_b2)
    reliable_ratio = n_reliable / max(n_total_pred, 1)
    reliable_bonus = reliable_ratio * 0.15

    score = hit_rate + consistency_bonus + trend_bonus_val + reliable_bonus
    return round(min(score, 1.0), 2)


# ── Main analysis function ──────────────────────────────────────────────

def run_step_analysis(draws, n_steps=5):
    """Run step-by-step analysis on historical draws."""
    total = len(draws)
    if total < n_steps + 20:
        return {"status": "error", "error": f"Недостаточно тиражей ({total}). Нужно минимум {n_steps + 20}."}

    # Detect game format from draws
    all_b1 = [x for d in draws for x in d.block1]
    all_b2 = [x for d in draws for x in d.block2]
    detected_b1_max = max(all_b1) if all_b1 else B1_MAX
    detected_b2_max = max(all_b2) if all_b2 else 0

    # Create predictor and bayes
    predictor = LP132()
    bayes = DualBayesRing(n=TOTAL_MODELS)

    train_end = total - n_steps  # Index of first test draw

    # ── Phase 1: Bulk training ─────────────────────────────────────────
    print(f"[progress] Bulk training: 0/{train_end}", file=sys.stderr)
    training_draws = draws[:train_end]
    predictor.update(training_draws)

    # Bayes warm-up: only 3 iterations (not 10) for speed
    for i in range(min(3, len(training_draws) - 1)):
        d = training_draws[-(i + 1)]
        try:
            preds = predictor.all_predictions()
            bayes.update(preds, list(d.block1), list(d.block2), draw_type=d.draw_type)
        except Exception:
            pass

    print(f"[progress] Training complete: {train_end} draws", file=sys.stderr)

    # ── Phase 2: Step-by-step predictions ──────────────────────────────
    steps = []
    hit_distribution = defaultdict(int)
    prev_pred_b1 = []
    prev_pred_b2 = []

    for step_idx in range(n_steps):
        draw_idx = train_end + step_idx
        actual_draw = draws[draw_idx]
        draw_type = getattr(actual_draw, 'draw_type', 'all')

        # v35.2.0: Wrap each step in try-except to prevent one bad step from crashing all
        try:
            # Get prediction (using predictor trained on draws[:draw_idx])
            pred_b1, pred_b2 = safe_prediction(predictor, bayes, draw_type)

            # Compute hits
            act_b1 = list(actual_draw.block1) if actual_draw.block1 else []
            act_b2 = list(actual_draw.block2) if actual_draw.block2 else []
            hits_b1, hits_b2, hits_total = compute_hits(pred_b1, pred_b2, act_b1, act_b2)
            hit_distribution[str(hits_total)] += 1

            # Consensus info
            cons_b1, cons_b2, models_used, top_b1, top_b2 = compute_consensus_info(predictor, draw_type)

            # Comparison with previous step
            comparison = None
            if prev_pred_b1:
                overlap_b1 = len(set(pred_b1) & set(prev_pred_b1))
                overlap_b2 = len(set(pred_b2) & set(prev_pred_b2))
                new_b1 = [x for x in pred_b1 if x not in set(prev_pred_b1)]
                new_b2 = [x for x in pred_b2 if x not in set(prev_pred_b2)]
                comparison = {
                    "overlap_with_prev": {"block1": overlap_b1, "block2": overlap_b2},
                    "new_numbers": {"block1": sorted(new_b1), "block2": sorted(new_b2)},
                }

            # Hit positions (which predicted numbers matched and at what index)
            hit_positions_b1 = []
            act_b1_set = set(act_b1)
            for idx, x in enumerate(pred_b1):
                if x in act_b1_set:
                    hit_positions_b1.append(idx + 1)  # 1-based position

            step_result = {
                "step": step_idx + 1,
                "draw_no": actual_draw.draw_no,
                "trained_on": draw_idx,  # Number of draws used for training
                "predicted": {"block1": sorted(pred_b1), "block2": sorted(pred_b2)},
                "actual": {"block1": sorted(act_b1), "block2": sorted(act_b2)},
                "hits": {"block1": hits_b1, "block2": hits_b2, "total": hits_total},
                "confidence": {"block1": cons_b1, "block2": cons_b2},
                "models_used": models_used,
                "top_numbers": {"block1": top_b1, "block2": top_b2},
                "comparison": comparison,
                "hit_positions": hit_positions_b1,
            }
            steps.append(step_result)

            prev_pred_b1 = pred_b1
            prev_pred_b2 = pred_b2

            print(f"[progress] Step {step_idx+1}/{n_steps}: draw #{actual_draw.draw_no}, hits={hits_total} (B1:{hits_b1} B2:{hits_b2})", file=sys.stderr)

            # Update bayes with accuracy
            try:
                preds = predictor.all_predictions()
                bayes.update(preds, act_b1, act_b2, draw_type=draw_type)
            except Exception:
                pass

            # INCREMENTAL update: only add the one new draw (~10x faster)
            predictor.update([draws[draw_idx]])
        except Exception as e:
            print(f"[warn] Step {step_idx+1} failed: {e}, continuing...", file=sys.stderr)
            # Add a zero-hit step to keep step count consistent
            act_b1 = list(actual_draw.block1) if actual_draw.block1 else []
            act_b2 = list(actual_draw.block2) if actual_draw.block2 else []
            steps.append({
                "step": step_idx + 1,
                "draw_no": actual_draw.draw_no,
                "trained_on": draw_idx,
                "predicted": {"block1": [], "block2": []},
                "actual": {"block1": sorted(act_b1), "block2": sorted(act_b2)},
                "hits": {"block1": 0, "block2": 0, "total": 0},
                "confidence": {"block1": 0, "block2": 0},
                "models_used": 0,
                "top_numbers": {"block1": [], "block2": []},
                "comparison": None,
                "hit_positions": [],
            })
            # Still update predictor with this draw
            try:
                predictor.update([draws[draw_idx]])
            except Exception:
                pass

    # ── Phase 3: Final prediction on ALL draws ────────────────────────
    final_pred_b1, final_pred_b2 = safe_prediction(predictor, bayes, 'all')
    final_cons_b1, final_cons_b2, _, final_top_b1, final_top_b2 = compute_consensus_info(predictor, 'all')

    # ── Phase 4: Build summary ────────────────────────────────────────
    all_hits = [s["hits"]["total"] for s in steps]
    avg_hits = sum(all_hits) / len(all_hits) if all_hits else 0
    max_hits_val = max(all_hits) if all_hits else 0
    min_hits_val = min(all_hits) if all_hits else 0
    median_hits = sorted(all_hits)[len(all_hits) // 2] if all_hits else 0
    trend = compute_trend(all_hits)
    consistency = compute_consistency(all_hits)

    # ── Phase 5: Final forecast analysis ──────────────────────────────
    most_reliable_b1, most_reliable_b2 = find_most_reliable_numbers(
        steps, final_pred_b1, final_pred_b2
    )
    reliability_score = compute_reliability_score(
        steps, final_pred_b1, final_pred_b2, consistency
    )

    # Expected hits based on step results
    expected_hits = {
        "avg": round(avg_hits, 1),
        "median": median_hits,
        "min": min_hits_val,
        "max": max_hits_val,
    }

    # Strongest numbers across all steps (weighted by hit success)
    success_weight_b1 = defaultdict(float)
    success_weight_b2 = defaultdict(float)
    for s in steps:
        weight = 1.0 + (s["hits"]["total"] / max(max_hits_val, 1))
        for x in s["predicted"]["block1"]:
            success_weight_b1[x] += weight
        for x in s["predicted"]["block2"]:
            success_weight_b2[x] += weight

    strongest_b1 = sorted(success_weight_b1, key=success_weight_b1.get, reverse=True)[:10]
    strongest_b2 = sorted(success_weight_b2, key=success_weight_b2.get, reverse=True)[:5]

    # Consensus numbers: numbers that appear in ALL step predictions
    all_pred_b1_sets = [set(s["predicted"]["block1"]) for s in steps]
    all_pred_b2_sets = [set(s["predicted"]["block2"]) for s in steps if s["predicted"]["block2"]]
    consensus_numbers_b1 = set.intersection(*all_pred_b1_sets) if all_pred_b1_sets else set()
    consensus_numbers_b2 = set.intersection(*all_pred_b2_sets) if all_pred_b2_sets else set()

    # Confidence level
    if avg_hits >= 3:
        confidence_level = "high"
        confidence_text = "Высокая"
    elif avg_hits >= 2:
        confidence_level = "medium"
        confidence_text = "Средняя"
    else:
        confidence_level = "low"
        confidence_text = "Низкая"

    # Analysis text
    total_nums = len(act_b1) + len(act_b2)
    trend_text = {
        "improving": "Точность моделей улучшается с новыми данными.",
        "declining": "Наблюдается снижение точности.",
        "stable": "Точность стабильна.",
        "insufficient_data": "Недостаточно данных для оценки тренда.",
    }.get(trend, "")

    analysis_text = (
        f"На основе поэтапного анализа {n_steps} последних тиражей: "
        f"среднее попадание {avg_hits:.1f} из {total_nums} чисел "
        f"(медиана: {median_hits}, max: {max_hits_val}). "
        f"{trend_text} "
        f"Уровень уверенности: {confidence_text}. "
    )
    if consensus_numbers_b1:
        analysis_text += f"Числа с максимальной уверенностью (во всех прогнозах): Б1 {sorted(consensus_numbers_b1)}. "
    analysis_text += f"Наиболее надёжные: Б1 {strongest_b1[:5]}, Б2 {strongest_b2[:3]}."

    # Numbers in final prediction that match strongest numbers
    strong_in_final_b1 = sorted(set(final_pred_b1) & set(strongest_b1[:5]))
    strong_in_final_b2 = sorted(set(final_pred_b2) & set(strongest_b2[:3]))

    # Best step
    best_step_idx = all_hits.index(max_hits_val) if all_hits else 0

    # ── Build result ──────────────────────────────────────────────────
    result = {
        "status": "ok",
        "n_steps": n_steps,
        "draws_analyzed": total,
        "game_format": f"{len(act_b1)} из {detected_b1_max}" + (f" + {len(act_b2)} из {detected_b2_max}" if act_b2 else ""),
        "draw_range": {
            "first": draws[0].draw_no,
            "last": draws[-1].draw_no,
        },
        "steps": steps,
        "final_prediction": {
            "block1": sorted(final_pred_b1),
            "block2": sorted(final_pred_b2),
            "confidence": {"block1": final_cons_b1, "block2": final_cons_b2},
            "expected_hits": expected_hits,
            "most_reliable_numbers": {
                "block1": most_reliable_b1,
                "block2": most_reliable_b2,
            },
            "reliability_score": reliability_score,
            "strong_numbers": {
                "block1": strong_in_final_b1,
                "block2": strong_in_final_b2,
            },
            "consensus_numbers": {
                "block1": sorted(consensus_numbers_b1),
                "block2": sorted(consensus_numbers_b2),
            },
            "strongest_numbers": {
                "block1": strongest_b1,
                "block2": strongest_b2,
            },
            "confidence_level": confidence_level,
            "confidence_text": confidence_text,
            "analysis": analysis_text,
        },
        "summary": {
            "avg_hits": round(avg_hits, 2),
            "median_hits": median_hits,
            "max_hits": max_hits_val,
            "min_hits": min_hits_val,
            "trend": trend,
            "hit_distribution": dict(sorted(hit_distribution.items())),
            "consistency": consistency,
            "best_step": best_step_idx + 1,
            "total_numbers": total_nums,
        },
    }

    return result


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Step-by-step lottery analysis')
    parser.add_argument('--file', required=True, help='Path to draw data file')
    parser.add_argument('--steps', type=int, default=5, help='Analysis steps (1-10, default: 5)')
    parser.add_argument('--from-draw', type=int, default=None, help='From draw number (inclusive)')
    parser.add_argument('--to-draw', type=int, default=None, help='To draw number (inclusive)')
    args = parser.parse_args()

    n_steps = max(1, min(10, args.steps))

    # Read file
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"Cannot read file: {e}"}))
        sys.exit(1)

    # Parse draws
    fname = os.path.basename(args.file)
    game_key = fname.replace('draws_', '').replace('.txt', '')
    draws = parse_text(text, game_name=game_key)
    if not draws:
        print(json.dumps({"status": "error", "error": "No valid draws found in file"}))
        sys.exit(1)

    # Draw range filter
    if args.from_draw is not None or args.to_draw is not None:
        before = len(draws)
        draws = [d for d in draws
                 if (args.from_draw is None or d.draw_no >= args.from_draw)
                 and (args.to_draw is None or d.draw_no <= args.to_draw)]
        if not draws:
            print(json.dumps({"status": "error", "error": f"No draws in range. Total: {before}"}))
            sys.exit(1)
        print(f"[range] Filtered {before} -> {len(draws)} draws", file=sys.stderr)

    print(f"[info] Draws: {len(draws)}, Steps: {n_steps}", file=sys.stderr)

    t0 = time.time()
    result = run_step_analysis(draws, n_steps=n_steps)
    elapsed = time.time() - t0

    if result.get("status") == "error":
        print(json.dumps(result))
        sys.exit(1)

    result["elapsed_seconds"] = round(elapsed, 1)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
