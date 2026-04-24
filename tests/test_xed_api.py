import tempfile
import sys
import types
import unittest
from contextlib import contextmanager
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


class NamelessLocation:
    pass


class TwoArgumentTextDocument(FakeDocument):
    def get_text(self, start, end):
        return self._text[start:end]


class FakeView:
    def __init__(self, document):
        self._document = document
        self._parent = None

    def get_buffer(self):
        return self._document

    def get_parent(self):
        return self._parent


class FakeTab:
    def __init__(self, document):
        self._document = document
        self._view = FakeView(document)

    def get_document(self):
        return self._document

    def get_view(self):
        return self._view


class ViewOnlyTab:
    def __init__(self, document):
        self._document = document

    def get_view(self):
        return FakeView(self._document)


class FakeGtkContentArea:
    def __init__(self):
        self.children = []

    def add(self, widget):
        self.children.append(widget)


class FakeGtkInfoBar:
    def __init__(self):
        if FakeGtk.info_bar_error is not None:
            raise FakeGtk.info_bar_error
        self.content_area = FakeGtkContentArea()
        self.buttons = []
        self.callback = None
        self.destroyed = False
        self.shown = False

    def get_content_area(self):
        return self.content_area

    def add_button(self, label, response_id):
        self.buttons.append((label, response_id))

    def connect(self, signal_name, callback):
        self.callback = callback

    def show_all(self):
        self.shown = True

    def destroy(self):
        self.destroyed = True

    def respond(self, response_id):
        self.callback(self, response_id)


class FakeGtkDialog:
    def __init__(self, **kwargs):
        if FakeGtk.dialog_error is not None:
            raise FakeGtk.dialog_error
        self.kwargs = kwargs
        self.destroyed = False

    def run(self):
        return FakeGtk.response

    def destroy(self):
        self.destroyed = True


class FakeGtk:
    response = 1
    dialog_error = None
    info_bar_error = None
    InfoBar = FakeGtkInfoBar
    Label = lambda label: types.SimpleNamespace(label=label)
    MessageDialog = FakeGtkDialog
    MessageType = types.SimpleNamespace(WARNING="warning")
    ButtonsType = types.SimpleNamespace(OK_CANCEL="ok-cancel")
    ResponseType = types.SimpleNamespace(OK=1, CANCEL=0)
    Align = types.SimpleNamespace(START="start")


class FakeGtkWindow:
    def __init__(self):
        self.message_area = FakeGtkContentArea()

    def get_message_area(self):
        return self.message_area


class AddOnlyWindow:
    def __init__(self):
        self.children = []

    def add(self, child):
        self.children.append(child)


class ActiveTabWindow:
    def __init__(self, tab):
        self._tab = tab

    def get_active_tab(self):
        return self._tab


class OverlayChildWindow:
    def __init__(self):
        self.child = FakeOverlay()

    def get_child(self):
        return self.child


class FakeOverlay:
    def __init__(self):
        self.overlays = []

    def add_overlay(self, child):
        self.overlays.append(child)


class AlignableInfoBar:
    def __init__(self):
        self.valign = None
        self.hexpand = None

    def set_valign(self, value):
        self.valign = value

    def set_hexpand(self, value):
        self.hexpand = value


class FakeBox:
    def __init__(self, parent=None):
        self._parent = parent
        self.packed = []
        self.reordered = []

    def get_parent(self):
        return self._parent

    def pack_start(self, child, expand, fill, padding):
        self.packed.append((child, expand, fill, padding))

    def reorder_child(self, child, position):
        self.reordered.append((child, position))


class FakeTabWidget(FakeTab):
    def __init__(self, document):
        super().__init__(document)
        self.box = FakeBox(parent=self)
        self._view._parent = self.box


@contextmanager
def fake_gtk(response=1, dialog_error=None, info_bar_error=None):
    old_repository = sys.modules.get("gi.repository")
    repository = types.ModuleType("gi.repository")
    repository.Gtk = FakeGtk
    FakeGtk.response = response
    FakeGtk.dialog_error = dialog_error
    FakeGtk.info_bar_error = info_bar_error
    sys.modules["gi.repository"] = repository
    try:
        yield
    finally:
        FakeGtk.dialog_error = None
        FakeGtk.info_bar_error = None
        if old_repository is None:
            sys.modules.pop("gi.repository", None)
        else:
            sys.modules["gi.repository"] = old_repository


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

    def test_get_tab_for_document_uses_active_tab(self):
        document = FakeDocument()
        active_tab = FakeTab(document)
        api = XedApi(ActiveTabWindow(active_tab), native_save=None)
        self.assertIs(api.get_tab_for_document(document), active_tab)
        self.assertIsNone(api.get_tab_for_document(FakeDocument()))

    def test_document_metadata_fallbacks(self):
        class NamedDocument:
            def get_name(self):
                return "name"

        api = XedApi(window=None, native_save=None)

        self.assertEqual(api.get_title(FakeDocument()), "short name")
        self.assertEqual(api.get_title(NamedDocument()), "name")
        self.assertEqual(api.get_title(object()), "Untitled Document")
        self.assertFalse(api.has_location(object()))
        self.assertTrue(api.is_modified(FakeDocument()))
        self.assertTrue(api.is_modified(object()))
        api.set_modified(object(), False)

    def test_get_local_path_returns_document_path_or_none(self):
        path = Path("saved.txt")
        api = XedApi(window=None, native_save=None)

        self.assertEqual(api.get_local_path(FakeDocument(path)), str(path))
        self.assertIsNone(api.get_local_path(FakeDocument()))

        document = FakeDocument()
        document._location = NamelessLocation()
        self.assertIsNone(api.get_local_path(document))

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

    def test_update_document_text_sets_text_and_modified_flag(self):
        document = FakeDocument(text="old")

        XedApi(window=None, native_save=None).update_document_text(document, "new")

        self.assertEqual(document._text, "new")
        self.assertFalse(document.modified)

        XedApi(window=None, native_save=None).update_document_text(document, "newer", modified=True)
        self.assertTrue(document.modified)

    def test_show_backup_warning_bar_uses_english_fallback_without_gtk(self):
        calls = []
        api = XedApi(window=None, native_save=None, logger=lambda *args, **kwargs: None)

        handle = api.show_backup_warning_bar(
            document=object(),
            backup={"modified_at_display": "2026-04-24 14:10:12"},
            on_restore=lambda: calls.append("restore"),
            on_accept=lambda: calls.append("accept"),
        )

        self.assertIn("Backup modified at 2026-04-24 14:10:12", handle.message)
        self.assertEqual(handle.restore_label, "Restore")
        self.assertEqual(handle.accept_label, "Accept Changes")

        handle.restore()
        handle.accept()
        handle.close()

        self.assertEqual(calls, ["restore", "accept"])
        self.assertTrue(handle.closed)

    def test_show_backup_warning_bar_uses_russian_locale(self):
        api = XedApi(window=None, native_save=None)

        with mock.patch.object(xed_api.locale, "getlocale", return_value=("ru_RU", "UTF-8")):
            handle = api.show_backup_warning_bar(
                document=object(),
                backup={"modified_at_display": "2026-04-24 14:10:12"},
                on_restore=lambda: None,
                on_accept=lambda: None,
            )

        self.assertEqual(handle.restore_label, "Восстановить")
        self.assertEqual(handle.accept_label, "Утвердить изменения")
        self.assertIn("Резервная копия изменена", handle.message)

    def test_backup_warning_handle_closes_widget_without_destroy(self):
        handle = xed_api.BackupWarningHandle(
            "message",
            "Restore",
            "Accept Changes",
            lambda: None,
            lambda: None,
            widget=object(),
        )

        handle.close()

        self.assertTrue(handle.closed)

    def test_default_constructor_loads_native_save(self):
        with mock.patch.object(xed_api, "_load_native_save", return_value="native"):
            api = XedApi(window=None)

        self.assertEqual(api._native_save, "native")

    def test_show_backup_warning_bar_attaches_fake_gtk_bar_and_confirms_actions(self):
        calls = []
        window = FakeGtkWindow()
        api = XedApi(window=window, native_save=None)

        with fake_gtk(response=FakeGtk.ResponseType.OK):
            handle = api.show_backup_warning_bar(
                document=object(),
                backup={"modified_at_display": "2026-04-24 14:10:12"},
                on_restore=lambda: calls.append("restore"),
                on_accept=lambda: calls.append("accept"),
            )
            handle._widget.respond(1)
            handle._widget.respond(2)

        self.assertEqual(calls, ["restore", "accept"])
        self.assertEqual(window.message_area.children, [handle._widget])
        self.assertEqual(handle._widget.buttons, [("Restore", 1), ("Accept Changes", 2)])

    def test_confirm_cancel_skips_action(self):
        with fake_gtk(response=FakeGtk.ResponseType.CANCEL):
            result = xed_api._confirm_with_gtk(object(), "question")

        self.assertFalse(result)

    def test_confirm_returns_true_when_gtk_import_fails_or_dialog_fails(self):
        with mock.patch.dict("sys.modules", {"gi.repository": None}):
            self.assertTrue(xed_api._confirm_with_gtk(object(), "question"))

        with fake_gtk(response=FakeGtk.ResponseType.OK, dialog_error=RuntimeError("no display")):
            self.assertTrue(xed_api._confirm_with_gtk(object(), "question"))

    def test_attach_info_bar_uses_window_add_fallback(self):
        window = AddOnlyWindow()
        info_bar = object()

        xed_api._attach_info_bar(window, info_bar)

        self.assertEqual(window.children, [info_bar])

    def test_attach_info_bar_prefers_overlay_child(self):
        window = OverlayChildWindow()
        info_bar = AlignableInfoBar()

        with fake_gtk():
            xed_api._attach_info_bar(window, info_bar)

        self.assertEqual(window.child.overlays, [info_bar])
        self.assertEqual(info_bar.valign, FakeGtk.Align.START)
        self.assertTrue(info_bar.hexpand)

    def test_show_backup_warning_bar_packs_into_tab_above_view(self):
        document = FakeDocument()
        tab = FakeTabWidget(document)
        api = XedApi(window=ActiveTabWindow(tab), native_save=None)

        with fake_gtk(response=FakeGtk.ResponseType.OK):
            handle = api.show_backup_warning_bar(
                document=document,
                backup={"modified_at_display": "2026-04-24 14:10:12"},
                on_restore=lambda: None,
                on_accept=lambda: None,
            )

        self.assertEqual(tab.box.packed, [(handle._widget, False, False, 0)])
        self.assertEqual(tab.box.reordered, [(handle._widget, 0)])

    def test_try_show_gtk_info_bar_logs_errors(self):
        logs = []
        api = XedApi(
            window=object(),
            native_save=None,
            logger=lambda *args, **kwargs: logs.append((args, kwargs)),
        )
        handle = xed_api.BackupWarningHandle(
            "message",
            "Restore",
            "Accept",
            lambda: None,
            lambda: None,
        )

        with fake_gtk(info_bar_error=RuntimeError("no display")):
            widget = api._try_show_gtk_info_bar(object(), handle)

        self.assertIsNone(widget)
        self.assertEqual(logs[0][0], ("backup warning bar unavailable",))

    def test_place_info_bar_tolerates_missing_gtk(self):
        info_bar = AlignableInfoBar()

        with mock.patch.dict("sys.modules", {"gi.repository": None}):
            xed_api._place_info_bar_at_top(info_bar)

        self.assertIsNone(info_bar.valign)
        self.assertTrue(info_bar.hexpand)

    def test_attach_info_bar_to_tab_returns_false_without_view_path(self):
        self.assertFalse(xed_api._attach_info_bar_to_tab(None, object()))
        self.assertFalse(xed_api._attach_info_bar_to_tab(FakeTab(FakeDocument()), object()))

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
