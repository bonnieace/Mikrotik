from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import threading
import time

import pytest

from vpn_agent.agent import AgentServer, PeerStore


def test_peer_store_preserves_manual_entries_and_reuses_address(tmp_path):
    secrets_file = tmp_path / "chap-secrets"
    secrets_file.write_text('"manual-user" "l2tpd" "manual-password" 10.10.10.10\n', encoding="utf-8")
    os.chmod(secrets_file, 0o600)
    store = PeerStore(
        str(secrets_file),
        str(tmp_path / "agent.lock"),
        "l2tpd",
        "10.10.10.10",
        "10.10.10.12",
        str(tmp_path / "backups"),
    )
    username = "router-11111111-1111-1111-1111-111111111111"

    created = store.mutate("create", username, "a-valid-password-value_123")
    rotated = store.mutate("rotate", username, "a-different-password_456")

    assert created == {"created": True, "ip_address": "10.10.10.11"}
    assert rotated == {"created": False, "ip_address": "10.10.10.11"}
    contents = secrets_file.read_text(encoding="utf-8")
    assert "manual-user" in contents
    assert "manual-password" in contents
    assert "a-valid-password-value_123" not in contents
    assert "a-different-password_456" in contents
    assert secrets_file.stat().st_mode & 0o777 == 0o600

    assert store.mutate("delete", username) == {"deleted": True}
    assert username not in secrets_file.read_text(encoding="utf-8")
    assert store.mutate("delete", username) == {"deleted": False}


def test_agent_authenticates_and_rejects_replayed_request(tmp_path):
    secrets_file = tmp_path / "chap-secrets"
    secrets_file.write_text("", encoding="utf-8")
    store = PeerStore(
        str(secrets_file),
        str(tmp_path / "agent.lock"),
        "l2tpd",
        "10.10.10.10",
        "10.10.10.12",
        str(tmp_path / "backups"),
    )
    socket_path = str(tmp_path / "agent.sock")
    shared_secret = "a" * 48
    try:
        server = AgentServer(socket_path, store, shared_secret)
    except PermissionError:
        pytest.skip("Unix sockets are blocked by the test sandbox")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    message = {"action": "health", "nonce": "b" * 32, "payload": {}, "timestamp": int(time.time())}
    canonical = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8")
    envelope = {**message, "signature": hmac.new(shared_secret.encode(), canonical, hashlib.sha256).hexdigest()}
    wire = json.dumps(envelope, separators=(",", ":")).encode("utf-8") + b"\n"

    def request() -> dict:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(socket_path)
            client.sendall(wire)
            return json.loads(client.makefile("rb").readline())

    try:
        assert request() == {"ok": True, "result": {"status": "ok"}}
        replay = request()
        assert replay["ok"] is False
        assert replay["error"] == "Replayed request"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
