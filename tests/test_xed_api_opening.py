import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path

from hadron_autosave.xed_api import XedApi
from hadron_autosave import xed_api
from tests.test_xed_api import FakeDocument, FakeTab


class FakeGioFile:
    def __init__(self, path):
        self.path = str(path)

    @classmethod
    def new_for_path(cls, path):
        return cls(path)


class FakeOpenWindow:
    def __init__(self, existing_tab=None):
        self.existing_tab = existing_tab
        self.created_arguments = []
        self.documents = []

    def get_documents(self):
        return self.documents

    def get_tab_from_location(self, location):
        if self.existing_tab is not None:
            return self.existing_tab
        return None

    def create_tab_from_location(self, *arguments):
        self.created_arguments.append(arguments)
        document = FakeDocument(Path(arguments[0].path))
        return FakeTab(document)


class NoLocationTabWindow:
    def __init__(self):
        self.documents = []

    def get_documents(self):
        return []


class RetryingOpenWindow(FakeOpenWindow):
    def create_tab_from_location(self, *arguments):
        self.created_arguments.append(arguments)
        if len(self.created_arguments) == 1:
            raise TypeError("wrong signature")
        document = FakeDocument(Path(arguments[0].path))
        return FakeTab(document)


class AddOnlyBox:
    def __init__(self, parent=None):
        self._parent = parent
        self.children = []

    def get_parent(self):
        return self._parent

    def add(self, child):
        self.children.append(child)


class ViewOnlyTabWithAttribute:
    def __init__(self):
        self.view = types.SimpleNamespace(get_parent=lambda: self)

    def get_document(self):
        return object()


@contextmanager
def fake_gio():
    old_repository = sys.modules.get("gi.repository")
    repository = types.ModuleType("gi.repository")
    repository.Gio = types.SimpleNamespace(File=FakeGioFile)
    sys.modules["gi.repository"] = repository
    try:
        yield
    finally:
        if old_repository is None:
            sys.modules.pop("gi.repository", None)
        else:
            sys.modules["gi.repository"] = old_repository


class XedApiOpeningTest(unittest.TestCase):
    def test_open_existing_file_reuses_already_open_document(self):
        document = FakeDocument(Path("/tmp/sample2.txt"))
        window = FakeOpenWindow()
        window.documents = [document]

        opened = XedApi(window, native_save=None).open_existing_file("/tmp/sample2.txt")

        self.assertIs(opened, document)
        self.assertEqual(window.created_arguments, [])

    def test_open_existing_file_uses_xed_location_tab_api(self):
        window = FakeOpenWindow()

        with fake_gio():
            opened = XedApi(window, native_save=None).open_existing_file("/tmp/sample2.txt")

        self.assertEqual(opened.get_location().get_path(), "/tmp/sample2.txt")
        self.assertEqual(window.created_arguments[0][0].path, "/tmp/sample2.txt")

    def test_open_existing_file_reuses_xed_tab_from_location(self):
        document = FakeDocument(Path("/tmp/sample2.txt"))
        window = FakeOpenWindow(existing_tab=FakeTab(document))

        with fake_gio():
            opened = XedApi(window, native_save=None).open_existing_file("/tmp/sample2.txt")

        self.assertIs(opened, document)
        self.assertEqual(window.created_arguments, [])

    def test_open_existing_file_retries_supported_create_signature(self):
        window = RetryingOpenWindow()

        with fake_gio():
            opened = XedApi(window, native_save=None).open_existing_file("/tmp/sample2.txt")

        self.assertEqual(opened.get_location().get_path(), "/tmp/sample2.txt")
        self.assertEqual(len(window.created_arguments), 2)

    def test_open_existing_file_returns_none_without_gio(self):
        class Window:
            def get_documents(self):
                return []

        with unittest.mock.patch.dict("sys.modules", {"gi.repository": None}):
            opened = XedApi(Window(), native_save=None).open_existing_file("/tmp/sample2.txt")

        self.assertIsNone(opened)

    def test_open_existing_file_returns_none_without_tab_api(self):
        with fake_gio():
            opened = XedApi(NoLocationTabWindow(), native_save=None).open_existing_file(
                "/tmp/sample2.txt"
            )

        self.assertIsNone(opened)

    def test_attach_info_bar_to_tab_uses_add_container_fallback(self):
        tab = types.SimpleNamespace()
        view = types.SimpleNamespace()
        box = AddOnlyBox(parent=tab)
        view.get_parent = lambda: box
        tab.get_view = lambda: view
        info_bar = object()

        attached = xed_api._attach_info_bar_to_tab(tab, info_bar)

        self.assertTrue(attached)
        self.assertEqual(box.children, [info_bar])

    def test_tab_content_child_uses_view_attribute_fallback(self):
        tab = ViewOnlyTabWithAttribute()

        self.assertIs(xed_api._tab_content_child(tab), tab.view)


if __name__ == "__main__":
    unittest.main()
