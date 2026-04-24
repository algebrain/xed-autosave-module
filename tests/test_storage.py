import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hadron_autosave.storage import AutosaveStorage


class AutosaveStorageTest(unittest.TestCase):
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
            self.assertEqual(storage.load_index(), {"documents": []})

            storage.index_path.write_text("[]", encoding="utf-8")
            self.assertEqual(storage.load_index(), {"documents": []})

            storage.index_path.write_text('{"documents": {}}', encoding="utf-8")
            self.assertEqual(storage.load_index(), {"documents": []})

    def test_load_index_returns_empty_when_open_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            with mock.patch.object(Path, "exists", return_value=True):
                with mock.patch.object(Path, "open", side_effect=OSError):
                    self.assertEqual(storage.load_index(), {"documents": []})

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
            storage._save_index({
                "documents": [
                    {"id": "missing-path"},
                    {"id": "doc-1", "path": "existing.txt", "title": ""},
                ],
            })

            entries = storage.restore_entries()

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["title"], "Untitled Document")
            self.assertEqual(entries[0]["text"], "hello")

    def test_empty_safe_filename_falls_back_to_document(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = AutosaveStorage(Path(directory))

            path = storage.path_for_unsaved("!!!", "Untitled Document 1")

            self.assertEqual(path.name, "unsaved-document.txt")


if __name__ == "__main__":
    unittest.main()
