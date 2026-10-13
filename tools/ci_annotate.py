"""Печатает упавшие тесты из отчётов JUnit XML как аннотации GitHub Actions.

Аннотации видны прямо на странице сборки (и через API), не нужно открывать журнал:

    python tools/ci_annotate.py test-results/*.xml tests/api/java/target/surefire-reports/*.xml
"""
from __future__ import annotations

import glob
import sys
import xml.etree.ElementTree as ET

LIMIT = 20


def esc(s: str) -> str:
    # специальные символы формата команд GitHub Actions
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(patterns: list[str]) -> int:
    # на Windows консоль CI не в UTF-8 — без этого кириллица в сообщениях роняет скрипт
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    shown = 0
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            try:
                root = ET.parse(path).getroot()
            except (ET.ParseError, OSError):
                continue
            for case in root.iter("testcase"):
                for tag in ("failure", "error"):
                    node = case.find(tag)
                    if node is None:
                        continue
                    name = f"{case.get('classname', '')}.{case.get('name', '')}".strip(".")
                    text = (node.get("message") or "") + "\n" + (node.text or "")
                    print(f"::error title={esc(name)[:200]}::{esc(text.strip()[:3000])}")
                    shown += 1
                    if shown >= LIMIT:
                        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
