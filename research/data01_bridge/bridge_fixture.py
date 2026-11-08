"""DATA-01 V2: offline bridge of two UNMERGED contracts to installed VectorBT.

Explicit file paths only; fixture-only. Does not open network or accounts.
Source paths must be independently pinned to PR #12 and #13 exact SHAs.
The bridge is a TEST HARNESS, not an execution or scientific admission gate.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ValueError("MISSING_CONTRACT")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def fixture():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(320):
        price = 100 + .09*i + 3*math.sin(i/10)
        bars.append(dict(t=int((start+timedelta(days=i)).timestamp()),
                         o=round(price-.3,4), h=round(price+1.2,4),
                         l=round(price-1.5,4), c=round(price,4), v=1000+i))
    provenance = dict(source_id="synthetic-v1",classification="SYNTHETIC_FIXTURE",
                      retrieved_at="2025-01-02T00:00:00Z",
                      requested_from="2024-01-01T00:00:00Z",
                      requested_to="2024-12-31T00:00:00Z",
                      symbol="KAIROS_FIXTURE",interval="1d",currency="USD",rights="FIXTURE_ONLY")
    return bars,provenance

def run(envelope_file, temporal_file, provider_file, provider_python):
    envelope = load(envelope_file, "data01_envelope")
    temporal = load(temporal_file, "api_sci00_temporal")
    bars, meta = fixture()
    payload = envelope.prepare(bars, meta)
    e = payload["data_envelope"]
    if e["classification"] != "SYNTHETIC_FIXTURE" or e["scientific_status"] != "NOT_EVALUATED":
        raise ValueError("UNTRUSTED_ENVELOPE")
    expected = sha256(json.dumps(bars,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if e["sha256"] != expected or e["bar_count"] != len(bars):
        raise ValueError("DIGEST_MISMATCH")
    temporal_evidence = dict(
        schema_version="fincept-kairos-science-v1",attempt_id="fixture-only-20261108",
        source_id=e["source_id"],content_digest=e["sha256"],
        observed_at=e["actual_last"],available_at="2024-11-16T00:00:00Z",
        received_at="2024-11-16T00:00:00Z",decision_as_of="2024-12-31T00:00:00Z",
        research_clock="HISTORICAL_AS_OF_DISCOVERY",
        dataset_class=e["classification"],entitlement_status="ALLOWED")
    verdict = temporal.preflight(temporal_evidence)
    if verdict["status"] != "FIXTURE_ONLY" or verdict["authority"] is not False:
        raise ValueError("TEMPORAL_PREFLIGHT_NOT_FIXTURE_ONLY")
    # Deliberately no network/provider retrieval: only fixture injected candles.
    request = {k:v for k,v in payload.items() if k != "data_envelope"}
    request.update(symbols=["KAIROS_FIXTURE"],startDate="2024-01-01",endDate="2024-12-31",
                   interval="1d",initialCapital=100000,commission=.001,slippage=.0005,
                   strategy=dict(type="sma_crossover",params=dict(fastPeriod=10,slowPeriod=30)),
                   benchmarkSymbol="")
    proc = subprocess.run([str(provider_python),str(provider_file),"run_backtest","--stdin"],
                          input=json.dumps(request),capture_output=True,text=True,
                          timeout=50,check=False,cwd=str(provider_file.parent))
    if proc.returncode != 0:
        raise RuntimeError("PROVIDER_NONZERO_EXIT")
    try:
        response=json.loads(proc.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("PROVIDER_NON_JSON") from exc
    data=response.get("data",{})
    if response.get("success") is not True or data.get("status") != "completed":
        raise RuntimeError("PROVIDER_DID_NOT_COMPLETE")
    # Never accept Fincept's usingSyntheticData=False as evidence of real data.
    if data.get("dataSource") != "synthetic-regression-fixture":
        raise RuntimeError("PROVIDER_SOURCE_MISMATCH")
    return dict(result="FIXTURE_PIPELINE_PASS",bar_count=len(bars),
                digest=e["sha256"],provenance_class=e["classification"],
                temporal_verdict=verdict["status"],provider_status=data["status"],
                provider_source=data["dataSource"],provider_synthetic_flag=data.get("usingSyntheticData"),
                scientific_status="NOT_EVALUATED",broker_authority=False)

def main():
    p=argparse.ArgumentParser()
    for arg in ("envelope-file","temporal-file","provider-file","provider-python"):
        p.add_argument("--"+arg,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.envelope_file,a.temporal_file,a.provider_file,a.provider_python),sort_keys=True))
if __name__=="__main__":
    main()
