from __future__ import annotations

from typing import Any

from app.core.config import get_settings


class FirestoreRepository:
    """Thin Firestore adapter. Imported only in Firebase/Firestore deployments."""

    def __init__(self) -> None:
        try:
            from firebase_admin import firestore
        except ImportError as exc:
            raise RuntimeError("firebase-admin must be installed for FirestoreRepository") from exc

        from app.core.firebase_app import ensure_firebase_app

        ensure_firebase_app(get_settings())
        self.db = firestore.client()

    def list(self, collection: str) -> list[dict[str, Any]]:
        return [doc.to_dict() for doc in self.db.collection(collection).stream()]

    def get(self, collection: str, value: Any, key: str = "id") -> dict[str, Any] | None:
        if key == "id":
            snap = self.db.collection(collection).document(str(value)).get()
            return snap.to_dict() if snap.exists else None
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = list(self.db.collection(collection).where(filter=FieldFilter(key, "==", value)).limit(1).stream())
        return docs[0].to_dict() if docs else None

    def upsert(self, collection: str, record: dict[str, Any], key: str) -> dict[str, Any]:
        if key not in record:
            raise ValueError(f"record for {collection} is missing key {key}")
        self.db.collection(collection).document(str(record[key])).set(record, merge=True)
        return record

    def append(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        self.db.collection(collection).add(record)
        return record

    def delete(self, collection: str, value: Any, key: str = "id") -> bool:
        if key != "id":
            row = self.get(collection, value, key)
            if not row:
                return False
            doc_id = row.get("id") or row.get(key)
        else:
            doc_id = value
        self.db.collection(collection).document(str(doc_id)).delete()
        return True

    def insert_if_absent(self, collection: str, record: dict[str, Any], key: str) -> bool:
        """Append-only: `create()` is rejected by Firestore if the doc exists."""
        from google.api_core.exceptions import AlreadyExists

        if key not in record:
            raise ValueError(f"record for {collection} is missing key {key}")
        try:
            self.db.collection(collection).document(str(record[key])).create(record)
            return True
        except AlreadyExists:
            return False

    def write_batch(self, ops: list[tuple[str, str, dict[str, Any], str]]) -> None:
        """One atomic batch commit for all ops.

        Firestore batches cannot express "create if absent" conditionally, so
        append-only entries are checked first; an existing document is left
        untouched and the remaining ops still commit together.
        """
        batch = self.db.batch()
        for op, collection, record, key in ops:
            if key not in record:
                raise ValueError(f"record for {collection} is missing key {key}")
            ref = self.db.collection(collection).document(str(record[key]))
            if op == "upsert":
                batch.set(ref, record, merge=True)
            elif op == "insert_if_absent":
                if not ref.get().exists:
                    batch.set(ref, record)
            else:
                raise ValueError(f"unsupported batch op {op}")
        batch.commit()
