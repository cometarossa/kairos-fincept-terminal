// Native QtCore regression of the EXACT production ScreenSmokeTest.cpp.
// All dependencies except QtCore and the original function are test stubs.
// This does NOT test actual widgets, showEvent, permissions or GUI behavior.
#include "app/ScreenSmokeTest.h"
#include "app/DockScreenRouter.h"
#include "auth/InactivityGuard.h"

#include <QCoreApplication>
#include <QString>
#include <cstdio>

namespace {
int failed = 0;
void verify(bool condition, const char* label) {
    if (condition) {
        std::fprintf(stdout, "PASS: %s\n", label);
    } else {
        std::fprintf(stderr, "FAIL: %s\n", label);
        ++failed;
    }
}
} // namespace

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    auto& guard = fincept::auth::InactivityGuard::instance();
    guard.set_test_locked(false);

    // Null pointer fails without dereferencing and before attempting navigation.
    verify(fincept::run_screen_smoke_test(nullptr) == 2, "null router returns 2");

    // Locked test must not read the registry or construct any route.
    fincept::DockScreenRouter locked;
    locked.registered << QStringLiteral("sample");
    guard.set_test_locked(true);
    verify(fincept::run_screen_smoke_test(&locked) == 3, "locked terminal returns 3");
    verify(locked.inventory_reads == 0 && locked.navigation_calls == 0,
           "lock gate precedes registry access");
    guard.set_test_locked(false);

    // The new fail-closed guard is exercised in the REAL C++ implementation.
    fincept::DockScreenRouter empty;
    verify(fincept::run_screen_smoke_test(&empty) == 4,
           "zero registered screens returns 4, not success");
    verify(empty.inventory_reads == 1 && empty.navigation_calls == 0,
           "empty registry never navigates");

    // Positive control ensures a nonempty registry can still return success.
    fincept::DockScreenRouter populated;
    populated.registered << QStringLiteral("sample");
    verify(fincept::run_screen_smoke_test(&populated) == 0,
           "one constructed mock screen returns 0");
    verify(populated.inventory_reads == 1 && populated.navigation_calls == 1 &&
           populated.last_navigation_exclusive,
           "positive navigation is exclusive and attempted once");

    std::fprintf(stdout, "%d native QtCore assertion(s) failed\n", failed);
    return failed ? 1 : 0;
}
