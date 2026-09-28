from __future__ import annotations

from datetime import date, datetime, timezone
from math import sqrt
from statistics import median
from typing import Iterable

import numpy as np


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    else:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def percentile(values: Iterable[float], q: float) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return float(np.percentile(vals, q * 100))


def robust_std(values: Iterable[float]) -> float:
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    med = median(vals)
    mad = median(abs(v - med) for v in vals)
    return float(1.4826 * mad)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(max(float(value), low), high)


def recency_weight(age_days: int, half_life_days: int = 90) -> float:
    return 0.5 ** (max(age_days, 0) / max(half_life_days, 1))


def weighted_mean(pairs: Iterable[tuple[float, float]], default: float = 0.0) -> float:
    pairs = [(float(v), max(float(w), 0.0)) for v, w in pairs]
    total = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total if total else default


def normalized_low_is_good(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 1.0
    return clamp(1 - (value - min_value) / (max_value - min_value))


def normalized_high_is_good(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 1.0
    return clamp((value - min_value) / (max_value - min_value))
