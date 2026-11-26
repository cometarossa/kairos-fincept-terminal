"""Deny-first CONNECT handler adapted from original pinned Fincept QA proxy."""
from __future__ import annotations

import argparse
import select
import socket
import socketserver
import sys
import threading
import time

APPROVED = frozenset({
    'query1.finance.yahoo.com',
    'query2.finance.yahoo.com',
    'fc.yahoo.com',
    'finance.yahoo.com',
})
# Maximum admitted CONNECT attempts, INCLUDING intentional local denials.
# Atomic admission closes the multithreaded race in a non-atomic += counter.
MAX_CONNECTIONS = 24
HOST_LABELS = {
    'query1.finance.yahoo.com': 'Q1',
    'query2.finance.yahoo.com': 'Q2',
    'fc.yahoo.com': 'FC',
    'finance.yahoo.com': 'FINANCE',
}
MAX_BYTES_PER_DIRECTION = 3_000_000
MAX_LIFETIME_SECONDS = 40


def parse_connect(line: bytes) -> str | None:
    """Strict CONNECT host:443 HTTP/1.0-1.1; no wildcard or broker access."""
    try:
        value = line.decode('ascii', errors='strict').strip('\r\n')
    except UnicodeDecodeError:
        return None
    parts = value.split(' ')
    if len(parts) != 3 or parts[0] != 'CONNECT' or parts[2] not in ('HTTP/1.1', 'HTTP/1.0'):
        return None
    if parts[1].count(':') != 1 or parts[1].split(':', 1)[1] != '443':
        return None
    host = parts[1].split(':', 1)[0]
    return host if host in APPROVED else None


class ConnectHandler(socketserver.BaseRequestHandler):
    def handle(self):
        connection = self.request
        connection.settimeout(4)
        if not self.server.shared_budget.admit(self.server.lane):
            return
        data = bytearray()
        while b'\r\n\r\n' not in data and len(data) < 8192:
            try:
                part = connection.recv(4096)
            except OSError:
                return
            if not part:
                return
            data.extend(part)
        if b'\r\n\r\n' not in data or len(data) >= 8192:
            return
        header, remainder = data.split(b'\r\n\r\n', 1)
        host = parse_connect(header.split(b'\r\n', 1)[0])
        if host is None or remainder:
            # Counters only; never log rejected host/IP/account tokens.
            print("QA_PROXY_DENIED_CONNECT", flush=True)
            try:
                connection.sendall(b'HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            except OSError:
                pass
            return
        # Report only a fixed approved-host family, never CONNECT lines or
        # request URLs. The caller aggregates these metadata-only tokens.
        with self.server._admission_lock:
            print("QA_PROXY_APPROVED_CONNECT_HOST=" + HOST_LABELS[host], flush=True)
        # DNS is resolved by this short-lived proxy only, never by Fincept's
        # original Python subprocess (which is confined by Seatbelt).
        try:
            upstream = self.server.connect_upstream((host, 443), timeout=7)
        except OSError:
            return
        try:
            connection.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            # select() is used for readiness; do NOT mark sockets nonblocking.
            # sendall() on a nonblocking socket can raise EAGAIN midway through
            # a TLS record, severing Yahoo HTTPS tunnels and causing retries.
            connection.settimeout(5)
            upstream.settimeout(5)
            totals = {connection: 0, upstream: 0}
            deadline = time.monotonic() + MAX_LIFETIME_SECONDS
            while time.monotonic() < deadline:
                readable, _, _ = select.select([connection, upstream], [], [], 1)
                if not readable:
                    continue
                for sender in readable:
                    try:
                        chunk = sender.recv(65536)
                    except OSError:
                        return
                    if not chunk:
                        return
                    totals[sender] += len(chunk)
                    if totals[sender] > MAX_BYTES_PER_DIRECTION:
                        return
                    dest = upstream if sender is connection else connection
                    try:
                        dest.sendall(chunk)
                    except OSError:
                        return
        finally:
            upstream.close()


