"""Block Python socket egress during local fixture-only functional audits.

Defense in depth, not a whole-OS network sandbox. No native-code claims.
"""
import socket


def _block(*args, **kwargs):
    raise RuntimeError("FINCEPT_AUDIT_NETWORK_BLOCKED: synthetic data only")


socket.socket.connect = _block
socket.socket.connect_ex = _block
socket.socket.sendto = _block
socket.create_connection = _block
