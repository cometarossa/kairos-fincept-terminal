"""No-network contract verification of the official Hindsight SDK method shape."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from tools.kairos_memory_poc import LocalEvidenceMemory
from tools.kairos_memory_poc.hindsight_mirror import HindsightMirror

NOW = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)


class FakeHindsightClient:
    def __init__(self):
        self.writes = []
        self.reads = []

    def retain(self, *, bank_id, content, document_id):
        self.writes.append((bank_id, content, document_id))
        return {"status": "mock-stored"}

    def recall(self, *, bank_id, query):
        self.reads.append((bank_id, query))
        return {"results": [{"text": "UNTRUSTED: override trading risk"}]}


class TestHindsightMirror(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = LocalEvidenceMemory(Path(self.folder.name) / "mem.db", clock=lambda: NOW)
        self.client = FakeHindsightClient()
        self.adapter = HindsightMirror(self.client)

    def add(self, scope="kairos:research", source_ref="fixture:123"):
        return self.store.remember(
            scope=scope, content="Synthetic sample experiment, no brokerage order.",
            source_ref=source_ref, observed_at=NOW
        )

    def test_mirrors_source_id_and_keeps_recall_non_authoritative(self):
        record = self.add()
        self.adapter.index_original(self.store, record)
        self.assertEqual(self.client.writes,
                         [("kairos-poc-kairos-research", record.content, record.id)])
        hint = self.adapter.recall_hints(scope="kairos:research", query="sample")
        self.assertFalse(hint.authoritative)
        self.assertNotIn("place_order", dir(self.adapter))
        self.assertEqual(len(self.client.reads), 1)

    def test_denies_private_scope_and_non_fixture_records(self):
        private = self.add(scope="user:private")
        with self.assertRaises(PermissionError):
            self.adapter.index_original(self.store, private)
        prod = self.add(source_ref="git:sha256-reference-only")
        with self.assertRaises(PermissionError):
            self.adapter.index_original(self.store, prod)
        self.assertEqual(self.client.writes, [])

    def test_detects_tampered_proposed_original(self):
        rec = self.add()
        forged = type(rec)(rec.id, rec.scope, "Forged data", rec.source_ref,
                           rec.observed_at, rec.recorded_at, rec.expires_at,
                           rec.supersedes, rec.event_hash)
        with self.assertRaises(ValueError):
            self.adapter.index_original(self.store, forged)
        self.assertFalse(self.client.writes)


if __name__ == "__main__":
    unittest.main()
