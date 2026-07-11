import json
import threading
import time
import urllib.request
import urllib.error
from uvicorn import Config, Server
from fastapi import FastAPI, Request
from PyQt6.QtCore import QObject, pyqtSignal

# Core FastAPI app definition
app = FastAPI()

# Global in-memory state store for party member cooldowns
# Format: { "player_name": { "skill_name": { "is_ready": bool, "timestamp": float } } }
PARTY_STATES = {}

@app.post("/update")
async def update_status(request: Request):
    try:
        data = await request.json()
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
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/status")
async def get_status():
    return PARTY_STATES

@app.post("/clear")
async def clear_status():
    PARTY_STATES.clear()
    return {"status": "cleared"}


class CooldownServer(QObject):
    started = pyqtSignal()
    stopped = pyqtSignal()
    
    def __init__(self, host="0.0.0.0", port=9090, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.server_thread = None
        self.server = None
        
    def start(self):
        if self.server_thread and self.server_thread.is_alive():
            return
            
        config = Config(app=app, host=self.host, port=self.port, log_level="warning", install_signal_handlers=False)
        self.server = Server(config=config)
        
        # Override default uvicorn server run to handle graceful shutdown safely
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.started.emit()
        
    def _run_server(self):
        try:
            self.server.run()
        except Exception:
            pass
            
    def stop(self):
        if self.server:
            self.server.should_exit = True
        self.stopped.emit()


class CooldownClient(QObject):
    status_updated = pyqtSignal(dict)  # Emits PARTY_STATES dictionary
    connection_failed = pyqtSignal(str)
    
    def __init__(self, server_url="http://127.0.0.1:9090", player_name="플레이어", parent=None):
        super().__init__(parent)
        self.server_url = server_url.rstrip("/")
        self.player_name = player_name
        self.polling_thread = None
        self.is_running = False
        
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
                with urllib.request.urlopen(req, timeout=2.0) as res:
                    res.read()
            except Exception as e:
                self.connection_failed.emit(f"업데이트 전송 실패: {str(e)}")
                
        threading.Thread(target=_send, daemon=True).start()
        
    def poll_loop(self):
        while self.is_running:
            url = f"{self.server_url}/status"
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2.0) as res:
                    response_data = json.loads(res.read().decode("utf-8"))
                    self.status_updated.emit(response_data)
            except Exception as e:
                self.connection_failed.emit(f"상태 가져오기 실패: {str(e)}")
                
            # Poll status every 500ms
            time.sleep(0.5)
