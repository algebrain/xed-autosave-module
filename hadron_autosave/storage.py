import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_AUTOSAVE_DIR = Path.home() / ".xed" / "hadron-autosave"


class AutosaveStorage:
    def __init__(self, root=DEFAULT_AUTOSAVE_DIR):
        self.root = Path(root)
        self.index_path = self.root / "index.json"

    def path_for_unsaved(self, document_id, title):
        safe_id = _safe_filename_part(document_id)
        return self.root / f"unsaved-{safe_id}.txt"

    def save_unsaved(self, document_id, title, text):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for_unsaved(document_id, title)
        _atomic_write_text(path, text)

        index = self.load_index()
        documents = [
            document for document in index["documents"]
            if document.get("id") != document_id
        ]
        documents.append({
            "id": document_id,
            "title": title,
            "path": path.name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        index["documents"] = documents
        self._save_index(index)
        return path

    def remove(self, document_id):
        index = self.load_index()
        index["documents"] = [
            document for document in index["documents"]
            if document.get("id") != document_id
        ]
        self._save_index(index)

    def delete(self, document_id):
        index = self.load_index()
        kept_documents = []
        removed_paths = []

        for document in index["documents"]:
            if document.get("id") == document_id:
                path_name = document.get("path")
                if path_name:
                    removed_paths.append(self.root / path_name)
            else:
                kept_documents.append(document)

        index["documents"] = kept_documents
        self._save_index(index)

        for path in removed_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def load_index(self):
        if not self.index_path.exists():
            return {"documents": []}

        try:
            with self.index_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {"documents": []}

        if not isinstance(data, dict):
            return {"documents": []}
        documents = data.get("documents")
        if not isinstance(documents, list):
            return {"documents": []}
        return {"documents": documents}

    def restore_entries(self):
        entries = []
        for document in self.load_index()["documents"]:
            path_name = document.get("path")
            if not path_name:
                continue
            path = self.root / path_name
            if not path.exists():
                continue
            entries.append({
                "id": document.get("id"),
                "title": document.get("title") or "Untitled Document",
                "path": path,
                "text": path.read_text(encoding="utf-8"),
            })
        return entries

    def _save_index(self, index):
        self.root.mkdir(parents=True, exist_ok=True)
        text = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True)
        _atomic_write_text(self.index_path, text + "\n")


def _safe_filename_part(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip(".-")
    return safe or "document"


def _atomic_write_text(path, text):
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)
