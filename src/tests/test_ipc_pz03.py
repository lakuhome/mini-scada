
import socket
import threading
import time
from contextlib import contextmanager

import pytest

from src.lab import api_client


@contextmanager
def mock_server(monkeypatch, parts, hold_open=0):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)

        port = listener.getsockname()[1]
        monkeypatch.setattr(api_client, "PORT", port)

        def serve():
            try:
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(5)
                    request = b""

                    while b"\r\n\r\n" not in request:
                        chunk = conn.recv(4096)
                        if not chunk:
                            return
                        request += chunk

                    for part in parts:
                        conn.sendall(part)
                        time.sleep(0.1)

                    if hold_open:
                        time.sleep(hold_open)

            except OSError:
                pass

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()

        try:
            yield
        finally:
            thread.join(timeout=7)


def test_fragmented_response(monkeypatch):
    parts = [
        b"HTTP/1.1 200 OK\r\n",
        b"Content-Length: 15\r\n",
        b"Connection: close\r\n\r\n",
        b'{"status":',
        b'"ok"}',
    ]

    with mock_server(monkeypatch, parts):
        status, headers, payload = api_client.request("/api/health")

    assert status == 200
    assert headers["content-length"] == "15"
    assert payload == {"status": "ok"}


def test_truncated_response(monkeypatch):
    parts = [
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 100\r\n"
        b"Connection: close\r\n\r\n"
        b'{"status":"ok"}'
    ]

    with mock_server(monkeypatch, parts):
        with pytest.raises(RuntimeError, match="Incomplete HTTP body"):
            api_client.request("/api/health")


def test_response_size_limit(monkeypatch):
    body = b"x" * (api_client.MAX_RESPONSE_BYTES + 1)

    parts = [
        (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii"),
        body,
    ]

    with mock_server(monkeypatch, parts):
        with pytest.raises(ValueError, match="exceeds lab limit"):
            api_client.request("/api/health")


def test_sender_does_not_close_socket(monkeypatch):
    parts = [
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Length: 15\r\n"
        b"Connection: close\r\n\r\n"
        b'{"status":"ok"}'
    ]

    with mock_server(monkeypatch, parts, hold_open=5):
        with pytest.raises(TimeoutError):
            api_client.request("/api/health")
