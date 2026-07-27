"""AST 기반 미사용 import 검사 (외부 린터 없이 동작).

실행: python design_preview/check_unused_imports.py
"""

import ast
import io
import os
import sys

TARGETS = (
    "magnifier.py",
    "network_manager.py",
    "server.py",
    "cooldown_detector.py",
    "cooldown_ocr.py",
    "capture_overlay.py",
)


def collect(path):
    source = io.open(path, encoding="utf-8").read()
    tree = ast.parse(source)

    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imported[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            # __future__ 지시자는 이름으로 참조되지 않으므로 검사에서 제외한다.
            if node.module == "__future__":
                continue
            for alias in node.names:
                name = alias.asname or alias.name
                imported[name] = node.lineno

    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)

    return {name: line for name, line in imported.items() if name not in used}


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    problems = 0
    for target in TARGETS:
        path = os.path.join(root, target)
        if not os.path.exists(path):
            continue
        unused = collect(path)
        if unused:
            problems += len(unused)
            detail = ", ".join(f"{name} (L{line})" for name, line in sorted(unused.items()))
            print(f"{target}: {detail}")
        else:
            print(f"{target}: clean")
    print(f"\ntotal unused imports: {problems}")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
