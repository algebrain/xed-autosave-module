import importlib
import sys
import types
import unittest


class FakeGObjectObject:
    pass


class FakeWindowActivatable:
    pass


class FakeDocument:
    def __init__(self, name="doc"):
        self.name = name
        self.handlers = {}
        self.disconnected = []

    def connect(self, signal_name, callback):
        handler_id = f"{self.name}-{signal_name}"
        self.handlers[handler_id] = callback
        return handler_id

    def disconnect(self, handler_id):
        self.disconnected.append(handler_id)


class FakeWindow:
    def __init__(self):
        self.handlers = {}
        self.disconnected = []

    def connect(self, signal_name, callback):
        handler_id = f"window-{signal_name}"
        self.handlers[handler_id] = callback
        return handler_id

    def disconnect(self, handler_id):
        self.disconnected.append(handler_id)


class FakeTab:
    def __init__(self, document):
        self.document = document


class FakeApi:
    def __init__(self, documents=None):
        self.documents = documents or []
        self.restored = []
        self.locations = {}
        self.modified = {}
        self.text = {}
        self.title = {}
        self.saved_existing = []
        self.set_modified_calls = []
        self.local_paths = {}
        self.warning_bars = []
        self.updated_text = []

    def get_documents(self):
        return self.documents

    def restore_unsaved(self, text, document_id):
        document = FakeDocument(f"restored-{document_id}")
        self.restored.append((text, document_id, document))
        return document

    def get_document_from_tab(self, tab):
        return tab.document

    def has_location(self, document):
        return self.locations.get(document, False)

    def is_modified(self, document):
        return self.modified.get(document, False)

    def save_existing(self, document):
        self.saved_existing.append(document)

    def get_text(self, document):
        return self.text.get(document, "")

    def get_title(self, document):
        return self.title.get(document, "Untitled Document")

    def set_modified(self, document, modified):
        self.set_modified_calls.append((document, modified))

    def get_local_path(self, document):
        return self.local_paths.get(document)

    def show_backup_warning_bar(self, document, backup, on_restore, on_accept):
        bar = FakeWarningBar(document, backup, on_restore, on_accept)
        self.warning_bars.append(bar)
        return bar

    def update_document_text(self, document, text, modified=False):
        self.updated_text.append((document, text, modified))


class FakeStorage:
    def __init__(self, entries=None):
        self.entries = entries or []
        self.removed = []
        self.deleted = []
        self.saved_unsaved = []
        self.backups = {}
        self.ensured_backups = []
        self.restored = []
        self.deleted_backups = []

    def restore_entries(self):
        return self.entries

    def active_existing_file_backups(self):
        return list(self.backups.values())

    def remove(self, document_id):
        self.removed.append(document_id)

    def delete(self, document_id):
        self.deleted.append(document_id)

    def save_unsaved(self, document_id, title, text):
        self.saved_unsaved.append((document_id, title, text))
        return "autosave.txt"

    def ensure_existing_file_backup(self, document_id, file_path):
        self.ensured_backups.append((document_id, file_path))
        backup = self.backups.setdefault(
            file_path,
            {
                "file_path": file_path,
                "path": f"backup-{file_path}",
                "modified_at_display": "2026-04-24 14:10:12",
            },
        )
        return backup

    def backup_for_existing(self, file_path):
        return self.backups.get(file_path)

    def restore_existing_file_backup(self, file_path):
        self.restored.append(file_path)
        self.backups.pop(file_path, None)
        return "restored text"

    def read_existing_file_backup(self, file_path):
        self.restored.append(file_path)
        return "restored text"

    def delete_existing_file_backup(self, file_path):
        self.deleted_backups.append(file_path)
        self.backups.pop(file_path, None)
        return True


class FakeWarningBar:
    def __init__(self, document, backup, on_restore, on_accept):
        self.document = document
        self.backup = backup
        self.on_restore = on_restore
        self.on_accept = on_accept
        self.closed = False

    def close(self):
        self.closed = True


class FakeScheduler:
    def __init__(self, clock, delay_ms, save_callback):
        self.clock = clock
        self.delay_ms = delay_ms
        self.save_callback = save_callback
        self.changed_documents = []
        self.forgotten = []
        self.cancelled = False

    def changed(self, document):
        self.changed_documents.append(document)

    def forget(self, document):
        self.forgotten.append(document)

    def cancel_all(self):
        self.cancelled = True


class FakeDocumentIds:
    def __init__(self):
        self.ids = {}
        self.forgotten = []

    def get(self, document):
        return self.ids.setdefault(document, f"id-{getattr(document, 'name', 'doc')}")

    def set(self, document, document_id):
        self.ids[document] = document_id

    def forget(self, document):
        self.forgotten.append(document)
        self.ids.pop(document, None)


class WindowPluginTest(unittest.TestCase):
    def setUp(self):
        self.module = self._load_module_with_fake_gi()

    def _load_module_with_fake_gi(self):
        gi = types.ModuleType("gi")
        gi.require_version = lambda namespace, version: None
        repository = types.ModuleType("gi.repository")
        repository.GLib = types.SimpleNamespace(
            timeout_add=lambda delay, callback, *args: ("timer", delay, callback, args),
            source_remove=lambda timer_id: None,
        )
        repository.GObject = types.SimpleNamespace(
            Object=FakeGObjectObject,
            Property=lambda **kwargs: None,
        )
        repository.Xed = types.SimpleNamespace(
            Window=object,
            WindowActivatable=FakeWindowActivatable,
        )

        old_modules = {
            name: sys.modules.get(name)
            for name in ["gi", "gi.repository", "hadron_autosave.window_plugin"]
        }
        sys.modules["gi"] = gi
        sys.modules["gi.repository"] = repository
        sys.modules.pop("hadron_autosave.window_plugin", None)

        try:
            return importlib.import_module("hadron_autosave.window_plugin")
        finally:
            for name, module in old_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def _plugin(self, api=None, storage=None):
        plugin = self.module.HadronAutosavePlugin()
        plugin.window = FakeWindow()
        plugin._api = api or FakeApi()
        plugin._storage = storage or FakeStorage()
        plugin._document_ids = FakeDocumentIds()
        plugin._handlers = {}
        plugin._window_handlers = []
        plugin._restored_ids = set()
        plugin._closing_window = False
        plugin._warning_bars = {}
        plugin._scheduler = FakeScheduler(None, 500, plugin._autosave_document)
        return plugin

    def test_glib_clock_delegates_to_glib(self):
        clock = self.module.GLibClock()

        timer_id = clock.call_later(500, lambda: None)
        clock.cancel(timer_id)

        self.assertEqual(timer_id[0], "timer")

    def test_activate_restores_documents_watches_existing_and_connects_window(self):
        existing = FakeDocument("existing")
        api = FakeApi([existing])
        storage = FakeStorage([
            {"id": "", "text": "ignored"},
            {"id": "doc-1", "text": "hello"},
            {"id": "doc-1", "text": "duplicate"},
        ])
        document_ids = FakeDocumentIds()
        scheduler_ref = []

        self.module.XedApi = lambda window: api
        self.module.AutosaveStorage = lambda: storage
        self.module.DocumentIds = lambda: document_ids
        self.module.AutosaveScheduler = lambda *args: scheduler_ref.append(FakeScheduler(*args)) or scheduler_ref[0]

        plugin = self.module.HadronAutosavePlugin()
        plugin.window = FakeWindow()

        plugin.do_activate()

        self.assertEqual(len(api.restored), 1)
        self.assertIn(existing, plugin._handlers)
        self.assertEqual(
            set(plugin.window.handlers),
            {"window-tab-added", "window-tab-removed", "window-delete-event"},
        )
        self.assertIs(plugin._scheduler, scheduler_ref[0])

    def test_activate_shows_warning_for_existing_backup(self):
        existing = FakeDocument("existing")
        api = FakeApi([existing])
        api.local_paths[existing] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.backups["/tmp/saved.txt"] = {"modified_at_display": "2026-04-24 14:10:12"}

        self.module.XedApi = lambda window: api
        self.module.AutosaveStorage = lambda: storage
        self.module.DocumentIds = FakeDocumentIds
        self.module.AutosaveScheduler = lambda *args: FakeScheduler(*args)

        plugin = self.module.HadronAutosavePlugin()
        plugin.window = FakeWindow()
        plugin.do_activate()

        self.assertEqual(len(api.warning_bars), 1)

    def test_deactivate_disconnects_documents_and_window_handlers(self):
        document = FakeDocument("doc")
        plugin = self._plugin()
        plugin._watch_document(document)
        plugin._window_handlers = ["window-tab-added"]
        plugin._warning_bars[document] = FakeWarningBar(document, {}, lambda: None, lambda: None)

        plugin.do_deactivate()

        self.assertTrue(plugin._scheduler.cancelled)
        self.assertEqual(document.disconnected, ["doc-changed"])
        self.assertEqual(plugin.window.disconnected, ["window-tab-added"])
        self.assertEqual(plugin._handlers, {})
        self.assertEqual(plugin._window_handlers, [])
        self.assertEqual(plugin._warning_bars, {})

    def test_update_state_is_noop(self):
        self.assertIsNone(self._plugin().do_update_state())

    def test_watch_document_ignores_already_watched_document(self):
        document = FakeDocument("doc")
        plugin = self._plugin()

        plugin._watch_document(document)
        plugin._watch_document(document)

        self.assertEqual(len(document.handlers), 1)

    def test_unwatch_deletes_unsaved_document_when_tab_is_closed(self):
        document = FakeDocument("doc")
        api = FakeApi()
        storage = FakeStorage()
        plugin = self._plugin(api=api, storage=storage)
        plugin._watch_document(document)

        plugin._unwatch_document(document, delete_unsaved=True)

        self.assertEqual(storage.deleted, ["id-doc"])
        self.assertEqual(plugin._scheduler.forgotten, [document])
        self.assertEqual(plugin._document_ids.forgotten, [document])

    def test_unwatch_keeps_existing_document_autosave(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.locations[document] = True
        storage = FakeStorage()
        plugin = self._plugin(api=api, storage=storage)

        plugin._unwatch_document(document, delete_unsaved=True)

        self.assertEqual(storage.deleted, [])

    def test_tab_added_and_removed_route_to_document(self):
        document = FakeDocument("doc")
        plugin = self._plugin()

        plugin._on_tab_added(plugin.window, FakeTab(document))
        plugin._on_tab_removed(plugin.window, FakeTab(document))

        self.assertEqual(plugin._document_ids.forgotten, [document])

    def test_tab_added_shows_warning_for_existing_backup(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.backups["/tmp/saved.txt"] = {"modified_at_display": "2026-04-24 14:10:12"}
        plugin = self._plugin(api=api, storage=storage)

        plugin._on_tab_added(plugin.window, FakeTab(document))

        self.assertEqual(len(api.warning_bars), 1)

    def test_window_delete_marks_closing_and_keeps_default_handler(self):
        plugin = self._plugin()

        result = plugin._on_window_delete_event(plugin.window, object())

        self.assertFalse(result)
        self.assertTrue(plugin._closing_window)

    def test_document_changed_schedules_autosave(self):
        document = FakeDocument("doc")
        plugin = self._plugin()

        plugin._on_document_changed(document)

        self.assertEqual(plugin._scheduler.changed_documents, [document])

    def test_autosave_existing_document_saves_and_removes_index_entry(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.locations[document] = True
        api.modified[document] = True
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        plugin = self._plugin(api=api, storage=storage)

        plugin._autosave_document(document)

        self.assertEqual(storage.ensured_backups, [("id-doc", "/tmp/saved.txt")])
        self.assertEqual(api.saved_existing, [document])
        self.assertEqual(storage.removed, ["id-doc"])
        self.assertEqual(len(api.warning_bars), 1)

    def test_autosave_existing_document_without_local_path_does_not_save(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.locations[document] = True
        api.modified[document] = True
        storage = FakeStorage()
        plugin = self._plugin(api=api, storage=storage)

        plugin._autosave_document(document)

        self.assertEqual(storage.ensured_backups, [])
        self.assertEqual(api.saved_existing, [])

    def test_autosave_existing_document_does_not_save_when_backup_fails(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.locations[document] = True
        api.modified[document] = True
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.ensure_existing_file_backup = lambda document_id, file_path: (_ for _ in ()).throw(OSError("no"))
        plugin = self._plugin(api=api, storage=storage)

        plugin._autosave_document(document)

        self.assertEqual(api.saved_existing, [])

    def test_autosave_existing_unmodified_document_does_nothing(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.locations[document] = True
        storage = FakeStorage()
        plugin = self._plugin(api=api, storage=storage)

        plugin._autosave_document(document)

        self.assertEqual(api.saved_existing, [])
        self.assertEqual(storage.removed, [])

    def test_autosave_unsaved_document_writes_storage_and_clears_modified(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.text[document] = "hello"
        api.title[document] = "Untitled"
        storage = FakeStorage()
        plugin = self._plugin(api=api, storage=storage)

        plugin._autosave_document(document)

        self.assertEqual(storage.saved_unsaved, [("id-doc", "Untitled", "hello")])
        self.assertEqual(api.set_modified_calls, [(document, False)])

    def test_autosave_errors_are_swallowed(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.get_text = lambda saved_document: (_ for _ in ()).throw(RuntimeError("boom"))
        plugin = self._plugin(api=api)

        plugin._autosave_document(document)

        self.assertEqual(plugin._scheduler.forgotten, [])

    def test_restore_backup_updates_document_and_hides_warning(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.backups["/tmp/saved.txt"] = {"modified_at_display": "2026-04-24 14:10:12"}
        plugin = self._plugin(api=api, storage=storage)
        plugin._show_backup_warning(document)

        plugin._restore_existing_backup(document)

        self.assertEqual(storage.restored, ["/tmp/saved.txt"])
        self.assertEqual(api.updated_text, [(document, "restored text", True)])
        self.assertEqual(api.saved_existing, [document])
        self.assertTrue(api.warning_bars[0].closed)
        self.assertEqual(plugin._warning_bars, {})

    def test_accept_backup_deletes_backup_and_hides_warning(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.backups["/tmp/saved.txt"] = {"modified_at_display": "2026-04-24 14:10:12"}
        plugin = self._plugin(api=api, storage=storage)
        plugin._show_backup_warning(document)

        plugin._accept_existing_backup(document)

        self.assertEqual(storage.deleted_backups, ["/tmp/saved.txt"])
        self.assertTrue(api.warning_bars[0].closed)
        self.assertEqual(plugin._warning_bars, {})

    def test_show_backup_warning_does_not_duplicate_bar(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.backups["/tmp/saved.txt"] = {"modified_at_display": "2026-04-24 14:10:12"}
        plugin = self._plugin(api=api, storage=storage)

        plugin._show_backup_warning(document)
        plugin._show_backup_warning(document)

        self.assertEqual(len(api.warning_bars), 1)

    def test_show_backup_warning_without_path_or_backup_does_nothing(self):
        document = FakeDocument("doc")
        api = FakeApi()
        storage = FakeStorage()
        plugin = self._plugin(api=api, storage=storage)

        plugin._show_backup_warning(document)
        api.local_paths[document] = "/tmp/saved.txt"
        plugin._show_backup_warning(document)

        self.assertEqual(api.warning_bars, [])

    def test_restore_backup_without_path_does_nothing(self):
        document = FakeDocument("doc")
        storage = FakeStorage()
        plugin = self._plugin(storage=storage)

        plugin._restore_existing_backup(document)

        self.assertEqual(storage.restored, [])

    def test_restore_backup_error_keeps_warning_visible(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.backups["/tmp/saved.txt"] = {"modified_at_display": "2026-04-24 14:10:12"}
        storage.read_existing_file_backup = lambda file_path: (_ for _ in ()).throw(OSError("no"))
        plugin = self._plugin(api=api, storage=storage)
        plugin._show_backup_warning(document)

        plugin._restore_existing_backup(document)

        self.assertIn(document, plugin._warning_bars)
        self.assertFalse(api.warning_bars[0].closed)

    def test_accept_backup_without_path_does_nothing(self):
        document = FakeDocument("doc")
        storage = FakeStorage()
        plugin = self._plugin(storage=storage)

        plugin._accept_existing_backup(document)

        self.assertEqual(storage.deleted_backups, [])

    def test_accept_backup_error_keeps_warning_visible(self):
        document = FakeDocument("doc")
        api = FakeApi()
        api.local_paths[document] = "/tmp/saved.txt"
        storage = FakeStorage()
        storage.backups["/tmp/saved.txt"] = {"modified_at_display": "2026-04-24 14:10:12"}
        storage.delete_existing_file_backup = lambda file_path: (_ for _ in ()).throw(OSError("no"))
        plugin = self._plugin(api=api, storage=storage)
        plugin._show_backup_warning(document)

        plugin._accept_existing_backup(document)

        self.assertIn(document, plugin._warning_bars)
        self.assertFalse(api.warning_bars[0].closed)


if __name__ == "__main__":
    unittest.main()
