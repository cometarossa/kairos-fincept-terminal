"""TOOL-01: one Fincept native volatility tool, synthetic-only, offline.

No market data, Qt, broker, credentials, network, model or KAIROS gate.
This script is a research harness, NOT an agent-exposed production adapter.
Run with the existing Fincept venv-numpy2 and an explicit source file path.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path

BARS = 120
FIELDS = ("atr", "bb_mavg", "bb_hband", "bb_lband",
          "kc_mavg", "dc_hband", "dc_lband", "ui")


def run(source_file: Path) -> dict:
    source_file = source_file.resolve(strict=True)
    if source_file.name != "volatility_indicators.py":
        raise ValueError("SOURCE_FILE_NOT_ALLOWLISTED")
    import pandas as pd  # required existing Fincept environment, no installs
    # Deterministic, plausible OHLC synthetic fixture, never real market data.
    close = [100 + .06 * i + 1.5 * math.sin(i / 7) for i in range(BARS)]
    high = [round(x + 1.2, 6) for x in close]
    low = [round(x - 1.3, 6) for x in close]
    data = pd.DataFrame({"high": high, "low": low,
                         "close": [round(x, 6) for x in close]})
    # Identity is calculated over the exact numeric input sent to Fincept.
    rows = data.to_dict(orient="records")
    digest = sha256(json.dumps(rows, sort_keys=True,
                               separators=(",", ":")).encode()).hexdigest()
    spec = importlib.util.spec_from_file_location("fincept_fixture_volatility", source_file)
    if spec is None or spec.loader is None:
        raise ValueError("SOURCE_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    computed = module.calculate_all_volatility_indicators(data)
    if len(computed) != BARS or not set(FIELDS).issubset(computed.columns):
        raise ValueError("INVALID_OUTPUT_SCHEMA")
    # Ignore warmup values: check only the last fully formed bar.
    result = {}
    for field in FIELDS:
        value = float(computed[field].iloc[-1])
        if not math.isfinite(value):
            raise ValueError("NONFINITE_INDICATOR:" + field)
        result[field] = value
    return {
        "tool_id": "fincept.research.volatility.fixture.v1",
        "capability": "research.compute",
        "source_file": "fincept-qt/scripts/technicals/volatility_indicators.py",
        "source_sha256": sha256(source_file.read_bytes()).hexdigest(),
        "source_id": "TOOL01_DETERMINISTIC_SYNTHETIC_V1",
        "dataset_class": "SYNTHETIC_FIXTURE",
        "input_sha256": digest,
        "bar_count": BARS,
        "observed_at": "2024-04-29T00:00:00Z",
        "available_at": "2024-04-29T00:00:00Z",
        "received_at": "NOT_APPLICABLE_OFFLINE_FIXTURE",
        "rights": "FIXTURE_ONLY",
        "cost": {"external_api_calls": 0, "provider_credits": 0},
        "quality_flags": ["SYNTHETIC", "NOT_MARKET_OBSERVED",
                          "NO_PIT_CERTIFICATION", "NO_INDEPENDENT_EVALUATOR"],
        "result": result,
        "scientific_status": "NOT_EVALUATED",
        "broker_authority": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--module-file", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(run(args.module_file), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
