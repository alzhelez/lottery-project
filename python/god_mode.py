#!/usr/bin/env python3
"""
God Mode: Single-run wrapper that executes predict + step_analysis + pipeline
for a given set of parameters. Called multiple times by the API for multi-run analysis.

v36.0 — Orchestrates predict → step_analysis → pipeline in one call.
"""

import argparse
import json
import os
import sys
import time
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _streamlit_mock import st_mock  # noqa: E402


def run_command(script_name, args, timeout=300):
    """Run a Python script and return parsed JSON output."""
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    cmd = [sys.executable, script_path] + args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return {"status": "error", "error": f"{script_name} failed: {result.stderr[:300]}"}
        
        # Parse JSON from stdout (handle potential non-JSON lines)
        stdout = result.stdout.strip()
        # Find JSON in output (might have progress lines before)
        json_start = stdout.rfind('{')
        if json_start >= 0:
            json_str = stdout[json_start:]
            return json.loads(json_str)
        return {"status": "error", "error": f"No JSON output from {script_name}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"{script_name} timed out"}
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='God Mode single run')
    parser.add_argument('--file', required=True, help='Path to draw data file')
    parser.add_argument('--game', required=True, help='Game key')
    parser.add_argument('--from-draw', type=int, default=None, help='From draw number')
    parser.add_argument('--to-draw', type=int, default=None, help='To draw number')
    parser.add_argument('--steps', type=int, default=5, help='Step analysis N (1-10)')
    parser.add_argument('--seed', type=int, default=None, help='Random seed')
    args = parser.parse_args()

    t0 = time.time()
    run_info = {
        "game": args.game,
        "file": args.file,
        "params": {
            "from_draw": args.from_draw,
            "to_draw": args.to_draw,
            "steps_n": args.steps,
            "seed": args.seed,
        },
    }

    # Build common args
    common_args = ['--file', args.file]
    if args.from_draw is not None:
        common_args.extend(['--from-draw', str(args.from_draw)])
    if args.to_draw is not None:
        common_args.extend(['--to-draw', str(args.to_draw)])

    # Set seed if provided
    if args.seed is not None:
        os.environ['GOD_MODE_SEED'] = str(args.seed)

    result = {
        "status": "ok",
        "run_info": run_info,
        "predict": None,
        "step_analysis": None,
        "pipeline": None,
        "elapsed_seconds": 0,
    }

    # 1. Run predict
    print("[progress] Starting prediction...", file=sys.stderr, flush=True)
    predict_result = run_command('predict.py', ['--game', args.game] + common_args, timeout=300)
    result["predict"] = predict_result
    predict_time = time.time() - t0
    print(f"[progress] Prediction done ({predict_time:.1f}s)", file=sys.stderr, flush=True)

    # 2. Run step analysis
    print("[progress] Starting step analysis...", file=sys.stderr, flush=True)
    sa_result = run_command('step_analysis.py', common_args + ['--steps', str(args.steps)], timeout=300)
    result["step_analysis"] = sa_result
    sa_time = time.time() - t0
    print(f"[progress] Step analysis done ({sa_time - predict_time:.1f}s)", file=sys.stderr, flush=True)

    # 3. Run pipeline
    print("[progress] Starting pipeline...", file=sys.stderr, flush=True)
    pipe_result = run_command('pipeline.py', ['--game', args.game] + common_args, timeout=300)
    result["pipeline"] = pipe_result
    total_time = time.time() - t0
    print(f"[progress] Pipeline done ({total_time - sa_time:.1f}s)", file=sys.stderr, flush=True)

    result["elapsed_seconds"] = round(total_time, 1)
    print(f"[info] Total God Mode run: {total_time:.1f}s", file=sys.stderr, flush=True)

    # Clean up seed env
    if 'GOD_MODE_SEED' in os.environ:
        del os.environ['GOD_MODE_SEED']

    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
