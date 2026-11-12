#pragma once
// Intentionally minimal, disposable router: NOT Fincept's ADS router or a GUI.
#include <QSet>
#include <QStringList>

namespace fincept {
class DockScreenRouter {
public:
    QStringList registered;
    bool materialize_on_navigation = true;
    mutable int inventory_reads = 0;
    int navigation_calls = 0;
    bool last_navigation_exclusive = false;

    QStringList all_screen_ids() const {
        ++inventory_reads;
        return registered;
    }

    void navigate(const QString& id, bool exclusive) {
        ++navigation_calls;
        last_navigation_exclusive = exclusive;
        if (materialize_on_navigation && registered.contains(id))
            materialized_.insert(id);
    }

    const void* screen_widget(const QString& id) const {
        return materialized_.contains(id) ? static_cast<const void*>(this) : nullptr;
    }

private:
    QSet<QString> materialized_;
};
} // namespace fincept
