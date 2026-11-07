"""Deterministic local-only, synthetic memory benchmark: no external LLM/backend."""
from datetime import datetime, timezone
from pathlib import Path
import json
import statistics
import tempfile
import time

from tools.kairos_memory_poc import LocalEvidenceMemory


def main():
    now = datetime(2026, 11, 7, 10, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix="kairos-memory-benchmark-") as folder:
        store = LocalEvidenceMemory(Path(folder) / "memory.sqlite", clock=lambda: now)
        ingest_start = time.perf_counter()
        for n in range(300):
            topic = ["volatilità", "rischio", "segnale", "fornitore", "ricerca"][n % 5]
            scope = ["kairos:research", "kairos:incidents", "fincept:code"][n % 3]
            store.remember(scope=scope,
                           content=f"Esperimento sintetico numero {n} sul tema {topic}: nessun ordine reale.",
                           source_ref=f"fixture:synthetic-{n:04d}",
                           observed_at=now)
        ingest_ms = round((time.perf_counter() - ingest_start) * 1000, 2)
        samples = []
        for _ in range(60):
            start = time.perf_counter()
            store.recall("volatilità", scope="kairos:research")
            samples.append((time.perf_counter() - start) * 1000)
        samples.sort()
        result = {
            "engine": "sqlite-fts5-synthetic-baseline",
            "records": store.event_count(),
            "ingest_total_ms": ingest_ms,
            "recall_p50_ms": round(statistics.median(samples), 3),
            "recall_p95_ms": round(samples[56], 3),
            "recall_query": "volatilità",
            "chain_verified": store.verify_chain(),
            "backend_semantic": False,
            "hindsight_tested": False,
            "mem0_tested": False,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
