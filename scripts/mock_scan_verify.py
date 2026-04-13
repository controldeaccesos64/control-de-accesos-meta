#!/usr/bin/env python3
"""
Simulador de lectura de códigos (QR/NFC) sin Raspberry.

Envía el mismo request que hace ingreso.py a /api/access/verify, para que puedas
reproducir problemas de permisos desde tu PC.

Requisitos:
  - Tener la app Laravel corriendo y accesible (APP_URL).
  - Conocer el token leído del QR (o el código de la tarjeta NFC).
  - Conocer el codigo_fisico del lector/puerta (ej: P2-ENT).

Uso (Windows PowerShell):
  $env:APP_URL="http://127.0.0.1:8000"
  $env:ACCESS_DEVICE_KEY="abcd1234"
  python scripts/mock_scan_verify.py

Variables:
  APP_URL            Base URL del backend (default http://127.0.0.1)
  ACCESS_DEVICE_KEY  Debe coincidir con ACCESS_DEVICE_KEY del servidor
"""

import json
import os
import sys

import requests


def main() -> int:
    app_url = (os.getenv("APP_URL") or "http://127.0.0.1").rstrip("/")
    device_key = os.getenv("ACCESS_DEVICE_KEY")
    if not device_key:
        print("Falta ACCESS_DEVICE_KEY en el entorno.", file=sys.stderr)
        return 2

    print("=== Simulador de lectura (scan) ===")
    print(f"Backend: {app_url}")
    token = input("Token leído (QR) o código (NFC): ").strip()
    codigo_fisico = input("codigo_fisico del lector/puerta (ej P2-ENT): ").strip()
    tipo_evento = (input("tipo_evento [entrada/salida] (default entrada): ").strip() or "entrada")
    dispositivo_id = (input("dispositivo_id (opcional): ").strip() or None)

    payload = {
        "token": token,
        "codigo_fisico": codigo_fisico,
        "tipo_evento": tipo_evento,
    }
    if dispositivo_id:
        payload["dispositivo_id"] = dispositivo_id

    url = f"{app_url}/api/access/verify"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-DEVICE-KEY": device_key,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception as e:
        print(f"Error conectando a {url}: {e}", file=sys.stderr)
        return 1

    print(f"\nHTTP {r.status_code}")
    try:
        data = r.json()
    except Exception:
        print(r.text)
        return 0

    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

