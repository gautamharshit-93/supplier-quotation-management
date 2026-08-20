"""
Storage abstraction layer.

STORAGE_BACKEND=local (default): files go to data/uploads, metadata/index
records go to a local JSON "database" file — works immediately, no cloud
account needed.

STORAGE_BACKEND=azure: swap in Azure Blob Storage (files) + Cosmos DB
(metadata) using the same function signatures — see azure_storage.py stub
below for what to fill in once you have credentials.

The rest of the app only calls the functions in this file, so switching
backends later does not require touching app.py or the analysis modules.
"""
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import config

_DB_FILE = config.DB_DIR / "records.json"


def _read_db() -> List[Dict]:
    if not _DB_FILE.exists():
        return []
    with open(_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_db(records: List[Dict]) -> None:
    with open(_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def save_uploaded_file(file_bytes: bytes, filename: str) -> str:
    """Saves a raw uploaded file to storage (local disk or, later, Blob) and
    returns the path/URI it was stored at."""
    dest = config.UPLOADS_DIR / filename
    with open(dest, "wb") as f:
        f.write(file_bytes)
    return str(dest)


def save_record(record: Dict) -> Dict:
    """
    Persists a processed document's metadata (parsed + extracted fields) so
    it can be listed/queried later, mimicking a Cosmos DB container.
    """
    records = _read_db()
    record = dict(record)  # avoid mutating caller's dict
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    records.append(record)
    _write_db(records)
    return record


def list_records(record_type: Optional[str] = None) -> List[Dict]:
    records = _read_db()
    if record_type:
        records = [r for r in records if r.get("record_type") == record_type]
    return records


def delete_all_records() -> None:
    _write_db([])
    if config.UPLOADS_DIR.exists():
        for f in config.UPLOADS_DIR.iterdir():
            if f.is_file():
                f.unlink()
