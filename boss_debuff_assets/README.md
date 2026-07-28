# 보스 디버프 (암흑 수류탄) 감지 에셋

## 폴더 구조

```
boss_debuff_assets/
├─ icons/dark_grenade/        아이콘 매칭 템플릿 (인게임 26x26 셀 크롭)
├─ timer_profiles/            남은 초 숫자 글리프 프로파일 (JSON)
├─ samples/                   부트스트랩에 쓴 크롭
│  └─ screenshots/            ← ★ 여기에 전체 스크린샷을 넣어 주세요
└─ reference/                 아이템 아이콘 원본 등 참고용 (매칭에 사용 안 함)
```

## 1. 아이콘 템플릿 (`icons/dark_grenade/`)

보스 체력바 아래 디버프 칸을 **테두리까지 포함해 정사각형으로** 자른 PNG만 넣습니다.
1920x1080 / UI 배율 100%에서는 26x26px입니다. 여러 장 넣으면 모두 후보로 사용하며,
감지 시에는 16~46px 범위로 크기를 바꿔가며 찾으므로 다른 해상도·UI 배율도 커버됩니다.

새 템플릿을 자동으로 만들려면 (셀 좌상단 좌표와 크기를 알 때):

```bash
py tools/bootstrap_boss_debuff_assets.py <스크린샷.png> <cell_x> <cell_y> <cell_size> --label 9
```

> 주의: 우측 하단 배틀 아이템 단축키 칸에도 같은 아이콘이 보입니다.
> 그 아이콘은 렌더링이 달라 일치율 0.52~0.61에 머물고, 감지 영역도 보스 체력바 아래
> 디버프 줄로만 제한하므로 오탐되지 않습니다.

## 2. 남은 초 숫자 표본 (`samples/screenshots/`)

인게임 숫자는 1080p에서 **높이 8px**밖에 안 되므로, 표본 없이는 숫자를 표시하지 않습니다
(대신 지속시간 기반 추정치를 씁니다). 표본을 모으는 방법은 두 가지입니다.

### 방법 A — 앱에서 자동 수집 (권장)

`설정 → 보스 디버프 → 숫자 샘플 수집`을 켜고 암흑 수류탄을 한 번 사용하세요.
2자리 → 1자리로 바뀌는 순간이 정확히 **9초**이므로, 그 시점을 기준으로 앞쪽 프레임까지
소급 라벨링되어 한 번의 사용으로 0~9 숫자가 모두 모입니다.
그 다음 `샘플로 숫자 학습` 버튼을 누르면 끝입니다.

### 방법 B — 스크린샷을 폴더에 넣고 일괄 학습

파일명에 **화면에 보이는 남은 초**를 넣어 `samples/screenshots/` 에 저장합니다.

```
samples/screenshots/카멘_12s.png
samples/screenshots/카멘_9s.png
samples/screenshots/카멘_3s.png
```

그리고 아래 명령을 실행하면 아이콘 위치를 자동으로 찾아 숫자 영역을 잘라 학습합니다.

```bash
py tools/boss_debuff_calibrate.py --screenshots boss_debuff_assets/samples/screenshots
py tools/boss_debuff_calibrate.py --report        # 현재 학습 상태 확인
```

0~9가 모두 채워지면 파티 현황창의 남은 시간이 `OCR` 소스로 바뀝니다.
그 전까지는 `추정`(지속시간 기반) 또는 `자동 보정`(자릿수 전환 기준)으로 표시됩니다.
