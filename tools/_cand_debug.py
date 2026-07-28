"""임시: 적대 배경에서 각 후보의 분류 결과까지 본다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import boss_debuff_detector as bd
import eval_timer_robustness as ev

VERIFIED = ROOT / "boss_debuff_assets" / "samples" / "verified"
profile = bd.TimerGlyphProfile.load_for(bd.DEFAULT_DEBUFF_ID)
names = ["dark_grenade_023_08s.png", "dark_grenade_005_17s.png", "dark_grenade_030_05s.png"]

for background in ("따뜻한 주황", "글자색과 유사한 살몬"):
    print(f"===== {background}")
    for name in names:
        path = VERIFIED / name
        label = bd.parse_sample_label(path)
        image = ev.composite(bd.read_image(path), background)
        print(f"  {name} label={label}")
        found = False
        for binary, suffix, digits, mode, thr, prio in bd.timer_hypotheses(image):
            found = True
            value, conf = profile.read_seconds(binary, digits)
            per = [profile.classify(bd.normalize_glyph(binary, b)) for b in digits]
            print(f"    {mode:7s} thr={thr:3d} digits={len(digits)} value={value} "
                  f"conf={conf:.2f} per={[(d, round(c, 2)) for d, c in per]}")
        if not found:
            print("    (게이트를 통과한 후보 없음)")
