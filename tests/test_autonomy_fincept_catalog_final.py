"""Full-surface Fincept MCP catalogue inventory (offline, no tool calls).

This checks only static reference-source identity and synthetic parser behavior.
It does not prove Fincept's native Qt runtime functions work. No IG access.
"""
from pathlib import Path
import hashlib
import importlib.util
import sys

ROOT=Path('/work') if Path('/work/fincept-qt').is_dir() else Path(__file__).resolve().parents[1]
SOURCE=ROOT/'fincept_mcp_tools_source.txt'
if not SOURCE.exists():SOURCE=ROOT/'fincept-qt/src/mcp/server/McpHttpServer_Tools.cpp'
assert SOURCE.is_file(), 'ORIGINAL_NATIVE_FINCEPT_SOURCE_REQUIRED'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='c75ac0f2cdfee1b9b94447f89a9a92178712d015e2b91bcaad8d82e3a256e698'
folder=ROOT/'fincept-qt/tests/research'
sys.path.insert(0,str(folder))
from test_mcp_catalog_boundary_v1 import catalogue_names
from test_mcp_catalog_report_v1 import audit_catalog

schema={'type':'object'}
rows=[{'name':name,'inputSchema':schema} for name in
      ['tool_list','tool_describe','get_quote','get_history','run_screener','study_indicator',
       'live_place_order','broker_account_info','credential_show','execute_trade','quantlab_backtest']]
result=audit_catalog({'tools':rows})
assert result['total']==len(rows)
assert result['all_names']==[r['name'] for r in rows], 'DO_NOT_DROP_UNSUPPORTED_FINCEPT_TOOLS'
assert set(result['suspected_sensitive'])=={'live_place_order','broker_account_info','credential_show','execute_trade'}
assert result['tool_calls_authorized'] is False
assert result['execution_authority'] is False
assert result['market_data_certified'] is False
assert result['complete_runtime_catalog'] is False
assert catalogue_names({'tools':rows})==[r['name'] for r in rows]
assert audit_catalog({'tools':[{'name':'get_quote','inputSchema':schema}]})['suspected_sensitive']==[]
for invalid in ({},None,{'tools':[]},{'tools':[{'name':'x','inputSchema':schema},{'name':'x','inputSchema':schema}]},
                {'tools':[{'name':'x','inputSchema':None}]},
                {'tools':[{'name':'../bad','inputSchema':schema}]}):
    try:audit_catalog(invalid)
    except (ValueError,TypeError):pass
    else:raise AssertionError('INVALID_FINCEPT_CATALOGUE_ACCEPTED '+repr(invalid))
print('FINCEPT_SOURCE_PINNED_FULL_CATALOGUE_OFFLINE_FINAL_PASS')
