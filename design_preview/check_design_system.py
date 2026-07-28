"""모달 디자인 시스템(MODAL_STYLE, 헬퍼)이 정상 로드되는지 확인한다."""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication


def main():
    app = QApplication(sys.argv)
    try:
        import magnifier

        style = magnifier.get_modal_style()
        print("modal style chars :", len(style))
        print("placeholder left  :", "__CHECK_IMAGE__" in style)
        print("check asset path  :", magnifier.get_check_asset_path())
        print("check asset exists:",
              os.path.exists(magnifier.get_check_asset_path().replace("/", os.sep)))

        header, close_btn = magnifier.build_modal_header(
            "제목", "부제", on_close=lambda: None)
        print("header built      :", header is not None, "close:", close_btn is not None)

        card, body = magnifier.build_section_card("섹션", magnifier.LUCIDE_USER_SVG)
        print("card built        :", card is not None, "body:", body is not None)
        print("divider built     :", magnifier.build_divider() is not None)
        print("OK")
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
