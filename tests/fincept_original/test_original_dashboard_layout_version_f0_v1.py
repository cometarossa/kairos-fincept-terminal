"""Offline original-Qt-source regression for F0 dashboard layout restore safety.

Does not certify a rendered Linux dashboard: native Qt/AppImage and a real
clean-profile GUI smoke run remain separate acceptance gates.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "fincept-qt/src/screens/dashboard/DashboardScreen.cpp"


class OriginalFinceptDashboardLayoutRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_text()
        cls.source = source
        cls.save = source[source.index("void DashboardScreen::save_layout()") :
                          source.index("void DashboardScreen::restore_layout()")]
        cls.restore = source[source.index("void DashboardScreen::restore_layout()") :
                             source.index("void DashboardScreen::build_default_layout()")]

    def test_writer_has_versioned_header_and_legacy_reader(self):
        self.assertIn("constexpr quint32 kDashLayoutVersion = 1;", self.source)
        self.assertIn("stream << kDashLayoutMagic << kDashLayoutVersion;", self.save)
        self.assertIn("const bool has_config = (lead == kDashLayoutMagic);", self.restore)
        self.assertIn("layout.cols = static_cast<int>(lead);", self.restore)

    def test_unknown_version_rejected_before_layout_items(self):
        r = self.restore
        check = r.index("version != kDashLayoutVersion")
        unpack = r.index("stream >> layout.cols >> layout.row_h >> layout.margin >> count;")
        iteration = r.index("for (int i = 0; i < count; ++i)")
        self.assertLess(check, unpack)
        self.assertLess(unpack, iteration)
        branch = r[r.rindex("if (", 0, check) : unpack]
        self.assertIn("self->build_default_layout();", branch)
        self.assertIn("return;", branch)

    def test_future_version_does_not_overwrite_saved_layout(self):
        r = self.restore
        part = r[r.index("version != kDashLayoutVersion") : r.index("stream >> layout.cols >> layout.row_h")]
        self.assertIn("self->setProperty(kDashLayoutLoadFailedProp, true);", part)
        self.assertLess(part.index("setProperty(kDashLayoutLoadFailedProp, true)"),
                        part.index("self->build_default_layout();"))
        self.assertIn("if (property(kDashLayoutLoadFailedProp).toBool())", self.save)
        self.assertLess(self.save.index("if (property(kDashLayoutLoadFailedProp).toBool())"),
                        self.save.index("SettingsRepository::instance().set"))

    def test_truncated_item_stream_cannot_be_applied_partially(self):
        r = self.restore
        loop = r.index("for (int i = 0; i < count; ++i)")
        partial = r.index("if (stream.status() != QDataStream::Ok)", loop)
        load = r.index("self->canvas_->load_layout(layout", loop)
        self.assertLess(loop, partial)
        self.assertLess(partial, load)
        reject = r[partial:load]
        self.assertIn("self->setProperty(kDashLayoutLoadFailedProp, true);", reject)
        self.assertIn("self->build_default_layout();", reject)
        self.assertIn("return;", reject)

    def test_user_sees_explicit_warning_on_incompatible_layout(self):
        r = self.restore
        self.assertIn('tr("Saved dashboard layout is incompatible")', r)
        self.assertIn('tr("Saved dashboard layout is incomplete")', r)
        self.assertIn("NotifLevel::Warning", r)
        self.assertIn("self->notif_toast_->show_notification(rec);", r)


if __name__ == "__main__":
    unittest.main()
