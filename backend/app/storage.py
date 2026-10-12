import json, threading
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from .core.config import get_settings

def now_iso():
    return datetime.now(timezone.utc).isoformat()

class LocalStore:
    """File-backed JSON storage for a single-user local demonstration."""
    names = ["tickets","knowledge","chats","automation_actions","software_requests","audit","servicenow"]
    def __init__(self, base: Path):
        self.base = base
        self.base.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        for name in self.names:
            if not self._path(name).exists():
                self._path(name).write_text("[]", encoding="utf-8")
    def _path(self, name):
        if name not in self.names: raise ValueError("Unknown collection")
        return self.base / f"{name}.json"
    def all(self, name):
        with self.lock: return json.loads(self._path(name).read_text(encoding="utf-8"))
    def insert(self, name, item):
        with self.lock:
            rows = self.all(name); item = dict(item)
            item.setdefault("_id", str(uuid4())); item.setdefault("created_at", now_iso())
            rows.append(item); self._path(name).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
            return item
    def get(self, name, item_id, field="id"):
        return next((x for x in self.all(name) if str(x.get(field, x.get("_id"))) == str(item_id)), None)
    def update(self, name, item_id, changes, field="id"):
        with self.lock:
            rows = self.all(name)
            for row in rows:
                if str(row.get(field, row.get("_id"))) == str(item_id):
                    row.update(changes); row["updated_at"] = now_iso()
                    self._path(name).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
                    return row
        return None

class MongoStore:
    """Optional Atlas implementation; explicit configuration never silently falls back."""
    names = LocalStore.names
    def __init__(self, uri, database):
        try: from pymongo import MongoClient
        except ImportError as exc: raise RuntimeError("Install pymongo to use STORAGE_MODE=mongodb") from exc
        if not uri: raise RuntimeError("MONGODB_URI is required")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=4000)
        self.client.admin.command("ping"); self.db = self.client[database]
    def all(self, name): return list(self.db[name].find({}, {"_id":0}))
    def insert(self, name, item):
        item = dict(item); item.setdefault("id", str(uuid4())); item.setdefault("created_at", now_iso())
        self.db[name].insert_one(item); return item
    def get(self, name, item_id, field="id"): return self.db[name].find_one({field:item_id},{"_id":0})
    def update(self, name, item_id, changes, field="id"):
        self.db[name].update_one({field:item_id},{"$set":{**changes,"updated_at":now_iso()}})
        return self.get(name,item_id,field)

_store = None
def get_store():
    global _store
    if _store is None:
        s = get_settings()
        _store = MongoStore(s.mongodb_uri,s.mongodb_database) if s.storage_mode.lower()=="mongodb" else LocalStore(s.data_path)
    return _store
def reset_store_for_tests():
    global _store
    _store = None
