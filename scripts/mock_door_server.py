#!/usr/bin/env python3
"""
Servidor simulado de puerta (sin Raspberry Pi ni GPIO).

Simula la API HTTP que expone ingreso.py en la Raspberry, para poder probar
desde Laravel (toggle, estado, conexión, reinicio) sin hardware.

Uso:
  1. Copia DOOR_API_KEY de tu .env (o usa la que viene por defecto abajo).
  2. Ejecuta: python scripts/mock_door_server.py
  3. En Laravel, edita una puerta y pon IP entrada (o salida) = 127.0.0.1
  4. Asegúrate de que DOOR_EMERGENCY_PORT en .env sea 8000 (o el mismo que uses aquí).

Variables de entorno:
  DOOR_API_KEY     - Clave que debe coincidir con la de Laravel (.env)
  DOOR_EMERGENCY_PORT - Puerto (default 8000)
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# Clave por defecto para pruebas (debe coincidir con DOOR_API_KEY en .env de Laravel)
DEFAULT_API_KEY = "cambia_esto_por_una_clave_secreta"
DOOR_API_KEY = os.getenv("DOOR_API_KEY", DEFAULT_API_KEY)
PORT = int(os.getenv("DOOR_EMERGENCY_PORT", "8000"))

# Estado en memoria (simula manual_open)
manual_open = False


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    api_key = handler.headers.get("X-API-KEY", "") or handler.headers.get("X-DEVICE-KEY", "")
    return api_key == DOOR_API_KEY


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class MockDoorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/door/status":
            _json(self, 200, {"ok": True, "manual_open": manual_open})
            return
        if self.path == "/api/emergency/status":
            _json(
                self,
                200,
                {
                    "ok": True,
                    "active": False,
                    "emergency_until": 0,
                    "remaining_seconds": 0,
                },
            )
            return
        _json(self, 404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        global manual_open

        if self.path == "/api/door/toggle":
            if not _authorized(self):
                _json(self, 401, {"ok": False, "error": "unauthorized"})
                return
            manual_open = not manual_open
            msg = "Puerta abierta" if manual_open else "Puerta cerrada"
            print(f"  [Mock] Toggle -> manual_open = {manual_open} ({msg})")
            _json(
                self,
                200,
                {"ok": True, "manual_open": manual_open, "message": msg},
            )
            return

        if self.path == "/reboot":
            if not _authorized(self):
                _json(self, 401, {"ok": False, "error": "unauthorized"})
                return
            print("  [Mock] Reinicio simulado (no se reinicia nada)")
            _json(self, 200, {"ok": True, "message": "Comando de reinicio ejecutado"})
            return

        if self.path == "/api/emergency/activate":
            if not _authorized(self):
                _json(self, 401, {"ok": False, "error": "unauthorized"})
                return
            _json(self, 200, {"ok": True, "duration_seconds": 60, "emergency_until": 0})
            return

        if self.path == "/api/emergency/deactivate":
            if not _authorized(self):
                _json(self, 401, {"ok": False, "error": "unauthorized"})
                return
            _json(self, 200, {"ok": True, "message": "Emergencia desactivada"})
            return

        _json(self, 404, {"ok": False, "error": "not_found"})

    def log_message(self, format, *args):
        print(f"[Mock] {args[0]}")


def main():
    server = HTTPServer(("0.0.0.0", PORT), MockDoorHandler)
    print(f"Servidor simulado de puerta en http://0.0.0.0:{PORT}")
    print(f"  DOOR_API_KEY (usa la misma en .env de Laravel): {DOOR_API_KEY[:8]}...")
    print("  Endpoints: GET /api/door/status, POST /api/door/toggle, POST /reboot")
    print("  Para probar: en una puerta pon IP entrada = 127.0.0.1")
    print("  Ctrl+C para salir.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando servidor simulado.")
        server.shutdown()


if __name__ == "__main__":
    main()
