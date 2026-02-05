"""
Pydantic models for the FX rate API.

Defines request validation and response schemas for all endpoints.
"""

from datetime import date as date_type
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BreakdownType(str, Enum):
    """Breakdown granularity for FX rate summary."""
    DAY = "day"
    NONE = "none"


class DailyRate(BaseModel):
    """Single day FX rate with percentage change from prior day."""
    date: date_type = Field(..., description="Date of the rate")
    rate: float = Field(..., description="EUR to USD exchange rate")
    pct_change: Optional[float] = Field(
        None,
        description="Percentage change from prior day (null for first day)"
    )


class TotalsSummary(BaseModel):
    """Aggregate statistics for the FX rate period."""
    start_rate: float = Field(..., description="Exchange rate on the start date")
    end_rate: float = Field(..., description="Exchange rate on the end date")
    total_pct_change: float = Field(
        ...,
        description="Total percentage change from start to end"
    )
    mean_rate: float = Field(..., description="Mean exchange rate over the period")


class SummaryResponse(BaseModel):
    """
    Response model for the /summary endpoint.
    
    Contains the requested date range, optional daily breakdown,
    and aggregate totals with statistics.
    """
    start_date: date_type = Field(..., description="Requested start date")
    end_date: date_type = Field(..., description="Requested end date")
    base_currency: str = Field(default="EUR", description="Base currency")
    target_currency: str = Field(default="USD", description="Target currency")
    breakdown: BreakdownType = Field(..., description="Breakdown granularity used")
    daily_rates: Optional[list[DailyRate]] = Field(
        None,
        description="Daily rate breakdown (only present when breakdown='day')"
    )
    totals: TotalsSummary = Field(..., description="Aggregate statistics")
    data_source: str = Field(
        ...,
        description="Source of the data: 'api', 'cache', or 'fallback'"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "start_date": "2025-01-20",
                "end_date": "2025-01-24",
                "base_currency": "EUR",
                "target_currency": "USD",
                "breakdown": "day",
                "daily_rates": [
                    {"date": "2025-01-20", "rate": 1.0421, "pct_change": None},
                    {"date": "2025-01-21", "rate": 1.0435, "pct_change": 0.1344},
                    {"date": "2025-01-22", "rate": 1.0412, "pct_change": -0.2204}
                ],
                "totals": {
                    "start_rate": 1.0421,
                    "end_rate": 1.0412,
                    "total_pct_change": -0.0864,
                    "mean_rate": 1.0423
                },
                "data_source": "api"
            }
        }
    }


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")


class ErrorResponse(BaseModel):
    """Standard error response format."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")
