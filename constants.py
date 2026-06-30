# constants.py
import os
# App info
APP_NAME = "CopodsConnect"
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# JWT
JWT_ALGORITHM = "HS256"

# Pagination
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

ALLOWED_EMAIL_DOMAIN = "copods.co"
# Moderation thresholds
MODERATION_REVIEW_THRESHOLD = 0.5      # score >= this → FLAGGED, admin reviews

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# Poll constraints
POLL_MIN_OPTIONS = 2
POLL_MAX_OPTIONS = 5