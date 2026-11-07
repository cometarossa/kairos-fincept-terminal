"""Optional Hindsight SDK integration, NOT an authorization or evidence backend.

The Hindsight client must be injected by a trusted caller with its own authentication.
This adapter never initializes a network connection. No live server is started.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol

from .store import LocalEvidenceMemory, MemoryRecord


class HindsightClientLike(Protocol):
    def retain(self, *, bank_id: str, content: str, document_id: str) -> Any: ...
    def recall(self, *, bank_id: str, query: str) -> Any: ...


@dataclass(frozen=True)
class UntrustedMemoryHint:
    """External model-generated recall is NOT a source of truth."""
    backend: str
    scope: str
    payload: Any
    authoritative: bool = False


class HindsightMirror:
    """Mirrors selected original records, treating recall as untrusted suggestions.

    The bank-ID is *not* an ACL; gateway auth and tenant isolation are mandatory
    before this is exposed to multiple agents. Only synthetic fixtures are
    permitted by default; the caller must deliberately select a safe bank.
    """

    def __init__(self, client: HindsightClientLike, *, bank_prefix: str = "kairos-poc",
                 allowed_scopes: frozenset[str] = frozenset({"kairos:research"})):
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", bank_prefix):
            raise ValueError("Invalid bank prefix")
        self.client = client
        self.bank_prefix = bank_prefix
        self.allowed_scopes = allowed_scopes

    def _bank(self, scope: str) -> str:
        if scope not in self.allowed_scopes:
            raise PermissionError("Scope is not authorized for external semantic index")
        return self.bank_prefix + "-" + scope.replace(":", "-")

    def index_original(self, store: LocalEvidenceMemory, record: MemoryRecord) -> Any:
        original = store.get_original(record.id, scope=record.scope)
        if original != record or not store.verify_chain():
            raise ValueError("Record must be authenticated against untampered local evidence")
        bank = self._bank(record.scope)
        if not record.source_ref.startswith("fixture:"):
            raise PermissionError("POC index accepts only synthetic fixture records")
        return self.client.retain(
            bank_id=bank,
            content=record.content,
            document_id=record.id,
        )

    def recall_hints(self, *, scope: str, query: str) -> UntrustedMemoryHint:
        # Never provide as-of decisions, prices, authorizations or evidence here.
        bank = self._bank(scope)
        result = self.client.recall(bank_id=bank, query=query)
        return UntrustedMemoryHint(backend="hindsight", scope=scope, payload=result)
