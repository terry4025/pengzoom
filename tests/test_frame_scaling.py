"""돋보기 프레임 변환 경로 회귀 테스트.

v2.46에서 PIL 파이프라인을 numpy -> QImage 직접 변환으로 교체했다.
이 테스트는 새 경로가 기존 PIL 경로와 픽셀 단위로 동일한 결과를 내는지
확인한다(PIL이 없으면 해당 비교만 건너뛴다).
"""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# `python tests/test_...py` 로 바로 실행할 수 있도록 저장소 루트를 import 경로에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PyQt6.QtWidgets import QApplication

from magnifier import scale_bgra_frame_to_qimage  # noqa: E402


class FrameScalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _make_bgra(width, height, seed=7):
        rng = np.random.default_rng(seed)
        frame = rng.integers(0, 256, size=(height, width, 4), dtype=np.uint8)
        frame[:, :, 3] = 255
        return frame

    def test_rejects_degenerate_sizes(self):
        payload = self._make_bgra(4, 4).tobytes()
        for args in ((0, 4, 8, 8), (4, 0, 8, 8), (4, 4, 0, 8), (4, 4, 8, 0)):
            image, buffer = scale_bgra_frame_to_qimage(payload, *args)
            self.assertIsNone(image)
            self.assertIsNone(buffer)

    def test_output_geometry_and_channel_order(self):
        frame = self._make_bgra(6, 5)
        image, buffer = scale_bgra_frame_to_qimage(frame.tobytes(), 6, 5, 6, 5)
        self.assertIsNotNone(image)
        self.assertEqual(image.width(), 6)
        self.assertEqual(image.height(), 5)

        # 1:1 배율이면 원본 BGR 채널이 그대로 유지되어야 한다.
        np.testing.assert_array_equal(buffer, frame[:, :, :3])

        # QImage가 실제로 올바른 RGB를 읽어내는지 픽셀로 확인한다.
        blue, green, red = (int(v) for v in frame[2, 3, :3])
        pixel = image.pixelColor(3, 2)
        self.assertEqual((pixel.red(), pixel.green(), pixel.blue()),
                         (red, green, blue))

    def test_matches_pillow_nearest_neighbour_output(self):
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover
            self.skipTest("Pillow is not installed")

        src_w, src_h, view_w, view_h = 7, 5, 23, 17
        frame = self._make_bgra(src_w, src_h, seed=99)
        payload = frame.tobytes()

        _, buffer = scale_bgra_frame_to_qimage(payload, src_w, src_h, view_w, view_h)

        # 교체 이전 구현과 동일한 PIL 경로로 기준값을 만든다.
        reference = Image.frombytes('RGB', (src_w, src_h), payload, 'raw', 'BGRX')
        reference = reference.resize((view_w, view_h), Image.Resampling.NEAREST)
        expected_rgb = np.asarray(reference, dtype=np.uint8)

        # 새 경로는 BGR 순서로 담기므로 채널을 뒤집어 비교한다.
        np.testing.assert_array_equal(buffer[:, :, ::-1], expected_rgb)

    def test_buffer_is_contiguous_for_qimage_stride(self):
        frame = self._make_bgra(9, 9, seed=3)
        image, buffer = scale_bgra_frame_to_qimage(frame.tobytes(), 9, 9, 30, 21)
        self.assertTrue(buffer.flags["C_CONTIGUOUS"])
        self.assertEqual(buffer.strides[0], 30 * 3)
        self.assertEqual(image.bytesPerLine(), buffer.strides[0])


if __name__ == "__main__":
    unittest.main()
