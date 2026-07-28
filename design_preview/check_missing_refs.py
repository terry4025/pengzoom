"""magnifier.py 안에서 '호출은 있는데 정의가 없는' 참조를 찾아낸다.

- self.<name>(...) 호출 중 클래스(및 PyQt 상위 클래스)에 없는 것
- objectName 톤 문자열 중 공용 QSS에 규칙이 없는 것
- 모듈 전역 이름 중 정의되지 않은 것

일회성 감사 스크립트다. 실행 후 삭제한다.
"""

import ast
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "magnifier.py")


def qt_attrs(base_names):
    """PyQt 상위 클래스에서 물려받는 속성 이름을 모은다."""
    names = set()
    from PyQt6 import QtCore, QtGui, QtWidgets
    for module in (QtWidgets, QtGui, QtCore):
        for base in base_names:
            cls = getattr(module, base, None)
            if cls is not None:
                names |= set(dir(cls))
    return names


def main():
    source = io.open(PATH, encoding="utf-8").read()
    tree = ast.parse(source)

    module_defined = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_defined.add(target.id)

    problems = []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        methods = {n.name for n in node.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        # 클래스 본문/메서드 안에서 self.x = ... 로 만들어지는 속성
        assigned = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign):
                for target in sub.targets:
                    if (isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                        assigned.add(target.attr)

        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        inherited = qt_attrs(bases)

        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id == "self"):
                continue
            name = sub.func.attr
            if name in methods or name in assigned or name in inherited:
                continue
            problems.append(
                f"{node.name}.{name}() 호출됨 (line {sub.lineno}) - 정의 없음")

    # 톤 문자열 검증
    tones = set()
    for match in ast.walk(tree):
        if (isinstance(match, ast.Call)
                and isinstance(match.func, ast.Attribute)
                and match.func.attr in ("apply_widget_tone", "_set_lookup_tone",
                                        "_apply_client_status_tone")):
            for arg in match.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    tones.add(arg.value)
    for call in ast.walk(tree):
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "apply_widget_tone" and len(call.args) == 2):
            arg = call.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                tones.add(arg.value)

    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)  # noqa: F841  (QSS 생성에 QPainter 필요)
    import magnifier

    style = magnifier.get_modal_style()
    for tone in sorted(tones):
        if f"#{tone}" not in style:
            problems.append(f"톤 '{tone}' 사용되나 공용 QSS에 규칙 없음")

    lines = [f"검사한 톤: {sorted(tones)}"]
    if problems:
        lines.append(f"문제 {len(problems)}건:")
        lines += [f"  - {item}" for item in problems]
    else:
        lines.append("미정의 참조 없음: OK")

    report = "\n".join(lines)
    with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "check_missing_refs.log"), "w", encoding="utf-8") as handle:
        handle.write(report)
    print(report)
    sys.stdout.flush()
    os._exit(1 if problems else 0)


if __name__ == "__main__":
    main()
