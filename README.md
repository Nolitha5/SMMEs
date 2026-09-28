# Inventory Management Agent — I1 + I2 + I3 + I4 + I5

Offline inventory monitoring, reorder point, and safety-stock system built with
Python and FastAPI.  No internet connection, database, LLM, or external APIs
required.

Part of the **25-Agent SME/Spaza Operations System** — Inventory Domain.

---

## Agents in this module

| Agent | Responsibility | Output contract |
|-------|---------------|----------------|
| **I1** Stock Monitor | Current stock position, stock health, alerts | `InventoryPosition` |
| **I2** Reorder Point | Reorder decision, reorder point, suggested qty | `ReorderNeed` |
| **I3** Safety Stock | Safety-stock target from forecast uncertainty + supplier reliability | `SafetyStockTarget` |
| **I4** Expiry & Slow-Stock | Expiry risk, slow stock, dead stock, excess stock | `StockRiskAlert` |
| **I5** Inventory Exception | Negative stock, reconciliation mismatches, large adjustments, suspicious movements | `InventoryException` |

---

## Project Structure

```
Inventory Management Agent/
├── app/
│   ├── main.py                         # FastAPI app entry point
│   ├── models/
│   │   ├── product.py                  # Product dataclass
│   │   ├── stock_level.py              # InventorySnapshot / StockLevel
│   │   ├── transaction.py              # Transaction + MovementType
│   │   ├── alert.py                    # Alert + AlertSeverity + AlertType
│   │   ├── inventory_position.py       # I1 output contract
│   │   ├── demand_forecast.py          # DemandForecast (D4 contract)
│   │   ├── supplier.py                 # Supplier + SupplierPerformance
│   │   ├── reorder_need.py             # I2 output contract
│   │   ├── agent_result.py             # Shared AgentResult contract
│   │   ├── safety_stock_target.py      # I3 output contract
│   │   ├── stock_risk_alert.py         # I4 output contract
│   │   └── inventory_exception.py      # I5 output contract ← NEW
│   ├── services/
│   │   ├── data_loader.py              # CSV/JSON file reader
│   │   ├── stock_monitor.py            # I1 engine
│   │   ├── reorder_point.py            # I2 engine
│   │   ├── safety_stock.py             # I3 engine
│   │   ├── stock_risk.py               # I4 engine
│   │   └── inventory_exception.py      # I5 engine ← NEW
│   └── routers/
│       ├── dashboard.py                # GET /dashboard
│       ├── products.py                 # GET /products
│       ├── stock.py                    # GET /stock
│       ├── alerts.py                   # GET /alerts
│       ├── reorders.py                 # GET /reorders
│       ├── safety_stock.py             # GET /api/safety-stock
│       ├── stock_risk.py               # GET /api/stock-risk
│       ├── inventory_exceptions.py      # GET /api/inventory-exceptions ← NEW
│       └── transactions.py             # GET /transactions
├── data/
│   ├── products.csv
│   ├── inventory_snapshots.csv
│   ├── inventory_movements.csv
│   ├── transactions.csv
│   ├── demand_forecasts.json           # D4 forecast contract (read-only)
│   ├── suppliers.csv
│   ├── supplier_performance.csv
│   ├── promotions.csv
│   ├── local_events.csv
│   └── config.json                     # Thresholds
├── tests/
│   ├── test_stock_monitor.py           # I1 tests (53 tests)
│   ├── test_reorder_point.py           # I2 tests (60 tests)
│   └── test_safety_stock.py            # I3 tests (77 tests)
├── requirements.txt
└── run.bat
```

---

## Quick Start

### 1. Install Python 3.10+

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the server

**Windows:** Double-click `run.bat`

**Command line:**
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open the API

| URL | Description |
|-----|-------------|
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/dashboard | KPI summary |
| http://localhost:8000/alerts | All active alerts |
| http://localhost:8000/alerts/critical | Critical alerts only |
| http://localhost:8000/reorders | I2 reorder decisions |
| http://localhost:8000/reorders/urgent | Urgent reorders |
| http://localhost:8000/api/safety-stock | I3 safety-stock targets |
| http://localhost:8000/api/stock-risk | I4 stock risk flags |
| http://localhost:8000/api/inventory-exceptions | I5 inventory exceptions |
| http://localhost:8000/stock | Full stock summary |
| http://localhost:8000/products | Product catalogue |
| http://localhost:8000/transactions | Transaction history |

---

## API Endpoints

### I5 Inventory Exceptions (NEW)
- `GET /api/inventory-exceptions` — All detected inventory exceptions
- `GET /api/inventory-exceptions/{product_id}` — Exceptions for one product

### I4 Expiry & Slow-Stock
- `GET /api/stock-risk` — All products with active stock risk flags
- `GET /api/stock-risk/{product_id}` — Risk flags for one product

### I3 Safety Stock
- `GET /api/safety-stock` — Safety-stock targets for all products
- `GET /api/safety-stock/{product_id}` — Safety-stock target for one product

### I2 Reorder Point
- `GET /reorders` — All I2 reorder-point decisions
- `GET /reorders/urgent` — Products where reorder is needed
- `GET /reorders/insufficient` — Products missing forecast or supplier data
- `GET /reorders/{product_id}` — I2 decision for one product

### I1 Stock Monitor
- `GET /stock` — Stock summary for all products (`?store_id=S1`)
- `GET /stock/{product_id}` — Stock detail for one product
- `GET /alerts` — All active alerts
- `GET /alerts/critical` — Critical alerts only
- `GET /dashboard` — KPI overview

### Products / Transactions
- `GET /products` — Product catalogue
- `GET /transactions` — Inventory movement history

---

## I3 — Safety Stock Agent

### What it does

I3 answers one question: **"How much safety stock should we maintain for this
product?"**

It combines demand-forecast uncertainty with supplier lead-time and reliability
to produce a statistically-grounded safety-stock target.  The output is used
by I2 to set a higher reorder point when needed.

I3 does NOT answer "Should we reorder?" (I2), "Which supplier?" (Procurement),
or execute any purchase.

### Inputs

| Input | Source | Field(s) used |
|-------|--------|---------------|
| **D4 DemandForecast** | `data/demand_forecasts.json` | `expected_qty`, `horizon`, `upper_bound`, `lower_bound`, `confidence` |
| **Supplier lead time** | `data/suppliers.csv` | `lead_time_days` |
| **Supplier reliability** | `data/suppliers.csv` | `reliability_score` (0–1) |
| **R3 LeadTimeRisk** *(future)* | Procurement team contract | `lead_time_risk_adjustment` optional parameter |

> **Current limitation:** The Procurement team's R3 LeadTimeRisk contract is not
> yet available in the local MVP.  I3 uses `reliability_score` from
> `suppliers.csv` as the available risk signal.  When R3 is ready, pass its
> buffer value via `lead_time_risk_adjustment` in `evaluate_product()` — no
> formula rewrite is needed.

### Formula (I3-v1)

```
Step 1  expected_daily_demand = expected_qty / horizon

Step 2  horizon_std = (upper_bound − lower_bound) / 4
        # treats forecast interval as ≈ ±2σ

Step 3  daily_std = horizon_std / √horizon
        # converts horizon uncertainty to daily uncertainty

Step 4  lead_time_demand_std = daily_std × √lead_time_days
        # uncertainty over the full replenishment lead time

Step 5  z = 1.65  (for 95% service level, configurable: 0.90→1.28, 0.99→2.33)

Step 6  reliability_factor = 1 + (1 − clamp(reliability_score, 0, 1))
        # perfect reliability (1.0) → factor 1.00
        # 90% reliability         → factor 1.10
        # 80% reliability         → factor 1.20

Step 7  raw_safety_stock = z × lead_time_demand_std × reliability_factor
        # optional: + lead_time_risk_adjustment  (R3 hook, default 0.0)

Step 8  safety_stock = ceil(raw_safety_stock)   # integer units, never < 0
```

**MVP assumption:** step 3 divides horizon std by √horizon to approximate daily
variance.  This is a lightweight single-product, single-period assumption
appropriate for the MVP; a richer multi-SKU covariance model can replace it
without changing the interface.

### Output contract — `SafetyStockTarget`

```python
SafetyStockTarget(
    product_id           = "P001",
    safety_stock         = 4,            # integer, never negative
    expected_daily_demand= 3.2857,
    forecast_uncertainty = 0.7559,       # daily_std
    lead_time_days       = 2,
    reliability_score    = 0.93,
    reliability_factor   = 1.07,
    service_level        = 0.95,
    z_score              = 1.65,
    raw_safety_stock     = 2.636,
    confidence           = "MEDIUM",
    reason               = "Safety stock of 4 units calculated from ...",
    formula_version      = "I3-v1",
    generated_at         = "2026-09-16T...",
)
```

### Relationship with I2

```
D4 DemandForecast
        ↓
       I3  ──── SafetyStockTarget
        ↓                ↓
       I2  ←─── safety_stock (integer)
        ↓
   ReorderNeed
        ↓
       R4
        ↓
PurchaseRecommendation
```

**I2 already accepts a `safety_stock` parameter.**  Pass I3's output:

```python
i3_target = i3_agent.evaluate_product(product_id, category)
need = i2_agent.evaluate_product(position, safety_stock=float(i3_target[0].safety_stock))
```

When I3 is not available, I2 defaults to `safety_stock=0.0` (conservative
baseline labelled `I3_PLACEHOLDER_ZERO`).

### Future R3 integration

```python
# When Procurement team's R3 LeadTimeRisk is available:
r3_signal = r3_agent.get_lead_time_risk(product_id)
target = i3_agent.evaluate_product(
    product_id,
    category,
    lead_time_risk_adjustment=r3_signal.buffer_units,  # no formula rewrite
)
```

### Error handling

| Condition | Behaviour |
|-----------|-----------|
| Missing forecast | Returns `None` (safe-failure, no invented value) |
| `horizon <= 0` | `ValueError` |
| `upper_bound < lower_bound` | `ValueError` |
| `lead_time_days < 0` | `ValueError` |
| Missing supplier | Returns `None` (safe-failure) |
| Missing reliability score | Falls back to `1.0` (perfect), noted in rationale |
| `upper_bound == lower_bound` | Zero uncertainty → safety stock may be 0 (valid) |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Expected: **336 tests passing** (53 I1 + 60 I2 + 77 I3 + 65 I4 + 81 I5)

---

## Architecture Notes

- **Offline-first**: all data read from local CSV/JSON files at startup
- **No database**: in-memory structures built from files on load
- **No LLM or AI**: pure deterministic rule-based logic
- **Modular**: models / services / routers fully separated
- **Stateless API**: each request reads from the in-memory cache
- **Firestore-ready**: agent output contracts contain IDs, timestamps,
  confidence, risk level, and rule version — compatible with the team's
  planned Firestore exchange layer (integration is a separate phase)

---

## I4 — Expiry & Slow-Stock Agent

### What it does

I4 answers one question: **"Which products are at risk of expiry, stagnation, or excessive accumulation?"**

It classifies each product's current inventory into one or more risk categories and flags them with severity levels (HIGH / MEDIUM / LOW).  The output is used by warehouse managers and by future exception-escalation agents (I5) to take corrective action.

I4 does NOT reorder, does NOT recommend a supplier, and does NOT modify any stock record.

### Risk categories

| Risk type | What it means |
|-----------|--------------|
| `EXPIRY_RISK` | Stock will expire before it can be sold (based on inventory age vs shelf life) |
| `SLOW_STOCK` | Days of cover 30–60: stock is moving slowly and may accumulate |
| `DEAD_STOCK` | No sales at all in the observation window but stock is still on hand |
| `EXCESS_STOCK` | Days of cover > 60: stock exceeds ~2 months of demand |

A single product can carry multiple risk flags simultaneously (e.g. DEAD_STOCK + EXPIRY_RISK).

### Inputs

| Input | Source | Field(s) used |
|-------|--------|---------------|
| **Products** | `data/products.csv` | `product_id`, `shelf_life_days` |
| **Inventory snapshots** | `data/inventory_snapshots.csv` | `stock_on_hand`, `reserved`, `damaged` (most-recent snapshot per product) |
| **Transactions** | `data/transactions.csv` | `qty` summed over observation window (sales velocity) |
| **Inventory movements** | `data/inventory_movements.csv` | Most-recent `RECEIPT` date (inventory age proxy) |

### Thresholds (I4-v1)

| Threshold | Value |
|-----------|-------|
| Observation window | 30 days |
| Slow stock (days of cover) | > 30 days |
| Excess stock (days of cover) | > 60 days |
| Expiry risk HIGH | ≤ 7 days to expiry |
| Expiry risk MEDIUM | ≤ 14 days to expiry |
| Dead stock velocity | = 0 units/day over observation window |

### Formulas (I4-v1)

```
available_stock  = stock_on_hand − reserved − damaged
sales_velocity   = units_sold_in_window / observation_days
days_of_cover    = available_stock / sales_velocity   (None when velocity = 0)
inventory_age    = today − most_recent_RECEIPT_date   (days)
days_to_expiry   = shelf_life_days − inventory_age    (None when shelf_life unknown)

Dead stock   : available_stock > 0 AND sales_velocity == 0
Slow stock   : days_of_cover > 30 AND <= 60
Excess stock : days_of_cover > 60
Expiry HIGH  : days_to_expiry <= 7
Expiry MEDIUM: days_to_expiry <= 14  (and > 7)
```

**MVP assumption — inventory age:** The snapshot CSV does not store the arrival date of the current batch. I4 uses the most-recent `RECEIPT` movement from `inventory_movements.csv` as a proxy. This is accurate for single-batch (FIFO) inventory. Multi-batch tracking is a future enhancement.

### Dead-stock severity

| Available stock | Severity |
|-----------------|----------|
| ≥ 10 units | HIGH |
| < 10 units | MEDIUM |

### Output contract — `StockRiskAlert`

```python
StockRiskAlert(
    product_id         = "P001",
    risk_type          = "EXPIRY_RISK",   # or SLOW_STOCK / DEAD_STOCK / EXCESS_STOCK
    severity           = "HIGH",          # HIGH / MEDIUM / LOW
    available_stock    = 12.0,
    sales_velocity     = 4.1,            # units/day (None for dead stock)
    days_of_cover      = 2.9,            # None when velocity = 0
    inventory_age_days = 4.0,
    shelf_life_days    = 3,
    days_to_expiry     = -1.0,           # negative = already expired
    reason             = "Expiry risk HIGH: ...",
    evidence_refs      = ["products.csv:P001", "inventory_snapshots.csv:P001", ...],
    confidence         = 0.9,
    generated_at       = "2026-09-21T...",
    formula_version    = "I4-v1",
)
```

Each `StockRiskAlert` is also wrapped in an `AgentResult` (shared contract) with:
- `agent_id = "I4"`
- `action_type = "FLAG_STOCK_RISK"`
- `entity_type = "PRODUCT"`
- `requires_approval = False`

### API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/stock-risk` | All products with at least one active risk flag |
| `GET /api/stock-risk/{product_id}` | Risk flags for a single product (404 if unknown; empty list if no risk) |

### Relationship with I1 / I2

```
I1 (stock levels + alerts)         I4 (expiry + slow-stock risk)
        ↓                                     ↓
   InventoryPosition               StockRiskAlert + AgentResult
        ↓                                     ↓
       I2 (reorder decision)           I5 (exception escalation — planned)
```

I4 reads the same raw CSV files as I1; it does NOT call I1's API endpoints.  The `available_stock` formula is identical (`stock_on_hand − reserved − damaged`) but computed independently within the I4 boundary.

### Error handling

| Condition | Behaviour |
|-----------|-----------|
| Product not in products.csv | `get_alerts_for_product()` returns `None` (→ HTTP 404) |
| No snapshot found for product | `available_stock = 0.0` (safe-fail, no invented value) |
| No RECEIPT movement found | `inventory_age_days = None`; expiry risk not evaluated |
| `shelf_life_days` missing/null | Expiry risk not evaluated |
| No transactions in window | `sales_velocity = 0` → dead-stock check applies |

### Future enhancements

- **Multi-batch FIFO:** Track each receipt separately; compute weighted-average age.
- **Promotion-aware velocity:** Exclude promotional-period transactions from baseline velocity.
- **Firestore integration:** Persist `StockRiskAlert` + `AgentResult` to the team's Firestore exchange layer. The contracts are Firestore-ready (IDs, timestamps, rule version included).
- **I5 escalation:** Pass HIGH-severity alerts to the planned I5 exception-escalation agent.

---

## I5 — Inventory Exception Agent

### What it does

I5 answers one question: **"Is there an inventory data or operational inconsistency that requires attention?"**

It detects inventory exceptions and inconsistencies across the product catalogue and flags them for human review.  The output is used by store managers and by future orchestration layers to trigger corrective workflows.

I5 does NOT:
- calculate reorder points or quantities (I2)
- calculate safety stock (I3)
- classify expiry or slow-stock risk (I4)
- make purchasing decisions
- execute purchases
- modify inventory
- implement Procurement / R5

### Inputs

| Input | Source | Fields used |
|-------|--------|-------------|
| **Products** | `data/products.csv` | `product_id` |
| **Inventory snapshots** | `data/inventory_snapshots.csv` | `stock_on_hand`, `reserved`, `damaged` (all snapshots, chronological) |
| **Inventory movements** | `data/inventory_movements.csv` | `movement_id`, `type`, `qty`, `timestamp` |

### Exception categories (I5-v1)

| Exception type | What it means | Severity |
|----------------|---------------|---------|
| `NEGATIVE_STOCK` | `available_stock < 0` — impossible inventory state | Always **HIGH** |
| `LARGE_STOCK_ADJUSTMENT` | Adjustment or damage movement with |qty| ≥ 10 units | MEDIUM (≥10), HIGH (≥20) |
| `MOVEMENT_SNAPSHOT_MISMATCH` | Net movements between consecutive snapshots don't reconcile with stock_on_hand change | MEDIUM (>5 units gap), HIGH (>20 units gap) |
| `RECEIPT_STOCK_MISMATCH` | RECEIPT movement not followed by expected stock increase; full check requires R5 data (see MVP limitations) | MEDIUM/HIGH |
| `DUPLICATE_SUSPICIOUS_MOVEMENT` | Duplicate movement_id, identical duplicate records, or impossible values (RECEIPT ≤ 0, SALE ≤ 0) | HIGH (impossible RECEIPT), MEDIUM (others) |

### Detection rules

**NEGATIVE_STOCK:**
```
available_stock = stock_on_hand − reserved − damaged
if available_stock < 0 → NEGATIVE_STOCK HIGH
```

**LARGE_STOCK_ADJUSTMENT:**
```
if movement.type in (ADJUSTMENT, DAMAGE) and |qty| >= 20 → HIGH
if movement.type in (ADJUSTMENT, DAMAGE) and |qty| >= 10 → MEDIUM
```

**MOVEMENT_SNAPSHOT_MISMATCH:**
```
expected_closing = opening_stock_on_hand + Σ(receipts) − Σ(sales) + Σ(adjustments+damage)
discrepancy = |expected_closing − actual_closing_stock_on_hand|
if discrepancy > 20 → HIGH
if discrepancy > 5  → MEDIUM
if discrepancy <= 2 → no exception (tolerance)
```

**DUPLICATE_SUSPICIOUS_MOVEMENT:**
- Duplicate movement_id (same ID > 1 time) → MEDIUM
- Identical record (same product/type/qty/timestamp) → MEDIUM
- RECEIPT with qty ≤ 0 → HIGH
- SALE with qty ≤ 0 → MEDIUM

### Output contract — `InventoryException`

```python
InventoryException(
    exception_id      = "I5-A3F1B2C4D5E6",
    product_id        = "P001",
    exception_type    = "NEGATIVE_STOCK",
    severity          = "HIGH",
    status            = "OPEN",
    message           = "Available stock is -1.0 units — negative inventory is impossible.",
    reason            = "Product P001 has stock_on_hand=0, reserved=0, damaged=1. ...",
    evidence_refs     = ["inventory_snapshots.csv:P001:2026-09-09T17:00:00"],
    affected_quantity = -1.0,
    expected_value    = 0.0,
    actual_value      = -1.0,
    generated_at      = "2026-09-21T...",
    formula_version   = "I5-v1",
    confidence        = 1.0,
)
```

Each `InventoryException` is also wrapped in an `AgentResult` with:
- `agent_id = "I5"`
- `action_type = "FLAG_INVENTORY_EXCEPTION"`
- `entity_type = "PRODUCT"`
- `requires_approval = False`

### Relationship to I1 / I2 / I3 / I4

```
I1 (stock levels + alerts)
        ↓
   InventoryPosition ─────────────────┐
        ↓                             │
       I2 (reorder decision)         I5 (exception detection)
        ↓                             │
   ReorderNeed                   InventoryException
        ↓                             ↓
       I3/I4                    Future: I6 / orchestration layer
```

I5 reads the same raw CSV files as I1; it does NOT call I1 via HTTP or import I1's service class. The `available_stock` formula (`stock_on_hand − reserved − damaged`) is computed independently within the I5 boundary.

### Future R5 Procurement integration

The final architecture allows I5 to consume Procurement delivery facts from R5 to perform full RECEIPT_STOCK_MISMATCH checks:

```python
# When R5 Procurement agent is available:
r5_deliveries = r5_agent.get_deliveries(product_id)
exceptions = i5_agent.evaluate_product(
    product_id,
    procurement_deliveries=[
        {"product_id": d.product_id, "delivered_qty": d.qty, "delivered_at": d.ts}
        for d in r5_deliveries
    ],
)
```

**No code rewrite is needed.** The `procurement_deliveries` parameter already exists in `evaluate_product()` and `get_all_exceptions()`. Currently it defaults to `None` (MVP partial check).

### Current local-MVP limitations

1. **RECEIPT_STOCK_MISMATCH** — Full reconciliation against Procurement delivery documents requires R5 data, which is not yet available. I5 performs a partial check (receipt qty vs. subsequent snapshot increase) with `confidence=0.75`.
2. **Single snapshot per product** — The mismatch check uses consecutive snapshots from `inventory_snapshots.csv`. If snapshots are sparse, some movement windows may not be covered.
3. **Inventory age not tracked** — I5 does not assess expiry (that is I4's responsibility).
4. **No resolution workflow** — All exceptions are created with `status=OPEN`. Acknowledgement and resolution are future scope (I5 v2).

I5 **detects** exceptions. It does **not** fix inventory, place orders, or make purchasing decisions.

