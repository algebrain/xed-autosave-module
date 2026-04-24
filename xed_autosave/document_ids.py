import uuid
import weakref


class DocumentIds:
    def __init__(self):
        self._weak_ids = weakref.WeakKeyDictionary()
        self._ids = {}

    def get(self, document):
        document_id = self._get(document)
        if document_id is None:
            document_id = uuid.uuid4().hex
            self.set(document, document_id)
        return document_id

    def set(self, document, document_id):
        try:
            self._weak_ids[document] = document_id
        except TypeError:
            self._ids[id(document)] = document_id

    def forget(self, document):
        try:
            self._weak_ids.pop(document, None)
        except TypeError:
            self._ids.pop(id(document), None)

    def _get(self, document):
        try:
            return self._weak_ids.get(document)
        except TypeError:
            return self._ids.get(id(document))
