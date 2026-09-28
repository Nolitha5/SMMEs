from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "Retail Procurement Agent")
    app_env: str = os.getenv("APP_ENV", "development")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    auth_mode: str = os.getenv("AUTH_MODE", "demo")
    repository_backend: str = os.getenv("REPOSITORY_BACKEND", "memory")
    firebase_project_id: str | None = os.getenv("FIREBASE_PROJECT_ID") or None
    firebase_storage_bucket: str | None = os.getenv("FIREBASE_STORAGE_BUCKET") or None
    firebase_credentials_json: str | None = os.getenv("FIREBASE_CREDENTIALS_JSON") or None
    cors_origins: list[str] = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
    demo_manager_email: str = os.getenv("DEMO_MANAGER_EMAIL", "manager@example.com")
    recommendation_ttl_hours: int = int(os.getenv("RECOMMENDATION_TTL_HOURS", "24"))
    supplier_quote_ttl_days: int = int(os.getenv("SUPPLIER_QUOTE_TTL_DAYS", "30"))
    max_po_value_without_second_review: float = float(os.getenv("MAX_PO_VALUE_WITHOUT_SECOND_REVIEW", "25000"))
    # DEV/TEST COMPATIBILITY ONLY. When true, Procurement may seed D4/I1/I2/I3
    # contracts into agent_state on the upstream agents' behalf so it can run
    # standalone. Must be false in the shared system, where Demand and
    # Inventory are the only producers of those contracts.
    allow_upstream_fixtures: bool = os.getenv("ALLOW_UPSTREAM_FIXTURES", "true").strip().lower() in {"1", "true", "yes"}

    @property
    def root_dir(self) -> Path:
        return Path(__file__).resolve().parents[3]

    @property
    def sample_data_dir(self) -> Path:
        preferred = self.root_dir / "sample_data"
        return preferred if preferred.exists() else Path("/sample_data")

    def firebase_credentials(self) -> dict | None:
        if not self.firebase_credentials_json:
            return None
        raw = self.firebase_credentials_json.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        p = Path(raw)
        if p.exists():
            return json.loads(p.read_text())
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
