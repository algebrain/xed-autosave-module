import ctypes
import locale
import os
from pathlib import Path

from .debug import debug

LIBXED_PATH = "/usr/lib/x86_64-linux-gnu/xed/libxed.so"
_DEFAULT_NATIVE_SAVE = object()


class BackupWarningHandle:
    def __init__(
        self,
        message,
        restore_label,
        accept_label,
        on_restore,
        on_accept,
        widget=None,
        on_close=None,
    ):
        self.message = message
        self.restore_label = restore_label
        self.accept_label = accept_label
        self._on_restore = on_restore
        self._on_accept = on_accept
        self._widget = widget
        self._on_close = on_close
        self.closed = False

    def restore(self):
        self._on_restore()

    def accept(self):
        self._on_accept()

    def close(self):
        self.closed = True
        if self._on_close is not None:
            self._on_close()
        if self._widget is not None:
            try:
                self._widget.destroy()
            except AttributeError:
                pass


class XedApi:
    def __init__(
        self,
        window,
        logger=debug,
        native_save=_DEFAULT_NATIVE_SAVE,
    ):
        self.window = window
        self._logger = logger
        if native_save is _DEFAULT_NATIVE_SAVE:
            self._native_save = _load_native_save()
        else:
            self._native_save = native_save

    def get_documents(self):
        if hasattr(self.window, "get_documents"):
            return list(self.window.get_documents())
        return [view.get_buffer() for view in self.window.get_views()]

    def get_document_from_tab(self, tab):
        if hasattr(tab, "get_document"):
            return tab.get_document()
        return tab.get_view().get_buffer()

    def get_tab_for_document(self, document):
        if hasattr(self.window, "get_active_tab"):
            tab = self.window.get_active_tab()
            if tab is not None and self.get_document_from_tab(tab) is document:
                return tab
        return None

    def get_title(self, document):
        if hasattr(document, "get_short_name_for_display"):
            return document.get_short_name_for_display()
        if hasattr(document, "get_name"):
            return document.get_name()
        return "Untitled Document"

    def has_location(self, document):
        return self.get_location(document) is not None

    def get_location(self, document):
        if hasattr(document, "get_location"):
            return document.get_location()
        return None

    def get_local_path(self, document):
        location = self.get_location(document)
        if location is None or not hasattr(location, "get_path"):
            return None
        return location.get_path()

    def is_modified(self, document):
        if hasattr(document, "get_modified"):
            return document.get_modified()
        return True

    def set_modified(self, document, modified):
        if hasattr(document, "set_modified"):
            document.set_modified(modified)

    def update_document_text(self, document, text, modified=False):
        if hasattr(document, "set_text"):
            document.set_text(text)
        self.set_modified(document, modified)

    def get_text(self, document):
        start = document.get_start_iter()
        end = document.get_end_iter()
        try:
            return document.get_text(start, end, True)
        except TypeError:
            return document.get_text(start, end)

    def save_existing(self, document):
        if self._native_save is not None:
            self._native_save(self.window, document)
            return

        location = self.get_location(document)
        if location is not None and hasattr(location, "get_path"):
            path = location.get_path()
            if path:
                text = self.get_text(document)
                _atomic_write_existing(path, text)
                self.set_modified(document, False)
                return

        if hasattr(document, "save"):
            document.save()
            return
        if hasattr(self.window, "save_document"):
            self.window.save_document(document)
            return
        raise RuntimeError("Xed document save API is not available")

    def restore_unsaved(self, text, document_id=None):
        tab = self.window.create_tab(True)
        document = self.get_document_from_tab(tab)
        document.set_text(text)
        self.set_modified(document, False)
        self._logger("restored unsaved document", document_id=document_id)
        return document

    def open_existing_file(self, file_path):
        document = self._find_open_document(file_path)
        if document is not None:
            return document

        try:
            from gi.repository import Gio
        except (ImportError, ValueError):
            self._logger("existing backup file open unavailable", file_path=file_path)
            return None

        location = Gio.File.new_for_path(str(file_path))
        tab = self._create_tab_from_location(location)
        if tab is None:
            self._logger("existing backup file open unavailable", file_path=file_path)
            return None
        self._logger("opened existing file with backup", file_path=file_path)
        return self.get_document_from_tab(tab)

    def show_backup_warning_bar(self, document, backup, on_restore, on_accept):
        strings = _ui_strings()
        modified_at = backup.get("modified_at_display") or backup.get("modified_at") or "unknown"
        message = strings["backup_warning"].format(time=modified_at)
        handle = BackupWarningHandle(
            message,
            strings["restore"],
            strings["accept"],
            lambda: self._confirm(strings["restore_confirm"], on_restore),
            lambda: self._confirm(strings["accept_confirm"], on_accept),
        )
        widget = self._try_show_gtk_info_bar(document, handle) if self.window is not None else None
        handle._widget = widget
        return handle

    def _confirm(self, message, callback):
        if _confirm_with_gtk(self.window, message):
            callback()

    def _try_show_gtk_info_bar(self, document, handle):
        try:
            from gi.repository import Gtk
        except (ImportError, ValueError):
            return None

        try:
            info_bar = Gtk.InfoBar()
            content_area = info_bar.get_content_area()
            content_area.add(Gtk.Label(label=handle.message))
            info_bar.add_button(handle.restore_label, 1)
            info_bar.add_button(handle.accept_label, 2)

            def on_response(bar, response_id):
                if response_id == 1:
                    handle.restore()
                elif response_id == 2:
                    handle.accept()

            info_bar.connect("response", on_response)
            if not _attach_info_bar_to_tab(self.get_tab_for_document(document), info_bar):
                _attach_info_bar(self.window, info_bar)
            info_bar.show_all()
            return info_bar
        except Exception as error:
            self._logger(
                "backup warning bar unavailable",
                error=f"{type(error).__name__}: {error}",
            )
            return None

    def _find_open_document(self, file_path):
        for document in self.get_documents():
            if self.get_local_path(document) == str(file_path):
                return document
        return None

    def _create_tab_from_location(self, location):
        tab = self._tab_from_location(location)
        if tab is not None:
            return tab
        if not hasattr(self.window, "create_tab_from_location"):
            return None

        argument_sets = [
            (location, None, 0, 0, False, True),
            (location, None, 0, 0, True),
            (location, None, 0, 0),
            (location, True),
            (location,),
        ]
        for arguments in argument_sets:
            try:
                return self.window.create_tab_from_location(*arguments)
            except TypeError:
                continue
        return None

    def _tab_from_location(self, location):
        if not hasattr(self.window, "get_tab_from_location"):
            return None
        try:
            return self.window.get_tab_from_location(location)
        except TypeError:
            return None


def _atomic_write_existing(path, text):
    tmp_path = f"{path}.hadron-autosave-tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


def _ui_strings():
    language = (locale.getlocale()[0] or "").lower()
    if language.startswith("ru"):
        return {
            "restore": "Восстановить",
            "accept": "Утвердить изменения",
            "backup_warning": "Файл был автосохранен. Резервная копия изменена {time}.",
            "restore_confirm": "Восстановить файл из резервной копии?",
            "accept_confirm": "Утвердить текущую версию и удалить резервную копию?",
        }
    return {
        "restore": "Restore",
        "accept": "Accept Changes",
        "backup_warning": "The file was autosaved. Backup modified at {time}.",
        "restore_confirm": "Restore the file from backup?",
        "accept_confirm": "Accept the current version and delete the backup?",
    }


def _confirm_with_gtk(window, message):
    if window is None:
        return True

    try:
        from gi.repository import Gtk
    except (ImportError, ValueError):
        return True

    try:
        dialog = Gtk.MessageDialog(
            transient_for=window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=message,
        )
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK
    except Exception:
        return True


def _attach_info_bar(window, info_bar):
    if hasattr(window, "get_message_area"):
        window.get_message_area().add(info_bar)
        return
    if hasattr(window, "get_child"):
        child = window.get_child()
        if hasattr(child, "add_overlay"):
            _place_info_bar_at_top(info_bar)
            child.add_overlay(info_bar)
            return
    if hasattr(window, "add"):
        window.add(info_bar)


def _attach_info_bar_to_tab(tab, info_bar):
    if tab is None:
        return False

    target = _tab_content_child(tab)
    if target is None:
        return False

    parent = target.get_parent() if hasattr(target, "get_parent") else None
    if parent is None:
        return False

    container = parent
    if not (hasattr(container, "pack_start") and hasattr(container, "reorder_child")):
        container = target

    if hasattr(container, "pack_start") and hasattr(container, "reorder_child"):
        container.pack_start(info_bar, False, False, 0)
        container.reorder_child(info_bar, 0)
        return True
    if hasattr(container, "add"):
        container.add(info_bar)
        return True
    return False


def _tab_content_child(tab):
    view = None
    if hasattr(tab, "get_view"):
        view = tab.get_view()
    elif hasattr(tab, "get_document"):
        view = getattr(tab, "view", None)
    if view is None or not hasattr(view, "get_parent"):
        return None

    child = view
    parent = child.get_parent()
    while parent is not None:
        if _same_widget(parent, tab):
            return child
        child = parent
        if not hasattr(child, "get_parent"):
            return None
        parent = child.get_parent()
    return None


def _same_widget(left, right):
    return left is right or left == right


def _place_info_bar_at_top(info_bar):
    try:
        from gi.repository import Gtk
    except (ImportError, ValueError):
        Gtk = None

    if Gtk is not None and hasattr(info_bar, "set_valign"):
        info_bar.set_valign(Gtk.Align.START)
    if hasattr(info_bar, "set_hexpand"):
        info_bar.set_hexpand(True)


def _load_native_save():
    library_path = LIBXED_PATH if Path(LIBXED_PATH).exists() else "libxed.so"
    try:
        library = ctypes.CDLL(library_path)
        save = library.xed_commands_save_document
    except OSError:
        return None

    save.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    save.restype = None

    def call(window, document):
        save(_gpointer(window), _gpointer(document))

    return call


def _gpointer(obj):
    return ctypes.c_void_p(hash(obj))
