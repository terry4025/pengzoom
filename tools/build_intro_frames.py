"""마스코트 인트로 스프라이트 시트를 재생 가능한 프레임으로 정규화한다.

생성 모델이 뽑아 준 시트는 칸마다 캐릭터 크기와 위치가 흔들린다(실측: 세로
322~451px, 중심 x ±55px). 그대로 재생하면 펭구가 커졌다 작아지며 좌우로
미끄러지므로, 프레임마다 아래 두 기준으로 맞춘 뒤 같은 캔버스에 다시 얹는다.

  * 배율  — 황토색 배 타원의 가로 폭. 날개를 들거나 펼치면 실루엣 전체는
            변하지만 배는 변하지 않으므로 포즈에 흔들리지 않는 척도다.
  * 위치  — 배 타원 중심 x(좌우)와 알파 경계 맨 아래 = 발바닥(상하).
            발바닥을 고정해야 스쿼시/스트레치가 땅에 붙어 보인다.

배율은 항상 1.0 이하만 쓴다(가장 작은 프레임에 맞춘다). 확대가 섞이면 선이
흐려져 프레임마다 선명도가 달라진다.

사용:
    py tools/build_intro_frames.py
    py tools/build_intro_frames.py --sheet <시트.png> --cols 3 --rows 2
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHEET = ROOT / "intro_assets" / "mascot_intro_sheet_v1.png"
OUTPUT_DIR = ROOT / "intro_assets" / "frames"

# 캔버스 여백(정규화 후 픽셀). 스쿼시/스트레치는 런타임 변환으로 주므로
# 캔버스 자체에는 최소한의 숨 쉴 공간만 둔다.
SIDE_MARGIN = 10
TOP_MARGIN = 10
BOTTOM_MARGIN = 10


def cell_images(sheet: Image.Image, cols: int, rows: int):
    """시트를 균일 격자로 잘라 (index, RGBA 배열) 목록을 만든다."""
    width, height = sheet.size
    if width % cols or height % rows:
        raise SystemExit(
            f"시트 크기 {width}x{height} 가 {cols}x{rows} 격자로 정확히 나뉘지 않습니다."
        )
    cell_w, cell_h = width // cols, height // rows
    array = np.array(sheet.convert("RGBA"))
    cells = []
    for row in range(rows):
        for col in range(cols):
            cell = array[row * cell_h:(row + 1) * cell_h,
                         col * cell_w:(col + 1) * cell_w]
            cells.append(cell.copy())
    return cells, (cell_w, cell_h)


def largest_blob(mask: np.ndarray) -> np.ndarray:
    """마스크에서 가장 큰 연결 요소만 남긴다.

    캐릭터 본체는 한 덩어리로 이어져 있고, 생성 이미지에는 칸 바깥쪽에 알파가
    희미하게 남은 티끌이 섞여 있다. 티끌을 그대로 두면 경계 상자가 부풀어
    프레임마다 다른 위치로 정렬된다.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8)
    if count <= 1:
        raise SystemExit("마스크가 비어 있습니다.")
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == biggest


def alpha_bbox(cell: np.ndarray, threshold: int = 40):
    """캐릭터 본체(가장 큰 알파 덩어리)의 경계 상자."""
    body = largest_blob(cell[..., 3] > threshold)
    ys, xs = np.where(body)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def belly_metrics(cell: np.ndarray):
    """황토색 배 타원의 가로 폭과 중심 x를 구한다.

    노란 물갈퀴 발도 같은 색 범위에 들어오므로, 색 마스크를 그대로 쓰면 두 발을
    가로지르는 행이 '가장 넓은 행'으로 뽑혀 폭이 실제 배보다 커진다. 배는 발보다
    면적이 훨씬 크므로 가장 큰 연결 요소만 남겨 이 혼동을 없앤다.
    """
    rgb = cell[..., :3].astype(int)
    opaque = cell[..., 3] > 200
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mask = opaque & (red > 170) & (green > 140) & (blue < 180) & (red - blue > 40)
    if mask.sum() < 200:
        raise SystemExit("배 타원을 찾지 못했습니다. 색이 참조 아이콘과 다른지 확인하세요.")
    belly = largest_blob(mask)
    widths = belly.sum(axis=1)
    waist = int(widths.argmax())
    row_xs = np.where(belly[waist])[0]
    return {
        "width": float(row_xs.max() - row_xs.min() + 1),
        "center_x": float((row_xs.max() + row_xs.min()) / 2.0),
        "waist_y": waist,
        "pixels": int(belly.sum()),
    }


def scale_rgba(cell: np.ndarray, scale: float) -> Image.Image:
    """알파를 프리멀티플라이한 뒤 축소한다.

    투명 영역의 RGB에는 쓰레기 값이 들어 있어(이 시트는 (43,44,43,0)),
    그냥 리샘플하면 그 색이 외곽선으로 번져 어두운 테가 생긴다.
    """
    height, width = cell.shape[:2]
    target = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    rgba = cell.astype(np.float64)
    alpha = rgba[..., 3:4] / 255.0
    premultiplied = np.concatenate([rgba[..., :3] * alpha, rgba[..., 3:4]], axis=2)
    resized = np.array(
        Image.fromarray(premultiplied.astype(np.uint8), "RGBA").resize(target, Image.LANCZOS),
        dtype=np.float64,
    )
    out_alpha = np.clip(resized[..., 3:4], 0, 255)
    safe = np.where(out_alpha > 0, out_alpha / 255.0, 1.0)
    straight = np.concatenate([np.clip(resized[..., :3] / safe, 0, 255), out_alpha], axis=2)
    return Image.fromarray(straight.astype(np.uint8), "RGBA")


def build(sheet_path: Path, cols: int, rows: int, output_dir: Path):
    sheet = Image.open(sheet_path)
    cells, cell_size = cell_images(sheet, cols, rows)

    measured = []
    for index, cell in enumerate(cells):
        x0, y0, x1, y1 = alpha_bbox(cell)
        belly = belly_metrics(cell)
        measured.append({
            "index": index,
            "bbox": (x0, y0, x1, y1),
            "belly_width": belly["width"],
            "belly_center_x": belly["center_x"],
            "baseline_y": y1,
        })

    target_belly = min(item["belly_width"] for item in measured)

    # 정규화 후 필요한 캔버스 크기: 발바닥 기준선 위로 가장 높이 솟는 프레임과
    # 배 중심에서 좌우로 가장 넓게 퍼지는 프레임을 모두 담아야 한다.
    up = left = right = 0.0
    for item in measured:
        scale = target_belly / item["belly_width"]
        x0, y0, x1, y1 = item["bbox"]
        up = max(up, (y1 - y0) * scale)
        left = max(left, (item["belly_center_x"] - x0) * scale)
        right = max(right, (x1 - item["belly_center_x"]) * scale)

    half = int(np.ceil(max(left, right))) + SIDE_MARGIN
    canvas_w = half * 2
    canvas_h = int(np.ceil(up)) + TOP_MARGIN + BOTTOM_MARGIN
    anchor_x = canvas_w // 2
    anchor_y = canvas_h - BOTTOM_MARGIN

    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("frame_*.png"):
        existing.unlink()

    report = []
    for item in measured:
        scale = target_belly / item["belly_width"]
        scaled = scale_rgba(cells[item["index"]], scale)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        offset_x = int(round(anchor_x - item["belly_center_x"] * scale))
        offset_y = int(round(anchor_y - (item["baseline_y"] + 1) * scale))
        canvas.alpha_composite(scaled, (offset_x, offset_y))

        name = f"frame_{item['index'] + 1}.png"
        canvas.save(output_dir / name)

        check = np.array(canvas)
        cx0, cy0, cx1, cy1 = alpha_bbox(check)
        report.append({
            "file": name,
            "scale": round(scale, 4),
            "belly_width": round(item["belly_width"], 1),
            "baseline_y": int(cy1),
            "belly_center_x": round(belly_metrics(check)["center_x"], 1),
            "bbox": [cx0, cy0, cx1, cy1],
        })

    manifest = {
        "source_sheet": sheet_path.name,
        "grid": {"cols": cols, "rows": rows, "cell": list(cell_size)},
        "canvas": [canvas_w, canvas_h],
        "anchor": [anchor_x, anchor_y],
        "frames": report,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"시트      : {sheet_path}")
    print(f"칸 크기   : {cell_size[0]}x{cell_size[1]}  ({cols}x{rows})")
    print(f"캔버스    : {canvas_w}x{canvas_h}, 앵커 ({anchor_x}, {anchor_y})")
    print(f"기준 배폭 : {target_belly:.1f}px")
    for row in report:
        print(f"  {row['file']}  scale={row['scale']:.3f}  "
              f"baseline_y={row['baseline_y']}  belly_cx={row['belly_center_x']}  "
              f"bbox={row['bbox']}")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, default=DEFAULT_SHEET)
    parser.add_argument("--cols", type=int, default=3)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)

    if not args.sheet.exists():
        raise SystemExit(f"시트를 찾을 수 없습니다: {args.sheet}")
    build(args.sheet, args.cols, args.rows, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
