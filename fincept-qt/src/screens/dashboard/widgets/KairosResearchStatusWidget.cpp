#include "screens/dashboard/widgets/KairosResearchStatusWidget.h"

#include "ui/theme/Theme.h"

#include <QDateTime>
#include <QFile>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QStringList>

namespace fincept::screens::widgets {
namespace {
constexpr qint64 kMaxReportBytes = 16384;
constexpr qint64 kMaxAgeSeconds = 86400;
const std::array<const char*, 4> kStages{
    "fincept_tool", "tool_gateway", "kairos_science", "theoretical_portfolio",
};
const std::array<const char*, 4> kTitles{
    "Fincept quantitative tool", "Read-only gateway", "KAIROS scientific gates",
    "Theoretical portfolio",
};

bool is_status(const QString& s) {
    return s == QStringLiteral("MOCK_PASS") || s == QStringLiteral("BLOCKED") ||
           s == QStringLiteral("NOT_VERIFIED");
}

QString status_text(const QString& s) {
    if (s == QStringLiteral("MOCK_PASS"))
        return QStringLiteral("SYNTHETIC TEST");
    if (s == QStringLiteral("BLOCKED"))
        return QStringLiteral("BLOCKED");
    return QStringLiteral("NOT VERIFIED");
}

QString status_color(const QString& s) {
    if (s == QStringLiteral("MOCK_PASS"))
        return ui::colors::WARNING();
    if (s == QStringLiteral("BLOCKED"))
        return ui::colors::NEGATIVE();
    return ui::colors::TEXT_TERTIARY();
}
} // namespace

KairosResearchStatusWidget::KairosResearchStatusWidget(QWidget* parent)
    : BaseWidget(tr("KAIROS RESEARCH"), parent, ui::colors::CYAN()) {
    auto* layout = content_layout();
    layout->setContentsMargins(10, 8, 10, 8);
    layout->setSpacing(6);

    provenance_ = new QLabel(this);
    provenance_->setWordWrap(true);
    provenance_->setTextFormat(Qt::PlainText);
    layout->addWidget(provenance_);

    for (std::size_t i = 0; i < kStages.size(); ++i) {
        auto* row = new QWidget(this);
        auto* horizontal = new QHBoxLayout(row);
        horizontal->setContentsMargins(0, 2, 0, 2);
        horizontal->setSpacing(8);
        stage_names_[i] = new QLabel(row);
        stage_names_[i]->setTextFormat(Qt::PlainText);
        stage_states_[i] = new QLabel(row);
        stage_states_[i]->setTextFormat(Qt::PlainText);
        stage_states_[i]->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
        horizontal->addWidget(stage_names_[i], 1);
        horizontal->addWidget(stage_states_[i]);
        layout->addWidget(row);
    }

    evidence_ = new QLabel(this);
    evidence_->setWordWrap(true);
    evidence_->setTextFormat(Qt::PlainText);
    layout->addWidget(evidence_);
    layout->addStretch();

    footer_ = new QLabel(this);
    footer_->setWordWrap(true);
    footer_->setTextFormat(Qt::PlainText);
    layout->addWidget(footer_);

    connect(this, &BaseWidget::refresh_requested, this,
            [this]() { refresh_data(); });
    refresh_data();
}

// Fail closed: the dashboard consumes a small, locally supplied fixture status.
// It never treats a local JSON file as proof of scientific or security admission.
void KairosResearchStatusWidget::refresh_data() {
    current_states_.fill(QStringLiteral("NOT_VERIFIED"));
    const QString path = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation) +
                         QStringLiteral("/kairos/research_status_v1.json");
    QFile file(path);
    QString label = tr("NO LOCAL REPORT");
    QString evidence = tr("Generate a synthetic fixture report on this machine; no live connection exists.");
    if (file.exists() && file.size() >= 1 && file.size() <= kMaxReportBytes &&
        file.open(QIODevice::ReadOnly)) {
        QJsonParseError error;
        const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &error);
        const QJsonObject obj = document.object();
        const QString generated = obj.value(QStringLiteral("generated_at_utc")).toString();
        const QDateTime date = QDateTime::fromString(generated, Qt::ISODate);
        const QString digest = obj.value(QStringLiteral("source_sha256")).toString();
        static const QRegularExpression sha256(QStringLiteral("^[0-9a-f]{64}$"));
        const qint64 age = date.secsTo(QDateTime::currentDateTimeUtc());
        const bool contract_ok =
            error.error == QJsonParseError::NoError && document.isObject() &&
            obj.value(QStringLiteral("schema")).toString() ==
                QStringLiteral("fincept_kairos_research_status_v1") &&
            obj.value(QStringLiteral("mode")).toString() == QStringLiteral("SYNTHETIC_FIXTURE") &&
            obj.value(QStringLiteral("scientific_status")).toString() ==
                QStringLiteral("NOT_EVALUATED") &&
            obj.value(QStringLiteral("broker_authority")).isBool() &&
            !obj.value(QStringLiteral("broker_authority")).toBool() &&
            obj.value(QStringLiteral("external_api_calls")).isDouble() &&
            obj.value(QStringLiteral("external_api_calls")).toInt(-1) == 0 &&
            date.isValid() && generated.endsWith(QLatin1Char('Z')) &&
            age >= -300 && age <= kMaxAgeSeconds &&
            sha256.match(digest).hasMatch() && obj.value(QStringLiteral("stages")).isObject();
        if (contract_ok) {
            const QJsonObject stages = obj.value(QStringLiteral("stages")).toObject();
            bool valid_stages = stages.size() == int(kStages.size());
            for (std::size_t i = 0; i < kStages.size(); ++i) {
                const QJsonValue value = stages.value(QLatin1String(kStages[i]));
                if (!value.isString() || !is_status(value.toString()))
                    valid_stages = false;
            }
            if (valid_stages &&
                stages.value(QStringLiteral("kairos_science")).toString() !=
                    QStringLiteral("MOCK_PASS") &&
                stages.value(QStringLiteral("theoretical_portfolio")).toString() !=
                    QStringLiteral("MOCK_PASS")) {
                for (std::size_t i = 0; i < kStages.size(); ++i)
                    current_states_[i] = stages.value(QLatin1String(kStages[i])).toString();
                label = tr("LOCAL SYNTHETIC REPORT — UNATTESTED");
                evidence = tr("UTC %1 · source %2… · external API calls 0")
                               .arg(generated, digest.left(12));
            } else {
                label = tr("INVALID LOCAL REPORT");
                evidence = tr("Stage claims exceed the synthetic-only contract.");
            }
        } else {
            label = tr("INVALID OR STALE LOCAL REPORT");
            evidence = tr("No valid current synthetic evidence; all stages remain unverified.");
        }
    } else if (file.exists()) {
        label = tr("UNREADABLE LOCAL REPORT");
        evidence = tr("The local file is empty, oversized, or inaccessible.");
    }
    provenance_->setText(label);
    evidence_->setText(evidence);
    for (std::size_t i = 0; i < kStages.size(); ++i) {
        stage_names_[i]->setText(tr(kTitles[i]));
        stage_states_[i]->setText(status_text(current_states_[i]));
    }
    footer_->setText(tr("RESEARCH ONLY · SCIENCE NOT EVALUATED · NO BROKER AUTHORITY"));
    footer_->setToolTip(tr("Read-only report path: %1").arg(path));
    apply_styles();
    set_loading(false);
}

void KairosResearchStatusWidget::on_theme_changed() {
    apply_styles();
}

void KairosResearchStatusWidget::retranslateUi() {
    BaseWidget::retranslateUi();
    set_title(tr("KAIROS RESEARCH"));
    refresh_data();
}

void KairosResearchStatusWidget::apply_styles() {
    provenance_->setStyleSheet(
        QStringLiteral("color:%1;font-size:11px;font-weight:bold;")
            .arg(ui::colors::WARNING()));
    evidence_->setStyleSheet(
        QStringLiteral("color:%1;font-size:9px;")
            .arg(ui::colors::TEXT_SECONDARY()));
    footer_->setStyleSheet(
        QStringLiteral("color:%1;font-size:9px;font-weight:bold;")
            .arg(ui::colors::TEXT_TERTIARY()));
    for (std::size_t i = 0; i < kStages.size(); ++i) {
        stage_names_[i]->setStyleSheet(
            QStringLiteral("color:%1;font-size:10px;")
                .arg(ui::colors::TEXT_PRIMARY()));
        stage_states_[i]->setStyleSheet(
            QStringLiteral("color:%1;font-size:9px;font-weight:bold;")
                .arg(status_color(current_states_[i])));
    }
}

} // namespace fincept::screens::widgets
