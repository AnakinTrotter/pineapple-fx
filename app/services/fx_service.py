"""
FX Rate Service.

Provides EUR to USD exchange rate data from the Frankfurter API with:
- Automatic retry on failure (up to 3 attempts with exponential backoff)
- In-memory caching (configurable TTL)
- Fallback to local JSON file when API is unavailable
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import httpx
from cachetools import TTLCache
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.models import (
    BreakdownType,
    DailyRate,
    SummaryResponse,
    TotalsSummary,
)
from app.settings import (
    FRANKFURTER_BASE_URL,
    FRANKFURTER_TIMEOUT,
    CACHE_MAX_SIZE,
    CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

# Cache with configurable size and TTL
_cache: TTLCache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)

# Local fallback data file
FALLBACK_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "sample_fx.json"


class FXServiceError(Exception):
    """Raised when FX rate data cannot be retrieved."""
    pass


def _safe_pct_change(current: float, previous: float) -> float:
    """
    Calculate percentage change between two values.
    
    Guards against division by zero - returns 0.0 if previous is zero.
    """
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 4)


def _get_cache_key(start_date: date, end_date: date) -> str:
    """Generate a cache key for the given date range."""
    return f"fx_{start_date.isoformat()}_{end_date.isoformat()}"


@retry(
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _fetch_from_api(start_date: date, end_date: date) -> dict[str, float]:
    """
    Fetch FX rates from the Frankfurter API.
    
    Retries up to 3 times with exponential backoff on network errors.
    Returns a dict mapping ISO date strings to USD rates.
    """
    # Single day vs date range use different URL formats
    if start_date == end_date:
        url = f"{FRANKFURTER_BASE_URL}/{start_date.isoformat()}"
    else:
        url = f"{FRANKFURTER_BASE_URL}/{start_date.isoformat()}..{end_date.isoformat()}"
    
    params = {"from": "EUR", "to": "USD"}
    
    logger.info(f"Fetching FX rates from API: {url}")
    
    async with httpx.AsyncClient(timeout=float(FRANKFURTER_TIMEOUT)) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    
    # Parse response - format differs for single day vs range
    if "rates" in data and isinstance(data["rates"], dict):
        first_value = next(iter(data["rates"].values()), None)
        if isinstance(first_value, dict):
            # Multi-day: {"rates": {"2025-01-20": {"USD": 1.04}, ...}}
            return {
                date_str: rates.get("USD", 0.0)
                for date_str, rates in data["rates"].items()
            }
        else:
            # Single-day: {"rates": {"USD": 1.04}}
            return {start_date.isoformat(): data["rates"].get("USD", 0.0)}
    
    raise FXServiceError("Unexpected API response format")


def _load_fallback_data(start_date: date, end_date: date) -> dict[str, float]:
    """
    Load FX rates from local fallback file.
    
    Filters to only include dates within the requested range.
    """
    if not FALLBACK_DATA_PATH.exists():
        raise FXServiceError(f"Fallback data file not found: {FALLBACK_DATA_PATH}")
    
    logger.warning(f"Using fallback data from {FALLBACK_DATA_PATH}")
    
    with open(FALLBACK_DATA_PATH, "r") as f:
        all_data = json.load(f)
    
    # Filter to requested date range
    filtered = {}
    for date_str, rate in all_data.get("rates", {}).items():
        try:
            d = date.fromisoformat(date_str)
            if start_date <= d <= end_date:
                # Handle both {"USD": 1.04} and raw float formats
                if isinstance(rate, dict):
                    filtered[date_str] = rate.get("USD", 0.0)
                else:
                    filtered[date_str] = rate
        except ValueError:
            continue
    
    if not filtered:
        raise FXServiceError(
            f"No data available in fallback for range {start_date} to {end_date}"
        )
    
    return filtered


async def get_fx_summary(
    start_date: date,
    end_date: date,
    breakdown: BreakdownType = BreakdownType.DAY,
) -> SummaryResponse:
    """
    Get FX rate summary for a date range.
    
    Checks cache first, then tries API, falls back to local file on failure.
    Returns daily rates (if breakdown='day') and aggregate totals.
    """
    cache_key = _get_cache_key(start_date, end_date)
    data_source = "api"
    
    # Check cache first
    if cache_key in _cache:
        logger.info(f"Cache hit for {cache_key}")
        rates_data = _cache[cache_key]
        data_source = "cache"
    else:
        # Try API, fall back to local file on any error
        try:
            rates_data = await _fetch_from_api(start_date, end_date)
            _cache[cache_key] = rates_data
            logger.info(f"Cached {len(rates_data)} rates for {cache_key}")
        except Exception as e:
            logger.error(f"API fetch failed: {e}. Using fallback data.")
            rates_data = _load_fallback_data(start_date, end_date)
            data_source = "fallback"
    
    # Sort by date
    sorted_dates = sorted(rates_data.keys())
    rates_list = [(d, rates_data[d]) for d in sorted_dates]
    
    if not rates_list:
        raise FXServiceError("No rate data available for the specified range")
    
    # Build daily rates with percentage changes
    daily_rates: list[DailyRate] = []
    for i, (date_str, rate) in enumerate(rates_list):
        pct_change: Optional[float] = None
        if i > 0:
            prev_rate = rates_list[i - 1][1]
            pct_change = _safe_pct_change(rate, prev_rate)
        
        daily_rates.append(DailyRate(
            date=date.fromisoformat(date_str),
            rate=round(rate, 6),
            pct_change=pct_change,
        ))
    
    # Calculate totals
    all_rates = [r for _, r in rates_list]
    start_rate = all_rates[0]
    end_rate = all_rates[-1]
    mean_rate = sum(all_rates) / len(all_rates) if all_rates else 0.0
    
    totals = TotalsSummary(
        start_rate=round(start_rate, 6),
        end_rate=round(end_rate, 6),
        total_pct_change=_safe_pct_change(end_rate, start_rate),
        mean_rate=round(mean_rate, 6),
    )
    
    return SummaryResponse(
        start_date=start_date,
        end_date=end_date,
        base_currency="EUR",
        target_currency="USD",
        breakdown=breakdown,
        daily_rates=daily_rates if breakdown == BreakdownType.DAY else None,
        totals=totals,
        data_source=data_source,
    )


def clear_cache() -> int:
    """Clear the FX rate cache. Returns number of entries cleared."""
    count = len(_cache)
    _cache.clear()
    return count
