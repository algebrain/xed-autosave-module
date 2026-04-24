import json
import os
import re
import hashlib
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

    def backup_path_for_existing(self, file_path):
        digest = hashlib.sha256(str(Path(file_path).resolve()).encode("utf-8")).hexdigest()
        return self.root / "backups" / f"file-{digest}.bak"

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

    def ensure_existing_file_backup(self, document_id, file_path):
        file_path = Path(file_path)
        if not file_path.is_file():
            raise OSError(f"Cannot back up non-regular file: {file_path}")

        existing = self.backup_for_existing(file_path)
        if existing is not None:
            return existing

        self.root.mkdir(parents=True, exist_ok=True)
        backup_path = self.backup_path_for_existing(file_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(backup_path, file_path.read_bytes())

        stat = file_path.stat()
        entry = {
            "id": _safe_filename_part(hashlib.sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()),
            "document_id": document_id,
            "file_path": str(file_path),
            "backup_path": str(backup_path.relative_to(self.root)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "original_mtime_ns": stat.st_mtime_ns,
            "original_size": stat.st_size,
        }

        index = self.load_index()
        index["backups"] = [
            backup for backup in index["backups"]
            if backup.get("file_path") != str(file_path)
        ]
        index["backups"].append(entry)
        self._save_index(index)
        return self._backup_entry_with_path(entry)

    def backup_for_existing(self, file_path):
        file_path = str(Path(file_path))
        for backup in self.load_index()["backups"]:
            if backup.get("file_path") != file_path:
                continue
            backup_path = backup.get("backup_path")
            if not backup_path:
                continue
            path = self.root / backup_path
            if not path.exists():
                continue
            return self._backup_entry_with_path(backup)
        return None

    def active_existing_file_backups(self):
        entries = []
        for backup in self.load_index()["backups"]:
            file_path = backup.get("file_path")
            backup_path = backup.get("backup_path")
            if not file_path or not backup_path:
                continue
            path = self.root / backup_path
            if not path.exists():
                continue
            entries.append(self._backup_entry_with_path(backup))
        return entries

    def restore_existing_file_backup(self, file_path):
        text = self.read_existing_file_backup(file_path)
        self.delete_existing_file_backup(file_path)
        return text

    def read_existing_file_backup(self, file_path):
        backup = self.backup_for_existing(file_path)
        if backup is None:
            raise FileNotFoundError(f"No backup for {file_path}")
        return backup["path"].read_text(encoding="utf-8")

    def delete_existing_file_backup(self, file_path):
        file_path = str(Path(file_path))
        index = self.load_index()
        kept_backups = []
        removed_paths = []

        for backup in index["backups"]:
            if backup.get("file_path") == file_path:
                backup_path = backup.get("backup_path")
                if backup_path:
                    removed_paths.append(self.root / backup_path)
            else:
                kept_backups.append(backup)

        if len(kept_backups) == len(index["backups"]):
            return False

        index["backups"] = kept_backups
        self._save_index(index)

        for path in removed_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        return True

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
            return _empty_index()

        try:
            with self.index_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return _empty_index()

        if not isinstance(data, dict):
            return _empty_index()
        documents = data.get("documents")
        if not isinstance(documents, list):
            documents = []
        backups = data.get("backups")
        if not isinstance(backups, list):
            backups = []
        return {"documents": documents, "backups": backups}

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
        index = {
            "documents": index.get("documents") if isinstance(index.get("documents"), list) else [],
            "backups": index.get("backups") if isinstance(index.get("backups"), list) else [],
        }
        text = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True)
        _atomic_write_text(self.index_path, text + "\n")

    def _backup_entry_with_path(self, entry):
        path = self.root / entry["backup_path"]
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        result = dict(entry)
        result["path"] = path
        result["modified_at"] = modified_at.isoformat()
        result["modified_at_display"] = modified_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        return result


def _empty_index():
    return {"documents": [], "backups": []}


def _safe_filename_part(value):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip(".-")
    return safe or "document"


def _atomic_write_text(path, text):
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


def _atomic_write_bytes(path, data):
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("wb") as handle:
        handle.write(data)
    os.replace(tmp_path, path)
