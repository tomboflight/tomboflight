from __future__ import annotations

import ipaddress
from pathlib import Path
import socket
import struct
from typing import Any

from app.config import settings

CHUNK_SIZE = 64 * 1024
MAX_RESPONSE_BYTES = 4096


def configuration_ready() -> tuple[bool, str]:
    host = str(settings.upload_clamav_host or "").strip()
    if not host:
        return False, "clamav_host_missing"
    port = int(settings.upload_clamav_port)
    if port < 1 or port > 65535:
        return False, "clamav_port_invalid"
    timeout = float(settings.upload_clamav_timeout_seconds)
    if timeout <= 0 or timeout > 120:
        return False, "clamav_timeout_invalid"
    return True, "clamav_configured"


def _peer_is_private(connection: socket.socket) -> bool:
    peer = connection.getpeername()
    address = ipaddress.ip_address(str(peer[0]).split("%", 1)[0])
    return bool(address.is_private or address.is_loopback or address.is_link_local)


def _connect() -> socket.socket:
    configured, detail = configuration_ready()
    if not configured:
        raise RuntimeError(detail)

    connection = socket.create_connection(
        (str(settings.upload_clamav_host).strip(), int(settings.upload_clamav_port)),
        timeout=float(settings.upload_clamav_timeout_seconds),
    )
    connection.settimeout(float(settings.upload_clamav_timeout_seconds))
    if bool(settings.upload_clamav_require_private_network) and not _peer_is_private(connection):
        connection.close()
        raise RuntimeError("clamav_public_network_refused")
    return connection


def _read_response(connection: socket.socket) -> str:
    payload = bytearray()
    while len(payload) < MAX_RESPONSE_BYTES:
        chunk = connection.recv(min(1024, MAX_RESPONSE_BYTES - len(payload)))
        if not chunk:
            break
        payload.extend(chunk)
        if b"\0" in chunk or b"\n" in chunk:
            break
    return bytes(payload).split(b"\0", 1)[0].decode("utf-8", errors="replace").strip()


def healthcheck() -> dict[str, Any]:
    configured, detail = configuration_ready()
    if not configured:
        return {"configured": False, "available": False, "detail": detail}
    try:
        with _connect() as connection:
            connection.sendall(b"zPING\0")
            response = _read_response(connection)
    except Exception as exc:
        return {
            "configured": True,
            "available": False,
            "detail": f"clamav_unavailable:{type(exc).__name__}",
        }
    return {
        "configured": True,
        "available": response.upper() == "PONG",
        "detail": "clamav_ready" if response.upper() == "PONG" else "clamav_invalid_ping_response",
    }


def scan(path: str) -> dict[str, str]:
    file_path = Path(path)
    if not file_path.is_file():
        return {"status": "error", "detail": "clamav_file_unavailable"}

    try:
        with _connect() as connection:
            connection.sendall(b"zINSTREAM\0")
            with file_path.open("rb") as file_handle:
                while True:
                    chunk = file_handle.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    connection.sendall(struct.pack("!I", len(chunk)))
                    connection.sendall(chunk)
            connection.sendall(struct.pack("!I", 0))
            response = _read_response(connection)
    except Exception as exc:
        return {
            "status": "error",
            "detail": f"clamav_unavailable:{type(exc).__name__}",
        }

    normalized = " ".join(response.replace("\x00", " ").split())[:500]
    upper = normalized.upper()
    if upper.endswith(" OK") or upper == "OK":
        return {"status": "clean", "detail": "clamav_clean"}
    if upper.endswith(" FOUND") or upper == "FOUND":
        signature = normalized.rsplit(" FOUND", 1)[0].split(":", 1)[-1].strip()
        return {
            "status": "infected",
            "detail": f"clamav_detected:{signature[:200] or 'unknown_signature'}",
        }
    return {"status": "error", "detail": "clamav_scan_error"}
