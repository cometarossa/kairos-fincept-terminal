// Compile the unmodified Fincept StatusBadge, SearchBar and ThemeManager.
// Does not load the installed app, credentials, screen factories or broker.
#include "ui/widgets/StatusBadge.h"
#include "ui/widgets/SearchBar.h"
#include <QApplication>
#include <QCoreApplication>
#include <QEvent>
#include <QLineEdit>
#include <QSignalSpy>
#include <QTest>
#include <cstdio>

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    int failures = 0;
    auto check = [&failures](bool good, const char* title) {
        std::fprintf(good ? stdout : stderr, "%s %s\n", good ? "PASS" : "FAIL", title);
        if (!good) ++failures;
    };

    fincept::ui::StatusBadge badge;
    check(badge.text() == QStringLiteral("READY"), "badge defaults READY");
    badge.set_status(fincept::ui::StatusBadge::Status::Connected);
    check(badge.text() == QStringLiteral("CONNECTED"), "connected status text");
    check(badge.styleSheet().contains(QStringLiteral("#16a34a")), "connected status color");
    badge.set_status(fincept::ui::StatusBadge::Status::Disconnected);
    check(badge.text() == QStringLiteral("OFFLINE"), "offline status text");
    check(badge.styleSheet().contains(QStringLiteral("#dc2626")), "offline status color");
    badge.set_custom(QStringLiteral("CUSTOM 123"), QStringLiteral("#123abc"));
    QEvent lang(QEvent::LanguageChange);
    QCoreApplication::sendEvent(&badge, &lang);
    check(badge.text() == QStringLiteral("CUSTOM 123"), "custom badge survives language change");
    check(badge.styleSheet().contains(QStringLiteral("#123abc")), "custom badge color retained");
    badge.set_status(fincept::ui::StatusBadge::Status::Loading);
    QCoreApplication::sendEvent(&badge, &lang);
    check(badge.text() == QStringLiteral("LOADING..."), "preset badge translation refresh");

    fincept::ui::SearchBar search;
    auto* input = search.findChild<QLineEdit*>();
    check(input != nullptr, "search input widget exists");
    if (!input) return 2;
    check(search.height() == 32, "search bar fixed height");
    QSignalSpy changes(&search, &fincept::ui::SearchBar::text_changed);
    QSignalSpy submitted(&search, &fincept::ui::SearchBar::search_submitted);
    input->setText(QStringLiteral("NVDA"));
    check(search.text() == QStringLiteral("NVDA"), "search text forwarded");
    check(changes.size() == 1 && changes.at(0).at(0).toString() == QStringLiteral("NVDA"), "search text_changed emits value");
    search.show();
    input->setFocus();
    QTest::keyClick(input, Qt::Key_Return);
    check(submitted.size() == 1 && submitted.at(0).at(0).toString() == QStringLiteral("NVDA"), "Return submits query");
    QCoreApplication::sendEvent(&search, &lang);
    check(input->placeholderText() == QStringLiteral("Enter command or search..."), "search placeholder on language change");
    search.clear();
    check(search.text().isEmpty(), "search clear resets input");
    check(changes.size() == 2 && changes.at(1).at(0).toString().isEmpty(), "clear emits changed");

    std::fprintf(stdout, "original QWidget smoke: %d failures\n", failures);
    return failures ? 1 : 0;
}
