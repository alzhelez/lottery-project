#!/usr/bin/env python3
"""
model_backtest.py — Per-model quality backtest on historical draw data.

For each of the 133 models, runs a walk-forward backtest on the last N draws:
  - For each test draw, trains on all draws before it
  - Gets each model's prediction via all_predictions()
  - Compares with actual results, counts hits per model
  - Computes per-model statistics: avg_hits, median_hits, std, consistency

Outputs a JSON report ranking all models by performance.
Identifies models that consistently underperform (below random baseline).

Usage:
    python model_backtest.py --file data/draws/draws_4x20.txt --test-size 50
    python model_backtest.py --file data/draws/draws_6x45plus.txt --test-size 50
"""

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════════════════════════════════════
#  MOCK STREAMLIT (must be BEFORE importing lp_v130_app)
# ═══════════════════════════════════════════════════════════════════════
from _streamlit_mock import st_mock  # noqa: E402

import lp_v130_app  # noqa: E402
from lp_v130_app import (  # noqa: E402
    LP132, FreqCache, parse_text,
    TOTAL_MODELS, _DISABLED_MODELS, _BOOSTED_MODELS,
    PICK_B1, PICK_B2, B1_MAX, B2_MAX,
)

# ── Model name mapping (ID 1-133) ──────────────────────────────────
MODEL_NAMES = {
    # G1: Base models (IDs 1-20)
    1: "Freq", 2: "EnhancedMarkov", 3: "EnhancedGap", 4: "Pattern",
    5: "Neural", 6: "MonteCarlo", 7: "Genetic", 8: "Balance",
    9: "Deep", 10: "Fibonacci", 11: "ModularPattern", 12: "Momentum",
    13: "ZScore", 14: "Entropy", 15: "Cyclic", 16: "EnhancedEnsemble",
    17: "Recency", 18: "NumberAffinity", 19: "RegressionMean", 20: "EWMA-0.15",
    # G2: Window variants (IDs 21-32)
    21: "Window-5", 22: "Window-10", 23: "Window-15", 24: "Window-20",
    25: "Window-30", 26: "Window-50", 27: "Window-70", 28: "Window-100",
    29: "Window-150", 30: "Window-200", 31: "Window-300", 32: "Window-500",
    # G3: Gap+Freq hybrids (IDs 33-45)
    33: "Gap+Freq-0.8", 34: "Gap+Freq-1.0", 35: "Gap+Freq-1.2",
    36: "Gap+Freq-1.5", 37: "Gap+Freq-2.0", 38: "Gap+Freq-0.5",
    39: "Gap+Freq-1.8", 40: "Gap+Freq-2.5", 41: "Gap+Freq-0.3",
    42: "Gap+Freq-3.0", 43: "Gap+Freq-0.6", 44: "Gap+Freq-1.3",
    45: "Gap+Freq-0.9",
    # G4: EWMA alphas (IDs 46-57)
    46: "EWMA-0.05", 47: "EWMA-0.10", 48: "EWMA-0.20", 49: "EWMA-0.25",
    50: "EWMA-0.30", 51: "EWMA-0.35", 52: "EWMA-0.40", 53: "EWMA-0.50",
    54: "EWMA-0.60", 55: "EWMA-0.08", 56: "EWMA-0.12", 57: "EWMA-0.18",
    # G5: Velocity/zscore/Bayes/drawtype (IDs 58-70)
    58: "Diff-5/15", 59: "Diff-15/30", 60: "RecencyZ-30",
    61: "RecencyZ-50", 62: "RecencyZ-80", 63: "Bayesian-0.3",
    64: "Bayesian-0.5", 65: "Bayesian-0.8", 66: "StreakReversal",
    67: "StreakReversal2", 68: "DrawTypeFreq", 69: "FreqGapHybrid",
    70: "PeriodDetect",
    # G6: Weighted ensembles / replaced models (IDs 71-99)
    71: "Ensemble-1", 72: "Diff-30/50", 73: "Ensemble-3",
    74: "Ensemble-4", 75: "Ensemble-5", 76: "RecencyGap-100",
    77: "RecencyGap-200", 78: "Ensemble-8", 79: "Ensemble-9",
    80: "FreqGapHybrid-0.5", 81: "Ensemble-11", 82: "Ensemble-12",
    83: "RecencyGap-50", 84: "Ensemble-14", 85: "Ensemble-15",
    86: "HotColdBalance", 87: "Ensemble-17", 88: "Ensemble-18",
    89: "AdaptWindow", 90: "AdaptWindow2", 91: "Ensemble-21",
    92: "ConstrainedSum", 93: "ConstrainedSum2", 94: "HotColdBalance2",
    95: "HotColdBalance3", 96: "Ensemble-26", 97: "Ensemble-27",
    98: "Ensemble-28", 99: "StreakReversal3",
    # G7: NEW unique models (IDs 100-120)
    100: "PosDrift", 101: "Window-25", 102: "AdaptiveZScore",
    103: "Bayesian-0.2", 104: "HotStreak-10", 105: "HotStreak-15",
    106: "GapMomentum", 107: "SumParity", 108: "RunLength",
    109: "HighLowSplit", 110: "DiffFreq", 111: "EnhancedMarkov2",
    112: "EntropyWeighted", 113: "MeanRevert-50", 114: "MeanRevert-100",
    115: "MeanRevert-150", 116: "LagCorrel", 117: "BlockSumTrend",
    118: "SmartMonteCarlo", 119: "AdaptiveZScore2", 120: "Bayesian-1.0",
    # G8: More models (IDs 121-133)
    121: "AdaptiveEWMA", 122: "GapMomentum2", 123: "ClusterAnalysis",
    124: "Pos-P0", 125: "Pos-P1", 126: "Pos-P2", 127: "Pos-P3",
    128: "Window-8", 129: "Window-12", 130: "Window-40",
    131: "Window-250", 132: "Bayesian-1.5", 133: "DrawTypeSpecific",
}


def compute_consistency(hits_list):
    """Compute consistency score (0..1). High = stable hits, low = erratic."""
    if len(hits_list) < 2:
        return 0.5
    mean = sum(hits_list) / len(hits_list)
    if mean == 0:
        return 1.0
    variance = sum((h - mean) ** 2 for h in hits_list) / len(hits_list)
    std = math.sqrt(variance)
    cv = std / mean if mean > 0 else 0
    consistency = max(0.0, min(1.0, 1.0 - cv * 0.7))
    return round(consistency, 3)


def run_backtest(draws, test_size=50):
    """Run walk-forward backtest on last test_size draws for all 133 models.

    Temporarily disables _DISABLED_MODELS to evaluate ALL models fairly.
    For each test draw, trains on all draws before it, then gets predictions.
    """
    total = len(draws)
    if total < test_size + 20:
        return {"status": "error", "error": f"Not enough draws ({total}). Need at least {test_size + 20}."}

    # Compute random baseline
    b2_max = max(B2_MAX, 1)
    baseline = PICK_B1 * (PICK_B1 / B1_MAX)
    if PICK_B2 > 0 and b2_max > 0:
        baseline += PICK_B2 * (PICK_B2 / b2_max)

    # ── Temporarily clear disabled models to evaluate ALL models ──
    orig_disabled = lp_v130_app._DISABLED_MODELS
    lp_v130_app._DISABLED_MODELS = frozenset()

    # Per-model hit tracking
    model_hits = defaultdict(list)  # 0-based index -> [hits per draw]

    predictor = LP132()
    train_end = total - test_size

    # ── Phase 1: Bulk training on first (total - test_size) draws ──
    print(f"[info] Game format: PICK_B1={PICK_B1}, PICK_B2={PICK_B2}, "
          f"B1_MAX={B1_MAX}, B2_MAX={B2_MAX}", file=sys.stderr)
    print(f"[info] Random baseline: {baseline:.2f} hits/draw", file=sys.stderr)
    print(f"[info] Bulk training: {train_end} draws...", file=sys.stderr)

    t0 = time.time()
    predictor.update(draws[:train_end])
    print(f"[info] Training complete in {time.time()-t0:.1f}s", file=sys.stderr)

    # ── Phase 2: Walk-forward evaluation ──
    print(f"[info] Evaluating {test_size} test draws...", file=sys.stderr)
    t1 = time.time()

    errors = 0
    for step in range(test_size):
        idx = train_end + step
        actual = draws[idx]

        try:
            all_p = predictor.all_predictions()
        except Exception as e:
            print(f"[warn] Step {step+1} all_predictions failed: {e}", file=sys.stderr)
            errors += 1
            # Still incrementally update
            predictor.draws.append(actual)
            predictor.gfc = FreqCache(predictor.draws)
            predictor._c.clear()
            continue

        # Evaluate each model (index 0-based → model ID = index + 1)
        for midx, (pred_b1, pred_b2) in enumerate(all_p):
            hits_b1 = len(set(pred_b1) & set(actual.block1)) if pred_b1 else 0
            hits_b2 = len(set(pred_b2) & set(actual.block2)) if pred_b2 else 0
            model_hits[midx].append(hits_b1 + hits_b2)

        # Incremental update: append draw, rebuild FreqCache, clear model cache
        predictor.draws.append(actual)
        predictor.gfc = FreqCache(predictor.draws)
        predictor._c.clear()

        if (step + 1) % 10 == 0 or step == 0:
            elapsed = time.time() - t1
            print(f"[progress] Step {step+1}/{test_size} "
                  f"(draw #{actual.draw_no}): {elapsed:.1f}s elapsed",
                  file=sys.stderr)

    eval_time = time.time() - t1
    print(f"[info] Evaluation complete: {eval_time:.1f}s, {errors} errors",
          file=sys.stderr)

    # ── Restore disabled models ──
    lp_v130_app._DISABLED_MODELS = orig_disabled

    # ── Phase 3: Compute per-model statistics ──
    results = []
    for midx in range(TOTAL_MODELS):
        model_id = midx + 1  # 1-based
        hits = model_hits.get(midx, [])
        if not hits:
            results.append({
                "model_id": model_id,
                "name": MODEL_NAMES.get(model_id, f"Unknown-{model_id}"),
                "avg_hits": 0,
                "median_hits": 0,
                "std_hits": 0,
                "consistency": 0,
                "min_hits": 0,
                "max_hits": 0,
                "vs_baseline": -baseline,
                "vs_baseline_pct": -100,
                "test_draws": 0,
                "status": "no_predictions",
            })
            continue

        n = len(hits)
        avg = sum(hits) / n
        sorted_hits = sorted(hits)
        median = sorted_hits[n // 2]
        variance = sum((h - avg) ** 2 for h in hits) / n
        std = math.sqrt(variance)
        consistency = compute_consistency(hits)

        results.append({
            "idx": midx,  # 0-based index (matches _DISABLED_MODELS)
            "model_id": model_id,  # 1-based display ID
            "name": MODEL_NAMES.get(model_id, f"Unknown-{model_id}"),
            "avg_hits": round(avg, 3),
            "median_hits": median,
            "std_hits": round(std, 3),
            "consistency": consistency,
            "min_hits": min(hits),
            "max_hits": max(hits),
            "vs_baseline": round(avg - baseline, 3),
            "vs_baseline_pct": round((avg - baseline) / baseline * 100, 1) if baseline > 0 else 0,
            "test_draws": n,
            "status": "active" if midx not in orig_disabled else "disabled",
        })

    # Sort by avg_hits descending
    results.sort(key=lambda x: -x["avg_hits"])

    # ── Phase 4: Analysis ──
    active_results = [r for r in results if r["status"] == "active"]
    disabled_results = [r for r in results if r["status"] == "disabled"]

    # Underperformers: below 95% of random baseline (currently active)
    underperformers = [r for r in active_results
                       if r["avg_hits"] < baseline * 0.95]
    # Overperformers: above 105% of random baseline
    overperformers = [r for r in results if r["avg_hits"] > baseline * 1.05]
    # Strong overperformers: above 115% of random baseline
    strong_overperformers = [r for r in results if r["avg_hits"] > baseline * 1.15]

    # Should remain disabled: disabled models that would still underperform
    should_stay_disabled = [r for r in disabled_results
                            if r["avg_hits"] < baseline * 0.95]
    # Should be re-enabled: disabled models that now perform well
    should_reenable = [r for r in disabled_results
                       if r["avg_hits"] >= baseline * 1.0]

    # Models currently boosted that should lose boost (use 0-based idx)
    should_remove_boost = [r for r in overperformers if r["idx"] not in _BOOSTED_MODELS]
    currently_boosted_perf = [r for r in results if r["idx"] in _BOOSTED_MODELS]
    boosted_underperforming = [r for r in currently_boosted_perf
                               if r["avg_hits"] < baseline * 1.0]

    ensemble_avg = sum(r["avg_hits"] for r in results) / len(results) if results else 0
    active_avg = (sum(r["avg_hits"] for r in active_results) / len(active_results)
                  if active_results else 0)

    report = {
        "status": "ok",
        "game": "",
        "test_size": test_size,
        "total_draws": total,
        "training_draws": train_end,
        "random_baseline": round(baseline, 3),
        "total_models": TOTAL_MODELS,
        "active_models": len(active_results),
        "disabled_models": len(disabled_results),
        "currently_disabled_ids": sorted(list(orig_disabled)),
        "currently_boosted_ids": sorted(list(_BOOSTED_MODELS)),
        "eval_time_seconds": round(eval_time, 1),
        "summary": {
            "ensemble_avg": round(ensemble_avg, 3),
            "active_avg": round(active_avg, 3),
            "top_10": results[:10],
            "bottom_10": results[-10:],
            "underperformers_count": len(underperformers),
            "overperformers_count": len(overperformers),
            "strong_overperformers_count": len(strong_overperformers),
        },
        "recommendations": {
            "new_disable": [{"id": r["model_id"], "name": r["name"],
                             "avg_hits": r["avg_hits"],
                             "vs_baseline_pct": r["vs_baseline_pct"]}
                            for r in underperformers],
            "new_boost": [{"id": r["model_id"], "name": r["name"],
                           "avg_hits": r["avg_hits"],
                           "vs_baseline_pct": r["vs_baseline_pct"]}
                          for r in strong_overperformers],
            "keep_disabled": [{"id": r["model_id"], "name": r["name"],
                               "avg_hits": r["avg_hits"]}
                              for r in should_stay_disabled],
            "reenable": [{"id": r["model_id"], "name": r["name"],
                          "avg_hits": r["avg_hits"]}
                         for r in should_reenable],
            "remove_boost": [{"id": r["model_id"], "name": r["name"],
                              "avg_hits": r["avg_hits"]}
                             for r in boosted_underperforming],
        },
        "models": results,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Model quality backtest")
    parser.add_argument('--file', required=True, help='Path to draw data file')
    parser.add_argument('--test-size', type=int, default=50,
                        help='Number of test draws (default: 50)')
    args = parser.parse_args()

    test_size = max(10, min(200, args.test_size))

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

    print(f"[info] Game: {game_key}, Draws: {len(draws)}, Test size: {test_size}",
          file=sys.stderr)

    t0 = time.time()
    report = run_backtest(draws, test_size=test_size)
    elapsed = time.time() - t0

    if report.get("status") == "error":
        print(json.dumps(report))
        sys.exit(1)

    report["game"] = game_key
    report["total_time_seconds"] = round(elapsed, 1)

    # Print summary to stderr for human readability
    print(f"\n{'='*70}", file=sys.stderr)
    print(f"BACKTEST RESULTS: {game_key}", file=sys.stderr)
    print(f"{'='*70}", file=sys.stderr)
    print(f"Total draws: {report['total_draws']}, "
          f"Training: {report['training_draws']}, "
          f"Test: {report['test_size']}", file=sys.stderr)
    print(f"Random baseline: {report['random_baseline']:.2f} hits/draw", file=sys.stderr)
    print(f"Ensemble avg (all models): {report['summary']['ensemble_avg']:.3f}", file=sys.stderr)
    print(f"Active avg: {report['summary']['active_avg']:.3f}", file=sys.stderr)
    print(f"Total time: {report['total_time_seconds']:.1f}s", file=sys.stderr)

    print(f"\n--- TOP 10 MODELS ---", file=sys.stderr)
    for r in report["summary"]["top_10"]:
        status = " [DISABLED]" if r["status"] == "disabled" else ""
        print(f"  #{r['model_id']:3d} {r['name']:25s} "
              f"avg={r['avg_hits']:.3f}  "
              f"vs_baseline={r['vs_baseline_pct']:+.1f}%  "
              f"std={r['std_hits']:.3f}  "
              f"consistency={r['consistency']:.2f}{status}", file=sys.stderr)

    print(f"\n--- BOTTOM 10 MODELS ---", file=sys.stderr)
    for r in report["summary"]["bottom_10"]:
        status = " [DISABLED]" if r["status"] == "disabled" else ""
        print(f"  #{r['model_id']:3d} {r['name']:25s} "
              f"avg={r['avg_hits']:.3f}  "
              f"vs_baseline={r['vs_baseline_pct']:+.1f}%  "
              f"std={r['std_hits']:.3f}{status}", file=sys.stderr)

    rec = report["recommendations"]
    if rec["new_disable"]:
        print(f"\n--- RECOMMEND TO DISABLE ({len(rec['new_disable'])}) ---", file=sys.stderr)
        for r in rec["new_disable"]:
            print(f"  #{r['id']:3d} {r['name']:25s} "
                  f"avg={r['avg_hits']:.3f} ({r['vs_baseline_pct']:+.1f}%)",
                  file=sys.stderr)

    if rec["keep_disabled"]:
        print(f"\n--- KEEP DISABLED ({len(rec['keep_disabled'])}) ---", file=sys.stderr)
        for r in rec["keep_disabled"]:
            print(f"  #{r['id']:3d} {r['name']:25s} avg={r['avg_hits']:.3f}",
                  file=sys.stderr)

    if rec["reenable"]:
        print(f"\n--- RECOMMEND TO RE-ENABLE ({len(rec['reenable'])}) ---", file=sys.stderr)
        for r in rec["reenable"]:
            print(f"  #{r['id']:3d} {r['name']:25s} avg={r['avg_hits']:.3f}",
                  file=sys.stderr)

    if rec["new_boost"]:
        print(f"\n--- RECOMMEND TO BOOST ({len(rec['new_boost'])}) ---", file=sys.stderr)
        for r in rec["new_boost"]:
            print(f"  #{r['id']:3d} {r['name']:25s} "
                  f"avg={r['avg_hits']:.3f} ({r['vs_baseline_pct']:+.1f}%)",
                  file=sys.stderr)

    if rec["remove_boost"]:
        print(f"\n--- RECOMMEND TO REMOVE BOOST ({len(rec['remove_boost'])}) ---", file=sys.stderr)
        for r in rec["remove_boost"]:
            print(f"  #{r['id']:3d} {r['name']:25s} avg={r['avg_hits']:.3f}",
                  file=sys.stderr)

    print(f"\n{'='*70}", file=sys.stderr)

    # Output full JSON to stdout
    print(json.dumps(report, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
