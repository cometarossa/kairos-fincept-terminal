import sys,pathlib,unittest
from unittest.mock import patch
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from test_multi_asset_total_fees import SERIES
sys.path.insert(0,str(ROOT/"fincept-qt/scripts/Analytics/backtesting/vectorbt"))
from vectorbt_provider import VectorBTProvider
from vbt_portfolio import SimplePortfolio
class FeeDenial(unittest.TestCase):
 def test_invalid_fees(self):
  req={"strategy":{"type":"sma_crossover","params":{"fastPeriod":5,"slowPeriod":20}},"symbols":["SYNA","SYNB"],"startDate":"2024-01-01","endDate":"2030-01-01","initialCapital":100000,"commission":0.001,"slippage":0.0005,"brokerCandles":SERIES,"brokerDataSource":"synthetic_test_fixture"}
  frame=pd.DataFrame({sym:pd.Series([x["c"] for x in rows],index=pd.to_datetime([x["t"] for x in rows],unit="s")) for sym,rows in SERIES.items()})
  for v in (float("nan"),float("inf"),-1.0,None):
   with self.subTest(value=v),patch.object(VectorBTProvider,"_load_market_data",return_value=(frame,False)),patch.object(SimplePortfolio,"total_fees",return_value=v) as fee:
    r=VectorBTProvider().run_backtest(req)
    assert fee.call_count==1, r.get("error")
    assert r.get("success") is False
  with patch.object(VectorBTProvider,"_load_market_data",return_value=(frame,False)),patch.object(SimplePortfolio,"total_fees",side_effect=AttributeError("synthetic missing fee evidence")) as fee:
   r=VectorBTProvider().run_backtest(req)
   assert fee.call_count==1, r.get("error")
   assert r.get("success") is False
if __name__=="__main__":unittest.main(verbosity=2)
