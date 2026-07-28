"""모달 공용 디자인 시스템 회귀 테스트.

설정/파티설정/도움말 모달의 인라인 QSS를 공용 팔레트로 합치면서, 상태 라벨
색을 objectName 교체(apply_widget_tone)로 바꾸는 방식을 도입했다. 이 구조는
두 가지로 조용히 깨진다.

1. 톤 헬퍼를 호출만 하고 정의하지 않으면 그 순간에야 AttributeError가 난다
   (모달을 띄우는 것만으로는 드러나지 않는다).
2. 쓰는 톤 이름에 대응하는 QSS 규칙이 없으면 예외 없이 색만 안 먹는다.

둘 다 실행 경로를 타야만 보이므로 정적으로 검사해 둔다.
"""

import ast
import io
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# `python tests/test_...py` 로 바로 실행할 수 있도록 저장소 루트를 import 경로에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication, QLabel

import magnifier  # noqa: E402

SOURCE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "magnifier.py")

# 톤 이름을 첫 번째/두 번째 인자로 받는 함수들
TONE_SETTERS_SELF = ("_set_lookup_tone", "_apply_client_status_tone")
TONE_SETTERS_WITH_TEXT = ("_set_client_status", "_set_selected_status")


def parse_source():
    """magnifier.py 를 AST로 읽는다."""
    with io.open(SOURCE_PATH, encoding="utf-8") as handle:
        return ast.parse(handle.read())


def collect_tone_names():
    """소스에서 실제로 사용되는 톤(objectName) 문자열을 모은다."""
    tree = parse_source()
    tones = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", getattr(node.func, "id", None))
        if name in TONE_SETTERS_SELF:
            args = node.args[:1]
        elif name in TONE_SETTERS_WITH_TEXT:
            args = node.args[1:2]
        elif name == "apply_widget_tone":
            args = node.args[1:2]
        else:
            continue
        for arg in args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
                tones.add(arg.value)
    return tones


class ModalDesignSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.style = magnifier.get_modal_style()
        cls.tones = collect_tone_names()

    def test_tone_helpers_are_defined(self):
        """톤 헬퍼는 호출부만 남고 정의가 빠지기 쉽다."""
        for name in TONE_SETTERS_SELF + TONE_SETTERS_WITH_TEXT:
            self.assertTrue(
                callable(getattr(magnifier.SettingsModal, name, None)),
                f"SettingsModal.{name} 이 정의되지 않았습니다",
            )
        self.assertTrue(callable(getattr(magnifier, "apply_widget_tone", None)))

    def test_every_used_tone_has_a_qss_rule(self):
        self.assertTrue(self.tones, "톤 사용처를 하나도 찾지 못했습니다")
        missing = [tone for tone in sorted(self.tones) if f"#{tone}" not in self.style]
        self.assertEqual([], missing, f"공용 QSS에 규칙이 없는 톤: {missing}")

    def test_style_template_has_no_unresolved_placeholder(self):
        """__CHECK_IMAGE__ 같은 자리표시자가 남으면 QSS 파싱이 조용히 실패한다."""
        self.assertNotIn("__", self.style.replace("_ModalContainer", ""))

    def test_generated_assets_exist(self):
        """체크마크·셰브론 PNG가 없으면 체크박스와 콤보 화살표가 사라진다."""
        for path in (magnifier.get_check_asset_path(),
                     magnifier.get_chevron_asset_path()):
            self.assertTrue(path, "애셋 경로 생성 실패")
            self.assertTrue(os.path.exists(path.replace("/", os.sep)), path)

    def test_apply_widget_tone_switches_object_name(self):
        label = QLabel()
        magnifier.apply_widget_tone(label, "StatusOk")
        self.assertEqual("StatusOk", label.objectName())
        magnifier.apply_widget_tone(label, "StatusWarn")
        self.assertEqual("StatusWarn", label.objectName())
        label.deleteLater()

    def test_modals_share_the_common_stylesheet(self):
        """세 모달이 각자 인라인 QSS로 되돌아가지 않았는지 확인한다."""
        tree = parse_source()
        expected = {"SettingsModal", "PartyOverlaySettingsModal", "HelpModal"}
        seen = set()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name in expected):
                continue
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and getattr(sub.func, "attr", None) == "setStyleSheet"
                        and sub.args
                        and isinstance(sub.args[0], ast.Call)
                        and getattr(sub.args[0].func, "id", None) == "get_modal_style"):
                    seen.add(node.name)
        self.assertEqual(expected, seen, f"공용 스타일을 안 쓰는 모달: {expected - seen}")


if __name__ == "__main__":
    unittest.main()
