import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hadron_autosave import xed_api
from hadron_autosave.xed_api import XedApi


class FakeLocation:
    def __init__(self, path):
        self._path = path

    def get_path(self):
        return str(self._path)


class FakeDocument:
    def __init__(self, path=None, text=""):
        self._location = FakeLocation(path) if path is not None else None
        self._text = text
        self.modified = True
        self.saved = False

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

    def get_short_name_for_display(self):
        return "short name"

    def get_modified(self):
        return self.modified

    def save(self):
        self.saved = True

    def set_text(self, text):
        self._text = text


class TwoArgumentTextDocument(FakeDocument):
    def get_text(self, start, end):
        return self._text[start:end]


class FakeView:
    def __init__(self, document):
        self._document = document

    def get_buffer(self):
        return self._document


class FakeTab:
    def __init__(self, document):
        self._document = document

    def get_document(self):
        return self._document


class ViewOnlyTab:
    def __init__(self, document):
        self._document = document

    def get_view(self):
        return FakeView(self._document)


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

    def test_get_documents_supports_documents_and_views(self):
        document = FakeDocument()

        class DocumentsWindow:
            def get_documents(self):
                return (item for item in [document])

        class ViewsWindow:
            def get_views(self):
                return [FakeView(document)]

        self.assertEqual(XedApi(DocumentsWindow(), native_save=None).get_documents(), [document])
        self.assertEqual(XedApi(ViewsWindow(), native_save=None).get_documents(), [document])

    def test_get_document_from_tab_supports_tab_and_view_api(self):
        document = FakeDocument()
        api = XedApi(window=None, native_save=None)

        self.assertIs(api.get_document_from_tab(FakeTab(document)), document)
        self.assertIs(api.get_document_from_tab(ViewOnlyTab(document)), document)

    def test_document_metadata_fallbacks(self):
        class NamedDocument:
            def get_name(self):
                return "name"

        api = XedApi(window=None, native_save=None)

        self.assertEqual(api.get_title(FakeDocument()), "short name")
        self.assertEqual(api.get_title(NamedDocument()), "name")
        self.assertEqual(api.get_title(object()), "Untitled Document")
        self.assertFalse(api.has_location(object()))
        self.assertTrue(api.is_modified(object()))
        api.set_modified(object(), False)

    def test_get_text_supports_two_argument_get_text(self):
        document = TwoArgumentTextDocument(text="hello")

        self.assertEqual(XedApi(window=None, native_save=None).get_text(document), "hello")

    def test_save_existing_uses_document_save_fallback(self):
        document = FakeDocument()
        api = XedApi(window=None, native_save=None)

        api.save_existing(document)

        self.assertTrue(document.saved)

    def test_save_existing_uses_window_save_fallback(self):
        calls = []
        document = object()

        class Window:
            def save_document(self, saved_document):
                calls.append(saved_document)

        XedApi(window=Window(), native_save=None).save_existing(document)

        self.assertEqual(calls, [document])

    def test_save_existing_raises_when_no_save_api_exists(self):
        with self.assertRaises(RuntimeError):
            XedApi(window=None, native_save=None).save_existing(object())

    def test_restore_unsaved_creates_tab_and_logs(self):
        logs = []
        document = FakeDocument()

        class Window:
            def create_tab(self, jump_to):
                self.jump_to = jump_to
                return ViewOnlyTab(document)

        window = Window()
        api = XedApi(window=window, native_save=None, logger=lambda *args, **kwargs: logs.append((args, kwargs)))

        restored = api.restore_unsaved("hello", "doc-1")

        self.assertIs(restored, document)
        self.assertEqual(document._text, "hello")
        self.assertFalse(document.modified)
        self.assertTrue(window.jump_to)
        self.assertEqual(logs[0][1]["document_id"], "doc-1")

    def test_load_native_save_returns_none_when_library_is_missing(self):
        with mock.patch.object(xed_api.Path, "exists", return_value=False):
            with mock.patch.object(xed_api.ctypes, "CDLL", side_effect=OSError):
                self.assertIsNone(xed_api._load_native_save())

    def test_load_native_save_wraps_native_function(self):
        calls = []

        class FakeSave:
            def __call__(self, window, document):
                calls.append((window.value, document.value))

        class FakeLibrary:
            xed_commands_save_document = FakeSave()

        with mock.patch.object(xed_api.Path, "exists", return_value=True):
            with mock.patch.object(xed_api.ctypes, "CDLL", return_value=FakeLibrary()):
                native_save = xed_api._load_native_save()

        native_save(1, 2)

        self.assertEqual(calls, [(hash(1), hash(2))])


if __name__ == "__main__":
    unittest.main()
