#!/usr/bin/env python3
"""Read-only gate in front of a container-engine unix socket.

Usage: ro_socket_proxy.py <real.sock> <proxy.sock>

Forwards ONLY HTTP GET and HEAD requests (list, inspect, logs, version).
Every other method (POST, PUT, DELETE, PATCH: create, start, stop, kill, exec,
remove, pull) is answered with 403 here and never reaches the engine.  One
request per connection; after the request head is forwarded, nothing further
from the client is relayed, so a second request cannot ride along.
Pure stdlib.  Runs on the HOST; the sandbox only ever sees <proxy.sock>.
"""
import os
import socket
import sys
import threading

ALLOWED = (b"GET", b"HEAD")
DENY = (b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nConnection: close\r\n"
        b"Content-Length: 41\r\n\r\nread-only socket: only GET/HEAD allowed.\n")


def handle(client: socket.socket, real_path: str) -> None:
    try:
        head = b""
        while b"\r\n\r\n" not in head and len(head) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                return
            head += chunk
        head = head.split(b"\r\n\r\n", 1)[0]          # drop any body bytes
        lines = head.split(b"\r\n")
        method = lines[0].split(b" ", 1)[0].upper()
        if method not in ALLOWED:
            client.sendall(DENY)
            return
        kept = [l for l in lines[1:] if not l.lower().startswith(
            (b"connection:", b"upgrade:", b"content-length:", b"transfer-encoding:"))]
        request = b"\r\n".join([lines[0]] + kept + [b"Connection: close"]) + b"\r\n\r\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as upstream:
            upstream.connect(real_path)
            upstream.sendall(request)
            while True:
                data = upstream.recv(65536)
                if not data:
                    break
                client.sendall(data)
    except OSError:
        pass
    finally:
        client.close()


def main() -> None:
    real_path, proxy_path = sys.argv[1], sys.argv[2]
    if os.path.exists(proxy_path):
        os.unlink(proxy_path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(proxy_path)
    os.chmod(proxy_path, 0o600)
    server.listen(16)
    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle, args=(conn, real_path), daemon=True).start()


if __name__ == "__main__":
    main()
