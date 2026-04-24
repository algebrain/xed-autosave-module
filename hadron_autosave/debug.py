import os
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_DEBUG_LOG = Path.home() / ".xed" / "autosave" / "hadron-autosave.log"


class DebugLogger:
    def __init__(self, enabled=None, stream=None, path=None):
        self.enabled = _env_enabled() if enabled is None else enabled
        self.stream = stream
        self.path = _env_path() if path is None else Path(path)

    def __call__(self, message, **fields):
        if not self.enabled:
            return

        suffix = "".join(f" {key}={value}" for key, value in fields.items())
        timestamp = datetime.now().isoformat(timespec="seconds")
        line = f"{timestamp} [hadron-autosave] {message}{suffix}\n"

        if self.stream is not None:
            self.stream.write(line)
            self.stream.flush()
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _env_enabled():
    value = os.environ.get("XED_AUTOSAVE_DEBUG", "")
    return value.lower() in ("1", "true", "yes", "on")


def _env_path():
    value = os.environ.get("XED_AUTOSAVE_DEBUG_LOG", "")
    return Path(value).expanduser() if value else DEFAULT_DEBUG_LOG


debug = DebugLogger()
