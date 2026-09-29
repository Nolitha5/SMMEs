from __future__ import annotations
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve()
FOUNDATION = HERE.parents[4]
VENDORED = FOUNDATION / "vendor" / "florah-demand" / "backend"
if not VENDORED.exists():
    raise RuntimeError(f"Florah Demand source is missing at {VENDORED}")
if str(VENDORED) not in sys.path:
    sys.path.insert(0, str(VENDORED))

import pandas as pd  # type: ignore
from app.agents.demand.d1_sales_history.agent import SalesHistoryAnalyzer  # type: ignore
from app.agents.demand.d2_seasonality.agent import SeasonalityDetector  # type: ignore
from app.agents.demand.d3_event_promotion.agent import EventPromotionSignalAgent  # type: ignore
from app.agents.demand.d4_forecast.agent import ForecastGenerator  # type: ignore
from app.agents.demand.d5_quality.agent import ForecastQualityMonitor  # type: ignore
from app.contracts.demand import DemandForecast  # type: ignore

SOURCE = "florah-demand"


def _frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)


def _calendar(start: date, end: date) -> pd.DataFrame:
    rows = []
    cur = start
    while cur <= end:
        dom = cur.day
        rows.append({
            "date": cur.isoformat(),
            "day_of_week": cur.weekday(),
            "day_name": cur.strftime("%A"),
            "day_of_month": dom,
            "month": cur.month,
            "month_name": cur.strftime("%B"),
            "is_weekend": cur.weekday() >= 5,
            "is_payday_window": (13 <= dom <= 16) or (27 <= dom <= 31),
        })
        cur += timedelta(days=1)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model


def bounded_d1(series):
    raw = dump(series)
    points = list(raw.get("series") or [])
    raw["series"] = points[-120:]
    raw["series_truncated"] = len(points) > 120
    return raw


def canonical_d4(forecast):
    raw = dump(forecast)
    return {
        "product_id": raw["product_id"],
        "horizon_days": int(raw.get("horizon_days", raw.get("horizon", 7))),
        "expected_qty": float(raw["expected_qty"]),
        "lower_bound": float(raw["lower_bound"]),
        "upper_bound": float(raw["upper_bound"]),
        "confidence": float(raw["confidence"]),
        "drivers": list(raw.get("drivers") or []),
        "model": raw.get("model"),
        "status": raw.get("status"),
        "insufficient_evidence": bool(raw.get("insufficient_evidence", False)),
        "evidence_notes": raw.get("evidence_notes", ""),
        "forecast_days": list(raw.get("forecast_days") or []),
        "generated_at": str(raw.get("generated_at")),
        "data_freshness_days": raw.get("data_freshness_days"),
        "source": SOURCE,
        "source_version": SOURCE,
    }




def native_forecast(raw: dict):
    if not raw:
        return None
    try:
        return DemandForecast(
            product_id=str(raw.get("product_id") or ""),
            horizon=int(raw.get("horizon_days", raw.get("horizon", 7))),
            expected_qty=float(raw.get("expected_qty", 0)),
            lower_bound=float(raw.get("lower_bound", 0)),
            upper_bound=float(raw.get("upper_bound", 0)),
            confidence=float(raw.get("confidence", 0)),
            drivers=list(raw.get("drivers") or []),
            model=raw.get("model") or "naive",
            forecast_days=list(raw.get("forecast_days") or []),
            status=raw.get("status") or "HEALTHY",
            insufficient_evidence=bool(raw.get("insufficient_evidence", False)),
            evidence_notes=str(raw.get("evidence_notes") or ""),
            generated_at=raw.get("generated_at") or datetime.utcnow().isoformat(),
            data_freshness_days=raw.get("data_freshness_days"),
        )
    except Exception:
        return None

def run(payload: dict) -> dict:
    products = payload.get("products") or []
    tx_rows = payload.get("transactions") or []
    promos = payload.get("promotions") or []
    events = payload.get("localEvents") or []
    prior_forecasts = {
        str(item.get("product_id")): native_forecast(item)
        for item in (payload.get("priorForecasts") or [])
        if item.get("product_id")
    }

    tx = _frame(tx_rows, ["transaction_id", "timestamp", "store_id", "product_id", "qty", "unit_price", "discount", "channel"])
    if not tx.empty:
        tx["timestamp"] = pd.to_datetime(tx["timestamp"], errors="coerce")
    product_df = _frame(products, ["product_id", "name", "category", "unit_cost", "sell_price", "shelf_life_days", "active"])
    promo_df = _frame(promos, ["promo_id", "product_id", "start", "end", "discount_type", "value", "channel"])
    if not promo_df.empty:
        promo_df["start"] = pd.to_datetime(promo_df["start"], errors="coerce")
        promo_df["end"] = pd.to_datetime(promo_df["end"], errors="coerce")
    event_df = _frame(events, ["event_id", "date", "event_name", "location", "event_type", "expected_impact"])
    if not event_df.empty:
        event_df["date"] = pd.to_datetime(event_df["date"], errors="coerce")

    valid_ts = tx["timestamp"].dropna() if not tx.empty else pd.Series(dtype="datetime64[ns]")
    reference = valid_ts.max().date() if not valid_ts.empty else date.today()
    min_date = valid_ts.min().date() if not valid_ts.empty else reference - timedelta(days=60)
    calendar = _calendar(min_date, reference + timedelta(days=30))

    d1 = SalesHistoryAnalyzer()
    d2 = SeasonalityDetector(calendar=calendar)
    d3 = EventPromotionSignalAgent()
    d4 = ForecastGenerator()
    d5 = ForecastQualityMonitor()

    output = {"reference_date": reference.isoformat(), "products": {}, "warnings": []}
    for product in products:
        if product.get("active") is False:
            continue
        pid = str(product.get("product_id") or "").strip()
        if not pid:
            continue
        row = {"product_id": pid}
        try:
            series = d1.run(tx, pid, reference)
            row["D1"] = bounded_d1(series)
        except Exception as exc:
            row["D1"] = {"status": "INSUFFICIENT_EVIDENCE", "reason": str(exc)}
            row["D2"] = {"status": "SKIPPED", "reason": "D1 did not produce a usable demand series."}
            row["D3"] = {"status": "SKIPPED", "reason": "D1 did not produce a usable demand series."}
            row["D4"] = None
            row["D5"] = {"status": "SKIPPED", "reason": "No forecast was produced."}
            output["products"][pid] = row
            continue

        try:
            seasonality = d2.run(series)
            row["D2"] = dump(seasonality)
        except Exception as exc:
            seasonality = None
            row["D2"] = {"status": "INSUFFICIENT_EVIDENCE", "reason": str(exc)}

        try:
            signals = d3.run(promo_df, event_df, series, product_df, reference)
            row["D3"] = {"product_id": pid, "signals": [dump(x) for x in signals], "signal_count": len(signals)}
        except Exception as exc:
            signals = []
            row["D3"] = {"status": "INSUFFICIENT_EVIDENCE", "reason": str(exc), "signals": [], "signal_count": 0}

        try:
            forecast = d4.run(series, seasonality, signals, horizon=7, reference_date=reference)
            row["D4"] = canonical_d4(forecast)
        except Exception as exc:
            forecast = None
            row["D4"] = None
            row["D4_error"] = str(exc)

        prior_forecast = prior_forecasts.get(pid)
        if prior_forecast is not None:
            try:
                report, alerts = d5.evaluate(prior_forecast, tx)
                row["D5"] = {
                    "report": dump(report),
                    "alerts": [dump(x) for x in alerts],
                    "evaluated_prior_forecast": True,
                }
            except Exception as exc:
                row["D5"] = {"status": "INSUFFICIENT_EVIDENCE", "reason": str(exc)}
        else:
            row["D5"] = {
                "status": "INSUFFICIENT_EVIDENCE",
                "reason": "Forecast quality becomes available after later sales actuals can be compared with a previous forecast.",
                "evaluated_prior_forecast": False,
            }
        output["products"][pid] = row
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(json.dumps(run(payload), default=str, separators=(",", ":")))


if __name__ == "__main__":
    main()
