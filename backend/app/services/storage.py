from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from app.core.config import get_settings


def archive_import(raw: bytes, filename: str, actor_id: str) -> dict:
    """Archive imported source evidence to Firebase Storage when a bucket is configured.

    Local/demo runs return checksum metadata without requiring Firebase.
    """
    checksum = sha256(raw).hexdigest()
    settings = get_settings()
    metadata = {
        "filename": filename,
        "bytes": len(raw),
        "sha256": checksum,
        "actor_id": actor_id,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "storage_uri": None,
    }
    if not settings.firebase_storage_bucket:
        return metadata
    try:
        from firebase_admin import storage

        from app.core.firebase_app import ensure_firebase_app

        ensure_firebase_app(settings)
        bucket = storage.bucket(settings.firebase_storage_bucket)
        safe_name = filename.replace("/", "_").replace("\\", "_")
        path = f"procurement-imports/{actor_id.replace(':','_')}/{checksum[:16]}-{safe_name}"
        blob = bucket.blob(path)
        blob.metadata = {"sha256": checksum, "actor_id": actor_id}
        blob.upload_from_string(raw, content_type="text/csv")
        metadata["storage_uri"] = f"gs://{settings.firebase_storage_bucket}/{path}"
        return metadata
    except Exception as exc:
        metadata["storage_error"] = str(exc)
        return metadata
