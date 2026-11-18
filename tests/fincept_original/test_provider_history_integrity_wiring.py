"""Source contract: original provider conversion cannot bypass strict Qt validation."""
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[2]


class ProviderHistoryIntegrityWiring(unittest.TestCase):
    def test_original_qt_history_callback_uses_strict_decode_not_default_zero(self):
        p = (BASE / "fincept-qt/src/services/markets/MarketDataService.cpp").read_text()
        body = p[p.index("void MarketDataService::fetch_history("):p.index("// ── Static symbol lists", p.index("void MarketDataService::fetch_history("))]
        self.assertIn("history_integrity::decode(doc)", body)
        self.assertIn("cb(false, {});", body)
        self.assertNotIn('o["timestamp"].toDouble()', body)
        self.assertNotIn('o["close"].toDouble()', body)

    def test_only_history_period_has_missing_volume_as_unknown(self):
        p = (BASE / "fincept-qt/scripts/yfinance_data.py").read_text()
        body = p[p.index('def get_historical_period('):p.index('def resolve_symbol(',p.index('def get_historical_period('))]
        self.assertIn('"volume": _int(row[\'Volume\'])', body)
        self.assertNotIn('_int(row[\'Volume\'], 0)', body)

    def test_decoder_rejects_missing_or_untrustworthy_without_claiming_freshness(self):
        p = (BASE / "fincept-qt/src/services/markets/HistoryIntegrity.h").read_text()
        for x in ('document.isArray()', 'input.isEmpty()', 'item.isObject()',
                  'std::isfinite(number)', 'std::floor(*timestamp)',
                  'previous_timestamp', 'std::floor(*volume)',
                  'std::nullopt', 'now_utc_seconds'):
            self.assertIn(x,p)
        self.assertNotIn('market_as_of_verified = true',p)


if __name__ == '__main__':
    unittest.main()
