"""Local Companion Web Server for Smartphone-assisted login on handhelds.

Sprache: Deutsch (pr0-Amtssprache) • Architektur: 100% zertifizierter Vibecode.
Runs a lightweight HTTP server on the local LAN. Allows users to open a
mobile-optimized web page on their smartphone or PC in the same Wi-Fi,
enter their pr0gramm credentials and solve the captcha on a touch screen.
"""

from __future__ import annotations

import base64
import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs

logger = logging.getLogger("pr0.auth_server")


def get_local_ip() -> str:
    """Find the local LAN IP address of the device."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


HTML_PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>pr0-retroconsole - Login</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: #161618;
      color: #f2f5f4;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 16px;
    }
    .card {
      background: #212124;
      border: 1px solid #323236;
      border-radius: 10px;
      max-width: 420px;
      width: 100%;
      padding: 24px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }
    .header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 20px;
    }
    .badge {
      background: #ee4d2e;
      color: #fff;
      font-weight: 800;
      font-size: 16px;
      padding: 3px 8px;
      border-radius: 4px;
      letter-spacing: 0.5px;
    }
    .title {
      font-size: 19px;
      font-weight: 700;
      color: #f2f5f4;
    }
    .subtitle {
      font-size: 13px;
      color: #88888e;
      margin-bottom: 20px;
      line-height: 1.4;
    }
    .form-group {
      margin-bottom: 16px;
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #bbbbbe;
      margin-bottom: 6px;
    }
    input[type="text"], input[type="password"] {
      width: 100%;
      background: #161618;
      border: 1px solid #38383c;
      color: #f2f5f4;
      font-size: 15px;
      padding: 10px 12px;
      border-radius: 6px;
      outline: none;
      transition: border-color 0.2s;
    }
    input[type="text"]:focus, input[type="password"]:focus {
      border-color: #ee4d2e;
    }
    .captcha-wrap {
      background: #161618;
      border: 1px solid #38383c;
      border-radius: 6px;
      padding: 8px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .captcha-img {
      max-width: 100%;
      height: auto;
      border-radius: 4px;
      background: #fff;
    }
    .btn-reload {
      background: transparent;
      border: 1px solid #444448;
      color: #aaa;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
    }
    .btn-reload:hover {
      border-color: #888;
      color: #fff;
    }
    .btn-submit {
      width: 100%;
      background: #ee4d2e;
      color: #ffffff;
      border: none;
      font-size: 16px;
      font-weight: 700;
      padding: 12px;
      border-radius: 6px;
      cursor: pointer;
      margin-top: 8px;
      transition: opacity 0.2s;
    }
    .btn-submit:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .btn-submit:hover:not(:disabled) {
      filter: brightness(1.1);
    }
    .status-msg {
      margin-top: 14px;
      font-size: 13px;
      text-align: center;
      min-height: 20px;
      padding: 8px;
      border-radius: 6px;
      display: none;
    }
    .status-error {
      display: block;
      background: rgba(238, 77, 46, 0.15);
      border: 1px solid #ee4d2e;
      color: #ff765b;
    }
    .status-success {
      display: block;
      background: rgba(0, 229, 153, 0.15);
      border: 1px solid #00e599;
      color: #00e599;
      font-weight: 600;
    }
    .success-box {
      display: none;
      text-align: center;
      padding: 20px 0;
    }
    .success-icon {
      font-size: 48px;
      color: #00e599;
      margin-bottom: 12px;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <span class="badge">pr0</span>
      <span class="title">Handheld Login</span>
    </div>
    <div id="formSection">
      <p class="subtitle">Gib deine Anmeldedaten ein, um deinen Handheld direkt anzumelden. Keine Passwörter werden dauerhaft gespeichert.</p>

      <form id="loginForm" onsubmit="submitLogin(event)">
        <div class="form-group">
          <label for="username">Benutzername</label>
          <input type="text" id="username" name="username" required autocomplete="username" autofocus>
        </div>

        <div class="form-group">
          <label for="password">Passwort</label>
          <input type="password" id="password" name="password" required autocomplete="current-password">
        </div>

        <div class="form-group">
          <label>Captcha-Prüfung</label>
          <div class="captcha-wrap">
            <img id="captchaImg" class="captcha-img" alt="Captcha lädt..." src="/captcha.png">
            <button type="button" class="btn-reload" onclick="reloadCaptcha()">↻ Neues Captcha laden</button>
          </div>
          <input type="text" id="captcha" name="captcha" placeholder="Captcha-Zeichen hier eingeben..." required autocomplete="off">
        </div>

        <button type="submit" id="submitBtn" class="btn-submit">Auf Handheld anmelden</button>
        <div id="statusMsg" class="status-msg"></div>
      </form>
    </div>

    <div id="successSection" class="success-box">
      <div class="success-icon">✓</div>
      <h2 style="margin-bottom: 8px;">Anmeldung erfolgreich!</h2>
      <p style="color: #aaa; font-size: 14px;">Dein Handheld ist jetzt eingeloggt als <strong id="successUser" style="color: #fff;"></strong>.<br><br>Du kannst diese Seite jetzt schließen.</p>
    </div>
  </div>

  <script>
    function reloadCaptcha() {
      const img = document.getElementById('captchaImg');
      img.src = '/captcha.png?t=' + Date.now();
      document.getElementById('captcha').value = '';
    }

    async function submitLogin(e) {
      e.preventDefault();
      const btn = document.getElementById('submitBtn');
      const status = document.getElementById('statusMsg');
      const username = document.getElementById('username').value.trim();
      const password = document.getElementById('password').value;
      const captcha = document.getElementById('captcha').value.trim();

      status.className = 'status-msg';
      status.style.display = 'none';
      btn.disabled = true;
      btn.textContent = 'Anmeldung läuft...';

      try {
        const resp = await fetch('/api/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: username, password: password, captcha: captcha })
        });
        const data = await resp.json();

        if (data.success) {
          document.getElementById('formSection').style.display = 'none';
          document.getElementById('successUser').textContent = data.username || username;
          document.getElementById('successSection').style.display = 'block';
        } else {
          status.textContent = data.error || 'Anmeldung fehlgeschlagen.';
          status.className = 'status-msg status-error';
          reloadCaptcha();
          btn.disabled = false;
          btn.textContent = 'Auf Handheld anmelden';
        }
      } catch (err) {
        status.textContent = 'Verbindungsfehler zum Handheld: ' + err.message;
        status.className = 'status-msg status-error';
        btn.disabled = false;
        btn.textContent = 'Auf Handheld anmelden';
      }
    }
  </script>
</body>
</html>
"""


class AuthCompanionServer:
    """Lightweight LAN companion web server for mobile login."""

    def __init__(
        self,
        api: Any,
        on_success: Callable[[str, str], None],
        preferred_port: int = 8080,
    ):
        self.api = api
        self.on_success = on_success
        self.preferred_port = preferred_port

        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port: int = preferred_port
        self.local_ip: str = get_local_ip()
        self.is_running: bool = False

        self.current_token: str = ""
        self.current_captcha_bytes: bytes = b""
        self.lock = threading.Lock()

    def _make_handler(self):
        parent = self

        class CompanionHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                # Suppress noisy HTTP request logging to console
                pass

            def do_GET(self) -> None:
                if self.path == "/" or self.path.startswith("/?"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    body = HTML_PAGE.encode("utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                elif self.path.startswith("/captcha.png"):
                    # Fetch fresh captcha challenge from pr0gramm API
                    c_data = parent.api.fetch_captcha()
                    token = c_data.get("token", "")
                    b64_str = c_data.get("captcha", "")
                    img_bytes = b""
                    if "," in b64_str:
                        try:
                            img_bytes = base64.b64decode(b64_str.split(",", 1)[1])
                        except Exception as e:
                            logger.error("Failed to decode base64 captcha: %s", e)

                    with parent.lock:
                        parent.current_token = token
                        parent.current_captcha_bytes = img_bytes

                    if img_bytes:
                        self.send_response(200)
                        self.send_header("Content-Type", "image/png")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Content-Length", str(len(img_bytes)))
                        self.end_headers()
                        self.wfile.write(img_bytes)
                    else:
                        self.send_error(500, "Captcha load error")

                elif self.path.startswith("/api/status"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    resp = json.dumps({"active": True, "ip": parent.local_ip}).encode("utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)

                else:
                    self.send_error(404, "Not Found")

            def do_POST(self) -> None:
                if self.path == "/api/login":
                    content_length = int(self.headers.get("Content-Length", 0))
                    post_data = self.rfile.read(content_length)

                    data: dict[str, str] = {}
                    try:
                        data = json.loads(post_data.decode("utf-8"))
                    except Exception:
                        try:
                            parsed = parse_qs(post_data.decode("utf-8"))
                            data = {k: v[0] for k, v in parsed.items()}
                        except Exception:
                            pass

                    name = str(data.get("name", "")).strip()
                    password = str(data.get("password", ""))
                    captcha = str(data.get("captcha", "")).strip()

                    with parent.lock:
                        token = parent.current_token

                    if not token:
                        # Fallback: grab fresh captcha token if none cached
                        c_data = parent.api.fetch_captcha()
                        token = c_data.get("token", "")

                    # Execute login
                    result = parent.api.login(
                        username=name,
                        password=password,
                        token=token,
                        captcha=captcha,
                    )

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    resp_bytes = json.dumps(result).encode("utf-8")
                    self.send_header("Content-Length", str(len(resp_bytes)))
                    self.end_headers()
                    self.wfile.write(resp_bytes)

                    if result.get("success"):
                        logger.info("Smartphone login succeeded for '%s'", name)
                        me_cookie = result.get("me_cookie", "")
                        parent.on_success(name, me_cookie)

                else:
                    self.send_error(404, "Not Found")

        return CompanionHandler

    def start(self) -> tuple[str, int]:
        """Start the companion HTTP server in a background thread."""
        if self.is_running:
            return self.local_ip, self.port

        handler_cls = self._make_handler()
        ports_to_try = [self.preferred_port, 8081, 8082, 8888, 8000]

        for p in ports_to_try:
            try:
                self.server = ThreadingHTTPServer(("0.0.0.0", p), handler_cls)
                self.port = p
                break
            except OSError:
                continue

        if not self.server:
            # Fallback to random free port
            self.server = ThreadingHTTPServer(("0.0.0.0", 0), handler_cls)
            self.port = self.server.server_port

        self.local_ip = get_local_ip()
        self.is_running = True

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info("Companion server running at http://%s:%d", self.local_ip, self.port)
        return self.local_ip, self.port

    def stop(self) -> None:
        """Shut down the companion HTTP server."""
        if not self.is_running or not self.server:
            return

        self.is_running = False
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception as e:
            logger.warning("Error stopping auth server: %s", e)

        self.server = None
        self.thread = None
        logger.info("Companion server stopped.")
