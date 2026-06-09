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
MODERATION_AUTO_REMOVE_THRESHOLD = 1 # score >= this → REMOVED, no review needed

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")