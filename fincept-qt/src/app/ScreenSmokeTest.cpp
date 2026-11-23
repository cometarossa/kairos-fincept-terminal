#include "app/ScreenSmokeTest.h"

#include "app/DockScreenRouter.h"
#include "auth/InactivityGuard.h"
#include "core/logging/Logger.h"
#include "screens/dashboard/canvas/DashboardCanvas.h"
#include "datahub/DataHub.h"
#include "datahub/DataHubMetaTypes.h"
#include "datahub/TopicPolicy.h"
#include "screens/dashboard/widgets/MarketQuoteStripWidget.h"
#include "services/markets/MarketDataService.h"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QString>
#include <QStringList>

#include <cstdio>

namespace fincept {

namespace {
// Pump the event loop for `ms` so showEvent, deferred singleShot(100) init, and
// lazy web-view / chart construction actually run before we judge the screen.
// We do NOT wait for data fetches to finish — only for the widget tree to build.
void spin(int ms) {
    QElapsedTimer t;
    t.start();
    while (t.elapsed() < ms)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
}

// Upper bound on how long one screen may take to materialise before we call it
// a failure. Generous on purpose: this is a "did it build at all" check, not a
// performance budget, and it gates releases on shared CI runners.
constexpr int kConstructDeadlineMs = 8000;

// Settle time after the widget appears, so showEvent-driven child construction
// runs before we move on. Short because the deadline loop already did the wait.
constexpr int kSettleMs = 120;

// Wait until `id`'s widget exists, or the deadline expires. Returns the elapsed
// milliseconds so a slow-but-passing screen can still be reported.
//
// A fixed spin() budget was the previous approach and it made this test lie: on
// a machine under memory pressure, 8 unrelated screens were reported as "did not
// construct" purely because deferred materialisation had not been serviced yet,
// and the same binary passed on the next run. Polling costs nothing when things
// are healthy — it returns on the first iteration — and stops the test failing
// a release for being busy rather than broken.
int wait_for_construction(DockScreenRouter* router, const QString& id) {
    QElapsedTimer t;
    t.start();
    while (!router->screen_widget(id) && t.elapsed() < kConstructDeadlineMs)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    return static_cast<int>(t.elapsed());
}

// Tests the original DataHub->dashboard widget delivery path with an unmistakably
// synthetic QA symbol. The topic is push-only BEFORE publish/subscribe: the test
// must never trigger Yahoo, IG, broker, or any other provider network request.
// Only --smoke-test invokes this, after the normal auth/PIN refusal gate.
bool dashboard_quote_datahub_smoke() {
    constexpr const char* kQaSymbol = "FINCEPT_QA_SYNTHETIC_ONLY";
    const QString symbol = QString::fromLatin1(kQaSymbol);
    const QString topic = QStringLiteral("market:quote:") + symbol;
    auto& hub = datahub::DataHub::instance();
    datahub::TopicPolicy policy;
    policy.push_only = true;
    policy.ttl_ms = 60'000;
    hub.set_policy(topic, policy);

    // A synthetic source is NOT financial evidence. It only verifies that the
    // production widget consumes the production DataHub topic and paints its
    // price and change labels, rather than sitting on the loading overlay.
    const services::QuoteData quote{symbol, symbol, 123.45, 1.50, 1.25,
                                    124.0, 122.0, 0.0,
                                    services::QuoteDeliveryOrigin::Unknown, QString{}};
    hub.publish(topic, QVariant::fromValue(quote));

    QJsonArray symbols;
    symbols.append(symbol);
    QJsonObject cfg;
    cfg.insert(QStringLiteral("symbols"), symbols);
    screens::widgets::MarketQuoteStripWidget widget(cfg);
    widget.show();

    QLabel* price = widget.findChild<QLabel*>(QStringLiteral("quoteStripPrice"));
    QLabel* change = widget.findChild<QLabel*>(QStringLiteral("quoteStripChange"));
    const auto rendered = [price, change]() {
        return price && change &&
               price->text() == QStringLiteral("123.45") &&
               change->text() == QStringLiteral("+1.25%");
    };
    // DataHub delivers cached values through a queued Qt callback. Poll until
    // painted rather than relying on a fixed delay on loaded CI machines.
    QElapsedTimer t;
    t.start();
    while (!rendered() && t.elapsed() < 2500)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    const bool valid = rendered();
    if (!valid) {
        std::fprintf(stderr,
                     "[Smoke] FAIL: original Quote Strip did not paint the synthetic DataHub price/change\n");
        std::fflush(stderr);
        LOG_ERROR("Smoke", "original dashboard Quote Strip did not consume synthetic DataHub value");
    } else {
        std::fprintf(stderr, "[Smoke] OK: original dashboard DataHub quote widget painted synthetic value\n");
        std::fflush(stderr);
    }
    // An unrelated quote error must never affect this widget. The real
    // DataHub error registry, not a mocked callback, delivers these events.
    hub.publish_error(QStringLiteral("market:quote:FINCEPT_QA_UNRELATED"), QStringLiteral("synthetic_other"));
    QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    const bool isolated = change && change->text() == QStringLiteral("+1.25%");

    hub.publish_error(topic, QStringLiteral("synthetic_qa_provider_unavailable"));
    QElapsedTimer err_t;
    err_t.start();
    while (change && change->text() != QStringLiteral("Last quote") && err_t.elapsed() < 2500)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    const bool old_quote_marked = price && change &&
                                  price->text() == QStringLiteral("123.45") &&
                                  change->text() == QStringLiteral("Last quote") &&
                                  change->toolTip().contains(QStringLiteral("synthetic_qa_provider_unavailable"));

    const services::QuoteData recovered{symbol, symbol, 125.0, 2.0, 1.60,
                                        126.0, 122.0, 0.0,
                                        services::QuoteDeliveryOrigin::Unknown, QString{}};
    hub.publish(topic, QVariant::fromValue(recovered));
    QElapsedTimer recovery_t;
    recovery_t.start();
    while (change && change->text() != QStringLiteral("+1.60%") && recovery_t.elapsed() < 2500)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    const bool recovered_cleanly = price && change &&
                                   price->text() == QStringLiteral("125.00") &&
                                   change->text() == QStringLiteral("+1.60%") &&
                                   change->toolTip().isEmpty();

    // The displayed last-good value must survive a hide/show after the
    // hub's cache TTL expires. A fresh subscription gets NO cached replay.
    widget.hide();
    datahub::TopicPolicy stale_policy = policy;
    stale_policy.ttl_ms = 1;
    hub.set_policy(topic, stale_policy);
    spin(20);
    widget.show();
    hub.publish_error(topic, QStringLiteral("synthetic_after_hide_expired_cache"));
    QElapsedTimer stale_t;
    stale_t.start();
    while (change && change->text() != QStringLiteral("Last quote") && stale_t.elapsed() < 2500)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    const bool preserved_after_hide = price && change &&
                                      price->text() == QStringLiteral("125.00") &&
                                      change->text() == QStringLiteral("Last quote");
    widget.hide();
    hub.unsubscribe(&widget);

    // A second genuine widget with no price at all must show a provider
    // error instead of indefinitely showing loading. A later valid quote
    // must clear that error and restore the original price rendering path.
    const QString missing_symbol = QStringLiteral("FINCEPT_QA_MISSING_ONLY");
    const QString missing_topic = QStringLiteral("market:quote:") + missing_symbol;
    hub.set_policy(missing_topic, policy); // push-only: no broker or public provider
    QJsonArray missing_symbols;
    missing_symbols.append(missing_symbol);
    QJsonObject missing_cfg;
    missing_cfg.insert(QStringLiteral("symbols"), missing_symbols);
    screens::widgets::MarketQuoteStripWidget missing(missing_cfg);
    missing.show();
    hub.publish_error(missing_topic, QStringLiteral("synthetic_no_quote"));
    QElapsedTimer missing_t;
    missing_t.start();
    while (!missing.is_showing_error() && missing_t.elapsed() < 2500)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    const bool empty_error = missing.is_showing_error();
    const services::QuoteData first_quote{missing_symbol, missing_symbol, 99.0, 1.0, 1.0,
                                          100.0, 98.0, 0.0,
                                          services::QuoteDeliveryOrigin::Unknown, QString{}};
    hub.publish(missing_topic, QVariant::fromValue(first_quote));
    QLabel* missing_price = missing.findChild<QLabel*>(QStringLiteral("quoteStripPrice"));
    QElapsedTimer clear_t;
    clear_t.start();
    while ((missing.is_showing_error() ||
            !missing_price || missing_price->text() != QStringLiteral("99.00")) &&
           clear_t.elapsed() < 2500)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
    const bool error_cleared = !missing.is_showing_error() &&
                               missing_price && missing_price->text() == QStringLiteral("99.00");
    missing.hide();
    hub.unsubscribe(&missing);

    const bool all_ok = valid && isolated && old_quote_marked &&
                        recovered_cleanly && preserved_after_hide &&
                        empty_error && error_cleared;
    if (!all_ok) {
        std::fprintf(stderr,
                     "[Smoke] FAIL: DataHub quote error isolation / last-known / recovery: %d %d %d %d %d %d\\n",
                     int(valid), int(isolated), int(old_quote_marked),
                     int(recovered_cleanly), int(empty_error), int(error_cleared));
        std::fflush(stderr);
    }
    return all_ok;
}

const QString kDashboardId = QStringLiteral("dashboard");
} // namespace

int run_screen_smoke_test(DockScreenRouter* router) {
    if (!router) {
        std::fprintf(stderr, "[Smoke] FAIL: no router\n");
        std::fflush(stderr);
        return 2;
    }

    // A PIN-locked terminal makes this test meaningless, and silently so.
    // DockScreenRouter::navigate() hard-refuses while the terminal is locked
    // (deliberately — nothing may mutate panel state behind the PIN gate), so
    // every navigation no-ops and EVERY lazily-registered screen is reported as
    // "did not construct". That produced 46 phantom failures on a developer
    // machine with a PIN set, while CI — a fresh runner with no PIN — passed.
    // A test that only works in one environment and lies in the other is worse
    // than no test, so detect the condition and say exactly what is wrong.
    //
    // Deliberately NOT auto-unlocking: a test harness must not learn to bypass
    // an authentication gate.
    if (auth::InactivityGuard::instance().is_terminal_locked()) {
        std::fprintf(stderr,
                     "[Smoke] FAIL: terminal is PIN-locked — navigate() is suppressed, so no screen can be\n"
                     "        constructed and every result would be a false failure.\n"
                     "        Clear the PIN (Settings > Security > Change PIN) and re-run.\n"
                     "        NOTE: --profile does NOT help. The PIN lives in machine-wide SecureStorage,\n"
                     "        not in the profile directory, so a fresh profile still hits the lock once it\n"
                     "        has an authenticated session. CI passes only because its runners have no PIN.\n");
        std::fflush(stderr);
        LOG_ERROR("Smoke", "Aborted: terminal is PIN-locked; navigate() is suppressed behind the lock gate");
        return 3;
    }

    const QStringList ids = router->all_screen_ids();
    if (ids.isEmpty()) {
        std::fprintf(stderr, "[Smoke] FAIL: all_screen_ids() is empty — no screens registered, nothing to test\n");
        std::fflush(stderr);
        LOG_ERROR("Smoke", "Aborted: no screens registered");
        return 4;
    }
    if (!ids.contains(kDashboardId)) {
        std::fprintf(stderr, "[Smoke] FAIL: '%s' is not registered with the router\n", qUtf8Printable(kDashboardId));
        std::fflush(stderr);
        LOG_ERROR("Smoke", "Aborted: dashboard screen is not registered");
        return 5;
    }
    std::fprintf(stderr, "[Smoke] walking %d screens\n", static_cast<int>(ids.size()));
    std::fflush(stderr);
    LOG_INFO("Smoke", QString("Screen smoke test: %1 screens").arg(ids.size()));

    QStringList failures;
    for (const QString& id : ids) {
        // Breadcrumb BEFORE construction so a hard process abort (e.g. a missing
        // QtWebEngineProcess.exe) names the culprit as the last line in the log.
        std::fprintf(stderr, "[Smoke] >>> constructing %s\n", qUtf8Printable(id));
        std::fflush(stderr);
        LOG_INFO("Smoke", QString("constructing %1").arg(id));

        // exclusive=true closes the previously-opened screen before opening this
        // one, so panels don't accumulate (non-exclusive navigation re-layouts an
        // ever-growing set → O(n^2) and a multi-minute walk). We only need each
        // screen open long enough to construct + fire showEvent.
        router->navigate(id, /*exclusive=*/true);
        const int waited_ms = wait_for_construction(router, id);

        if (!router->screen_widget(id)) {
            failures << id;
            std::fprintf(stderr, "[Smoke] !!! %s did not construct within %d ms\n", qUtf8Printable(id),
                         kConstructDeadlineMs);
            std::fflush(stderr);
            continue;
        }

        // Let showEvent-driven child construction run before moving on.
        spin(kSettleMs);

        // F0 independent-terminal gate: navigating the REAL dashboard must
        // construct its original canvas, not merely an empty QWidget shell.
        // Check during the normal screen walk; do not navigate twice, which
        // could trigger duplicate subscriptions or provider reads.
        if (id == kDashboardId && !router->screen_widget(id)->findChild<screens::DashboardCanvas*>()) {
            failures << id;
            std::fprintf(stderr, "[Smoke] !!! dashboard constructed without DashboardCanvas\n");
            std::fflush(stderr);
            LOG_ERROR("Smoke", "dashboard constructed without its original DashboardCanvas");
        }

        // Surface slow screens without failing them — a screen that needs seconds
        // to build is a real finding, just not this test's verdict to make.
        if (waited_ms > 1000) {
            std::fprintf(stderr, "[Smoke] ... %s took %d ms to construct\n", qUtf8Printable(id), waited_ms);
            std::fflush(stderr);
            LOG_WARN("Smoke", QString("%1 took %2 ms to construct").arg(id).arg(waited_ms));
        }
    }

    if (failures.isEmpty() && !dashboard_quote_datahub_smoke()) {
        failures << QStringLiteral("dashboard_datahub_quote_widget");
    }

    if (failures.isEmpty()) {
        std::fprintf(stderr, "[Smoke] OK: all %d screens constructed\n", static_cast<int>(ids.size()));
        std::fflush(stderr);
        LOG_INFO("Smoke", "All screens constructed OK");
        return 0;
    }

    std::fprintf(stderr, "[Smoke] FAIL: %d screen(s) did not construct: %s\n", static_cast<int>(failures.size()),
                 qUtf8Printable(failures.join(", ")));
    std::fflush(stderr);
    LOG_ERROR("Smoke", QString("%1 screen(s) failed: %2").arg(failures.size()).arg(failures.join(", ")));
    return 1;
}

} // namespace fincept
