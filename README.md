# Pineapple FX

> *Coins alone do not tell the story; see the pattern and the change.*

A FastAPI service providing EUR to USD exchange rate summaries with day-by-day breakdowns, trend visualizations, and aggregate statistics.

andiron-cursor :white_check_mark:

## Live Demo

- **Web UI**: http://v4kggccswckssg4gkosogoo8.217.160.150.10.sslip.io/
- **Direct IP**: http://217.160.150.10:8000/
- **API Docs**: http://v4kggccswckssg4gkosogoo8.217.160.150.10.sslip.io/docs

---

## Features

- **Day-by-day rate breakdown** with percentage changes
- **Aggregate statistics**: start/end rates, total change, mean rate
- **Automatic retry** with exponential backoff (up to 3 attempts)
- **In-memory caching** (configurable TTL)
- **Fallback to local data** when API is unavailable
- **Rate limiting** (configurable per endpoint)
- **Admin authentication** for protected endpoints
- **Interactive chart visualization** in the web UI
- **Live request preview** showing the API call as you configure it
- **Docker support** for easy deployment

## Quick Start

### Option 1: Run with Python

```bash
cd pineapple-fx

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python run.py
```

### Option 2: Run with Docker

```bash
# Build the image
docker build -t pineapple-fx .

# Run the container
docker run -p 8000:8000 pineapple-fx

# Run with custom configuration
docker run -p 8000:8000 \
  -e PINEAPPLE_ADMIN_KEY=your-secret-key \
  -e CACHE_TTL_SECONDS=600 \
  pineapple-fx
```

The server will start at `http://localhost:8000`

- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Configuration

All settings are configured via environment variables in `app/settings.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PINEAPPLE_HOST` | `0.0.0.0` | Server bind host |
| `PINEAPPLE_PORT` | `8000` | Server bind port |
| `PINEAPPLE_DEBUG` | `false` | Enable debug mode and auto-reload |
| `PINEAPPLE_ADMIN_KEY` | (generated) | API key for admin endpoints |
| `FRANKFURTER_BASE_URL` | `https://api.frankfurter.dev/v1` | FX rate API URL |
| `FRANKFURTER_TIMEOUT` | `30` | API request timeout (seconds) |
| `CACHE_MAX_SIZE` | `100` | Maximum cache entries |
| `CACHE_TTL_SECONDS` | `300` | Cache time-to-live (seconds) |
| `RATE_LIMIT_HEALTH` | `60/minute` | Rate limit for /health |
| `RATE_LIMIT_SUMMARY` | `30/minute` | Rate limit for /summary |
| `RATE_LIMIT_ADMIN` | `10/minute` | Rate limit for admin endpoints |

---

## API Endpoints

### Health Check

```http
GET /health
```

Returns service health status. Rate limited to 60 requests per minute.

**Response:**

```json
{
  "status": "healthy",
  "service": "Pineapple FX",
  "version": "1.0.0"
}
```

### FX Rate Summary

```http
GET /summary?start_date={date}&end_date={date}&breakdown={day|none}
```

Get EUR to USD exchange rate summary for a date range. Rate limited to 30 requests per minute.

**Parameters:**

| Parameter    | Type   | Required | Description                                      |
|--------------|--------|----------|--------------------------------------------------|
| `start_date` | date   | Yes      | Start date (inclusive) in `YYYY-MM-DD` format    |
| `end_date`   | date   | Yes      | End date (inclusive) in `YYYY-MM-DD` format      |
| `breakdown`  | string | No       | `day` (default) for daily rates, `none` for totals only |

---

## Examples

### Example 1: Get daily breakdown for a week

```bash
curl "http://localhost:8000/summary?start_date=2025-01-20&end_date=2025-01-24&breakdown=day"
```

**Response:**

```json
{
  "start_date": "2025-01-20",
  "end_date": "2025-01-24",
  "base_currency": "EUR",
  "target_currency": "USD",
  "breakdown": "day",
  "daily_rates": [
    {
      "date": "2025-01-20",
      "rate": 1.0421,
      "pct_change": null
    },
    {
      "date": "2025-01-21",
      "rate": 1.0435,
      "pct_change": 0.1344
    },
    {
      "date": "2025-01-22",
      "rate": 1.0412,
      "pct_change": -0.2204
    },
    {
      "date": "2025-01-23",
      "rate": 1.0398,
      "pct_change": -0.1345
    },
    {
      "date": "2025-01-24",
      "rate": 1.0487,
      "pct_change": 0.8559
    }
  ],
  "totals": {
    "start_rate": 1.0421,
    "end_rate": 1.0487,
    "total_pct_change": 0.6334,
    "mean_rate": 1.0431
  },
  "data_source": "api"
}
```

### Example 2: Get totals only (no daily breakdown)

```bash
curl "http://localhost:8000/summary?start_date=2025-01-01&end_date=2025-01-31&breakdown=none"
```

**Response:**

```json
{
  "start_date": "2025-01-01",
  "end_date": "2025-01-31",
  "base_currency": "EUR",
  "target_currency": "USD",
  "breakdown": "none",
  "daily_rates": null,
  "totals": {
    "start_rate": 1.0352,
    "end_rate": 1.0368,
    "total_pct_change": 0.1546,
    "mean_rate": 1.0389
  },
  "data_source": "api"
}
```

### Example 3: Using Python requests

```python
import requests

response = requests.get(
    "http://localhost:8000/summary",
    params={
        "start_date": "2025-01-20",
        "end_date": "2025-01-24",
        "breakdown": "day"
    }
)

data = response.json()
print(f"Total change: {data['totals']['total_pct_change']:.4f}%")
print(f"Mean rate: {data['totals']['mean_rate']:.6f}")

for day in data['daily_rates']:
    change = f"{day['pct_change']:+.4f}%" if day['pct_change'] else "-"
    print(f"  {day['date']}: {day['rate']:.6f} ({change})")
```

### Example 4: Health check

```bash
curl http://localhost:8000/health
```

### Example 5: Rate limit exceeded response

When you exceed the rate limit, you'll receive HTTP 429:

```json
{
  "detail": "Rate limit exceeded. Please slow down.",
  "error_code": "RATE_LIMIT_EXCEEDED"
}
```

---

## Data Source

This service uses the [Frankfurter API](https://frankfurter.dev/) for exchange rate data:

- **Primary**: Live API calls to `api.frankfurter.dev/v1`
- **Fallback**: Local file `data/sample_fx.json` when API is unavailable

The response includes a `data_source` field indicating where the data came from:
- `"api"` - Fresh data from Frankfurter API
- `"cache"` - Cached data from a previous API call
- `"fallback"` - Local fallback file data

---

## Extra Credit Features

### Retry Logic
Failed API requests are automatically retried up to 3 times with exponential backoff (1s, 2s, 4s delays).

### In-Memory Cache
Results are cached for 5 minutes (configurable via `CACHE_TTL_SECONDS`). Cache key is based on the date range.

### Rate Limiting
API endpoints are protected with rate limits using slowapi:
- `/health` - 60 requests per minute
- `/summary` - 30 requests per minute
- `/cache/clear` - 10 requests per minute

All limits are configurable via environment variables.

### Admin Authentication
The `/cache/clear` endpoint requires an API key in the `X-Admin-Key` header.

Set the key via environment variable:
```bash
export PINEAPPLE_ADMIN_KEY="your-secret-key"
```

If not set, a temporary key is generated and logged at startup.

Example usage:
```bash
curl -X POST http://localhost:8000/cache/clear -H "X-Admin-Key: your-secret-key"
```

### Division by Zero Guard
When calculating percentage changes, if the denominator is zero, the service returns `0.0` instead of crashing.

---

## Project Structure

```
pineapple-fx/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   ├── settings.py          # Configuration from environment
│   └── services/
│       ├── __init__.py
│       └── fx_service.py    # FX rate service with caching and retry
├── data/
│   └── sample_fx.json       # Fallback data (3 years of historical rates)
├── static/
│   └── index.html           # Web UI with chart and request preview
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── run.py
└── README.md
```

---

## Pydantic Models

### Response Models

- `SummaryResponse` - Complete summary response with daily rates and totals
- `DailyRate` - Single day rate with date, rate, and pct_change
- `TotalsSummary` - Aggregate statistics (start_rate, end_rate, total_pct_change, mean_rate)
- `HealthResponse` - Health check response
- `ErrorResponse` - Error response format
- `BreakdownType` - Enum for breakdown granularity (`day`, `none`)

---

## License

MIT

---

🍍
