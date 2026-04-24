import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hadron_autosave.storage import AutosaveStorage, DEFAULT_AUTOSAVE_DIR


class AutosaveStorageTest(unittest.TestCase):
    def test_default_autosave_dir_is_hadron_specific(self):
        self.assertEqual(DEFAULT_AUTOSAVE_DIR, Path.home() / ".xed" / "hadron-autosave")

    def test_reuses_autosave_path_for_same_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = AutosaveStorage(root)

            first = storage.path_for_unsaved("doc-1", "Untitled Document 1")
            second = storage.path_for_unsaved("doc-1", "Untitled Document 1")

            self.assertEqual(second, first)
            self.assertEqual(first.parent, root)
            self.assertEqual(first.name, "unsaved-doc-1.txt")

    def test_write_unsaved_document_updates_index(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            path = storage.save_unsaved("doc-1", "Untitled Document 1", "hello")

            self.assertEqual(path.read_text(encoding="utf-8"), "hello")
            index = storage.load_index()
            self.assertEqual(index["documents"][0]["id"], "doc-1")
            self.assertEqual(index["documents"][0]["title"], "Untitled Document 1")
            self.assertEqual(index["documents"][0]["path"], "unsaved-doc-1.txt")

    def test_save_unsaved_overwrites_existing_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            storage.save_unsaved("doc-1", "First title", "one")
            path = storage.save_unsaved("doc-1", "Second title", "two")

            self.assertEqual(path.read_text(encoding="utf-8"), "two")
            index = storage.load_index()
            self.assertEqual(len(index["documents"]), 1)
            self.assertEqual(index["documents"][0]["title"], "Second title")

    def test_remove_document_deletes_index_entry_not_file(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))
            path = storage.save_unsaved("doc-1", "Untitled Document 1", "hello")

            storage.remove("doc-1")

            self.assertTrue(path.exists())
            self.assertEqual(storage.load_index()["documents"], [])

    def test_delete_document_removes_index_entry_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))
            path = storage.save_unsaved("doc-1", "Untitled Document 1", "hello")

            storage.delete("doc-1")

            self.assertFalse(path.exists())
            self.assertEqual(storage.load_index()["documents"], [])

    def test_delete_ignores_missing_autosave_file(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))
            path = storage.save_unsaved("doc-1", "Untitled Document 1", "hello")
            path.unlink()

            storage.delete("doc-1")

            self.assertEqual(storage.load_index()["documents"], [])

    def test_load_index_returns_empty_for_invalid_files(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            storage.index_path.parent.mkdir(parents=True, exist_ok=True)
            storage.index_path.write_text("not json", encoding="utf-8")
            self.assertEqual(storage.load_index(), {"documents": [], "backups": []})

            storage.index_path.write_text("[]", encoding="utf-8")
            self.assertEqual(storage.load_index(), {"documents": [], "backups": []})

            storage.index_path.write_text('{"documents": {}}', encoding="utf-8")
            self.assertEqual(storage.load_index(), {"documents": [], "backups": []})

    def test_load_index_returns_empty_when_open_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            with mock.patch.object(Path, "exists", return_value=True):
                with mock.patch.object(Path, "open", side_effect=OSError):
                    self.assertEqual(storage.load_index(), {"documents": [], "backups": []})

    def test_restore_entries_skips_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = AutosaveStorage(root)
            storage.save_unsaved("doc-1", "Untitled Document 1", "hello")
            Path(root, "unsaved-doc-1.txt").unlink()

            self.assertEqual(storage.restore_entries(), [])

    def test_restore_entries_skips_missing_path_and_uses_default_title(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = AutosaveStorage(root)
            root.mkdir(parents=True, exist_ok=True)
            (root / "existing.txt").write_text("hello", encoding="utf-8")
            (root / "kept.txt").write_text("keep", encoding="utf-8")
            storage._save_index({
                "documents": [
                    {"id": "missing-path"},
                    {"id": "doc-1", "path": "existing.txt", "title": ""},
                    {"id": "doc-2", "path": "kept.txt", "title": "Kept"},
                ],
            })

            entries = storage.restore_entries()

            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["title"], "Untitled Document")
            self.assertEqual(entries[0]["text"], "hello")

    def test_empty_safe_filename_falls_back_to_document(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            path = storage.path_for_unsaved("!!!", "Untitled Document 1")

            self.assertEqual(path.name, "unsaved-document.txt")

    def test_existing_file_backup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "saved.txt"
            file_path.write_text("original text", encoding="utf-8")
            storage = AutosaveStorage(root / "store")

            first = storage.ensure_existing_file_backup("doc-1", file_path)
            file_path.write_text("autosaved text", encoding="utf-8")
            second = storage.ensure_existing_file_backup("doc-1", file_path)

            self.assertEqual(second["backup_path"], first["backup_path"])
            self.assertEqual(first["path"].read_text(encoding="utf-8"), "original text")
            self.assertEqual(second["path"].read_text(encoding="utf-8"), "original text")

    def test_existing_file_backup_can_be_found_by_file_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "saved.txt"
            file_path.write_text("original text", encoding="utf-8")
            storage = AutosaveStorage(root / "store")

            created = storage.ensure_existing_file_backup("doc-1", file_path)
            found = storage.backup_for_existing(file_path)

            self.assertEqual(found["id"], created["id"])
            self.assertEqual(found["path"], created["path"])
            self.assertIn("modified_at", found)

    def test_active_existing_file_backups_returns_backups_with_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "saved.txt"
            file_path.write_text("original text", encoding="utf-8")
            storage = AutosaveStorage(root / "store")

            created = storage.ensure_existing_file_backup("doc-1", file_path)
            active = storage.active_existing_file_backups()

            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["file_path"], str(file_path))
            self.assertEqual(active[0]["path"], created["path"])

    def test_active_existing_file_backups_skips_malformed_and_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = AutosaveStorage(root / "store")
            storage._save_index({
                "backups": [
                    {"file_path": "/tmp/sample.txt"},
                    {"backup_path": "backups/file.bak"},
                    {"file_path": "/tmp/sample.txt", "backup_path": "missing.bak"},
                ],
            })

            self.assertEqual(storage.active_existing_file_backups(), [])

    def test_backup_for_existing_skips_malformed_and_missing_backup_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "saved.txt"
            file_path.write_text("original text", encoding="utf-8")
            storage = AutosaveStorage(root / "store")
            storage._save_index({
                "backups": [
                    {"file_path": str(root / "other.txt")},
                    {"file_path": str(file_path)},
                    {"file_path": str(file_path), "backup_path": "missing.bak"},
                ],
            })

            self.assertIsNone(storage.backup_for_existing(file_path))

    def test_restore_existing_file_backup_returns_text_and_deletes_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "saved.txt"
            file_path.write_text("original text", encoding="utf-8")
            storage = AutosaveStorage(root / "store")
            backup = storage.ensure_existing_file_backup("doc-1", file_path)
            file_path.write_text("autosaved text", encoding="utf-8")

            restored_text = storage.restore_existing_file_backup(file_path)

            self.assertEqual(restored_text, "original text")
            self.assertEqual(file_path.read_text(encoding="utf-8"), "autosaved text")
            self.assertFalse(backup["path"].exists())
            self.assertIsNone(storage.backup_for_existing(file_path))

    def test_delete_existing_file_backup_removes_entry_and_ignores_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file_path = root / "saved.txt"
            file_path.write_text("original text", encoding="utf-8")
            storage = AutosaveStorage(root / "store")
            backup = storage.ensure_existing_file_backup("doc-1", file_path)
            backup["path"].unlink()

            self.assertTrue(storage.delete_existing_file_backup(file_path))

            self.assertIsNone(storage.backup_for_existing(file_path))

    def test_delete_existing_file_backup_returns_false_when_not_found(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            self.assertFalse(storage.delete_existing_file_backup("missing.txt"))

    def test_restore_existing_file_backup_raises_when_not_found(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            with self.assertRaises(FileNotFoundError):
                storage.restore_existing_file_backup("missing.txt")

    def test_existing_file_backup_rejects_non_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = AutosaveStorage(root / "store")

            with self.assertRaises(OSError):
                storage.ensure_existing_file_backup("doc-1", root)


if __name__ == "__main__":
    unittest.main()
