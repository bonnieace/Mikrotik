#!/usr/bin/env python3
"""Minimal authenticated Unix-socket agent for Uzanet-owned PPP peers."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shlex
import shutil
import socketserver
import tempfile
import threading
import time
from pathlib import Path


MAX_REQUEST_BYTES = 16_384
PEER_PATTERN = re.compile(r"router-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
PASSWORD_PATTERN = re.compile(r"[A-Za-z0-9_-]{20,128}")


class AgentError(Exception):
    def __init__(self, message: str, code: str = "invalid_request"):
        super().__init__(message)
        self.code = code


class PeerStore:
    def __init__(self, secrets_path: str, lock_path: str, server_name: str, first_ip: str, last_ip: str, backup_dir: str):
        self.path = Path(secrets_path)
        self.lock_path = Path(lock_path)
        self.server_name = server_name
        self.first_ip = ipaddress.ip_address(first_ip)
        self.last_ip = ipaddress.ip_address(last_ip)
        self.backup_dir = Path(backup_dir)
        if self.first_ip.version != 4 or self.last_ip.version != 4 or self.first_ip > self.last_ip:
            raise RuntimeError("Invalid IPv4 allocation range")

    @staticmethod
    def _tokens(line: str) -> list[str]:
        try:
            return shlex.split(line, comments=True)
        except ValueError:
            return []

    @staticmethod
    def _quote(value: str) -> str:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _managed(self, tokens: list[str]) -> bool:
        return len(tokens) >= 4 and bool(PEER_PATTERN.fullmatch(tokens[0]))

    def _allocate(self, lines: list[str]) -> str:
        used = set()
        for line in lines:
            tokens = self._tokens(line)
            if len(tokens) >= 4:
                try:
                    used.add(ipaddress.ip_address(tokens[3]))
                except ValueError:
                    pass
        current = self.first_ip
        while current <= self.last_ip:
            if current not in used:
                return str(current)
            current += 1
        raise AgentError("No L2TP addresses are available", "pool_exhausted")

    def _write(self, lines: list[str]) -> None:
        original = self.path.stat()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup = self.backup_dir / f"chap-secrets.{int(time.time())}.{secrets.token_hex(3)}"
        shutil.copy2(self.path, backup)
        backups = sorted(self.backup_dir.glob("chap-secrets.*"), key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in backups[20:]:
            stale.unlink(missing_ok=True)

        fd, temporary = tempfile.mkstemp(prefix=".chap-secrets.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write("\n".join(lines).rstrip("\n") + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chown(temporary, original.st_uid, original.st_gid)
            os.chmod(temporary, original.st_mode & 0o777)
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def mutate(self, action: str, username: str, password: str | None = None) -> dict:
        if not PEER_PATTERN.fullmatch(username):
            raise AgentError("Invalid managed peer username")
        if action in {"create", "rotate"} and (not password or not PASSWORD_PATTERN.fullmatch(password)):
            raise AgentError("Invalid peer password")
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            lines = self.path.read_text(encoding="utf-8").splitlines()
            matches = []
            retained = []
            for line in lines:
                tokens = self._tokens(line)
                if self._managed(tokens) and tokens[0] == username:
                    matches.append(tokens)
                else:
                    retained.append(line)

            if action == "delete":
                if matches:
                    self._write(retained)
                return {"deleted": bool(matches)}

            ip_address = matches[0][3] if matches else self._allocate(lines)
            retained.append(
                f"{self._quote(username)} {self._quote(self.server_name)} "
                f"{self._quote(password or '')} {ip_address}"
            )
            self._write(retained)
            return {"created": not bool(matches), "ip_address": ip_address}


class NonceCache:
    def __init__(self):
        self.values: dict[str, int] = {}
        self.lock = threading.Lock()

    def consume(self, nonce: str, timestamp: int) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", nonce):
            raise AgentError("Invalid nonce")
        now = int(time.time())
        if abs(now - timestamp) > 60:
            raise AgentError("Expired request")
        with self.lock:
            self.values = {key: value for key, value in self.values.items() if now - value <= 60}
            if nonce in self.values:
                raise AgentError("Replayed request")
            self.values[nonce] = timestamp


class AgentServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, path: str, store: PeerStore, shared_secret: str):
        self.store = store
        self.shared_secret = shared_secret
        self.nonces = NonceCache()
        super().__init__(path, AgentHandler)


class AgentHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if not raw or len(raw) > MAX_REQUEST_BYTES:
                raise AgentError("Invalid request size")
            envelope = json.loads(raw)
            signature = str(envelope.pop("signature", ""))
            canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
            expected = hmac.new(self.server.shared_secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise AgentError("Authentication failed", "unauthorized")
            timestamp = int(envelope.get("timestamp", 0))
            self.server.nonces.consume(str(envelope.get("nonce", "")), timestamp)
            action = str(envelope.get("action", ""))
            payload = envelope.get("payload") or {}
            if action == "health":
                result = {"status": "ok"}
            elif action in {"create", "rotate", "delete"}:
                result = self.server.store.mutate(action, str(payload.get("username", "")), payload.get("password"))
            else:
                raise AgentError("Unsupported action")
            response = {"ok": True, "result": result}
        except AgentError as exc:
            response = {"ok": False, "code": exc.code, "error": str(exc)}
        except Exception:
            response = {"ok": False, "code": "internal_error", "error": "Provisioning agent failed"}
        self.wfile.write(json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n")


def main() -> None:
    shared_secret = os.environ.get("UZANET_AGENT_SHARED_SECRET", "")
    if len(shared_secret) < 32:
        raise SystemExit("UZANET_AGENT_SHARED_SECRET must contain at least 32 characters")
    socket_path = os.environ.get("UZANET_AGENT_SOCKET", "/run/uzanet-vpn-agent/agent.sock")
    socket_gid = int(os.environ.get("UZANET_AGENT_SOCKET_GID", "10001"))
    Path(socket_path).parent.mkdir(parents=True, exist_ok=True)
    os.chown(Path(socket_path).parent, 0, socket_gid)
    os.chmod(Path(socket_path).parent, 0o770)
    Path(socket_path).unlink(missing_ok=True)
    store = PeerStore(
        os.environ.get("UZANET_CHAP_SECRETS", "/etc/ppp/chap-secrets"),
        os.environ.get("UZANET_AGENT_LOCK", "/run/uzanet-vpn-agent/chap.lock"),
        os.environ.get("UZANET_PPP_SERVER_NAME", "l2tpd"),
        os.environ.get("UZANET_IP_RANGE_START", "10.10.10.10"),
        os.environ.get("UZANET_IP_RANGE_END", "10.10.10.100"),
        os.environ.get("UZANET_AGENT_BACKUP_DIR", "/var/lib/uzanet-vpn-agent/backups"),
    )
    with AgentServer(socket_path, store, shared_secret) as server:
        os.chown(socket_path, 0, socket_gid)
        os.chmod(socket_path, 0o660)
        server.serve_forever()


if __name__ == "__main__":
    main()
