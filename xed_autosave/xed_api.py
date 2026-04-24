import ctypes
import os
from pathlib import Path

from .debug import debug

LIBXED_PATH = "/usr/lib/x86_64-linux-gnu/xed/libxed.so"
_DEFAULT_NATIVE_SAVE = object()


class XedApi:
    def __init__(self, window, logger=debug, native_save=_DEFAULT_NATIVE_SAVE):
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

    def is_modified(self, document):
        if hasattr(document, "get_modified"):
            return document.get_modified()
        return True

    def set_modified(self, document, modified):
        if hasattr(document, "set_modified"):
            document.set_modified(modified)

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


def _atomic_write_existing(path, text):
    tmp_path = f"{path}.xed-autosave-tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


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
