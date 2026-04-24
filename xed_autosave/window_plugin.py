import gi

gi.require_version("Xed", "1.0")

from gi.repository import GLib, GObject, Xed

from .debug import debug
from .document_ids import DocumentIds
from .scheduler import AutosaveScheduler
from .storage import AutosaveStorage
from .xed_api import XedApi
from .config import AUTOSAVE_DELAY_MS, PLUGIN_VERSION


class GLibClock:
    def call_later(self, delay_ms, callback, *args):
        return GLib.timeout_add(delay_ms, callback, *args)

    def cancel(self, timer_id):
        GLib.source_remove(timer_id)


class XedAutosavePlugin(GObject.Object, Xed.WindowActivatable):
    __gtype_name__ = "XedAutosavePlugin"

    window = GObject.Property(type=Xed.Window)

    def do_activate(self):
        self._api = XedApi(self.window)
        self._storage = AutosaveStorage()
        self._document_ids = DocumentIds()
        self._handlers = {}
        self._window_handlers = []
        self._restored_ids = set()
        self._closing_window = False
        self._scheduler = AutosaveScheduler(
            GLibClock(),
            AUTOSAVE_DELAY_MS,
            self._autosave_document,
        )

        self._restore_unsaved_documents()
        for document in self._api.get_documents():
            self._watch_document(document)

        self._window_handlers.append(
            self.window.connect("tab-added", self._on_tab_added)
        )
        self._window_handlers.append(
            self.window.connect("tab-removed", self._on_tab_removed)
        )
        self._window_handlers.append(
            self.window.connect("delete-event", self._on_window_delete_event)
        )
        debug(
            "activated plugin",
            version=PLUGIN_VERSION,
            delay_ms=AUTOSAVE_DELAY_MS,
        )

    def do_deactivate(self):
        self._scheduler.cancel_all()

        for document, handler_id in list(self._handlers.items()):
            document.disconnect(handler_id)
        self._handlers.clear()

        for handler_id in self._window_handlers:
            self.window.disconnect(handler_id)
        self._window_handlers.clear()
        debug("deactivated plugin")

    def do_update_state(self):
        pass

    def _restore_unsaved_documents(self):
        for entry in self._storage.restore_entries():
            if not entry["id"] or entry["id"] in self._restored_ids:
                continue
            document = self._api.restore_unsaved(entry["text"], entry["id"])
            self._document_ids.set(document, entry["id"])
            self._restored_ids.add(entry["id"])

    def _watch_document(self, document):
        if document in self._handlers:
            return
        handler_id = document.connect("changed", self._on_document_changed)
        self._handlers[document] = handler_id
        document_id = self._document_ids.get(document)
        debug("watching document", document_id=document_id)

    def _unwatch_document(self, document, delete_unsaved=False):
        document_id = self._document_ids.get(document)

        handler_id = self._handlers.pop(document, None)
        if handler_id is not None:
            document.disconnect(handler_id)
        self._scheduler.forget(document)

        if delete_unsaved and not self._api.has_location(document):
            self._storage.delete(document_id)
            debug("deleted unsaved document autosave", document_id=document_id)

        self._document_ids.forget(document)

    def _on_tab_added(self, window, tab):
        self._watch_document(self._api.get_document_from_tab(tab))

    def _on_tab_removed(self, window, tab):
        self._unwatch_document(
            self._api.get_document_from_tab(tab),
            delete_unsaved=not self._closing_window,
        )

    def _on_window_delete_event(self, window, event):
        self._closing_window = True
        return False

    def _on_document_changed(self, document):
        document_id = self._document_ids.get(document)
        debug("document changed", document_id=document_id)
        self._scheduler.changed(document)

    def _autosave_document(self, document):
        document_id = self._document_ids.get(document)
        try:
            if self._api.has_location(document):
                if self._api.is_modified(document):
                    self._api.save_existing(document)
                    self._storage.remove(document_id)
                    debug("saved existing document", document_id=document_id)
                return

            text = self._api.get_text(document)
            title = self._api.get_title(document)
            path = self._storage.save_unsaved(document_id, title, text)
            self._api.set_modified(document, False)
            debug("saved unsaved document", document_id=document_id, path=path)
        except Exception as error:
            debug(
                "autosave failed",
                document_id=document_id,
                error=f"{type(error).__name__}: {error}",
            )
