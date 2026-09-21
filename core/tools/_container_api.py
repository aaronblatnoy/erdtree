"""List containers over engine unix sockets (Docker-compatible HTTP API).

Used when ERDTREE_CONTAINER_SOCKETS names one or more sockets
("label=/path,label=/path").  Only GET requests are ever issued from here.
Pure stdlib.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
from typing import Any


class _UnixConn(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float = 8.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def configured_sockets() -> list[tuple[str, str]]:
    out = []
    for item in os.environ.get("ERDTREE_CONTAINER_SOCKETS", "").split(","):
        label, _, path = item.strip().partition("=")
        if label and path and os.path.exists(path):
            out.append((label, path))
    return out


def list_containers(show_all: bool = False) -> list[dict[str, Any]]:
    """One dict per container: engine, name, image, state, status, ports[(host_port, proto)]."""
    rows: list[dict[str, Any]] = []
    for label, path in configured_sockets():
        try:
            conn = _UnixConn(path)
            conn.request("GET", "/containers/json" + ("?all=true" if show_all else ""))
            resp = conn.getresponse()
            data = json.loads(resp.read() or b"[]") if resp.status == 200 else []
            conn.close()
        except (OSError, ValueError, http.client.HTTPException):
            continue
        for c in data if isinstance(data, list) else []:
            ports = sorted({(p.get("PublicPort"), p.get("Type", "tcp"))
                            for p in (c.get("Ports") or []) if p.get("PublicPort")})
            names = c.get("Names") or [""]
            rows.append({
                "engine": label,
                "name": str(names[0]).lstrip("/"),
                "image": str(c.get("Image", ""))[:48],
                "state": c.get("State", ""),
                "status": c.get("Status", ""),
                "ports": ports,
            })
    return rows
