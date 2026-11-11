"""Offline preservation smoke of ALL FIVE ORIGINAL Fincept technical indicator modules.

A human-controlled local development test: imports byte-pinned, trusted original
Fincept modules and runs deterministic OHLCV input. Does NOT attest installation,
GUI, data rights, predictive alpha, package supply chain or security sandboxing.
No broker/account, provider, paid API, Qt, writes, scheduling, or cloud calls.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import socket
import sys

SOURCE_RELATIVE = "fincept-qt/scripts/technicals"
# hashes of ORIGINAL files on fork main 7716ee8613249fb44c4d14036c5bc16ed6f34e97
PINNED_MODULES = {
    "volatility": ("76c8a2329c3109d801222ecc987f57005041533e8264c90f1d8b46a4c0109897", 21),
    "momentum": ("931056f67fd992f26c7f02be6ec12c865dcd20a6ef27c777a62287d76d14d845", 18),
    "trend": ("9aba65b9c162ff51b060984ded86e8ab5e1cc3760f10a8cbec9f68ba491e72fd", 30),
    "volume": ("81cac7f2e4ef2e3e5b6140d969d3d7c4e0822f9d9453457243fdc223fe352004", 10),
    "others": ("c0c8b9f93a99ae4a699f96112927cdd18553a7a3e5b486b09c18bde0fdf4f117", 3),
}
OHLCV_BARS = 180
# PSAR_up / PSAR_down are sparse regime-specific series. The original trend
# module returns no active PSAR_down value in this fixture's final up regime,
# but its prior 69 values are finite; this is NOT an instrument failure.
EXPECTED_SPARSE_FINAL = {"trend": {"psar_down"}}


class TechnicalProbeError(ValueError):
    pass


def synthetic_ohlcv():
    import pandas as pd

    close = [
        round(100 + 0.06 * i + 1.5 * math.sin(i / 7), 6)
        for i in range(OHLCV_BARS)
    ]
    return pd.DataFrame({
        "high": [round(x + 1.2, 6) for x in close],
        "low": [round(x - 1.3, 6) for x in close],
        "close": close,
        "open": [round(x - 0.2, 6) for x in close],
        "volume": [
            10000 + i * 17 + int(200 * math.sin(i / 6))
            for i in range(OHLCV_BARS)
        ],
    })


def _load_pinned_module(path: Path, name: str, expected: str):
    if path.is_symlink() or not path.is_file() or path.name != f"{name}_indicators.py":
        raise TechnicalProbeError("MISSING_OR_INVALID_PINNED_ORIGINAL:" + name)
    data = path.read_bytes()
    if sha256(data).hexdigest() != expected:
        raise TechnicalProbeError("CHANGED_ORIGINAL_SOURCE_SHA256:" + name)
    spec = importlib.util.spec_from_file_location("original_fincept_" + name, path)
    if not spec or not spec.loader:
        raise TechnicalProbeError("UNAVAILABLE_ORIGINAL_MODULE:" + name)
    module = importlib.util.module_from_spec(spec)
    # Execute exactly the bytes whose hash was checked above. A matching
    # timestamp/size .pyc can otherwise substitute different code, and the
    # source loader may write a new cache during this read-only probe.
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def run_all(source_dir: Path) -> dict:
    """No outputs persisted. Only in-memory synthetic computations."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create = socket.create_connection

    def deny_network(*args, **kwargs):
        raise TechnicalProbeError("NETWORK_ATTEMPT_DENIED")

    # Narrow network guard: defense-in-depth for Python sockets only.
    # Not an OS sandbox, not a guarantee about native/transitive libraries.
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    socket.create_connection = deny_network
    try:
        data = synthetic_ohlcv()
        modules = []
        for name, (expected_sha, expected_count) in PINNED_MODULES.items():
            mod = _load_pinned_module(source_dir / (name + "_indicators.py"), name, expected_sha)
            input_before = data.copy(deep=True)
            original_cols = tuple(input_before.columns)
            output = getattr(mod, "calculate_all_" + name + "_indicators")(data)
            # Detect in-place mutation as well as altered OHLCV values in output.
            import pandas as pd
            try:
                pd.testing.assert_frame_equal(data, input_before, check_exact=True)
                pd.testing.assert_frame_equal(output.loc[:, list(original_cols)], input_before, check_exact=True)
            except (AssertionError, KeyError, ValueError, TypeError) as exc:
                raise TechnicalProbeError("ORIGINAL_OHLCV_VALUES_CHANGED:" + name) from exc
            if tuple(output.columns[:len(original_cols)]) != original_cols:
                raise TechnicalProbeError("INPUT_COLUMNS_CHANGED:" + name)
            generated = [col for col in output.columns if col not in original_cols]
            if len(generated) != expected_count or len(set(generated)) != len(generated):
                raise TechnicalProbeError("INDICATOR_COUNT_DRIFT:" + name)
            observed_sparse = set()
            for col in generated:
                series = output[col]
                # Historical infinity is invalid even when the final bar is finite.
                # NaN warm-up and inactive-regime observations remain permitted.
                import numpy as np
                if bool(np.isinf(series.to_numpy(dtype=float)).any()):
                    raise TechnicalProbeError("INFINITE_INDICATOR_HISTORY:" + name + ":" + col)
                last = series.iloc[-1]
                if not isinstance(last, (int, float)) and not hasattr(last, "item"):
                    raise TechnicalProbeError("NON_NUMERIC_INDICATOR:" + name + ":" + col)
                last_number = float(last)
                if not math.isfinite(last_number):
                    observed_sparse.add(col)
                    # A sparse series can be inactive at the latest bar; it
                    # must have finite historical values, not be all-NaN.
                    if series.notna().sum() < 1:
                        raise TechnicalProbeError("ALWAYS_MISSING_SERIES:" + name + ":" + col)
            if observed_sparse != EXPECTED_SPARSE_FINAL.get(name, set()):
                raise TechnicalProbeError("UNEXPECTED_LAST_BAR_MISSING:" + name +
                                          ":" + ",".join(sorted(observed_sparse)))
            modules.append({
                "module": name,
                "source_sha256": expected_sha,
                "computed_indicator_columns": expected_count,
                "sparse_inactive_at_last_bar": sorted(observed_sparse),
                "status": "SYNTHETIC_COMPUTATION_PASS",
            })
        return {
            "schema": "fincept_original_technicals_offline_probe_v1",
            "source_kind": "SYNTHETIC_FIXTURE_NOT_MARKET_DATA",
            "bar_count": OHLCV_BARS,
            "module_count": len(modules),
            "total_indicator_columns": sum(x["computed_indicator_columns"] for x in modules),
            "scientific_status": "NOT_EVALUATED",
            "broker_authority": False,
            "modules": modules,
        }
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.create_connection = original_create


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only original Fincept indicator family probe")
    parser.add_argument("--original-technicals-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_all(args.original_technicals_dir)
    except (TechnicalProbeError, OSError, ImportError, AttributeError, ValueError) as e:
        print(json.dumps({
            "schema": "fincept_original_technicals_offline_probe_v1",
            "status": "FAILED_OR_UNVERIFIED",
            "reason": str(e)[:180],
            "broker_authority": False,
        }))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
