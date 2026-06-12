#!/usr/bin/env python3
"""
Обёртка для fetch_draws.py — выгрузка тиражей с stoloto.ru.
Использование: python fetch.py --game 4x20 [--output /path/to/file]
Возвращает JSON: { game, total_draws, data_file }
"""
import json
import os
import subprocess
import sys

# Use the same Python that runs this script (ensures requests is available)
PYTHON = sys.executable


def main():
    game = None
    output_path = None
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == "--game" and i + 1 < len(sys.argv):
            game = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    if not game:
        print(json.dumps({"error": "Missing --game argument"}, ensure_ascii=False))
        sys.exit(1)

    # Default output file path (use OS temp dir for portability)
    if not output_path:
        import tempfile
        output_path = os.path.join(tempfile.gettempdir(), f"draws_{game}.txt")

    # Path to the actual fetch script (look in same directory first, then upload/)
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_script_dir)
    fetch_script = os.path.join(_script_dir, "fetch_draws.py")
    if not os.path.exists(fetch_script):
        fetch_script = os.path.join(_project_root, "upload", "fetch_draws.py")

    if not os.path.exists(fetch_script):
        print(json.dumps({"error": f"fetch_draws.py not found at {fetch_script}"}, ensure_ascii=False))
        sys.exit(1)

    # Pre-check: verify requests module is available
    try:
        subprocess.run([PYTHON, "-c", "import requests; print('OK')"],
                       capture_output=True, text=True, timeout=10, check=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        print(json.dumps({"error": "Python module 'requests' not available. Run: pip install requests numpy scipy pandas plotly"}, ensure_ascii=False))
        sys.exit(1)

    # Run the fetch script with explicit python path
    try:
        result = subprocess.run(
            [PYTHON, fetch_script, "--game", game, "--output", output_path],
            capture_output=True,
            text=True,
            timeout=900,  # v39.3.0: 15 minutes (was 10) for games with 10k+ draws
            cwd=_project_root
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({"error": "Timeout: fetch took more than 15 minutes"}, ensure_ascii=False))
        sys.exit(1)

    # Count draws in the output file
    total_draws = 0
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                total_draws = sum(1 for line in f if line.strip() and "||" in line)
        except OSError:
            pass

    output = {
        "game": game,
        "total_draws": total_draws,
        "data_file": output_path,
    }

    if result.returncode != 0 and total_draws == 0:
        stderr_tail = (result.stderr or "")[-800:]
        # Check for module errors
        if "ModuleNotFoundError" in stderr_tail:
            output["error"] = f"Missing Python module. {stderr_tail.strip()[-200:]}"
        else:
            output["error"] = stderr_tail.strip()[-500:] or "Unknown error"
        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
