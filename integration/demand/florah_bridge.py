"""Execution bridge from vendored Florah DemandService to the canonical platform.

This bridge is intentionally transport-neutral. It does not write Firebase.
Testing/deployment code can call it and then publish the returned canonical
output through the shared Firestore exchange runtime.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
VENDORED_BACKEND = ROOT / "vendor" / "florah-demand" / "backend"
if str(VENDORED_BACKEND) not in sys.path:
    sys.path.insert(0, str(VENDORED_BACKEND))

from app.services.demand_service import DemandService  # type: ignore  # noqa: E402
from integration.demand.florah_adapter import shared_output_from_d4  # noqa: E402


def run_d4(product_id: str, business_id: str, horizon: int = 7, run_id: str = "demand-live") -> dict:
    service = DemandService()
    native = service.run_d4(product_id, horizon=horizon)
    return shared_output_from_d4(native, business_id=business_id, run_id=run_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True)
    parser.add_argument("--business", required=True)
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--run-id", default="demand-live")
    args = parser.parse_args()
    print(json.dumps(run_d4(args.product, args.business, args.horizon, args.run_id), indent=2, default=str))


if __name__ == "__main__":
    main()
