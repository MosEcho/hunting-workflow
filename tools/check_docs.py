#!/usr/bin/env python3
"""Check local Markdown links without contacting external sites."""
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    paths = list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md")) + list((ROOT / ".github").rglob("*.md"))
    for path in paths:
        for match in re.finditer(r"!?\[[^\]\n]*\]\(([^\n)]+)\)", path.read_text(encoding="utf-8")):
            target = unquote(match.group(1).strip("<>").split("#", 1)[0])
            if not target or re.match(r"^[a-zA-Z][\w+.-]*:", target):
                continue
            if not (path.parent / target).exists():
                errors.append(str(path.relative_to(ROOT)) + " -> " + target)
    for error in errors:
        print(error)
    print("PASS" if not errors else "FAIL", "documentation files:", len(paths))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
