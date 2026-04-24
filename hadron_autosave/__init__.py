"""Hadron Autosave plugin package."""

try:
    from .window_plugin import HadronAutosavePlugin
except (ImportError, ValueError):
    HadronAutosavePlugin = None

__all__ = ["HadronAutosavePlugin"]
