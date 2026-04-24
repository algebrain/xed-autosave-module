import unittest

from tests import test_window_plugin as helpers


class ExistingBackupStartupTest(unittest.TestCase):
    def setUp(self):
        self.module = helpers.WindowPluginTest()._load_module_with_fake_gi()

    def test_activate_opens_files_that_still_have_backups(self):
        api = helpers.FakeApi([])
        opened = []
        api.open_existing_file = lambda file_path: opened.append(file_path)
        storage = helpers.FakeStorage()
        storage.active_existing_file_backups = lambda: [
            {"file_path": "/tmp/sample2.txt"},
            {"file_path": ""},
            {},
        ]

        self.module.XedApi = lambda window: api
        self.module.AutosaveStorage = lambda: storage
        self.module.DocumentIds = helpers.FakeDocumentIds
        self.module.AutosaveScheduler = lambda *args: helpers.FakeScheduler(*args)

        plugin = self.module.HadronAutosavePlugin()
        plugin.window = helpers.FakeWindow()
        plugin.do_activate()

        self.assertEqual(opened, ["/tmp/sample2.txt"])

    def test_open_existing_file_backups_watches_opened_document(self):
        document = helpers.FakeDocument("sample2")
        api = helpers.FakeApi([])
        api.local_paths[document] = "/tmp/sample2.txt"
        api.open_existing_file = lambda file_path: document
        storage = helpers.FakeStorage()
        storage.active_existing_file_backups = lambda: [{"file_path": "/tmp/sample2.txt"}]
        plugin = self.module.HadronAutosavePlugin()
        plugin.window = helpers.FakeWindow()
        plugin._api = api
        plugin._storage = storage
        plugin._document_ids = helpers.FakeDocumentIds()
        plugin._handlers = {}
        plugin._warning_bars = {}
        plugin._scheduler = helpers.FakeScheduler(None, 500, plugin._autosave_document)

        plugin._open_existing_file_backups()

        self.assertIn(document, plugin._handlers)


if __name__ == "__main__":
    unittest.main()
