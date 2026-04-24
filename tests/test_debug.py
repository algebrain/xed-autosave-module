import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hadron_autosave.debug import DebugLogger


class DebugLoggerTest(unittest.TestCase):
    def test_debug_logger_is_silent_when_disabled(self):
        stream = io.StringIO()
        logger = DebugLogger(enabled=False, stream=stream)

        logger("scheduled autosave", document_id="doc-1", delay_ms=10_000)

        self.assertEqual(stream.getvalue(), "")

    def test_debug_logger_writes_short_messages_to_stderr(self):
        stream = io.StringIO()
        logger = DebugLogger(enabled=True, stream=stream)

        logger("scheduled autosave", document_id="doc-1", delay_ms=10_000)

        output = stream.getvalue()
        self.assertIn("scheduled autosave", output)
        self.assertIn("document_id=doc-1", output)
        self.assertIn("delay_ms=10000", output)

    def test_debug_logger_writes_to_file_when_path_is_set(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hadron-autosave.log"
            logger = DebugLogger(enabled=True, path=path)

            logger("saved unsaved document", document_id="doc-1", path="autosave.txt")

            output = path.read_text(encoding="utf-8")
            self.assertIn("saved unsaved document", output)
            self.assertIn("document_id=doc-1", output)
            self.assertIn("path=autosave.txt", output)

    def test_debug_logger_uses_hadron_default_log_path(self):
        with mock.patch.dict("os.environ", {"XED_AUTOSAVE_DEBUG_LOG": ""}):
            logger = DebugLogger(enabled=False)

        self.assertEqual(logger.path.name, "hadron-autosave.log")


if __name__ == "__main__":
    unittest.main()
