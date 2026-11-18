"""Independent final research-only backtest evidence certification refusal."""
from pathlib import Path
import hashlib,sys
ROOT=Path('/work') if Path('/work/fincept-qt').is_dir() else Path(__file__).resolve().parents[1]
src=ROOT/'fincept_mcp_tools_source.txt'
if not src.exists():src=ROOT/'fincept-qt/src/mcp/server/McpHttpServer_Tools.cpp'
assert src.is_file() and hashlib.sha256(src.read_bytes()).hexdigest()=='c75ac0f2cdfee1b9b94447f89a9a92178712d015e2b91bcaad8d82e3a256e698'
sys.path.insert(0,str(ROOT/'fincept-qt/tests/research'))
from test_backtest_asof_boundary_v1 import validate_backtest_window
from test_backtest_asof_report_v1 import audit_backtest_evidence
p=dict(decision_at='2026-11-01T12:00:00Z',data_asof='2026-11-01T11:00:00Z',train_end='2026-10-31T00:00:00Z',evaluation_start='2026-11-02T00:00:00Z',evaluation_end='2026-11-09T00:00:00Z',provider='HISTORICAL',dataset_sha256='f'*64)
r=audit_backtest_evidence(p)
assert set(r)=={'window','evidence_kind','scientific_fitness_certified','real_market_data_certified','out_of_sample_certified','execution_authority'}
assert r['window']==p and r['window'] is not p
assert r['evidence_kind']=='RESEARCH_METADATA_ONLY'
assert all(r[k] is False for k in ('scientific_fitness_certified','real_market_data_certified','out_of_sample_certified','execution_authority'))
for bad in ({**p,'scientific_fitness_certified':True},{**p,'train_end':'2026-11-04T00:00:00Z'},{**p,'dataset_sha256':'invalid'},None):
 try:audit_backtest_evidence(bad)
 except (ValueError,TypeError):pass
 else:raise AssertionError('UNTRUSTED_BACKTEST_PROOF_ACCEPTED')
print('FINCEPT_BACKTEST_ASOF_EVIDENCE_FINAL_PASS')
