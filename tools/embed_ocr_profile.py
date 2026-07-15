"""Generate the Python-embedded fallback for the bundled OCR profile."""

from __future__ import annotations

import base64
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ocr_profiles" / "lostark_1080p_100.json"
OUTPUT = ROOT / "ocr_default_profile.py"


def main() -> None:
    payload = base64.b85encode(zlib.compress(SOURCE.read_bytes(), 9)).decode("ascii")
    chunks = [payload[index:index + 100] for index in range(0, len(payload), 100)]
    lines = [
        '"""Generated fallback OCR profile. Run tools/embed_ocr_profile.py to refresh."""',
        "",
        "import base64",
        "import json",
        "import zlib",
        "",
        "_PAYLOAD = (",
        *[f"    {chunk!r}" for chunk in chunks],
        ")",
        "PROFILE_DATA = json.loads(zlib.decompress(base64.b85decode(_PAYLOAD)).decode('utf-8'))",
        "",
    ]
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
