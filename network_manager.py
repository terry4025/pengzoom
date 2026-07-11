import json
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
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
                
                if player and skill is not None:
                    if player not in PARTY_STATES:
                        PARTY_STATES[player] = {}
                    PARTY_STATES[player][skill] = {
                        "is_ready": is_ready,
                        "timestamp": time.time()
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
            
        try:
            # Use multi-threaded HTTP server if possible
            from http.server import ThreadingHTTPServer
            self.httpd = ThreadingHTTPServer((self.host, self.port), PartyStatusHandler)
        except ImportError:
            self.httpd = HTTPServer((self.host, self.port), PartyStatusHandler)
            
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.started.emit()
        
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
            
    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        self.stopped.emit()


class CooldownClient(QObject):
    status_updated = pyqtSignal(dict)  # Emits PARTY_STATES dictionary
    connection_failed = pyqtSignal(str)
    
    def __init__(self, server_url="http://127.0.0.1:19090", player_name="플레이어", parent=None):
        super().__init__(parent)
        self.server_url = server_url.rstrip("/")
        self.player_name = player_name
        self.polling_thread = None
        self.is_running = False
        
        # Create a custom urllib opener that explicitly bypasses system proxy settings.
        # This fixes WinError connection timeouts (urlopen error timed out) caused by proxies trying to route 127.0.0.1/localhost.
        proxy_support = urllib.request.ProxyHandler({})
        self.opener = urllib.request.build_opener(proxy_support)
        
    def start(self):
        self.is_running = True
        self.polling_thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.polling_thread.start()
        
    def stop(self):
        self.is_running = False
        
    def send_update(self, skill_name, is_ready):
        # Fire-and-forget HTTP POST request to server in background thread to avoid GUI freeze
        def _send():
            url = f"{self.server_url}/update"
            data = json.dumps({
                "player": self.player_name,
                "skill": skill_name,
                "is_ready": is_ready
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
                    self.status_updated.emit(response_data)
            except Exception as e:
                self.connection_failed.emit(f"상태 가져오기 실패: {str(e)}")
                
            # Poll status every 500ms
            time.sleep(0.5)
