import json
import threading
import time
import urllib.request
import urllib.error
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PyQt6.QtCore import QObject, pyqtSignal

# Global in-memory state store for party member cooldowns
# Format: { "player_name": { "skill_name": { "is_ready": bool, "timestamp": float } } }
PARTY_STATES = {}

class PartyStatusHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Mute console logging to keep execution clean
        pass
        
    def do_POST(self):
        try:
            if self.path == "/update":
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode("utf-8"))
                
                player = data.get("player")
                skill = data.get("skill")
                is_ready = data.get("is_ready")
                cooldown_duration = data.get("cooldown_duration", 0)
                
                if player and skill is not None:
                    if player not in PARTY_STATES:
                        PARTY_STATES[player] = {}
                    PARTY_STATES[player][skill] = {
                        "is_ready": is_ready,
                        "timestamp": time.time(),
                        "cooldown_duration": cooldown_duration
                    }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"success"}')
            elif self.path == "/clear":
                PARTY_STATES.clear()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"cleared"}')
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
            except Exception:
                pass

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(PARTY_STATES).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


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


class CooldownClient(QObject):
    status_updated = pyqtSignal(dict)  # Emits PARTY_STATES dictionary
    connection_failed = pyqtSignal(str)
    connection_ok = pyqtSignal()       # Emitted on successful poll — used to clear error UI
    
    def __init__(self, server_url="http://127.0.0.1:19090", player_name="플레이어", parent=None):
        super().__init__(parent)
        self.server_url = server_url.rstrip("/")
        self.player_name = player_name
        self.polling_thread = None
        self.is_running = False
        self.consecutive_failures = 0
        
        # Create a custom urllib opener that explicitly bypasses system proxy settings.
        # This fixes WinError connection timeouts (urlopen error timed out) caused by proxies trying to route 127.0.0.1/localhost.
        proxy_support = urllib.request.ProxyHandler({})
        self.opener = urllib.request.build_opener(proxy_support)
        
    def start(self):
        self.is_running = True
        self.consecutive_failures = 0
        self.polling_thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.polling_thread.start()
        
    def stop(self):
        self.is_running = False
        
    def send_update(self, skill_name, is_ready, cooldown_duration=0):
        # Fire-and-forget HTTP POST request to server in background thread to avoid GUI freeze
        def _send():
            url = f"{self.server_url}/update"
            data = json.dumps({
                "player": self.player_name,
                "skill": skill_name,
                "is_ready": is_ready,
                "cooldown_duration": cooldown_duration
            }).encode("utf-8")
            
            try:
                req = urllib.request.Request(
                    url, 
                    data=data, 
                    headers={'Content-Type': 'application/json'},
                    method="POST"
                )
                with self.opener.open(req, timeout=2.0) as res:
                    res.read()
            except Exception as e:
                self.connection_failed.emit(f"업데이트 전송 실패: {str(e)}")
                
        threading.Thread(target=_send, daemon=True).start()
        
    def poll_loop(self):
        while self.is_running:
            url = f"{self.server_url}/status"
            try:
                req = urllib.request.Request(url, method="GET")
                with self.opener.open(req, timeout=2.0) as res:
                    response_data = json.loads(res.read().decode("utf-8"))
                    self.consecutive_failures = 0
                    self.status_updated.emit(response_data)
                    self.connection_ok.emit()
            except Exception as e:
                self.consecutive_failures += 1
                self.connection_failed.emit(f"상태 가져오기 실패: {str(e)}")
                
            # Poll status every 1 second (was 0.5s — reduced to avoid TIME_WAIT socket exhaustion)
            time.sleep(1.0)
