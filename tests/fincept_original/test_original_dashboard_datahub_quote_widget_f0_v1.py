"""Original Fincept Qt source contract for native dashboard/DataHub widget smoke.

This test is an offline structural regression. It is NOT a native Qt runtime
result: the original --smoke-test must execute in Linux CI and in the
independent packaged Debian QA guest before the F0 milestone is accepted.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "fincept-qt/src/app/ScreenSmokeTest.cpp"
STRIP = ROOT / "fincept-qt/src/screens/dashboard/widgets/MarketQuoteStripWidget.cpp"
HUB = ROOT / "fincept-qt/src/datahub/DataHub.cpp"
MARKET = ROOT / "fincept-qt/src/services/markets/MarketDataService.cpp"


class OriginalDashboardDataHubQuoteWidgetF0(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = SMOKE.read_text()
        cls.strip = STRIP.read_text()
        cls.hub = HUB.read_text()
        cls.market = MARKET.read_text()

    def test_original_widget_has_real_datahub_subscription_and_label_paint(self):
        self.assertIn('QStringLiteral("market:quote:") + sym', self.strip)
        self.assertIn('hub.subscribe(this, topic, [this](const QVariant& v)', self.strip)
        self.assertIn('on_quote(v.value<fincept::services::QuoteData>());', self.strip)
        self.assertIn('r.price->setText(QString::number(q.price', self.strip)
        self.assertIn('r.change->setText(QString(', self.strip)

    def test_real_original_producer_and_datahub_deliver_values(self):
        self.assertIn('python::PythonWorker::instance().submit(', self.market)
        self.assertIn('"batch_all", payload,', self.market)
        self.assertIn('self->publish_quote_to_hub(qd);', self.market)
        self.assertIn('void DataHub::deliver_initial_value(', self.hub)
        self.assertIn('slot(snapshot);', self.hub)

    def test_smoke_uses_qatopic_not_a_realtime_asset(self):
        self.assertIn('FINCEPT_QA_SYNTHETIC_ONLY', self.smoke)
        self.assertIn('services::QuoteDeliveryOrigin::Unknown, QString{}', self.smoke)
        self.assertNotIn('SPY', self.smoke)
        self.assertIn('void spin(int ms)', self.smoke)
        self.assertIn('bool dashboard_quote_datahub_smoke()', self.smoke)

    def test_synthetic_topic_is_push_only_before_any_publish_or_subscribe(self):
        helper = self.smoke.split('bool dashboard_quote_datahub_smoke()', 1)[1]
        helper = helper.split('const QString kDashboardId', 1)[0]
        policy = helper.index('policy.push_only = true;')
        configure = helper.index('hub.set_policy(topic, policy);')
        publish = helper.index('hub.publish(topic, QVariant::fromValue(quote));')
        show = helper.index('widget.show();')
        self.assertLess(policy, configure)
        self.assertLess(configure, publish)
        self.assertLess(publish, show)
        self.assertNotIn('MarketDataService::instance()', helper)
        self.assertNotIn('python::PythonWorker', helper)
        self.assertIn('!st.policy.push_only', self.hub)

    def test_smoke_checks_both_price_and_change_rendered_by_real_widget(self):
        helper = self.smoke.split('bool dashboard_quote_datahub_smoke()', 1)[1]
        helper = helper.split('const QString kDashboardId', 1)[0]
        self.assertIn('screens::widgets::MarketQuoteStripWidget widget(cfg);', helper)
        self.assertIn('findChild<QLabel*>(QStringLiteral("quoteStripPrice"))', helper)
        self.assertIn('findChild<QLabel*>(QStringLiteral("quoteStripChange"))', helper)
        self.assertIn('price->text() == QStringLiteral("123.45")', helper)
        self.assertIn('change->text() == QStringLiteral("+1.25%")', helper)
        self.assertIn('hub.unsubscribe(&widget);', helper)
        self.assertIn('widget.hide();', helper)

    def test_smoke_gate_is_after_pin_refusal_and_screen_walk(self):
        smoke = self.smoke
        guard = smoke.index('auth::InactivityGuard::instance().is_terminal_locked()')
        walk = smoke.index('for (const QString& id : ids)')
        check = smoke.index('if (failures.isEmpty() && !dashboard_quote_datahub_smoke())')
        success = smoke.index('if (failures.isEmpty()) {', check)
        self.assertLess(guard, walk)
        self.assertLess(walk, check)
        self.assertLess(check, success)
        self.assertIn('failures << QStringLiteral("dashboard_datahub_quote_widget");', smoke)

if __name__ == "__main__":
    unittest.main()
