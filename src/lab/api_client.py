"""Клиент для наблюдения HTTP/TCP-обмена с FastAPI в отдельном процессе.

Использует только безопасные GET-запросы. Не отправляет команды управления ПЛК.
Один запрос отправляется двумя частями, чтобы проверить обработку неполного
поступления заголовка на стороне HTTP-сервера. Само кадрирование HTTP выполняет
Uvicorn/Starlette; клиент вручную выполняет socket connect/send/recv/close.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from typing import Any

HOST = "127.0.0.1"
PORT = int(os.getenv("SCADA_API_PORT", "8000"))
MAX_REQUEST_BYTES = 1024
MAX_RESPONSE_BYTES = 65536
LAB_TAG_ID = "LAB_DEMO_TEMP"


def request(path: str, *, split_request: bool = False) -> tuple[int, dict[str, str], Any]:
    raw_request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    if len(raw_request) > MAX_REQUEST_BYTES:
        raise ValueError(
            f"HTTP request exceeds lab limit: {len(raw_request)} > {MAX_REQUEST_BYTES}"
        )

    with socket.create_connection((HOST, PORT), timeout=4.0) as sock:
        sock.settimeout(4.0)
        if split_request:
            split_at = max(1, len(raw_request) // 2)
            sock.sendall(raw_request[:split_at])
            split_pause = float(os.getenv("SCADA_LAB_SPLIT_PAUSE", "0.15"))
            time.sleep(max(0.0, split_pause))
            sock.sendall(raw_request[split_at:])
        else:
            sock.sendall(raw_request)

        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            if sum(map(len, chunks)) > MAX_RESPONSE_BYTES:
                raise ValueError(
                    f"HTTP response exceeds lab limit of {MAX_RESPONSE_BYTES} bytes"
                )

    response = b"".join(chunks)
    header_end = response.find(b"\r\n\r\n")
    if header_end < 0:
        raise RuntimeError(f"Incomplete HTTP response: {response!r}")

    header_bytes = response[:header_end]
    body = response[header_end + 4:]
    header_lines = header_bytes.decode("iso-8859-1").split("\r\n")
    status_parts = header_lines[0].split(" ", 2)
    if len(status_parts) < 2:
        raise RuntimeError(f"Invalid HTTP status line: {header_lines[0]!r}")
    status = int(status_parts[1])

    headers: dict[str, str] = {}
    for line in header_lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()

    declared_length = headers.get("content-length")
    if declared_length is not None and int(declared_length) != len(body):
        raise RuntimeError(
            f"Incomplete HTTP body: expected {declared_length}, received {len(body)} bytes"
        )

    payload: Any = None
    if body:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = body.decode("utf-8", errors="replace")

    return status, headers, payload


def show(path: str, *, split_request: bool = False) -> tuple[int, Any]:
    status, headers, payload = request(path, split_request=split_request)
    print(f"GET {path} -> HTTP {status}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return status, payload


def main() -> int:
    try:
        status, _ = show("/api/health", split_request=True)
        if status != 200:
            return 1

        status, tags = show("/api/tags")
        if status != 200:
            return 1

        # StorageService архивирует стартовый тег асинхронно. Даём ему время
        # обработать replay_current перед чтением истории.
        history_status = 0
        history: Any = None
        for _ in range(15):
            history_status, history = show(f"/api/tags/{LAB_TAG_ID}/history?limit=10")
            if history_status != 200:
                return 1
            if isinstance(history, dict) and history.get("count", 0) > 0:
                break
            time.sleep(0.1)

        if history_status != 200:
            return 1

        # Ошибочный ID проверяет штатный путь HTTP 404 без изменения БД/ПЛК.
        missing_status, _ = show("/api/tags/NO_SUCH_LAB_TAG")
        if missing_status != 404:
            print("Ожидался HTTP 404 для отсутствующего тега", file=sys.stderr)
            return 1

        if isinstance(tags, dict):
            print(f"Итого: /api/tags вернул count={tags.get('count')}")
        print("API client finished; каждый TCP-сокет закрыт после ответа.")
        return 0

    except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"API client error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
