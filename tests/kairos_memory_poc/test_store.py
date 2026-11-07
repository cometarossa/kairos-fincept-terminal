"""Safety regression tests: synthetic evidence only, no broker or network access."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from tools.kairos_memory_poc import LocalEvidenceMemory

UTC = timezone.utc
T0 = datetime(2026, 11, 7, 8, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 7, 9, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)


class TestEvidenceMemory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kairos-memory-test-")
        self.addCleanup(self.temp.cleanup)
        self.now = T1
        self.path = Path(self.temp.name) / "evidence.sqlite"
        self.store = LocalEvidenceMemory(self.path, clock=lambda: self.now)

    def add(self, content="Il laboratorio ha sospeso il test per volatilità.",
            scope="kairos:research", observed_at=T0, expires_at=None):
        return self.store.remember(
            scope=scope, content=content, observed_at=observed_at,
            expires_at=expires_at, source_ref="fixture:synthetic-v1",
        )

    def test_persistence_and_exact_original(self):
        event = self.add()
        reopened = LocalEvidenceMemory(self.path, clock=lambda: self.now)
        self.assertEqual(event.content, reopened.get_original(event.id, scope=event.scope).content)
        self.assertEqual(reopened.event_count(), 1)
        self.assertTrue(reopened.verify_chain())
        self.assertEqual(len(reopened.recall("volatilità", scope=event.scope)), 1)

    def test_scopes_do_not_mix(self):
        first = self.add(content="Volatilità elevata in KAIROS")
        self.add(content="Volatilità nel conto simulato", scope="fincept:code")
        self.assertEqual([x.id for x in self.store.recall("Volatilità", scope="kairos:research")], [first.id])
        self.assertIsNone(self.store.get_original(first.id, scope="fincept:code"))
        with self.assertRaises(ValueError):
            self.store.recall("volatilità", scope="*", limit=10)

    def test_anti_hindsight_and_correction_timeline(self):
        original = self.add(content="Il test sul dataset sintetico è PASS")
        self.now = T2
        corrected = self.store.supersede(
            original.id, scope="kairos:research",
            corrected_content="Il test sul dataset sintetico è FAIL",
            source_ref="fixture:correction-v2", observed_at=T1,
        )
        self.assertEqual([x.id for x in self.store.recall("test", scope="kairos:research", as_of=T1)], [original.id])
        self.assertEqual([x.id for x in self.store.recall("test", scope="kairos:research", as_of=T2)], [corrected.id])
        self.assertEqual(self.store.event_count(), 2)
        self.assertTrue(self.store.verify_chain())
        with self.assertRaises(ValueError):
            self.store.supersede(original.id, scope="kairos:research",
                corrected_content="Conflicting correction", source_ref="fixture:invalid", observed_at=T1)

    def test_no_knowledge_before_recorded_time_or_observed_time(self):
        self.add(content="Evento fittizio scoperto dopo il test", observed_at=T0)
        self.assertEqual(self.store.recall("Evento", scope="kairos:research", as_of=T0), [])
        self.assertEqual(len(self.store.recall("Evento", scope="kairos:research", as_of=T1)), 1)
        with self.assertRaises(ValueError):
            self.add(content="Un fatto che arriverà domani", observed_at=T2)

    def test_expiry_and_validation(self):
        self.add(content="Indicatore sintetico in scadenza", expires_at=T2)
        self.assertEqual(len(self.store.recall("Indicatore", scope="kairos:research", as_of=T1)), 1)
        self.assertEqual(self.store.recall("Indicatore", scope="kairos:research", as_of=T2), [])
        with self.assertRaises(ValueError):
            self.store.remember(scope="kairos:research", content=" ", source_ref="fixture:x", observed_at=T0)
        with self.assertRaises(ValueError):
            self.store.remember(scope="kairos:research", content="secret", source_ref="unknown:x", observed_at=T0)
        with self.assertRaises(ValueError):
            self.store.remember(scope="kairos:research", content="too old",
                                source_ref="fixture:x", observed_at=T0, expires_at=T0)

    def test_query_escapes_fts_operators_and_bounds(self):
        self.add("L'ordine simulato non è un ordine broker")
        for malicious in ('" OR NOT *', "volatilità' OR 1=1 --", "((( )))", "\x00", ""):
            self.store.recall(malicious, scope="kairos:research")
        with self.assertRaises(ValueError):
            self.store.recall("ordine", scope="kairos:research", limit=200)

    def test_idempotent_replay_does_not_duplicate_events(self):
        first = self.add("Duplicazione sintetica di una prova")
        replay = self.add("Duplicazione sintetica di una prova")
        self.assertEqual(first.id, replay.id)
        self.assertEqual(self.store.event_count(), 1)
        self.now = T2
        correction = self.store.supersede(
            first.id, scope="kairos:research",
            corrected_content="Duplicazione sintetica corretta",
            source_ref="fixture:correction", observed_at=T1,
        )
        again = self.store.supersede(
            first.id, scope="kairos:research",
            corrected_content="Duplicazione sintetica corretta",
            source_ref="fixture:correction", observed_at=T1,
        )
        self.assertEqual(correction.id, again.id)
        self.assertEqual(self.store.event_count(), 2)
        self.assertTrue(self.store.verify_chain())

    def test_existing_symlink_is_rejected(self):
        link = Path(self.temp.name) / "linked.sqlite"
        link.symlink_to(self.path)
        with self.assertRaises(PermissionError):
            LocalEvidenceMemory(link)

    def test_hash_tamper_detection(self):
        self.add()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE memory_events SET content='tampered' WHERE seq=1")
        self.assertFalse(self.store.verify_chain())

    def test_file_permissions(self):
        if os.name != "posix":
            self.skipTest("POSIX file mode test")
        self.assertEqual(self.path.stat().st_mode & 0o077, 0)
        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / "shared"
            shared.mkdir()
            shared.chmod(0o777)
            with self.assertRaises(PermissionError):
                LocalEvidenceMemory(shared / "db.sqlite")

    def test_no_broker_or_network_methods(self):
        banned = {"place_order", "cancel_order", "set_risk_override", "enable_live", "execute_trade"}
        self.assertTrue(banned.isdisjoint(dir(self.store)))


if __name__ == "__main__":
    unittest.main()
