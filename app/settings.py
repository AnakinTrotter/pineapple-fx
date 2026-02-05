"""
Application settings loaded from environment variables.

All configuration is centralized here for easy management.
"""

import os
import secrets


# Server settings
HOST = os.getenv("PINEAPPLE_HOST", "0.0.0.0")
PORT = int(os.getenv("PINEAPPLE_PORT", "8000"))
DEBUG = os.getenv("PINEAPPLE_DEBUG", "false").lower() == "true"

# Admin API key for protected endpoints
# If not set, generates a random key (logged at startup)
ADMIN_API_KEY = os.getenv("PINEAPPLE_ADMIN_KEY", "")

# Frankfurter API settings (.dev requires /v1 prefix)
FRANKFURTER_BASE_URL = os.getenv("FRANKFURTER_BASE_URL", "https://api.frankfurter.dev/v1")
FRANKFURTER_TIMEOUT = int(os.getenv("FRANKFURTER_TIMEOUT", "30"))

# Cache settings
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "100"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

# Rate limiting (requests per minute)
RATE_LIMIT_HEALTH = os.getenv("RATE_LIMIT_HEALTH", "60/minute")
RATE_LIMIT_SUMMARY = os.getenv("RATE_LIMIT_SUMMARY", "30/minute")
RATE_LIMIT_ADMIN = os.getenv("RATE_LIMIT_ADMIN", "10/minute")


def get_admin_key() -> str:
    """
    Get the admin API key.
    
    If PINEAPPLE_ADMIN_KEY is not set, generates a secure random key.
    """
    if ADMIN_API_KEY:
        return ADMIN_API_KEY
    return secrets.token_urlsafe(32)
