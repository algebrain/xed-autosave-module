import configparser
import unittest
from pathlib import Path


class PluginMetadataTest(unittest.TestCase):
    def test_plugin_file_uses_hadron_names(self):
        metadata_path = Path("hadron-autosave.plugin")

        self.assertTrue(metadata_path.exists())

        parser = configparser.ConfigParser()
        parser.read(metadata_path, encoding="utf-8")

        plugin = parser["Plugin"]
        self.assertEqual(plugin["Module"], "hadron_autosave")
        self.assertEqual(plugin["Name"], "Hadron Autosave")
        self.assertEqual(plugin["Name[ru]"], "Адронное автосохранение")


if __name__ == "__main__":
    unittest.main()
