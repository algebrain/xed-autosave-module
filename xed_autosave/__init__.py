"""Xed autosave plugin package."""

try:
    from .window_plugin import XedAutosavePlugin
except (ImportError, ValueError):
    XedAutosavePlugin = None

__all__ = ["XedAutosavePlugin"]
