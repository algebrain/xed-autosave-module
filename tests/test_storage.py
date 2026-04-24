import tempfile
import unittest
from pathlib import Path

from xed_autosave.storage import AutosaveStorage


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

    def test_restore_entries_skips_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = AutosaveStorage(root)
            storage.save_unsaved("doc-1", "Untitled Document 1", "hello")
            Path(root, "unsaved-doc-1.txt").unlink()

            self.assertEqual(storage.restore_entries(), [])


if __name__ == "__main__":
    unittest.main()
