"""검증된 타이머 ROI 프레임을 저장소에 복사하고 번들 글리프 프로파일을 만든다.

라벨은 8배 확대 몬타주를 눈으로 읽어 확정했다(tools/verify_timer_pipeline.py 와
같은 표). 결과물:
    boss_debuff_assets/samples/verified/dark_grenade_<순번>_<라벨>s.png
    boss_debuff_assets/timer_profiles/dark_grenade.json

사용법:
    py -3.14 tools/build_timer_seed.py [원본_샘플_폴더]
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import boss_debuff_detector as bd  # noqa: E402
from verify_timer_pipeline import GROUND_TRUTH, load_index  # noqa: E402

VERIFIED_DIR = ROOT / "boss_debuff_assets" / "samples" / "verified"
PROFILE_PATH = ROOT / "boss_debuff_assets" / "timer_profiles" / f"{bd.DEFAULT_DEBUFF_ID}.json"


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        bd.user_data_root() / "samples" / bd.DEFAULT_DEBUFF_ID
    index = load_index(source)
    if not index:
        print(f"원본 샘플이 없습니다: {source}")
        return 1

    if VERIFIED_DIR.exists():
        shutil.rmtree(VERIFIED_DIR)
    VERIFIED_DIR.mkdir(parents=True, exist_ok=True)

    copied = []
    for seq, truth in sorted(GROUND_TRUTH.items()):
        path = index.get(seq)
        if path is None or float(truth) < 1.0:   # 소수 표시 프레임은 학습 대상이 아니다
            continue
        target = VERIFIED_DIR / f"{bd.DEFAULT_DEBUFF_ID}_{seq:03d}_{int(truth):02d}s.png"
        shutil.copyfile(path, target)
        copied.append(target)
    print(f"검증 프레임 {len(copied)}장 복사 -> {VERIFIED_DIR}")

    result = bd.train_timer_profile(
        sorted(copied),
        bd.DEFAULT_DEBUFF_ID,
        base_profile=bd.TimerGlyphProfile(profile_id=bd.DEFAULT_DEBUFF_ID),
        output_path=PROFILE_PATH,
    )
    result["source"] = "verified-samples"
    print(f"학습 이미지 {result['used_images']}장 · 글리프 {result['added_glyphs']}개 · "
          f"숫자 {result['digits']} · 정확도 {result['accuracy']} · 신뢰 {result['trusted']}")
    for line in result["skipped"]:
        print("  건너뜀:", line)
    return 0 if result["trusted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
