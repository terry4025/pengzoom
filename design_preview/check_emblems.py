"""클래스 엠블럼 캐시 조회가 실제로 성공하는지 확인한다."""

import os
import sys

os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication


def main():
    app = QApplication(sys.argv)
    import magnifier

    print("CACHE_DIR =", magnifier.CACHE_DIR)
    print("exists    =", os.path.isdir(magnifier.CACHE_DIR))
    svgs = [n for n in os.listdir(magnifier.CACHE_DIR)
            if n.endswith(".svg")] if os.path.isdir(magnifier.CACHE_DIR) else []
    print("cached svg count =", len(svgs))

    missing = 0
    for cls in ("홀리나이트", "바드", "도화가", "소서리스", "브레이커", "발키리"):
        pixmap = magnifier.get_class_emblem(cls, 22, "#f5f5f7")
        ok = pixmap is not None and not pixmap.isNull()
        if not ok:
            missing += 1
        print(f"  {cls}: {'OK' if ok else 'MISSING'}")

    print("missing =", missing)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
