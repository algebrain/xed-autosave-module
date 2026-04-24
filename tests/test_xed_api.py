import tempfile
import unittest
from pathlib import Path

from xed_autosave.xed_api import XedApi


class FakeLocation:
    def __init__(self, path):
        self._path = path

    def get_path(self):
        return str(self._path)


class FakeDocument:
    def __init__(self, path, text):
        self._location = FakeLocation(path)
        self._text = text
        self.modified = True

    def get_location(self):
        return self._location

    def get_start_iter(self):
        return 0

    def get_end_iter(self):
        return len(self._text)

    def get_text(self, start, end, include_hidden_chars=True):
        return self._text[start:end]

    def set_modified(self, modified):
        self.modified = modified


class XedApiTest(unittest.TestCase):
    def test_save_existing_prefers_native_xed_save(self):
        calls = []
        document = object()
        window = object()
        api = XedApi(
            window=window,
            native_save=lambda called_window, called_document: calls.append(
                (called_window, called_document)
            ),
        )

        api.save_existing(document)

        self.assertEqual(calls, [(window, document)])

    def test_save_existing_writes_document_text_to_location(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.txt"
            path.write_text("old", encoding="utf-8")
            document = FakeDocument(path, "new text")
            api = XedApi(window=None, native_save=None)

            api.save_existing(document)

            self.assertEqual(path.read_text(encoding="utf-8"), "new text")
            self.assertFalse(document.modified)


if __name__ == "__main__":
    unittest.main()
