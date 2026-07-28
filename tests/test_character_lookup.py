import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

# `python tests/test_...py` 로 바로 실행할 수 있도록 저장소 루트를 import 경로에 둔다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from network_manager import CharacterProfileLookup  # noqa: E402


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class CharacterProfileLookupTests(unittest.TestCase):
    def setUp(self):
        self.lookup = CharacterProfileLookup()
        self.loaded = []
        self.failed = []
        self.progress = []
        self.lookup.profile_loaded.connect(lambda request_id, payload: self.loaded.append((request_id, payload)))
        self.lookup.lookup_failed.connect(lambda request_id, message: self.failed.append((request_id, message)))
        self.lookup.lookup_progress.connect(lambda request_id, message: self.progress.append((request_id, message)))

    def test_first_timeout_retries_and_succeeds_without_user_click(self):
        success = _FakeResponse({"character_class": "브레이커", "server_name": "루페온"})
        with mock.patch(
            "network_manager.urllib.request.urlopen",
            side_effect=[TimeoutError(), success],
        ) as urlopen, mock.patch("network_manager.time.sleep"):
            self.lookup._lookup_worker(7, "https://relay.example", "캐릭터")

        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(self.failed, [])
        self.assertEqual(self.loaded[0][0], 7)
        self.assertEqual(self.loaded[0][1]["character_class"], "브레이커")
        self.assertEqual(self.loaded[0][1]["requested_name"], "캐릭터")
        self.assertTrue(self.progress)

    def test_three_timeouts_emit_one_final_failure(self):
        with mock.patch(
            "network_manager.urllib.request.urlopen",
            side_effect=[TimeoutError(), TimeoutError(), TimeoutError()],
        ) as urlopen, mock.patch("network_manager.time.sleep"):
            self.lookup._lookup_worker(8, "https://relay.example", "캐릭터")

        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(self.loaded, [])
        self.assertEqual(self.failed, [(8, "캐릭터 조회 시간이 초과되었습니다.")])

    def test_not_found_does_not_retry(self):
        error = urllib.error.HTTPError(
            "https://relay.example/character",
            404,
            "Not Found",
            None,
            io.BytesIO(json.dumps({"message": "캐릭터를 찾을 수 없습니다."}).encode("utf-8")),
        )
        with mock.patch("network_manager.urllib.request.urlopen", side_effect=error) as urlopen:
            self.lookup._lookup_worker(9, "https://relay.example", "없는캐릭터")

        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(self.loaded, [])
        self.assertEqual(self.failed, [(9, "캐릭터를 찾을 수 없습니다.")])


if __name__ == "__main__":
    unittest.main()
