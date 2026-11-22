"""Real ORIGINAL yfinance_data.py daemon framing, patched Ticker, no network.

This proves PythonWorker's protocol-compatible Python peer can deliver a list
of OHLCV bars through the actual `--daemon` dispatcher; it does NOT certify
that the Yahoo network dependency is usable in the Qt persistent worker.
"""
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

ORIGINAL = Path(__file__).resolve().parents[2] / 'fincept-qt/scripts/yfinance_data.py'


def encode(frame):
    raw=json.dumps(frame,separators=(',',':')).encode()
    return struct.pack('>I',len(raw))+raw


def unpack(stream):
    buf=io.BytesIO(stream)
    values=[]
    while True:
        head=buf.read(4)
        if not head:break
        assert len(head)==4
        amount=struct.unpack('>I',head)[0]
        assert 0 < amount < 100000
        payload=buf.read(amount)
        assert len(payload)==amount
        values.append(json.loads(payload))
    return values


class OriginalDaemonHistoryNoProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stub=types.ModuleType('yfinance')
        stub.Ticker=lambda *_: (_ for _ in ()).throw(AssertionError('NETWORK_NOT_AUTHORIZED'))
        cls.old_yfinance=sys.modules.get('yfinance')
        sys.modules['yfinance']=stub
        spec=importlib.util.spec_from_file_location('fincept_original_history_daemon_qa', ORIGINAL)
        assert spec and spec.loader
        cls.module=importlib.util.module_from_spec(spec)
        sys.path.insert(0,str(ORIGINAL.parent))
        try:spec.loader.exec_module(cls.module)
        finally:sys.path.remove(str(ORIGINAL.parent))

    @classmethod
    def tearDownClass(cls):
        if cls.old_yfinance is None:sys.modules.pop('yfinance',None)
        else:sys.modules['yfinance']=cls.old_yfinance

    def test_actual_daemon_frames_and_history_dispatch(self):
        index=pd.DatetimeIndex(['2024-01-02 09:30','2024-01-03 09:30'],tz='America/New_York')
        frame=pd.DataFrame({'Open':[100.0,103.0],'High':[105.0,107.0],
                            'Low':[99.0,101.0],'Close':[102.0,105.0],
                            'Volume':[1000,1100]}, index=index)
        fake=types.SimpleNamespace(history=lambda **_:frame)
        req={"id":7,"action":"historical_period","payload":{"symbol":"SPY","period":"5d","interval":"1d"}}
        shutdown={"id":8,"action":"shutdown","payload":{}}
        stdin=types.SimpleNamespace(buffer=io.BytesIO(encode(req)+encode(shutdown)))
        output=io.BytesIO()
        stdout=types.SimpleNamespace(buffer=output)
        with patch.object(self.module.yf,'Ticker',return_value=fake) as ticker:
            with patch.object(self.module.sys,'stdin',stdin),patch.object(self.module.sys,'stdout',stdout):
                self.module.run_daemon()
        ticker.assert_called_once_with('SPY')
        frames=unpack(output.getvalue())
        self.assertEqual(len(frames),3)
        self.assertTrue(frames[0]['ready'])
        self.assertEqual(frames[1]['id'],7)
        self.assertTrue(frames[1]['ok'])
        bars=frames[1]['result']
        self.assertIsInstance(bars,list)
        self.assertEqual(len(bars),2)
        self.assertEqual(bars[1]['timestamp'],int(index[1].timestamp()))
        self.assertEqual(bars[1]['close'],105.0)
        self.assertEqual(bars[1]['volume'],1100)
        self.assertEqual(frames[2]['id'],8)
        self.assertTrue(frames[2]['result']['shutdown'])

    def test_provider_exception_returns_error_object_without_fabricated_bars(self):
        def fail(**_):raise RuntimeError('PUBLIC_PROVIDER_UNAVAILABLE')
        with patch.object(self.module.yf,'Ticker',return_value=types.SimpleNamespace(history=fail)):
            result=self.module._daemon_dispatch('historical_period',{'symbol':'SPY','period':'5d','interval':'1d'})
        self.assertIsInstance(result,dict)
        self.assertIn('error',result)
        self.assertNotIn('bars',result)


if __name__=='__main__':unittest.main()
