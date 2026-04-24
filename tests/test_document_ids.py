import unittest

from xed_autosave.document_ids import DocumentIds


class DocumentIdsTest(unittest.TestCase):
    def test_returns_same_id_for_same_document_object(self):
        ids = DocumentIds()
        document = object()

        first = ids.get(document)
        second = ids.get(document)

        self.assertEqual(second, first)

    def test_forget_removes_document_id(self):
        ids = DocumentIds()
        document = object()
        first = ids.get(document)

        ids.forget(document)
        second = ids.get(document)

        self.assertNotEqual(second, first)


if __name__ == "__main__":
    unittest.main()
