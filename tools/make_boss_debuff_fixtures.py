"""Generate the small PNG fixtures used by tests/test_boss_debuff_detector.py."""
from pathlib import Path
import os
import shutil
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(os.environ["TEMP"])
FIX = ROOT / "tests" / "fixtures" / "boss_debuff"
REF = ROOT / "boss_debuff_assets" / "reference"

SHOT_A = TMP / "orca-paste-1785174605304-dbc40ce6-72fe-409d-8e95-a77ed0e69122.png"
SHOT_B = TMP / "orca-paste-1785174661146-ec392761-cd39-45e9-94a5-b8cc90be44e8.png"
ITEM_ICON = TMP / "orca-paste-1785174112367-a7a388b0-e530-422a-bcdd-c8384584aba6.png"
ITEM_ART = TMP / "orca-paste-1785174290721-e3d70e6f-aa6b-4ab0-973a-d3396820dcfa.png"
INVEN = TMP / "orca-paste-1785174352655-5227e847-41ea-4661-9666-b91107d6e936.png"


def rd(path, flags=cv2.IMREAD_COLOR):
    if not path.exists():
        print(f"!! missing {path}")
        return None
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), flags)


def wr(path: Path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", image)
    if ok:
        buf.tofile(str(path))
    print(f"{'ok ' if ok else 'ERR'} {path.relative_to(ROOT)} {image.shape}")


def main():
    a, b = rd(SHOT_A), rd(SHOT_B)
    if a is None or b is None:
        return 1
    # Boss debuff strip band, same rectangle in both captures.  The cell sits at
    # x=930 in A and x=926 in B, which is exactly the drift we must tolerate.
    wr(FIX / "band_1080p_9s_a.png", a[130:210, 560:1340])
    wr(FIX / "band_1080p_9s_b.png", b[130:210, 560:1340])
    # Bottom-right battle-item hotkey bar: the same item icon is visible there
    # and must never be reported as a boss debuff.
    wr(FIX / "hotkeybar_1080p.png", a[950:1079, 1020:1360])
    # Timer ROI crop with a known label, used by the calibration test.
    wr(FIX / "timer_roi_09s.png", a[182:198, 921:965])

    icon = rd(ITEM_ICON, cv2.IMREAD_UNCHANGED)
    if icon is not None:
        wr(REF / "item_icon_48.png", icon)
    art = rd(ITEM_ART)
    if art is not None:
        wr(REF / "item_art_360.png", art)
    inven = rd(INVEN)
    if inven is not None:
        wr(REF / "boss_debuff_strip_reference.png", inven)
    return 0


if __name__ == "__main__":
    sys.exit(main())
