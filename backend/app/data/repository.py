from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any, Protocol


class Repository(Protocol):
    def list(self, collection: str) -> list[dict[str, Any]]: ...
    def get(self, collection: str, value: Any, key: str = "id") -> dict[str, Any] | None: ...
    def upsert(self, collection: str, record: dict[str, Any], key: str) -> dict[str, Any]: ...
    def append(self, collection: str, record: dict[str, Any]) -> dict[str, Any]: ...
    def delete(self, collection: str, value: Any, key: str = "id") -> bool: ...

    def insert_if_absent(self, collection: str, record: dict[str, Any], key: str) -> bool:
        """Append-only write. Returns False, changing nothing, if the key exists."""
        ...

    def write_batch(self, ops: list[tuple[str, str, dict[str, Any], str]]) -> None:
        """Apply (op, collection, record, key) tuples atomically where the store supports it.

        op is "upsert" or "insert_if_absent". Firestore applies these in one
        batch commit; the in-memory store applies them under a single lock.
        """
        ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._lock = RLock()

    def list(self, collection: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._data.get(collection, []))

    def get(self, collection: str, value: Any, key: str = "id") -> dict[str, Any] | None:
        with self._lock:
            for row in self._data.get(collection, []):
                if str(row.get(key)) == str(value):
                    return deepcopy(row)
        return None

    def upsert(self, collection: str, record: dict[str, Any], key: str) -> dict[str, Any]:
        if key not in record:
            raise ValueError(f"record for {collection} is missing key {key}")
        with self._lock:
            rows = self._data.setdefault(collection, [])
            for i, row in enumerate(rows):
                if str(row.get(key)) == str(record[key]):
                    rows[i] = deepcopy(record)
                    return deepcopy(record)
            rows.append(deepcopy(record))
        return deepcopy(record)

    def append(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._data.setdefault(collection, []).append(deepcopy(record))
        return deepcopy(record)

    def delete(self, collection: str, value: Any, key: str = "id") -> bool:
        with self._lock:
            rows = self._data.get(collection, [])
            before = len(rows)
            self._data[collection] = [row for row in rows if str(row.get(key)) != str(value)]
            return len(self._data[collection]) < before

    def insert_if_absent(self, collection: str, record: dict[str, Any], key: str) -> bool:
        if key not in record:
            raise ValueError(f"record for {collection} is missing key {key}")
        with self._lock:
            rows = self._data.setdefault(collection, [])
            if any(str(row.get(key)) == str(record[key]) for row in rows):
                return False
            rows.append(deepcopy(record))
            return True

    def write_batch(self, ops: list[tuple[str, str, dict[str, Any], str]]) -> None:
        with self._lock:
            for op, collection, record, key in ops:
                if op == "upsert":
                    self.upsert(collection, record, key)
                elif op == "insert_if_absent":
                    self.insert_if_absent(collection, record, key)
                else:
                    raise ValueError(f"unsupported batch op {op}")

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
