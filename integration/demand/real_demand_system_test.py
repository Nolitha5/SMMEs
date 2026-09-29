from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
VENDORED_BACKEND = ROOT / "vendor" / "florah-demand" / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(VENDORED_BACKEND) not in sys.path:
    sys.path.insert(0, str(VENDORED_BACKEND))

from app.services.demand_service import DemandService  # type: ignore  # noqa: E402
from integration.demand.florah_adapter import canonicalize_d4, shared_output_from_d4  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    service = DemandService()
    product_id = "P001"
    business_id = "dev-business"

    data = service._load_all()
    tx = data["transactions"]
    product_tx = tx[tx["product_id"] == product_id]
    check(not product_tx.empty, "P001 test transactions are missing")
    reference_date = product_tx["timestamp"].max().date()

    d1_map = service.run_d1(product_id=product_id, reference_date=reference_date)
    check(product_id in d1_map, "D1 did not return P001")
    d1 = d1_map[product_id]
    check(d1.clean_observations >= 7, "D1 clean observation minimum failed")

    d2 = service.run_d2(d1)
    check(d2.product_id == product_id, "D2 product identity mismatch")

    d3 = service.run_d3(d1, reference_date=reference_date)
    check(isinstance(d3, list), "D3 must return a list")

    native_d4 = service.run_d4(product_id, horizon=7, reference_date=reference_date)
    canonical_d4 = canonicalize_d4(native_d4)
    check(canonical_d4["product_id"] == product_id, "D4 product identity mismatch")
    check(canonical_d4["horizon_days"] == 7, "D4 horizon adapter failed")
    check(canonical_d4["lower_bound"] <= canonical_d4["expected_qty"] <= canonical_d4["upper_bound"], "D4 bounds invalid")
    check(0 <= canonical_d4["confidence"] <= 1, "D4 confidence invalid")
    check(canonical_d4["source_version"] == "florah-demand-e3534ef", "D4 source version is not pinned")

    d5_report, d5_alerts = service.run_d5(native_d4)
    check(d5_report.product_id == product_id, "D5 product identity mismatch")
    check(isinstance(d5_alerts, list), "D5 alerts must be a list")

    shared = shared_output_from_d4(native_d4, business_id=business_id, run_id="real-demand-test")
    check(shared["capabilityId"] == "D4", "shared D4 capabilityId invalid")
    check(shared["outputType"] == "DemandForecast", "shared D4 outputType invalid")
    check(shared["payload"] == canonical_d4, "shared D4 payload differs from canonical adapter")

    report = {
        "passed": True,
        "product_id": product_id,
        "reference_date": reference_date.isoformat(),
        "d1": {
            "observations": d1.observations,
            "clean_observations": d1.clean_observations,
            "outliers_detected": d1.outliers_detected,
            "missing_dates": d1.missing_dates,
        },
        "d2": {
            "seasonality_strength": d2.seasonality_strength,
            "confidence": d2.confidence,
            "data_sufficient": d2.data_sufficient,
        },
        "d3": {"signal_count": len(d3)},
        "d4": canonical_d4,
        "d5": {
            "status": str(d5_report.status),
            "actuals_count": d5_report.actuals_count,
            "alert_count": len(d5_alerts),
        },
        "shared_output": shared,
    }

    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "real-demand-source-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("Florah real D1: PASS")
    print("Florah real D2: PASS")
    print("Florah real D3: PASS")
    print(f"Florah real D4: PASS ({canonical_d4['expected_qty']:.2f} units / 7 days)")
    print(f"Florah real D5: PASS ({d5_report.status})")
    print("Florah D4 canonical adapter: PASS")
    print("REAL_DEMAND_SOURCE_TEST_OK")


if __name__ == "__main__":
    main()
