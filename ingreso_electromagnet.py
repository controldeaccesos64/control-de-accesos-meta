#!/usr/bin/python3
"""
Sistema de control de acceso con ELECTROIMANES

Este archivo está optimizado para electroimanes que necesitan mantener el pin activo.
Usa un sistema de CICLO (activar/desactivar periódicamente) para evitar sobrecalentamiento.

SISTEMA DE CICLO:
- Activa el electroimán por 3 segundos
- Lo desactiva por 0.5 segundos (permite disipar calor)
- Repite el ciclo hasta completar el tiempo total
- Reduce el calor generado en ~14% mientras mantiene la puerta funcional
- Mejor disipación de calor que 5s/0.5s (más tiempo desactivado)

NOTA: Este sistema NO incluye fotocelda. Los electroimanes usan solo el sistema de ciclo.

Usa este archivo si tu sistema utiliza electroimanes para controlar las puertas.
"""
import os
import time
import json
import threading
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import RPi.GPIO as GPIO
from tkinter import Tk, Entry, mainloop

# Forzar display en Raspberry (si aplica)
if os.environ.get("DISPLAY", "") == "":
    os.environ.__setitem__("DISPLAY", ":0.0")

# =========================
# Config API (Laravel)
# =========================
# Cada Raspberry controla un SOLO tipo de evento (entrada o salida).
# Configura por dispositivo vía variables de entorno para no tocar el código.
#
# Ejemplo (Raspberry entrada):
#   export CODIGO_FISICO="P1-ENT"
#   export TIPO_EVENTO="entrada"
#   export DISPOSITIVO_ID="P1-ENT-RPI-ENTRADA"
#
# Ejemplo (Raspberry salida):
#   export TIPO_EVENTO="salida"
#   export DISPOSITIVO_ID="P1-ENT-RPI-SALIDA"
API_BASE = os.getenv("API_BASE", "http://172.22.66.217")
CODIGO_FISICO = os.getenv("CODIGO_FISICO", "GMET-M-PF1")
TIPO_EVENTO = os.getenv("TIPO_EVENTO", "entrada")  # "entrada" o "salida"
DISPOSITIVO_ID = os.getenv("DISPOSITIVO_ID", "GMET-M-PF1")
# Header X-DEVICE-KEY (backend: ACCESS_DEVICE_KEY)
# IMPORTANTE: en producción debería venir por env para evitar desalineaciones entre backend y lector.
DEVICE_KEY = (
    os.getenv("ACCESS_DEVICE_KEY")
    or os.getenv("DEVICE_KEY")
    or "2E549F77FCF4349499C7FAE55AE255A7"
)

# Debounce para evitar doble lectura del mismo QR (lectores suelen repetir el ENTER/CRLF o la lectura)
try:
    DEBOUNCE_SECONDS = float(os.getenv("DEBOUNCE_SECONDS", "0.7"))
except Exception:
    DEBOUNCE_SECONDS = 0.7

# Reintentos/backoff ante 429 (throttle) o errores transitorios
try:
    API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "2"))
except Exception:
    API_MAX_RETRIES = 2

# Session HTTP reutilizable (reduce overhead y problemas de conexiones)
SESSION = requests.Session()


# Relés / pines GPIO (BOARD) - Nota: aunque se llamen RELAY_PINS, aquí controlan electroimanes
RELAY_PINS = [35, 37, 29, 31, 33]
OPEN_SECONDS = float(os.getenv("OPEN_SECONDS", "5"))

# Sistema de ciclo para electroimanes (evita sobrecalentamiento)
# Tiempo activo: 3 segundos, Tiempo desactivado: 0.5 segundos
# Con 3s/0.5s: activo 85.7% del tiempo, reduce calor en ~14%
# Con 5s/0.5s: activo 90.9% del tiempo, reduce calor en ~9%
# El ciclo de 3s/0.5s disipa MÁS calor (más tiempo desactivado)
ELECTROMAGNET_ON_TIME = float(
    os.getenv("ELECTROMAGNET_ON_TIME", "3.0")
)  # Segundos activo
ELECTROMAGNET_OFF_TIME = float(
    os.getenv("ELECTROMAGNET_OFF_TIME", "0.5")
)  # Segundos desactivado

# Estado de apertura manual (persistente en disco)
MANUAL_OPEN_STATE_PATH = os.getenv(
    "MANUAL_OPEN_STATE_PATH", "/var/lib/door/manual_open.json"
)

# =========================
# Emergencia (modo libre) - sin dependencias
# =========================
# Hardcodeado para este dispositivo (debe coincidir con Laravel)
DOOR_API_KEY = "D8738A38CC8FC927C5EC594F47A22787"
EMERGENCY_PORT = 8000
STATE_PATH = os.getenv("DOOR_STATE_PATH", "/var/lib/door/emergency.json")

# Control de ciclo de emergencia (thread-safe)
emergency_cycle_active = threading.Event()
emergency_cycle_stop = threading.Event()


def _load_state():
    """Carga el estado de emergencia desde disco"""
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict):
    """Guarda el estado de emergencia en disco (atomic write)"""
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_PATH)


def emergency_until() -> int:
    """Retorna timestamp Unix hasta cuándo está activa la emergencia"""
    st = _load_state()
    return int(st.get("emergency_until", 0) or 0)


def emergency_active() -> bool:
    """Verifica si la emergencia está activa (no vencida)"""
    return int(time.time()) < emergency_until()


def set_emergency(seconds: int) -> int:
    """Activa emergencia por N segundos. Retorna timestamp de vencimiento

    IMPORTANTE: Abre físicamente TODOS los electroimanes inmediatamente.
    Usa sistema de ciclo para evitar sobrecalentamiento.
    """
    now = int(time.time())
    until = now + int(seconds)
    _save_state({"emergency_until": until})

    # ✅ ABRIR TODOS LOS ELECTROIMANES INMEDIATAMENTE
    print(f"🚨 EMERGENCIA ACTIVADA: Abriendo todas las puertas por {seconds} segundos")
    print(
        f"   Usando sistema de ciclo: {ELECTROMAGNET_ON_TIME}s ON / {ELECTROMAGNET_OFF_TIME}s OFF"
    )

    # Activar inmediatamente
    for pin in RELAY_PINS:
        GPIO.output(pin, True)

    # Activar el ciclo de emergencia
    emergency_cycle_stop.clear()
    emergency_cycle_active.set()

    return until


def deactivate_emergency():
    """Desactiva la emergencia y cierra todos los electroimanes"""
    _save_state({"emergency_until": 0})

    # Detener el ciclo de emergencia
    emergency_cycle_stop.set()
    emergency_cycle_active.clear()

    # ✅ Solo cerrar electroimanes si NO está en modo manual
    if not is_manual_open():
        print("🚨 EMERGENCIA FINALIZADA: Cerrando todas las puertas")
        for pin in RELAY_PINS:
            GPIO.output(pin, False)
    else:
        print("🚨 EMERGENCIA FINALIZADA: Puerta permanece abierta (modo manual activo)")


def electromagnet_cycle(duration: float, stop_event: threading.Event = None):
    """Ejecuta un ciclo de activar/desactivar para el electroimán

    Args:
        duration: Tiempo total que debe estar "abierto" (en segundos)
        stop_event: Evento para detener el ciclo antes de tiempo (opcional)

    El ciclo funciona así:
    - Activa por ELECTROMAGNET_ON_TIME segundos
    - Desactiva por ELECTROMAGNET_OFF_TIME segundos
    - Repite hasta completar duration o hasta que stop_event esté activo
    """
    tiempo_inicio = time.time()

    while (time.time() - tiempo_inicio) < duration:
        if stop_event and stop_event.is_set():
            break

        # Fase ON: Activar electroimán
        tiempo_on_inicio = time.time()
        while (time.time() - tiempo_on_inicio) < ELECTROMAGNET_ON_TIME:
            if stop_event and stop_event.is_set():
                return
            for pin in RELAY_PINS:
                GPIO.output(pin, True)
            time.sleep(0.1)  # Verificar cada 100ms

        # Fase OFF: Desactivar electroimán (permite disipar calor)
        tiempo_off_inicio = time.time()
        while (time.time() - tiempo_off_inicio) < ELECTROMAGNET_OFF_TIME:
            if stop_event and stop_event.is_set():
                return
            for pin in RELAY_PINS:
                GPIO.output(pin, False)
            time.sleep(0.1)  # Verificar cada 100ms


class EmergencyHandler(BaseHTTPRequestHandler):
    """Handler HTTP para recibir comandos de emergencia desde Laravel"""

    def _json(self, code, payload):
        """Envía respuesta JSON"""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        """Verifica API key en header (soporta X-API-KEY y X-DEVICE-KEY)"""
        api_key = self.headers.get("X-API-KEY", "") or self.headers.get(
            "X-DEVICE-KEY", ""
        )
        return api_key == DOOR_API_KEY

    def do_GET(self):
        """GET /api/emergency/status - Consulta estado de emergencia
        GET /api/door/status - Consulta estado de la puerta (manual open)"""

        if self.path == "/api/door/status":
            self._json(
                200,
                {
                    "ok": True,
                    "manual_open": is_manual_open(),
                },
            )
            return

        if self.path != "/api/emergency/status":
            self._json(404, {"ok": False, "error": "not_found"})
            return

        now = int(time.time())
        until = emergency_until()
        self._json(
            200,
            {
                "ok": True,
                "active": now < until,
                "now": now,
                "emergency_until": until,
                "remaining_seconds": max(0, until - now),
            },
        )

    def do_POST(self):
        """POST /api/emergency/activate - Activa emergencia por N segundos
        POST /api/emergency/deactivate - Desactiva emergencia inmediatamente
        POST /reboot - Reinicia la Raspberry Pi
        POST /api/door/toggle - Abre/cierra la puerta manualmente"""

        # Endpoint de apertura/cierre manual
        if self.path == "/api/door/toggle":
            if not self._authorized():
                self._json(401, {"ok": False, "error": "unauthorized"})
                return

            try:
                # Obtener estado actual
                estado_actual = is_manual_open()
                # Cambiar estado (toggle)
                nuevo_estado = not estado_actual
                mantener_puerta_abierta(nuevo_estado)

                self._json(
                    200,
                    {
                        "ok": True,
                        "manual_open": nuevo_estado,
                        "message": (
                            "Puerta abierta" if nuevo_estado else "Puerta cerrada"
                        ),
                    },
                )
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return

        # Endpoint de reinicio
        if self.path == "/reboot":
            if not self._authorized():
                self._json(401, {"ok": False, "error": "unauthorized"})
                return

            # Ejecutar sudo reboot en un proceso separado
            try:
                # Ejecutar sudo reboot en background (el servidor se desconectará)
                subprocess.Popen(
                    ["sudo", "reboot"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._json(
                    200, {"ok": True, "message": "Comando de reinicio ejecutado"}
                )
            except Exception as e:
                self._json(500, {"ok": False, "error": str(e)})
            return

        # Endpoint de desactivación de emergencia
        if self.path == "/api/emergency/deactivate":
            if not self._authorized():
                self._json(401, {"ok": False, "error": "unauthorized"})
                return

            deactivate_emergency()
            self._json(200, {"ok": True, "message": "Emergencia desactivada"})
            return

        # Endpoint de activación de emergencia
        if self.path != "/api/emergency/activate":
            self._json(404, {"ok": False, "error": "not_found"})
            return

        if not self._authorized():
            self._json(401, {"ok": False, "error": "unauthorized"})
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_json"})
            return

        seconds = int(data.get("duration_seconds", 900) or 900)
        # Límites básicos para evitar abusos
        if seconds < 10 or seconds > 3600:
            self._json(422, {"ok": False, "error": "duration_out_of_range"})
            return

        until = set_emergency(seconds)
        self._json(
            200, {"ok": True, "duration_seconds": seconds, "emergency_until": until}
        )

    def log_message(self, format, *args):
        """Silencia logs del servidor HTTP (opcional)"""
        pass


def emergency_cycle_monitor():
    """Monitorea la emergencia y ejecuta el ciclo de activar/desactivar

    Este thread mantiene el ciclo de emergencia activo mientras haya emergencia.
    El ciclo reduce el calor generado en ~14% mientras mantiene la puerta funcional.
    """
    while True:
        try:
            if emergency_cycle_active.is_set() and emergency_active():
                # Hay emergencia activa: ejecutar ciclo
                until = emergency_until()
                now = int(time.time())
                remaining = until - now

                if remaining > 0:
                    # Ejecutar ciclo por el tiempo restante
                    electromagnet_cycle(remaining, emergency_cycle_stop)
                else:
                    # Emergencia expirada
                    emergency_cycle_active.clear()
            else:
                # No hay emergencia: esperar
                time.sleep(1)

        except Exception as e:
            print(f"Error en monitor de ciclo de emergencia: {e}")
            time.sleep(1)


def emergency_monitor():
    """Monitorea el estado de emergencia y cierra puertas cuando expira

    Se ejecuta en un thread separado y verifica cada segundo si la emergencia
    ha expirado para cerrar los electroimanes automáticamente.
    """
    while True:
        try:
            time.sleep(1)  # Verificar cada segundo

            until = emergency_until()
            now = int(time.time())

            # Si había emergencia activa y acaba de expirar
            if until > 0 and now >= until:
                deactivate_emergency()

        except Exception as e:
            print(f"Error en monitor de emergencia: {e}")


def start_emergency_server():
    """Inicia el servidor HTTP en un thread separado"""
    server = HTTPServer(("0.0.0.0", EMERGENCY_PORT), EmergencyHandler)
    print(f"Servidor de emergencia iniciado en puerto {EMERGENCY_PORT}")
    server.serve_forever()


def mantener_puerta_abierta(abierta: bool):
    """Mantener la puerta abierta (activar electroimanes) o cerrarla (desactivar electroimanes)

    Si se intenta cerrar pero hay emergencia activa, los electroimanes permanecen abiertos.
    """
    # Guardar estado primero
    _save_manual_state({"manual_open": abierta})

    # Si se intenta cerrar pero hay emergencia, mantener abierto
    if not abierta and emergency_active():
        print("⚠️ No se puede cerrar: EMERGENCIA activa")
        return

    # Aplicar el estado a los electroimanes
    for pin in RELAY_PINS:
        GPIO.output(pin, abierta)


def _save_manual_state(state: dict):
    """Guarda el estado de apertura manual en disco"""
    global MANUAL_OPEN_STATE_PATH

    try:
        os.makedirs(os.path.dirname(MANUAL_OPEN_STATE_PATH), exist_ok=True)
    except PermissionError:
        # Si no hay permisos, usar directorio temporal alternativo
        alt_path = os.path.join("/tmp", "door_manual_open.json")
        MANUAL_OPEN_STATE_PATH = alt_path
        print(
            f"⚠️ Sin permisos en /var/lib/door, usando ruta alternativa: {MANUAL_OPEN_STATE_PATH}"
        )

    tmp = MANUAL_OPEN_STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, MANUAL_OPEN_STATE_PATH)


def _load_manual_state() -> dict:
    """Carga el estado de apertura manual desde disco"""
    try:
        with open(MANUAL_OPEN_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"manual_open": False}


def is_manual_open() -> bool:
    """Retorna si la puerta está manualmente abierta"""
    state = _load_manual_state()
    return bool(state.get("manual_open", False))


def abrir_puerta(segundos: float = None):
    """Abre la puerta por el tiempo especificado usando sistema de ciclo.

    Para electroimanes: usa sistema de ciclo (activar/desactivar) para evitar sobrecalentamiento.
    El ciclo es de 3s ON / 0.5s OFF, lo que permite mejor disipación de calor.
    """
    tiempo_apertura = segundos if segundos is not None else OPEN_SECONDS

    # Usar sistema de ciclo para evitar sobrecalentamiento
    print(
        f"🔓 Abriendo puerta por {tiempo_apertura} segundos (sistema de ciclo: {ELECTROMAGNET_ON_TIME}s ON / {ELECTROMAGNET_OFF_TIME}s OFF)"
    )

    # Crear evento para detener el ciclo si es necesario
    stop_cycle = threading.Event()

    # Ejecutar ciclo de apertura
    electromagnet_cycle(tiempo_apertura, stop_cycle)

    # Cerrar después del ciclo
    for pin in RELAY_PINS:
        GPIO.output(pin, False)


def denegar_puerta():
    # Aquí puedes agregar sonido / led / UI. Por ahora solo log.
    print("Acceso denegado")


def verify_access(token: str) -> dict:
    url = f"{API_BASE}/api/access/verify"
    headers = {"Accept": "application/json"}
    if DEVICE_KEY:
        headers["X-DEVICE-KEY"] = DEVICE_KEY

    payload = {
        "token": token,
        "codigo_fisico": CODIGO_FISICO,
        "tipo_evento": TIPO_EVENTO,
        "dispositivo_id": DISPOSITIVO_ID,
    }

    last_error = None
    for attempt in range(0, API_MAX_RETRIES + 1):
        try:
            # timeout=(connect, read)
            r = SESSION.post(url, json=payload, headers=headers, timeout=(2, 4))
        except Exception as ex:
            last_error = ex
            time.sleep(0.25 * (attempt + 1))
            continue

        # Si el backend tiene throttle, 429 se ve como "se dañó" si no lo manejamos.
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            try:
                wait_s = float(retry_after) if retry_after else 1.0
            except Exception:
                wait_s = 1.0
            print(
                f"⚠️ API 429 (throttle). Esperando {wait_s}s y reintentando... intento={attempt+1}/{API_MAX_RETRIES+1}"
            )
            time.sleep(min(max(wait_s, 0.5), 5.0))
            last_error = RuntimeError(f"HTTP 429: {r.text[:300]}")
            continue

        if not r.ok:
            raise RuntimeError(f"API HTTP {r.status_code}. Body: {r.text[:600]}")

        try:
            data = r.json()
        except Exception:
            raise RuntimeError(
                f"API respondió 200 pero JSON inválido. Body: {r.text[:600]}"
            )

        if not isinstance(data, dict):
            raise ValueError("Respuesta JSON inválida (no es objeto)")
        if "permitido" not in data:
            data["permitido"] = False
            data["message"] = data.get("message") or "Respuesta sin campo 'permitido'"
        return data

    raise RuntimeError(
        f"No se pudo validar acceso tras reintentos. Último error: {last_error}"
    )


def _cli_verify_only() -> None:
    """Modo CLI para probar la controladora desde consola:

    python3 ingreso_electromagnet.py --verify \"TOKEN_QR\"

    Nota: Este modo NO usa GPIO ni Tk; solo llama a la API y muestra el JSON.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--verify", required=True, help="Token leído del QR (valor plano)."
    )
    args = parser.parse_args()

    token = (args.verify or "").strip()
    if not token:
        print("Token vacío.", file=sys.stderr)
        raise SystemExit(2)

    try:
        res = verify_access(token)
    except Exception as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        raise SystemExit(1)

    print(json.dumps(res, ensure_ascii=False))
    raise SystemExit(0 if bool(res.get("permitido")) else 3)


if __name__ == "__main__" and "--verify" in os.sys.argv:
    _cli_verify_only()


if GPIO is None:
    raise RuntimeError(
        "RPi.GPIO no disponible. Este script debe ejecutarse en Raspberry Pi "
        "(o usa el modo --verify para probar solo la API)."
    )
if Tk is None or Entry is None or mainloop is None:
    raise RuntimeError(
        "Tkinter no disponible (entorno headless). Para UI se requiere entorno gráfico; "
        "o usa --verify para probar solo la API."
    )


GPIO.setmode(GPIO.BOARD)
for pin in RELAY_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, False)

print("⚙️  Tipo de actuador: ELECTROMAGNET (Electroimanes)")
print(
    f"   Sistema de ciclo: {ELECTROMAGNET_ON_TIME}s ON / {ELECTROMAGNET_OFF_TIME}s OFF"
)
reduccion_calor = int(
    (ELECTROMAGNET_OFF_TIME / (ELECTROMAGNET_ON_TIME + ELECTROMAGNET_OFF_TIME)) * 100
)
print(f"   Reducción de calor: ~{reduccion_calor}%")
print(
    f"   Tiempo activo: {int((ELECTROMAGNET_ON_TIME / (ELECTROMAGNET_ON_TIME + ELECTROMAGNET_OFF_TIME)) * 100)}% del tiempo"
)

# Restaurar estado de apertura manual al iniciar (si estaba abierta)
try:
    if is_manual_open():
        print("Restaurando estado: puerta abierta manualmente")
        mantener_puerta_abierta(True)
except Exception as e:
    print(f"Error restaurando estado manual: {e}")

# Restaurar estado de emergencia al iniciar (si estaba activa)
try:
    if emergency_active():
        remaining = emergency_until() - int(time.time())
        print(f"🚨 Restaurando EMERGENCIA: {remaining} segundos restantes")
        # Activar ciclo de emergencia
        emergency_cycle_stop.clear()
        emergency_cycle_active.set()
except Exception as e:
    print(f"Error restaurando estado de emergencia: {e}")


master = Tk()
e = Entry(master)
e.pack()
e.focus_set()

_last_token = None
_last_token_ts = 0.0


def callback(event):
    global _last_token, _last_token_ts
    try:
        token = e.get().strip()
        if not token:
            return

        # Debounce anti-doble lectura (misma cadena muy seguida)
        now_ts = time.time()
        if (
            DEBOUNCE_SECONDS > 0
            and _last_token == token
            and (now_ts - _last_token_ts) < DEBOUNCE_SECONDS
        ):
            print(
                f"ℹ️ Debounce: token repetido en {now_ts - _last_token_ts:.2f}s. Ignorando."
            )
            return
        _last_token = token
        _last_token_ts = now_ts

        # ✅ Si está abierta manualmente: los electroimanes ya están activos, solo abrir físicamente (no registrar)
        if is_manual_open():
            print(
                "✅ PUERTA ABIERTA MANUALMENTE: acceso permitido (electroimanes ya activos)"
            )
            return

        # ✅ Si está en emergencia: los electroimanes ya están activos, solo abrir físicamente (no registrar)
        if emergency_active():
            print("🚨 EMERGENCIA ACTIVA: acceso permitido (electroimanes ya activos)")
            return

        # Llamada al backend (Laravel) para validar permisos y registrar el evento.
        try:
            res = verify_access(token)
        except Exception as ex:
            print("❌ Error conectando/validando con API:", ex)
            print(
                f"   Config: API_BASE={API_BASE} CODIGO_FISICO={CODIGO_FISICO} TIPO_EVENTO={TIPO_EVENTO} DISPOSITIVO_ID={DISPOSITIVO_ID}"
            )
            denegar_puerta()
            return

        permitido = bool(res.get("permitido", False))
        mensaje = res.get("message", "")
        tiempo_apertura = res.get("tiempo_apertura")

        print("API:", permitido, mensaje)
        if tiempo_apertura is not None:
            print(f"Tiempo de apertura: {tiempo_apertura} segundos")

        if permitido:
            # Usar el tiempo de apertura de la API si está disponible, sino usar OPEN_SECONDS
            tiempo = (
                float(tiempo_apertura) if tiempo_apertura is not None else OPEN_SECONDS
            )
            abrir_puerta(tiempo)
        else:
            denegar_puerta()
    except Exception as ex:
        print("error:", ex)
    finally:
        e.delete("0", "end")


# ✅ Arranca el servidor HTTP en paralelo (no bloquea Tk)
t_server = threading.Thread(target=start_emergency_server, daemon=True)
t_server.start()

# ✅ Arranca el monitor de emergencia en paralelo
t_monitor = threading.Thread(target=emergency_monitor, daemon=True)
t_monitor.start()

# ✅ Arranca el monitor de ciclo de emergencia en paralelo
t_emergency_cycle = threading.Thread(target=emergency_cycle_monitor, daemon=True)
t_emergency_cycle.start()

master.bind("<Return>", callback)
mainloop()
