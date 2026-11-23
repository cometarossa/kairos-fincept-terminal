"""Bound original Qt DataHub error lane to the quote strip (source-only checks).

Real behavior is covered by --smoke-test in the native Linux Qt build.
These source checks are not evidence that the C++ code compiled.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
STRIP = ROOT / "fincept-qt/src/screens/dashboard/widgets/MarketQuoteStripWidget.cpp"
SMOKE = ROOT / "fincept-qt/src/app/ScreenSmokeTest.cpp"
HUB = ROOT / "fincept-qt/src/datahub/DataHub.cpp"


class OriginalQuoteErrorF0(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strip = STRIP.read_text(encoding="utf-8")
        cls.smoke = SMOKE.read_text(encoding="utf-8")
        cls.hub = HUB.read_text(encoding="utf-8")

    def test_real_error_subscription_follows_original_quote_path(self):
        source = self.strip.split("void MarketQuoteStripWidget::hub_resubscribe()", 1)[1]
        source = source.split("void MarketQuoteStripWidget::hub_unsubscribe_all()", 1)[0]
        self.assertIn("hub.subscribe(this, topic, [this](const QVariant& v)", source)
        self.assertIn('hub.subscribe_pattern_errors(this, QStringLiteral("market:quote:*")', source)
        self.assertIn("on_quote(v.value<fincept::services::QuoteData>());", source)

    def test_only_configured_symbols_can_signal_errors(self):
        region = self.strip.split("hub.subscribe_pattern_errors(this", 1)[1]
        region = region.split("hub_active_ = true;", 1)[0]
        self.assertIn('const QString symbol = topic.mid(QStringLiteral("market:quote:").size());', region)
        self.assertIn("auto it = rows_.find(symbol);", region)
        self.assertIn("if (it == rows_.end())", region)
        self.assertIn("return;", region)
        self.assertIn('set_error(tr("Quote %1 unavailable: %2")', region)
        self.assertIn("if (received_.isEmpty())", region)

    def test_explicit_error_lifecycle_and_valid_quote_recovery(self):
        self.assertIn('hub.unsubscribe_pattern_errors(this, QStringLiteral("market:quote:*"));', self.strip)
        self.assertIn("hub.unsubscribe(this);", self.strip)
        quote = self.strip.split("void MarketQuoteStripWidget::on_quote(", 1)[1]
        quote = quote.split("QDialog* MarketQuoteStripWidget::make_config_dialog(", 1)[0]
        self.assertIn("r.change->setToolTip(QString{});", quote)
        self.assertIn("set_loading_progress(received_.size(), symbols_.size());", quote)
        self.assertIn('row.change->setText(tr("Last quote"));', self.strip)
        self.assertIn('row.change->setText(tr("Unavailable"));', self.strip)

    def test_native_smoke_exercises_error_and_recovery_without_provider(self):
        smoke = self.smoke.split("bool dashboard_quote_datahub_smoke()", 1)[1]
        smoke = smoke.split("const QString kDashboardId", 1)[0]
        for text in (
            "hub.publish_error(topic,",
            "hub.publish_error(missing_topic,",
            'change->text() == QStringLiteral("Last quote")',
            "missing.is_showing_error()",
            "recovered_cleanly",
            "error_cleared",
            "hub.unsubscribe(&missing);",
            "return all_ok;",
        ):
            with self.subTest(text=text):
                self.assertIn(text, smoke)
        self.assertNotIn("MarketDataService::instance()", smoke)
        self.assertNotIn("python::PythonWorker", smoke)
        self.assertIn("publish_error", self.hub)


    def test_linux_ci_runs_real_binary_smoke_not_just_source_checks(self):
        workflow = (ROOT / ".github/workflows/build-linux-qa.yml").read_text(encoding="utf-8")
        self.assertIn("Run original dashboard DataHub quote/error smoke (Linux)", workflow)
        self.assertIn('if: runner.os == \'Linux\'', workflow)
        self.assertIn('ci_app_checks.sh smoke "build/', workflow)
        self.assertIn("ci-quote-error-smoke 540", workflow)


    def test_expired_cache_hide_show_keeps_last_good_row_and_separate_progress(self):
        header = (ROOT / "fincept-qt/src/screens/dashboard/widgets/MarketQuoteStripWidget.h").read_text()
        self.assertIn("QSet<QString> has_quote_;", header)
        self.assertIn("has_quote_.clear();", self.strip)
        self.assertIn("has_quote_.insert(q.symbol);", self.strip)
        self.assertIn("if (has_quote_.contains(symbol))", self.strip)
        resub = self.strip.split("void MarketQuoteStripWidget::hub_resubscribe()", 1)[1]
        resub = resub.split("void MarketQuoteStripWidget::hub_unsubscribe_all()", 1)[0]
        self.assertIn("received_.clear();", resub)
        self.assertNotIn("has_quote_.clear();", resub)
        smoke = self.smoke.split("bool dashboard_quote_datahub_smoke()", 1)[1]
        smoke = smoke.split("const QString kDashboardId", 1)[0]
        self.assertIn("stale_policy.ttl_ms = 1;", smoke)
        self.assertIn("spin(20);", smoke)
        self.assertIn("preserved_after_hide", smoke)
        self.assertIn("recovered_cleanly && preserved_after_hide", smoke)


if __name__ == "__main__":
    unittest.main()
