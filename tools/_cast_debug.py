"""임시: 캐스트 단조성을 깨는 프레임을 찾아 원인을 본다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import boss_debuff_detector as bd
import eval_timer_robustness as ev

profile = bd.TimerGlyphProfile.load_for(bd.DEFAULT_DEBUFF_ID)
casts = ev.load_user_casts(bd.user_data_root() / "samples" / bd.DEFAULT_DEBUFF_ID)
for index, cast in enumerate(casts):
    seq = []
    for path, label in cast:
        image = bd.read_image(path)
        reading = bd.read_timer_value(image, profile)
        seq.append((path.name, label, reading.value, reading.mode, reading.threshold,
                    round(reading.confidence, 2), reading.glyph_count,
                    round(ev.background_warm(image))))
    print(f"=== 캐스트 {index} ({len(cast)}장)")
    previous = None
    for name, label, value, mode, thr, conf, count, warm in seq:
        flag = ""
        if value is not None and previous is not None and not (0 <= previous - value <= 1):
            flag = "  <== 모순"
        if value is not None:
            previous = value
        print(f"  {name[15:]:>22} label={label:>3} read={str(value):>4} "
              f"{mode:6s} thr={thr:3d} conf={conf:4.2f} n={count} warm={warm:4d}{flag}")
