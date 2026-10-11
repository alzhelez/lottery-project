"""Движок анализа лотерейных тиражей Столото."""
import json as _json
from pathlib import Path as _Path

__version__ = _json.loads((_Path(__file__).resolve().parents[2] / "config" / "version.json").read_text(encoding="utf-8"))["version"]
