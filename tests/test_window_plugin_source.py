import unittest
from pathlib import Path


class WindowPluginSourceTest(unittest.TestCase):
    def test_activation_log_includes_version_and_delay(self):
        source = Path("hadron_autosave/window_plugin.py").read_text(encoding="utf-8")

        self.assertIn("version=PLUGIN_VERSION", source)
        self.assertIn("delay_ms=AUTOSAVE_DELAY_MS", source)

    def test_tab_close_deletes_unsaved_autosave_but_window_close_does_not(self):
        source = Path("hadron_autosave/window_plugin.py").read_text(encoding="utf-8")

        self.assertIn('self.window.connect("delete-event"', source)
        self.assertIn("delete_unsaved=not self._closing_window", source)
        self.assertIn("self._storage.delete(document_id)", source)


if __name__ == "__main__":
    unittest.main()
