#pragma once
// Offline, read-only KAIROS research checkpoint tile.
// Reads a local synthetic fixture report only; never calls KAIROS/broker/network.
#include "screens/dashboard/widgets/BaseWidget.h"

#include <QLabel>
#include <array>

namespace fincept::screens::widgets {

class KairosResearchStatusWidget final : public BaseWidget {
  public:
    explicit KairosResearchStatusWidget(QWidget* parent = nullptr);

  protected:
    void on_theme_changed() override;
    void retranslateUi() override;

  private:
    void refresh_data();
    void apply_styles();

    QLabel* provenance_ = nullptr;
    QLabel* evidence_ = nullptr;
    QLabel* footer_ = nullptr;
    std::array<QLabel*, 4> stage_names_{};
    std::array<QLabel*, 4> stage_states_{};
    std::array<QString, 4> current_states_{};
};

} // namespace fincept::screens::widgets
