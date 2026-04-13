#!/usr/bin/python3
"""
Sistema de control de acceso con RELÉS

Este script puede operar en dos modos (configurable por variables de entorno):

- RELAY_MODE=hold  -> "contacto sostenido": mantiene el relé activo N segundos (comportamiento histórico).
- RELAY_MODE=pulse -> "modo pulso": activa el relé solo un pulso corto (0.3-1.0s) y la controladora Autoline/Photonic
                      ejecuta el ciclo de apertura/cierre con sus sensores internos (recomendado para speed gates).

IMPORTANTE:
- Para evitar aperturas espurias al energizar, BLINDA los GPIO desde firmware (config.txt) además de inicializarlos en Python.
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
CODIGO_FISICO = os.getenv("CODIGO_FISICO", "GMET-MPV8-SAL")
TIPO_EVENTO = os.getenv("TIPO_EVENTO", "salida")  # "entrada" o "salida"
DISPOSITIVO_ID = os.getenv("DISPOSITIVO_ID", "GMET-MPV8-SAL")
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


# Relés / pines GPIO (BOARD)
RELAY_PINS = [35, 37, 29, 31, 33]
try:
    OPEN_SECONDS = float(os.getenv("OPEN_SECONDS", "5"))
except Exception:
    OPEN_SECONDS = 5.0

# Modo de disparo del relé:
# - hold  = mantener contacto por OPEN_SECONDS / tiempo_apertura
# - pulse = pulso corto fijo (PULSE_SECONDS) y usar OPEN_SECONDS/tiempo_apertura solo como cooldown anti-doble disparo
RELAY_MODE = (os.getenv("RELAY_MODE", "hold") or "hold").strip().lower()
try:
    PULSE_SECONDS = float(os.getenv("PULSE_SECONDS", "0.6"))
except Exception:
    PULSE_SECONDS = 0.6

# Guardia de arranque (seg): ignora lecturas durante homing/boot de Autoline (mitiga estados indeterminados al energizar)
try:
    BOOT_GUARD_SECONDS = float(os.getenv("BOOT_GUARD_SECONDS", "15"))
except Exception:
    BOOT_GUARD_SECONDS = 0.0
_START_TS = time.time()

# Lock global para evitar escrituras concurrentes a GPIO (threads: HTTP, monitor, UI)
GPIO_LOCK = threading.Lock()


def set_relays(open_state: bool) -> None:
    """Activa/desactiva todos los relés de forma thread-safe."""
    with GPIO_LOCK:
        for pin in RELAY_PINS:
            GPIO.output(pin, open_state)


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

    IMPORTANTE: Abre físicamente TODOS los relés inmediatamente.
    Los relés mantienen el estado, no necesitan mantenerse activos continuamente.
    """
    now = int(time.time())
    until = now + int(seconds)
    _save_state({"emergency_until": until})

    # ✅ ABRIR TODOS LOS RELÉS INMEDIATAMENTE
    print(f"🚨 EMERGENCIA ACTIVADA: Abriendo todas las puertas por {seconds} segundos")
    set_relays(True)

    return until


def deactivate_emergency():
    """Desactiva la emergencia y cierra todos los relés"""
    _save_state({"emergency_until": 0})

    # ✅ Solo cerrar relés si NO está en modo manual
    if not is_manual_open():
        print("🚨 EMERGENCIA FINALIZADA: Cerrando todas las puertas")
        set_relays(False)
    elif is_manual_open():
        print("🚨 EMERGENCIA FINALIZADA: Puerta permanece abierta (modo manual activo)")


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


def emergency_monitor():
    """Monitorea el estado de emergencia y cierra puertas cuando expira

    Se ejecuta en un thread separado y verifica cada segundo si la emergencia
    ha expirado para cerrar los relés automáticamente.

    Los relés mantienen el estado, no necesitan mantenerse activos continuamente.
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
    """Mantener la puerta abierta (activar relés) o cerrarla (desactivar relés)

    Si se intenta cerrar pero hay emergencia activa, los relés permanecen abiertos.
    """
    # Guardar estado primero
    _save_manual_state({"manual_open": abierta})

    # Si se intenta cerrar pero hay emergencia, mantener abierto
    if not abierta and emergency_active():
        print("⚠️ No se puede cerrar: EMERGENCIA activa")
        return

    # Aplicar el estado a los relés
    set_relays(abierta)


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


def abrir_puerta(segundos: float = None, mode: str = None):
    """Dispara la apertura.

    - RELAY_MODE=hold:
        Mantiene el contacto cerrado por N segundos (OPEN_SECONDS/tiempo_apertura) y luego libera.
        Si durante el ciclo se activa emergencia o modo manual, NO se libera el contacto.

    - RELAY_MODE=pulse:
        Envía un pulso corto (PULSE_SECONDS) y libera. La controladora de puerta debe manejar el ciclo completo.
        OPEN_SECONDS/tiempo_apertura se usa SOLO como cooldown del escáner (anti doble disparo), no como tiempo de contacto.
    """
    # Permite override por evento (p.ej. sugerido por API). Si no se pasa, usa RELAY_MODE global.
    mode = (mode or RELAY_MODE or "hold").strip().lower()

    if mode == "pulse":
        # Pulso corto y seguro (clamp)
        try:
            pulse_s = float(PULSE_SECONDS)
        except Exception:
            pulse_s = 0.6
        pulse_s = min(max(pulse_s, 0.05), 2.0)

        set_relays(True)
        try:
            time.sleep(pulse_s)
        finally:
            # Si se activó emergencia o modo manual durante el pulso, respetarlo (no forzar cierre)
            try:
                if emergency_active():
                    print(
                        "ℹ️ Pulso enviado, pero EMERGENCIA activa: relés permanecen abiertos"
                    )
                    return
                if is_manual_open():
                    print(
                        "ℹ️ Pulso enviado, pero modo manual activo: relés permanecen abiertos"
                    )
                    return
            except Exception:
                # Si no podemos leer estados, cerramos el pulso normal.
                pass
            set_relays(False)
        return

    # --- Modo 'hold' (histórico) ---
    tiempo_apertura = segundos if segundos is not None else OPEN_SECONDS
    try:
        tiempo_apertura = float(tiempo_apertura)
    except Exception:
        tiempo_apertura = OPEN_SECONDS
    if tiempo_apertura < 0:
        tiempo_apertura = OPEN_SECONDS

    # Activar relés (mantienen el estado)
    set_relays(True)
    try:
        # Esperar el tiempo de apertura (los relés mantienen el estado)
        time.sleep(tiempo_apertura)
    finally:
        # No cerrar si hay emergencia o modo manual activo
        try:
            if emergency_active():
                print("ℹ️ Autocierre omitido: EMERGENCIA activa")
                return
            if is_manual_open():
                print("ℹ️ Autocierre omitido: modo manual activo")
                return
        except Exception as ex:
            # Si no podemos leer estados, por seguridad cerramos el contacto normal (evita quedar abierto indefinidamente)
            print(f"⚠️ No se pudo leer estado emergencia/manual al cerrar: {ex}")

        set_relays(False)


def denegar_puerta():
    # Aquí puedes agregar sonido / led / UI. Por ahora solo log.
    print("Acceso denegado")


# =============================================================================
# FLUJO PRINCIPAL (lo que hace el script en esencia):
#
#   1. Usuario escanea QR → se obtiene el token.
#   2. Se llama a la API: POST /api/access/verify con token, codigo_fisico, tipo_evento, dispositivo_id.
#   3. Si la respuesta tiene permitido=true:
#        → Se dispara apertura según el modo efectivo:
#             - pulse: pulso corto (PULSE_SECONDS) y la controladora Autoline/Photonic maneja fotocelda/autocierre.
#             - hold : contacto sostenido por tiempo_apertura (o OPEN_SECONDS).
#          El modo efectivo puede venir en la respuesta API como 'relay_mode' (p.ej. pulse normal y hold para discapacitado),
#          o como configuración local via RELAY_MODE.
#   4. Si permitido=false o hay error de red/API:
#        → No se activan los relés (denegar_puerta = log/sonido opcional).
#
# Todo lo demás (threads, scanner_locked, emergencia, modo manual, debounce) es
# para no bloquear la UI, evitar dobles lecturas y respetar emergencia/apertura manual.
# =============================================================================


def verify_access(token: str) -> dict:
    """Llama al backend Laravel y devuelve el JSON (permitido, message, tiempo_apertura)."""
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

    # Fail-closed:
    # - Si HTTP != 2xx o JSON inválido => excepción (no abrir)
    # - Si falta la llave 'permitido' => tratar como denegado
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

        break
    else:
        raise RuntimeError(
            f"No se pudo validar acceso tras reintentos. Último error: {last_error}"
        )

    if not isinstance(data, dict):
        raise ValueError("Respuesta JSON inválida (no es objeto)")
    if "permitido" not in data:
        data["permitido"] = False
        data["message"] = data.get("message") or "Respuesta sin campo 'permitido'"
    return data


GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
for pin in RELAY_PINS:
    # initial=LOW reduce glitch al iniciar Python (NO sustituye el blindaje de firmware)
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

if RELAY_MODE == "pulse":
    print(f"⚙️  Tipo de actuador: RELAY (modo PULSO). PULSE_SECONDS={PULSE_SECONDS}s")
else:
    print("⚙️  Tipo de actuador: RELAY (modo HOLD / contacto sostenido)")

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
        # Abrir relés inmediatamente
        set_relays(True)
except Exception as e:
    print(f"Error restaurando estado de emergencia: {e}")


master = Tk()
e = Entry(master)
e.pack()
e.focus_set()

# Bloqueo lógico del escáner mientras la puerta está en ciclo de apertura
scanner_locked = threading.Event()

_last_token = None
_last_token_ts = 0.0


def set_scanner_enabled(enabled: bool) -> None:
    """Habilita/deshabilita el Entry de forma segura (Tk solo en hilo principal)."""
    state = "normal" if enabled else "disabled"
    try:
        master.after(0, lambda: e.config(state=state))
    except Exception:
        # Si Tk aún no está listo o ya cerró, ignorar.
        pass


def update_scanner_state() -> None:
    """Aplica política de escaneo:
    - Deshabilitar si hay emergencia o modo manual (puerta abierta/override)
    - Deshabilitar si está en ciclo de apertura/procesando (scanner_locked)
    """
    try:
        if emergency_active() or is_manual_open() or scanner_locked.is_set():
            set_scanner_enabled(False)
        else:
            set_scanner_enabled(True)
    except Exception:
        # Nunca fallar-abierto por error de UI
        try:
            set_scanner_enabled(False)
        except Exception:
            pass


def unlock_scanner() -> None:
    scanner_locked.clear()
    update_scanner_state()
    try:
        master.after(0, lambda: e.delete("0", "end"))
    except Exception:
        pass


def lock_scanner_for(seconds: float) -> None:
    """Bloquea el escáner por N segundos (descarta lecturas)."""
    scanner_locked.set()
    update_scanner_state()
    # Programar desbloqueo (ms)
    ms = max(0, int((seconds + 0.25) * 1000))  # +250ms de colchón
    try:
        master.after(ms, unlock_scanner)
    except Exception:
        # Si no se puede programar, al menos liberar el lock
        unlock_scanner()


def process_token(token: str) -> None:
    """
    Núcleo del flujo: llamar API → si permitido, activar relé X segundos; si no, no activar.
    El resto (thread, lock/unlock del escáner) es para no bloquear Tk y evitar dobles lecturas.
    """
    try:
        res = verify_access(token)
    except Exception as ex:
        print("❌ Error conectando/validando con API:", ex)
        print(
            f"   Config: API_BASE={API_BASE} CODIGO_FISICO={CODIGO_FISICO} TIPO_EVENTO={TIPO_EVENTO} DISPOSITIVO_ID={DISPOSITIVO_ID}"
        )
        denegar_puerta()
        try:
            master.after(250, unlock_scanner)
        except Exception:
            unlock_scanner()
        return

    permitido = bool(res.get("permitido", False))
    mensaje = res.get("message", "")
    tiempo_apertura = res.get("tiempo_apertura")
    relay_mode_api = (res.get("relay_mode") or "").strip().lower()

    print("API:", permitido, mensaje)
    if tiempo_apertura is not None:
        print(f"Tiempo de apertura: {tiempo_apertura} segundos")

    # --- Respuesta NO permitida: no activar relés ---
    if not permitido:
        denegar_puerta()
        try:
            master.after(250, unlock_scanner)
        except Exception:
            unlock_scanner()
        return

    # --- Respuesta permitida: si no hay emergencia/manual, activar relés X segundos ---
    if emergency_active():
        print("ℹ️ Acceso permitido, pero EMERGENCIA activa: relés ya abiertos")
        try:
            master.after(250, unlock_scanner)
        except Exception:
            unlock_scanner()
        return
    if is_manual_open():
        print("ℹ️ Acceso permitido, pero modo manual activo: relés ya abiertos")
        try:
            master.after(250, unlock_scanner)
        except Exception:
            unlock_scanner()
        return

    tiempo = OPEN_SECONDS
    if tiempo_apertura is not None:
        try:
            tiempo = float(tiempo_apertura)
        except Exception:
            pass

    lock_scanner_for(tiempo)
    # Política de modo:
    # - Si API manda relay_mode explícito (pulse/hold), respétalo.
    # - Si no, usar RELAY_MODE del dispositivo.
    effective_mode = (
        relay_mode_api if relay_mode_api in ("pulse", "hold") else RELAY_MODE
    )
    print(
        f"Modo relé (API): {relay_mode_api or '(none)'} | Modo relé (local): {RELAY_MODE} | Efectivo: {effective_mode}"
    )

    # En modo pulso, el tiempo de API se usa como cooldown (anti doble disparo) y NO como contacto sostenido.
    if effective_mode == "pulse":
        abrir_puerta(None, mode=effective_mode)
    else:
        abrir_puerta(tiempo, mode=effective_mode)


def callback(event):
    global _last_token, _last_token_ts
    try:
        # Guardia de arranque: evita disparos durante homing/estados indeterminados tras energizar.
        if BOOT_GUARD_SECONDS > 0 and (time.time() - _START_TS) < BOOT_GUARD_SECONDS:
            remaining = BOOT_GUARD_SECONDS - (time.time() - _START_TS)
            print(
                f"⏳ Arranque/Homing: escaneo inhibido por {remaining:.1f}s (BOOT_GUARD_SECONDS={BOOT_GUARD_SECONDS})"
            )
            return

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

        # Mientras haya emergencia o modo manual, NO enviar requests (evitar spam)
        if emergency_active() or is_manual_open():
            print("⛔ Escaneo deshabilitado: EMERGENCIA o modo manual activo.")
            update_scanner_state()
            return

        # Si la puerta está en ciclo de apertura (o procesando), ignorar escaneos
        if scanner_locked.is_set():
            print("⏳ Ignorando escaneo: puerta ocupada/abierta.")
            return

        # Bloquear de inmediato para evitar múltiples requests por ráfaga de escaneos
        scanner_locked.set()
        update_scanner_state()

        # Procesar en background para no congelar Tk
        t = threading.Thread(target=process_token, args=(token,), daemon=True)
        t.start()
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


def _poll_scanner_state():
    update_scanner_state()
    master.after(500, _poll_scanner_state)


# Aplicar estado inicial y mantenerlo sincronizado con emergencia/manual
update_scanner_state()
_poll_scanner_state()

master.bind("<Return>", callback)
mainloop()
