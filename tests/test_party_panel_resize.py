"""파티 현황판 크기 조절 회귀 테스트.

v2.47에서 높이 자동 맞춤을 넣으면서 오른쪽 변만 조절되던 문제를 고쳤다.
네 변 + 네 모서리 8방향 모두 동작해야 하고, 커서가 방향을 알려줘야 한다.
"""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# `python tests/test_...py` 로 바로 실행할 수 있도록 저장소 루트를 import 경로에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication

from magnifier import PartyPanel  # noqa: E402


class ResizeZoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = PartyPanel()
        self.panel.timer.stop()
        self.panel.resize(400, 300)

    def tearDown(self):
        self.panel.close()

    def test_all_eight_zones_are_detected(self):
        width, height = self.panel.width(), self.panel.height()
        mid_x, mid_y = width // 2, height // 2
        expected = {
            "TopLeft": QPoint(2, 2),
            "TopRight": QPoint(width - 3, 2),
            "BottomLeft": QPoint(2, height - 3),
            "BottomRight": QPoint(width - 3, height - 3),
            "Left": QPoint(2, mid_y),
            "Right": QPoint(width - 3, mid_y),
            "Top": QPoint(mid_x, 2),
            "Bottom": QPoint(mid_x, height - 3),
        }
        for zone, point in expected.items():
            with self.subTest(zone=zone):
                self.assertEqual(self.panel._resize_zone(point), zone)

    def test_centre_is_not_a_resize_zone(self):
        centre = QPoint(self.panel.width() // 2, self.panel.height() // 2)
        self.assertIsNone(self.panel._resize_zone(centre))

    def test_every_zone_maps_to_a_direction_cursor(self):
        diagonal = {
            "TopLeft": Qt.CursorShape.SizeFDiagCursor,
            "BottomRight": Qt.CursorShape.SizeFDiagCursor,
            "TopRight": Qt.CursorShape.SizeBDiagCursor,
            "BottomLeft": Qt.CursorShape.SizeBDiagCursor,
        }
        straight = {
            "Left": Qt.CursorShape.SizeHorCursor,
            "Right": Qt.CursorShape.SizeHorCursor,
            "Top": Qt.CursorShape.SizeVerCursor,
            "Bottom": Qt.CursorShape.SizeVerCursor,
        }
        for zone, cursor in {**diagonal, **straight}.items():
            with self.subTest(zone=zone):
                self.assertEqual(PartyPanel._RESIZE_CURSORS[zone], cursor)
        # 8방향이 빠짐없이 등록되어 있어야 한다.
        self.assertEqual(len(PartyPanel._RESIZE_CURSORS), 8)


class ResizeGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = PartyPanel()
        self.panel.timer.stop()
        self.panel.setGeometry(100, 100, 400, 300)

    def tearDown(self):
        self.panel.close()

    def test_right_edge_grows_width_only(self):
        self.panel._apply_resize("Right", QPoint(600, 250))
        geometry = self.panel.geometry()
        self.assertEqual(geometry.left(), 100)
        self.assertEqual(geometry.top(), 100)
        self.assertEqual(geometry.height(), 300)
        self.assertGreater(geometry.width(), 400)

    def test_bottom_edge_grows_height_only(self):
        self.panel._apply_resize("Bottom", QPoint(300, 520))
        geometry = self.panel.geometry()
        self.assertEqual(geometry.width(), 400)
        self.assertGreater(geometry.height(), 300)

    def test_bottom_right_corner_grows_both_axes(self):
        self.panel._apply_resize("BottomRight", QPoint(640, 560))
        geometry = self.panel.geometry()
        self.assertGreater(geometry.width(), 400)
        self.assertGreater(geometry.height(), 300)
        # 좌상단은 고정되어야 한다.
        self.assertEqual(geometry.topLeft(), QPoint(100, 100))

    def test_left_edge_moves_origin_and_keeps_right_edge(self):
        original_right = self.panel.geometry().right()
        self.panel._apply_resize("Left", QPoint(40, 250))
        geometry = self.panel.geometry()
        self.assertEqual(geometry.right(), original_right)
        self.assertLess(geometry.left(), 100)
        self.assertGreater(geometry.width(), 400)

    def test_top_edge_moves_origin_and_keeps_bottom_edge(self):
        original_bottom = self.panel.geometry().bottom()
        self.panel._apply_resize("Top", QPoint(300, 30))
        geometry = self.panel.geometry()
        self.assertEqual(geometry.bottom(), original_bottom)
        self.assertLess(geometry.top(), 100)
        self.assertGreater(geometry.height(), 300)

    def test_top_left_corner_keeps_bottom_right_anchored(self):
        original = self.panel.geometry().bottomRight()
        self.panel._apply_resize("TopLeft", QPoint(20, 20))
        self.assertEqual(self.panel.geometry().bottomRight(), original)

    def test_resize_cannot_shrink_below_content_minimum(self):
        # 반대편을 넘어서는 좌표로 끌어도 최소 크기 아래로는 줄지 않는다.
        self.panel._apply_resize("BottomRight", QPoint(-500, -500))
        geometry = self.panel.geometry()
        self.assertGreaterEqual(geometry.width(), 160)
        self.assertGreaterEqual(geometry.height(), 90)

    def test_manual_resize_is_not_undone_by_autofit(self):
        self.panel._apply_resize("BottomRight", QPoint(700, 700))
        manual = self.panel.size()
        self.assertTrue(self.panel._user_sized)

        self.panel._relayout()
        self.panel._autofit_size()

        self.assertEqual(self.panel.size(), manual)


if __name__ == "__main__":
    unittest.main()
