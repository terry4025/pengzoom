"""magnifier.py의 특정 라인 범위를 다른 파일 내용으로 치환하는 보조 스크립트.

사용:
    python design_preview/_splice.py <target> <start_line> <end_line> <replacement_file>

start_line / end_line 은 1-based 포함 범위.
"""
import sys


def main():
    target, start, end, replacement = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    with open(target, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    with open(replacement, "r", encoding="utf-8") as handle:
        new_lines = handle.readlines()

    print(f"replacing lines {start}..{end} ({end - start + 1} lines) "
          f"with {len(new_lines)} lines")
    print(f"  first removed: {lines[start - 1].rstrip()}")
    print(f"  last  removed: {lines[end - 1].rstrip()}")

    lines[start - 1:end] = new_lines
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.writelines(lines)
    print(f"done. file now has {len(lines)} lines")


if __name__ == "__main__":
    main()
