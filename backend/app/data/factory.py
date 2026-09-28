from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.data.repository import InMemoryRepository, Repository


@lru_cache
def get_repository() -> Repository:
    settings = get_settings()
    if settings.repository_backend.lower() == "firestore":
        from app.data.firestore_repository import FirestoreRepository
        return FirestoreRepository()
    return InMemoryRepository()


def reset_repository() -> Repository:
    get_repository.cache_clear()
    return get_repository()
