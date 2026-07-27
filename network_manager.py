import json
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import socket
import hashlib
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PyQt6.QtCore import QObject, pyqtSignal, QUrl, QTimer
from PyQt6.QtWebSockets import QWebSocket
from PyQt6.QtNetwork import QAbstractSocket

# Global lock and clients dictionary for local WebSocket handling
STATE_LOCK = threading.Lock()
WEBSOCKET_CLIENTS = {}  # { room_id: set(handler) }

# 프레임/요청 크기 상한. 파티 상태 메시지는 실제로 수백 바이트 수준이므로
# 넉넉하게 잡아도 정상 트래픽에는 영향이 없다. 상한이 없으면 64비트 길이
# 필드에 수 GB를 넣은 단일 프레임으로 서버 메모리를 고갈시킬 수 있다.
MAX_WS_PAYLOAD_BYTES = 64 * 1024
MAX_HTTP_BODY_BYTES = 64 * 1024
MAX_ROOM_ID_LEN = 64
MAX_PLAYER_NAME_LEN = 64
MAX_SKILL_NAME_LEN = 64


def sanitize_token(value, max_len, fallback=None):
    """room_id / player / skill 같은 식별자를 길이와 타입 기준으로 정규화한다.

    비정상 값이면 fallback을 반환한다(fallback이 None이면 거부를 의미).
    """
    if not isinstance(value, str):
        return fallback
    trimmed = value.strip()
    if not trimmed or len(trimmed) > max_len:
        return fallback
    return trimmed


def coerce_cooldown_duration(value):
    """쿨타임 값을 0~24시간 범위의 실수로 강제한다."""
    try:
        seconds = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if seconds != seconds or seconds in (float("inf"), float("-inf")):
        return 0.0
    return max(0.0, min(86400.0, seconds))


def read_ws_frame(rfile, max_payload=MAX_WS_PAYLOAD_BYTES):
    first_byte = rfile.read(1)
    if not first_byte:
        return None, None
    header = first_byte[0]
    opcode = header & 0x0F
    
    second_byte = rfile.read(1)
    if not second_byte:
        return None, None
    mask_and_len = second_byte[0]
    is_masked = (mask_and_len & 0x80) != 0
    payload_len = mask_and_len & 0x7F
    
    if payload_len == 126:
        len_bytes = rfile.read(2)
        if len(len_bytes) < 2:
            return None, None
        payload_len = int.from_bytes(len_bytes, byteorder='big')
    elif payload_len == 127:
        len_bytes = rfile.read(8)
        if len(len_bytes) < 8:
            return None, None
        payload_len = int.from_bytes(len_bytes, byteorder='big')

    # 상한을 넘는 프레임은 읽지 않고 연결을 끊는다. read()를 시도하는 순간
    # 선언된 길이만큼 버퍼를 할당하게 되므로 반드시 할당 전에 걸러야 한다.
    if payload_len > max_payload:
        return None, None

    masking_key = b""
    if is_masked:
        masking_key = rfile.read(4)
        if len(masking_key) < 4:
            return None, None
            
    payload = rfile.read(payload_len)
    if len(payload) < payload_len:
        return None, None
        
    if is_masked:
        unmasked = bytearray(payload_len)
        for i in range(payload_len):
            unmasked[i] = payload[i] ^ masking_key[i % 4]
        payload = bytes(unmasked)
        
    return opcode, payload

def send_ws_message(wfile, text):
    try:
        payload = text.encode('utf-8')
        length = len(payload)
        
        frame = bytearray([0x81]) # FIN + Text
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(length.to_bytes(2, byteorder='big'))
        else:
            frame.append(127)
            frame.extend(length.to_bytes(8, byteorder='big'))
            
        frame.extend(payload)
        wfile.write(frame)
        wfile.flush()
        return True
    except Exception:
        return False

# Global in-memory state store for party member cooldowns
# Format: { room_id: { player_name: { skill_name: { is_ready: bool, timestamp: float, cooldown_duration: int } } } }
PARTY_STATES = {}

class PartyStatusHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Mute console logging to keep execution clean
        pass

    def _read_json_body(self):
        """Content-Length를 검증한 뒤 본문을 JSON으로 파싱한다.

        이전에는 선언된 Content-Length를 그대로 신뢰해 rfile.read()에 넘겼다.
        따라서 임의 클라이언트가 거대한 길이를 선언해 메모리를 고갈시킬 수
        있었다. 이제 상한을 넘으면 413으로 거절한다.

        Returns:
            (dict, None) 또는 (None, 상태코드)
        """
        try:
            content_length = int(self.headers.get('Content-Length', 0) or 0)
        except (TypeError, ValueError):
            return None, 400
        if content_length < 0:
            return None, 400
        if content_length > MAX_HTTP_BODY_BYTES:
            return None, 413
        if content_length == 0:
            return {}, None
        raw = self.rfile.read(content_length)
        if len(raw) < content_length:
            return None, 400
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None, 400
        if not isinstance(parsed, dict):
            return None, 400
        return parsed, None

    def _send_json(self, status, payload_bytes):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(payload_bytes)

    def do_POST(self):
        try:
            if self.path == "/update":
                data, error_status = self._read_json_body()
                if error_status is not None:
                    self._send_json(error_status, b'{"status":"rejected"}')
                    return

                room_id = sanitize_token(data.get("room_id", "default"),
                                         MAX_ROOM_ID_LEN, "default")
                player = sanitize_token(data.get("player"), MAX_PLAYER_NAME_LEN)
                skill = sanitize_token(data.get("skill"), MAX_SKILL_NAME_LEN)
                is_ready = bool(data.get("is_ready"))
                cooldown_duration = coerce_cooldown_duration(data.get("cooldown_duration", 0))

                if player and skill:
                    # ThreadingHTTPServer는 요청마다 스레드를 띄우므로 공유 dict
                    # 접근은 반드시 STATE_LOCK 아래에서 해야 한다. WS 핸들러는
                    # 이미 락을 쓰고 있었지만 HTTP 핸들러는 빠져 있었다.
                    with STATE_LOCK:
                        PARTY_STATES.setdefault(room_id, {}).setdefault(player, {})[skill] = {
                            "is_ready": is_ready,
                            "timestamp": time.time(),
                            "cooldown_duration": cooldown_duration
                        }
                self._send_json(200, b'{"status":"success"}')
            elif self.path == "/clear":
                data, error_status = self._read_json_body()
                if error_status is not None:
                    self._send_json(error_status, b'{"status":"rejected"}')
                    return

                room_id = sanitize_token(data.get("room_id", "default"),
                                         MAX_ROOM_ID_LEN, "default")
                with STATE_LOCK:
                    if room_id in PARTY_STATES:
                        PARTY_STATES[room_id].clear()

                self._send_json(200, b'{"status":"cleared"}')
            else:
                self.send_response(404)
                self.end_headers()
        except Exception:
            # 예외 문자열을 그대로 돌려주면 내부 경로/상태가 노출된다.
            try:
                self._send_json(500, b'{"status":"error"}')
            except Exception:
                pass

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/ws":
            headers = self.headers
            if headers.get("Upgrade", "").lower() == "websocket":
                key = headers.get("Sec-WebSocket-Key")
                if not key:
                    self.send_response(400)
                    self.end_headers()
                    return
                
                accept_val = base64.b64encode(
                    hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode('utf-8')).digest()
                ).decode('utf-8')
                
                self.send_response(101, "Switching Protocols")
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept_val)
                self.end_headers()
                
                self.handle_ws_connection()
                return
            else:
                self.send_response(400)
                self.end_headers()
        elif parsed_url.path == "/status":
            query_params = parse_qs(parsed_url.query)
            room_id = sanitize_token(query_params.get("room_id", ["default"])[0],
                                     MAX_ROOM_ID_LEN, "default")
            # 락 없이 읽으면 다른 스레드의 setdefault 중간 상태를 직렬화할 수 있다.
            # 응답 생성 중 dict가 바뀌지 않도록 락 안에서 얕은 복사를 만든다.
            with STATE_LOCK:
                room_states = {
                    player: {skill: dict(state) for skill, state in skills.items()}
                    for player, skills in PARTY_STATES.get(room_id, {}).items()
                }

            response_data = {
                "server_time": time.time(),
                "states": room_states
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def handle_ws_connection(self):
        room_id = "default"
        player_name = "unknown"
        registered = False
        
        try:
            while True:
                opcode, payload = read_ws_frame(self.rfile)
                if opcode is None:
                    break
                if opcode == 8:  # Close
                    break
                elif opcode == 9:  # Ping
                    pong_frame = bytearray([0x8A, 0])
                    self.wfile.write(pong_frame)
                    self.wfile.flush()
                    continue
                elif opcode == 1:  # Text
                    msg_text = payload.decode('utf-8')
                    try:
                        msg = json.loads(msg_text)
                    except Exception:
                        continue
                    
                    action = msg.get("action")
                    if action == "join":
                        room_id = sanitize_token(msg.get("room_id", "default"),
                                                 MAX_ROOM_ID_LEN, "default")
                        player_name = sanitize_token(msg.get("player", "unknown"),
                                                     MAX_PLAYER_NAME_LEN, "unknown")
                        
                        with STATE_LOCK:
                            if room_id not in WEBSOCKET_CLIENTS:
                                WEBSOCKET_CLIENTS[room_id] = set()
                            WEBSOCKET_CLIENTS[room_id].add(self)
                            registered = True
                            
                            # Send initial room state
                            room_states = PARTY_STATES.get(room_id, {})
                            join_response = {
                                "type": "status",
                                "server_time": time.time(),
                                "states": room_states
                            }
                            send_ws_message(self.wfile, json.dumps(join_response))
                            
                    elif action == "update":
                        room_id = sanitize_token(msg.get("room_id", "default"),
                                                 MAX_ROOM_ID_LEN, "default")
                        player = sanitize_token(msg.get("player"), MAX_PLAYER_NAME_LEN)
                        skill = sanitize_token(msg.get("skill"), MAX_SKILL_NAME_LEN)
                        is_ready = bool(msg.get("is_ready"))
                        cooldown_duration = coerce_cooldown_duration(msg.get("cooldown_duration", 0))
                        
                        if player and skill:
                            with STATE_LOCK:
                                if room_id not in PARTY_STATES:
                                    PARTY_STATES[room_id] = {}
                                if player not in PARTY_STATES[room_id]:
                                    PARTY_STATES[room_id][player] = {}
                                    
                                PARTY_STATES[room_id][player][skill] = {
                                    "is_ready": is_ready,
                                    "timestamp": time.time(),
                                    "cooldown_duration": cooldown_duration
                                }
                                
                                # Broadcast update to all clients in the same room
                                broadcast_msg = {
                                    "type": "update",
                                    "server_time": time.time(),
                                    "player": player,
                                    "skill": skill,
                                    "state": PARTY_STATES[room_id][player][skill]
                                }
                                payload_str = json.dumps(broadcast_msg)
                                
                                dead_clients = set()
                                for client in WEBSOCKET_CLIENTS.get(room_id, []):
                                    if not send_ws_message(client.wfile, payload_str):
                                        dead_clients.add(client)
                                
                                if dead_clients:
                                    WEBSOCKET_CLIENTS[room_id].difference_update(dead_clients)
        except Exception:
            pass
        finally:
            if registered:
                with STATE_LOCK:
                    if room_id in WEBSOCKET_CLIENTS:
                        WEBSOCKET_CLIENTS[room_id].discard(self)


def get_local_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Try to connect to public DNS to get local route IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_network_category():
    import subprocess
    try:
        # Check network category without popping up CMD window using CREATE_NO_WINDOW flag
        res = subprocess.run(
            ["powershell", "-Command", "Get-NetConnectionProfile | Select-Object -ExpandProperty NetworkCategory"],
            capture_output=True,
            text=True,
            creationflags=0x08000000
        )
        output = res.stdout.strip()
        if "Public" in output:
            return "Public"
        elif "Private" in output:
            return "Private"
        return "Unknown"
    except Exception:
        return "Error"


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with SO_REUSEADDR enabled.
    
    This prevents 'Address already in use' errors when restarting the server
    quickly after it was stopped, because TIME_WAIT zombie sockets from the
    previous session's polling connections would otherwise block the port
    for up to 2 minutes (Windows default TIME_WAIT timeout).
    """
    allow_reuse_address = True
    
    def server_bind(self):
        # Explicitly set SO_REUSEADDR before binding
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


class CooldownServer(QObject):
    started = pyqtSignal()
    stopped = pyqtSignal()
    
    def __init__(self, host="0.0.0.0", port=19090, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.server_thread = None
        self.httpd = None
        
    def start(self):
        if self.server_thread and self.server_thread.is_alive():
            return
            
        PARTY_STATES.clear()
            
        host = self.host
        port = self.port
        success = False
        last_err = None
        
        # Try binding from port to port+100 dynamically to bypass Windows port reservations
        for p in range(port, port + 100):
            try:
                self.httpd = ReusableThreadingHTTPServer((host, p), PartyStatusHandler)
                self.port = p
                success = True
                break
            except OSError as e:
                last_err = e
                continue
                
        if not success:
            err_msg = str(last_err) if last_err else "포트 바인딩 실패"
            raise OSError(f"19090 ~ 19190 포트 대역 중 사용 가능한 네트워크 포트를 찾을 수 없거나 방화벽/백신에 의해 바인딩이 차단되었습니다. 상세 오류: {err_msg}")
            
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.started.emit()
        
        # Verify if the server is actually up and responding via self-ping
        threading.Thread(target=self.verify_self_ping, daemon=True).start()
        
    def _run_server(self):
        try:
            self.httpd.serve_forever()
        except Exception as e:
            import traceback
            try:
                with open("server_error.log", "w", encoding="utf-8") as f:
                    f.write(f"Server Run Error: {str(e)}\n{traceback.format_exc()}\n")
            except Exception:
                pass
                
    def verify_self_ping(self):
        time.sleep(0.3)
        url = f"http://127.0.0.1:{self.port}/status"
        proxy_support = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_support)
        try:
            req = urllib.request.Request(url, method="GET")
            with opener.open(req, timeout=1.5) as res:
                res.read()
            with open("server_running.log", "w", encoding="utf-8") as f:
                f.write(f"[SUCCESS] Server is successfully running at http://127.0.0.1:{self.port} (0.0.0.0 binding)\n")
        except Exception as e:
            with open("server_running.log", "w", encoding="utf-8") as f:
                f.write(f"[FAIL] Self-ping failed at {url}. Error: {str(e)}\n")
            
    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
        PARTY_STATES.clear()
        self.stopped.emit()


class CharacterProfileLookup(QObject):
    profile_loaded = pyqtSignal(int, dict)
    lookup_failed = pyqtSignal(int, str)
    lookup_progress = pyqtSignal(int, str)

    RETRY_TIMEOUTS = (15, 25, 25)
    RETRY_DELAY_SECONDS = 1.5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._request_lock = threading.Lock()
        self._request_id = 0

    def lookup(self, server_url, character_name):
        character_name = (character_name or "").strip()
        server_url = self.normalize_server_url(server_url)
        with self._request_lock:
            self._request_id += 1
            request_id = self._request_id

        worker = threading.Thread(
            target=self._lookup_worker,
            args=(request_id, server_url, character_name),
            daemon=True,
        )
        worker.start()
        return request_id

    @staticmethod
    def normalize_server_url(server_url):
        server_url = (server_url or "").strip().rstrip("/")
        if server_url.startswith("wss://"):
            return "https://" + server_url[6:]
        if server_url.startswith("ws://"):
            return "http://" + server_url[5:]
        if "://" not in server_url:
            scheme = "http://" if server_url.startswith(("127.0.0.1", "localhost")) else "https://"
            return scheme + server_url
        return server_url

    def _lookup_worker(self, request_id, server_url, character_name):
        query = urllib.parse.urlencode({"name": character_name})
        url = f"{server_url}/character?{query}"
        last_error = None
        for attempt, timeout_seconds in enumerate(self.RETRY_TIMEOUTS, start=1):
            try:
                if attempt > 1:
                    self.lookup_progress.emit(
                        request_id,
                        f"자동 감지 서버 준비 중 · 자동 재시도 {attempt}/{len(self.RETRY_TIMEOUTS)}",
                    )
                request = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json"},
                    method="GET",
                )
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict) or not payload.get("character_class"):
                    raise ValueError("invalid profile response")
                payload["requested_name"] = character_name
                self.profile_loaded.emit(request_id, payload)
                return
            except urllib.error.HTTPError as error:
                last_error = error
                # Render cold-start gateways can transiently return these codes.
                if error.code not in (502, 503, 504) or attempt >= len(self.RETRY_TIMEOUTS):
                    self.lookup_failed.emit(request_id, self._http_error_message(error))
                    return
            except (TimeoutError, socket.timeout, urllib.error.URLError) as error:
                last_error = error
                if attempt >= len(self.RETRY_TIMEOUTS):
                    break
            except Exception:
                self.lookup_failed.emit(request_id, "캐릭터 정보를 확인하지 못했습니다.")
                return

            self.lookup_progress.emit(
                request_id,
                f"첫 응답이 늦어 서버를 깨우는 중 · 잠시 후 자동 재시도합니다 ({attempt}/{len(self.RETRY_TIMEOUTS)})",
            )
            time.sleep(self.RETRY_DELAY_SECONDS)

        if isinstance(last_error, (TimeoutError, socket.timeout)) or (
            isinstance(last_error, urllib.error.URLError)
            and isinstance(getattr(last_error, "reason", None), (TimeoutError, socket.timeout))
        ):
            self.lookup_failed.emit(request_id, "캐릭터 조회 시간이 초과되었습니다.")
        else:
            self.lookup_failed.emit(request_id, "자동 감지 서버에 연결할 수 없습니다.")

    @staticmethod
    def _http_error_message(error):
        try:
            payload = json.loads(error.read().decode("utf-8"))
            if isinstance(payload, dict) and payload.get("message"):
                return str(payload["message"])
        except Exception:
            pass
        if error.code == 404:
            return "캐릭터를 찾을 수 없습니다. 이름을 확인해 주세요."
        if error.code == 429:
            return "조회 요청이 많습니다. 잠시 후 다시 시도해 주세요."
        if error.code == 503:
            return "캐릭터 자동 감지 기능을 준비 중입니다."
        return "캐릭터 정보를 확인하지 못했습니다."


class CooldownClient(QObject):
    status_updated = pyqtSignal(dict)  # Emits PARTY_STATES dictionary
    connection_failed = pyqtSignal(str)
    connection_ok = pyqtSignal()       # Emitted on successful connection — used to clear error UI
    
    def __init__(self, server_url="http://127.0.0.1:19090", player_name="플레이어", room_id="default", client_id=None, class_name="홀리나이트", parent=None):
        super().__init__(parent)
        self.server_url = server_url.rstrip("/")
        self.player_name = player_name
        self.room_id = room_id
        self.client_id = client_id
        self.class_name = class_name
        
        self.is_running = False
        self.party_states = {}  # Local cache of the full party states dict
        
        # Initialize QWebSocket
        self.ws = QWebSocket()
        self.ws.connected.connect(self.on_connected)
        self.ws.disconnected.connect(self.on_disconnected)
        self.ws.textMessageReceived.connect(self.on_message_received)
        self.ws.errorOccurred.connect(self.on_error)
        
        # Reconnect timer for WebSocket
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setInterval(3000)
        self.reconnect_timer.timeout.connect(self.connect_ws)
        
    def start(self):
        self.is_running = True
        self.connect_ws()
        
    def stop(self):
        self.is_running = False
        self.reconnect_timer.stop()
        self.ws.close()
        
    def connect_ws(self):
        if not self.is_running:
            return
        if self.ws.state() == QAbstractSocket.SocketState.UnconnectedState:
            ws_url = self.server_url
            if ws_url.startswith("https://"):
                ws_url = ws_url.replace("https://", "wss://")
            elif ws_url.startswith("http://"):
                ws_url = ws_url.replace("http://", "ws://")
            else:
                ws_url = "wss://" + ws_url
                
            if not ws_url.endswith("/ws"):
                ws_url = ws_url + "/ws"
                
            self.ws.open(QUrl(ws_url))
            
    def on_connected(self):
        self.reconnect_timer.stop()
        self.connection_ok.emit()
        
        # Send join message
        join_msg = {
            "action": "join",
            "room_id": self.room_id,
            "player": self.player_name,
            "client_id": self.client_id,
            "class_name": self.class_name
        }
        self.ws.sendTextMessage(json.dumps(join_msg))
        
    def on_disconnected(self):
        if self.is_running:
            self.reconnect_timer.start()
            
    def on_error(self, error):
        error_str = self.ws.errorString()
        self.connection_failed.emit(f"웹소켓 에러: {error_str}")
            
    def send_update(self, skill_name, is_ready, cooldown_duration=0):
        if not self.is_running:
            return
            
        if self.ws.state() == QAbstractSocket.SocketState.ConnectedState:
            update_msg = {
                "action": "update",
                "room_id": self.room_id,
                "player": self.player_name,
                "client_id": self.client_id,
                "class_name": self.class_name,
                "skill": skill_name,
                "is_ready": is_ready,
                "cooldown_duration": cooldown_duration
            }
            try:
                self.ws.sendTextMessage(json.dumps(update_msg))
            except Exception as e:
                self.connection_failed.emit(f"웹소켓 전송 실패: {str(e)}")

    def set_class_name(self, class_name):
        """Persist and immediately share a class change without waiting for a skill event."""
        self.class_name = class_name
        if not self.is_running or self.ws.state() != QAbstractSocket.SocketState.ConnectedState:
            return
        self.ws.sendTextMessage(json.dumps({
            "action": "class",
            "room_id": self.room_id,
            "player": self.player_name,
            "client_id": self.client_id,
            "class_name": self.class_name,
        }))
            
    def on_message_received(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "status":
                states = data.get("states", {})
                server_time = data.get("server_time", time.time())
                
                time_offset = time.time() - server_time
                for player, skills in states.items():
                    if isinstance(skills, dict):
                        for skill, info in skills.items():
                            if isinstance(info, dict) and "timestamp" in info:
                                info["timestamp"] = info["timestamp"] + time_offset
                                
                self.party_states = states
                self.status_updated.emit(self.party_states)
                self.connection_ok.emit()
                
            elif msg_type == "update":
                player = data.get("player")
                skill = data.get("skill")
                state = data.get("state")
                server_time = data.get("server_time", time.time())
                
                time_offset = time.time() - server_time
                if isinstance(state, dict) and "timestamp" in state:
                    state["timestamp"] = state["timestamp"] + time_offset
                    
                if player and skill is not None:
                    if player not in self.party_states:
                        self.party_states[player] = {}
                    self.party_states[player][skill] = state
                    
                self.status_updated.emit(self.party_states)
                self.connection_ok.emit()
            elif msg_type == "remove":
                player = data.get("player")
                if player:
                    self.party_states.pop(player, None)
                    self.status_updated.emit(self.party_states)
            elif msg_type == "class":
                player = data.get("player")
                class_name = data.get("class_name")
                if player and class_name:
                    self.party_states.setdefault(player, {})["_class"] = class_name
                    self.status_updated.emit(self.party_states)
        except Exception as e:
            pass
