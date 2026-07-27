"""릴레이/내장 서버 보안 하드닝 회귀 테스트.

v2.46에서 다음을 수정했다.
1. WebSocket 프레임 payload 길이 상한 (무제한 -> 64KB)
2. 내장 HTTP 핸들러의 PARTY_STATES 접근에 STATE_LOCK 적용
3. HTTP body 크기 상한 + 식별자 길이/타입 검증
"""

import inspect
import io
import json
import threading
import unittest

import network_manager
import server


def make_frame(payload, opcode=0x1, force_len=None, masked=False):
    """테스트용 WebSocket 텍스트 프레임을 만든다.

    force_len을 주면 실제 payload와 다른 길이를 선언해 악성 프레임을 흉내낸다.
    """
    body = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    declared = len(body) if force_len is None else force_len
    frame = bytearray([0x80 | opcode])
    mask_bit = 0x80 if masked else 0x00
    if declared < 126:
        frame.append(mask_bit | declared)
    elif declared < 65536:
        frame.append(mask_bit | 126)
        frame.extend(declared.to_bytes(2, "big"))
    else:
        frame.append(mask_bit | 127)
        frame.extend(declared.to_bytes(8, "big"))
    if masked:
        frame.extend(b"\x00\x00\x00\x00")
    frame.extend(body)
    return bytes(frame)


class WebSocketPayloadCapTests(unittest.TestCase):
    """1. 선언된 길이가 상한을 넘으면 버퍼를 할당하지 않고 끊어야 한다."""

    def test_normal_frame_is_still_accepted(self):
        for module in (network_manager, server):
            with self.subTest(module=module.__name__):
                text = json.dumps({"action": "update", "player": "p", "skill": "s"})
                opcode, payload = module.read_ws_frame(io.BytesIO(make_frame(text)))
                self.assertEqual(opcode, 1)
                self.assertEqual(json.loads(payload.decode("utf-8"))["player"], "p")

    def test_masked_frame_is_unmasked(self):
        raw = b"hello"
        key = b"\x01\x02\x03\x04"
        masked_body = bytes(raw[i] ^ key[i % 4] for i in range(len(raw)))
        frame = bytearray([0x81, 0x80 | len(raw)])
        frame.extend(key)
        frame.extend(masked_body)
        for module in (network_manager, server):
            with self.subTest(module=module.__name__):
                opcode, payload = module.read_ws_frame(io.BytesIO(bytes(frame)))
                self.assertEqual(opcode, 1)
                self.assertEqual(payload, raw)

    def test_frame_declaring_gigabytes_is_rejected(self):
        # 64비트 길이 필드에 4GB를 선언한다. 상한 검사가 없으면 read()가
        # 그만큼 버퍼를 할당하려 든다.
        hostile = make_frame(b"", force_len=4 * 1024 * 1024 * 1024)
        for module in (network_manager, server):
            with self.subTest(module=module.__name__):
                opcode, payload = module.read_ws_frame(io.BytesIO(hostile))
                self.assertIsNone(opcode)
                self.assertIsNone(payload)

    def test_frame_just_over_cap_is_rejected_and_under_cap_passes(self):
        for module in (network_manager, server):
            cap = module.MAX_WS_PAYLOAD_BYTES
            with self.subTest(module=module.__name__):
                over = make_frame(b"", force_len=cap + 1)
                self.assertEqual(module.read_ws_frame(io.BytesIO(over)), (None, None))

                under = make_frame(b"x" * cap)
                opcode, payload = module.read_ws_frame(io.BytesIO(under))
                self.assertEqual(opcode, 1)
                self.assertEqual(len(payload), cap)

    def test_cap_is_enforced_before_allocation(self):
        """상한 초과 시 rfile.read(payload_len)이 호출되지 않아야 한다."""

        class TrackingReader:
            def __init__(self, data):
                self.stream = io.BytesIO(data)
                self.max_requested = 0

            def read(self, size):
                self.max_requested = max(self.max_requested, size)
                return self.stream.read(size)

        huge = 4 * 1024 * 1024 * 1024
        for module in (network_manager, server):
            with self.subTest(module=module.__name__):
                reader = TrackingReader(make_frame(b"", force_len=huge))
                module.read_ws_frame(reader)
                # 헤더(최대 8바이트)까지만 읽어야 한다.
                self.assertLessEqual(reader.max_requested, 8)


class InputSanitizationTests(unittest.TestCase):
    """3. 식별자 길이/타입 검증과 쿨타임 값 정규화."""

    def test_sanitize_token_accepts_normal_values(self):
        for module in (network_manager, server):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.sanitize_token("테리4025", 64), "테리4025")
                self.assertEqual(module.sanitize_token("  room1  ", 64), "room1")

    def test_sanitize_token_rejects_oversized_and_wrong_types(self):
        for module in (network_manager, server):
            with self.subTest(module=module.__name__):
                self.assertIsNone(module.sanitize_token("x" * 65, 64))
                self.assertIsNone(module.sanitize_token("", 64))
                self.assertIsNone(module.sanitize_token("   ", 64))
                self.assertIsNone(module.sanitize_token(None, 64))
                self.assertIsNone(module.sanitize_token(12345, 64))
                self.assertIsNone(module.sanitize_token({"a": 1}, 64))
                self.assertEqual(module.sanitize_token("x" * 65, 64, "default"), "default")

    def test_cooldown_duration_is_clamped(self):
        for module in (network_manager, server):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.coerce_cooldown_duration(30), 30.0)
                self.assertEqual(module.coerce_cooldown_duration(-5), 0.0)
                self.assertEqual(module.coerce_cooldown_duration(10 ** 12), 86400.0)
                self.assertEqual(module.coerce_cooldown_duration("nan"), 0.0)
                self.assertEqual(module.coerce_cooldown_duration("inf"), 0.0)
                self.assertEqual(module.coerce_cooldown_duration("not-a-number"), 0.0)
                self.assertEqual(module.coerce_cooldown_duration(None), 0.0)


class _FakeRequestHandler(network_manager.PartyStatusHandler):
    """BaseHTTPRequestHandler를 소켓 없이 구동하기 위한 최소 스텁."""

    def __init__(self, path, body=b"", declared_length=None):
        self.path = path
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        length = len(body) if declared_length is None else declared_length
        self.headers = {"Content-Length": str(length)}
        self.responses = []

    def send_response(self, code, message=None):
        self.responses.append(code)

    def send_header(self, *args, **kwargs):
        pass

    def end_headers(self):
        pass


class HttpBodyLimitTests(unittest.TestCase):
    """3. Content-Length를 신뢰하지 않고 상한을 적용해야 한다."""

    def setUp(self):
        with network_manager.STATE_LOCK:
            network_manager.PARTY_STATES.clear()

    def tearDown(self):
        with network_manager.STATE_LOCK:
            network_manager.PARTY_STATES.clear()

    def test_valid_update_is_stored(self):
        body = json.dumps({
            "room_id": "raid", "player": "펭구", "skill": "축복",
            "is_ready": True, "cooldown_duration": 45,
        }).encode("utf-8")
        handler = _FakeRequestHandler("/update", body)
        handler.do_POST()

        self.assertEqual(handler.responses, [200])
        stored = network_manager.PARTY_STATES["raid"]["펭구"]["축복"]
        self.assertTrue(stored["is_ready"])
        self.assertEqual(stored["cooldown_duration"], 45.0)

    def test_oversized_content_length_is_rejected_with_413(self):
        handler = _FakeRequestHandler(
            "/update", b"{}", declared_length=network_manager.MAX_HTTP_BODY_BYTES + 1)
        handler.do_POST()

        self.assertEqual(handler.responses, [413])
        self.assertEqual(network_manager.PARTY_STATES, {})

    def test_malformed_body_is_rejected_with_400(self):
        for body in (b"not json", b"[1,2,3]", b"\xff\xfe"):
            with self.subTest(body=body):
                handler = _FakeRequestHandler("/update", body)
                handler.do_POST()
                self.assertEqual(handler.responses, [400])
        self.assertEqual(network_manager.PARTY_STATES, {})

    def test_oversized_identifiers_are_dropped(self):
        body = json.dumps({
            "room_id": "r", "player": "p" * 200, "skill": "s",
            "is_ready": True, "cooldown_duration": 10,
        }).encode("utf-8")
        handler = _FakeRequestHandler("/update", body)
        handler.do_POST()

        # 요청 자체는 200으로 끝나지만 상태는 오염되지 않아야 한다.
        self.assertEqual(handler.responses, [200])
        self.assertEqual(network_manager.PARTY_STATES, {})

    def test_error_response_does_not_leak_exception_text(self):
        handler = _FakeRequestHandler("/update", b"not json")
        handler.do_POST()
        self.assertNotIn(b"Traceback", handler.wfile.getvalue())
        self.assertNotIn(b"Expecting value", handler.wfile.getvalue())


class StateLockUsageTests(unittest.TestCase):
    """2. 내장 서버의 공유 상태 접근이 락으로 감싸여 있어야 한다."""

    def test_http_handlers_take_the_state_lock(self):
        for method in (network_manager.PartyStatusHandler.do_POST,
                       network_manager.PartyStatusHandler.do_GET):
            source = inspect.getsource(method)
            with self.subTest(method=method.__name__):
                self.assertIn("PARTY_STATES", source)
                self.assertIn("with STATE_LOCK", source)

    def test_concurrent_updates_do_not_lose_writes(self):
        with network_manager.STATE_LOCK:
            network_manager.PARTY_STATES.clear()

        players = 24
        skills_each = 8

        def worker(index):
            for skill_index in range(skills_each):
                body = json.dumps({
                    "room_id": "raid",
                    "player": f"player{index}",
                    "skill": f"skill{skill_index}",
                    "is_ready": False,
                    "cooldown_duration": 12,
                }).encode("utf-8")
                _FakeRequestHandler("/update", body).do_POST()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(players)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        room = network_manager.PARTY_STATES["raid"]
        self.assertEqual(len(room), players)
        for index in range(players):
            self.assertEqual(len(room[f"player{index}"]), skills_each)

        with network_manager.STATE_LOCK:
            network_manager.PARTY_STATES.clear()


if __name__ == "__main__":
    unittest.main()
