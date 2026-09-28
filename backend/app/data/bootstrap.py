from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from app.contracts.models import (
    DemandForecast, GoodsReceipt, PurchaseOrder, ReorderNeed, SafetyStockTarget,
    Supplier, SupplierInvoice, SupplierPerformance, SupplierQuote,
)
from app.contracts.shared import InventoryPosition
from app.core.config import get_settings
from app.data.output_repository import OutputRepository
from app.data.repository import Repository
from app.services.data_quality import validate_rows
from app.services.imports import import_records

# Operational collections Procurement owns or reads. Loaded as plain records.
OPERATIONAL_SEED = {
    "suppliers.csv": ("suppliers", Supplier, "supplier_id"),
    "supplier_quotes.csv": ("supplier_quotes", SupplierQuote, "quote_id"),
    "supplier_performance.csv": ("supplier_performance", SupplierPerformance, "performance_id"),
    "purchase_orders.csv": ("purchase_orders", PurchaseOrder, "po_id"),
    "goods_receipts.csv": ("goods_receipts", GoodsReceipt, "receipt_id"),
    "invoices.csv": ("invoices", SupplierInvoice, "invoice_id"),
}

# Shared read-only context. Procurement never writes these in production; the
# fixtures exist so the shared shape is present locally.
SHARED_CONTEXT_SEED = {
    "products.csv": ("products", None, "product_id"),
    "inventory_snapshots.csv": ("inventory_snapshots", None, "snapshot_id"),
    "inventory_movements.csv": ("inventory_movements", None, "movement_id"),
}

# Upstream published contracts. These are NOT stored as Procurement collections;
# they are projected into agent_outputs/agent_state on behalf of their agents.
UPSTREAM_SEED = {
    "demand_forecasts.csv": ("D4", DemandForecast),
    "inventory_positions.csv": ("I1", InventoryPosition),
    "reorder_needs.csv": ("I2", ReorderNeed),
    "safety_stock_targets.csv": ("I3", SafetyStockTarget),
}


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def seed_upstream_contracts(
    repo: Repository, agent_id: str, rows: list[dict], model: Type[BaseModel], *, stamp_now: bool = False
) -> dict:
    """Validate rows against the upstream contract and publish them as that agent.

    `stamp_now` is for synthetic demo fixtures, which represent "the upstream
    agent published this just now". Real imports keep the file's own
    `generated_at` so freshness enforcement sees genuine provenance.
    """
    valid, errors, duplicates = validate_rows(rows, model, "product_id")
    outputs = OutputRepository(repo)
    now = datetime.now(timezone.utc)
    for record in valid:
        if stamp_now:
            record["generated_at"] = now.isoformat()
        outputs.seed_upstream_contract(
            agent_id, record["product_id"], record,
            confidence=float(record.get("confidence", 1.0) or 1.0),
            generated_at=now if stamp_now else model.model_validate(record).generated_at,
            source_version=str(record.get("source_version", "external")),
        )
    return {"agent_id": agent_id, "published": len(valid), "rejected": len(errors), "duplicate_ids": duplicates, "errors": errors}


def bootstrap_sample_data(repo: Repository, sample_dir: Path | None = None) -> dict[str, dict]:
    sample_dir = sample_dir or get_settings().sample_data_dir
    summary: dict[str, dict] = {}

    for filename, (collection, model, key) in OPERATIONAL_SEED.items():
        path = sample_dir / filename
        if not path.exists():
            continue
        result = import_records(repo, collection, _read_csv(path), model, key)
        summary[collection] = result.model_dump(mode="json")

    for filename, (collection, _, key) in SHARED_CONTEXT_SEED.items():
        path = sample_dir / filename
        if not path.exists():
            continue
        rows = _read_csv(path)
        for row in rows:
            if row.get(key):
                repo.upsert(collection, row, key)
        summary[collection] = {"collection": collection, "imported": len(rows)}

    # DEV/TEST COMPATIBILITY ONLY. In the shared system Demand and Inventory
    # publish these contracts; Procurement must not stand in for them.
    if get_settings().allow_upstream_fixtures:
        for filename, (agent_id, model) in UPSTREAM_SEED.items():
            path = sample_dir / filename
            if not path.exists():
                continue
            summary[f"agent_state:{agent_id}"] = seed_upstream_contracts(
                repo, agent_id, _read_csv(path), model, stamp_now=True,
            )
    else:
        summary["agent_state"] = {"skipped": "upstream fixtures disabled (ALLOW_UPSTREAM_FIXTURES=false)"}

    return summary
