"""Проверка окружения перед запуском (tools/ensure-venv.bat, start.sh) должна знать все
библиотеки из requirements.txt: иначе после git pull или смены ветки новые библиотеки не
ставятся в уже созданное окружение, и программа падает на импорте."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPORT_NAME = {"scikit-learn": "sklearn"}


def _required() -> set[str]:
    names = set()
    for line in (ROOT / "python" / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pkg = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].lower()
            names.add(IMPORT_NAME.get(pkg, pkg))
    return names


def _checked(path: Path) -> set[str]:
    if not path.exists():
        return _required()        # скрипта нет в этой ветке — проверять нечего
    m = re.search(r'import ([\w, ]+)"', path.read_text(encoding="utf-8"))
    assert m, f"в {path.name} нет проверки импортов"
    return {x.strip() for x in m.group(1).split(",")}


def test_ensure_venv_checks_every_requirement():
    assert _required() <= _checked(ROOT / "tools" / "ensure-venv.bat")


def test_start_sh_checks_every_requirement():
    assert _required() <= _checked(ROOT / "start.sh")
